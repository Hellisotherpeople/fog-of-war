/**
 * Runtime glue for sampler telemetry.
 *
 * Owns the three data sources the extension can actually reach:
 *
 * 1. the outgoing request body (`before_provider_request`), which is where
 *    `n_probs` / `post_sampling_probs` get injected;
 * 2. the recording proxy, which is the only way to see per-token
 *    probabilities — omp's provider parser drops `logprobs`;
 * 3. `/slots`, which reports live decode counters and slot configurations at
 *    no generation cost. These may belong to previous or unrelated requests.
 *
 * Nothing here throws into the agent's path: every callback is defensive, and
 * the proxy is off unless the user turns it on.
 */

import fs from "node:fs";
import path from "node:path";
import { vllmSamplerChain, vllmSamplerConfig } from "../vllm";
import {
	GenerationBuilder,
	type GenerationRecord,
	GenerationStore,
	parseChunk,
} from "./capture";
import {
	diffSamplerChain,
	inferSamplerSupport,
	LlamaClient,
	type LlamaProps,
	type SamplerSupportEntry,
	slotSamplers,
} from "./llama";
import { type RecordingProxy, startRecordingProxy } from "./proxy";
import { summarizeGeneration, tokenChosenRank, tokenEntropy, tokenWidth } from "./report";

export interface ScopeConfig {
	/** Ask llama.cpp for per-token probabilities on every request. */
	capture: boolean;
	/** Run the recording proxy so those probabilities can be read back. */
	proxy: boolean;
	/**
	 * `post` reports the candidates the chain left alive (truncation width);
	 * `raw` reports the model's unmodified top-K. One request can carry only one.
	 */
	probeMode: "post" | "raw";
	/** Preview depth; full width and entropy are reported separately by the custom server. */
	nProbs: number;
	/** Show the live widget above the editor. */
	widget: boolean;
	/** Poll /slots during generation for the server's effective configuration. */
	slots: boolean;
	/** Append every finished generation to a JSONL file for offline analysis. */
	jsonl: boolean;
}

export const DEFAULT_SCOPE_CONFIG: ScopeConfig = {
	capture: false,
	proxy: false,
	probeMode: "post",
	nProbs: 20,
	widget: true,
	slots: true,
	jsonl: false,
};

export interface ScopeLogger {
	debug(message: string, data?: Record<string, unknown>): void;
	warn(message: string, data?: Record<string, unknown>): void;
}

export interface SlotSnapshot {
	at: number;
	processing: boolean;
	decoded?: number;
	promptTokens?: number;
	cachedTokens?: number;
	samplers?: string[];
	tokPerSec?: number;
}

export interface ScopeOptions {
	/** Apply the active profile to vLLM requests which bypass OMP's request hook (compaction). */
	vllmTransformRequest?: (body: Record<string, unknown>) => void;
	logger: ScopeLogger;
	/** Knob keys worth recording from a request body. */
	knobKeys: readonly string[];
	/** Limit recorded knobs to the active stages, so unused saved knobs do not split averages. */
	knobsBySampler?: Record<string, readonly string[]>;
	/** Internal routing tool name, used to label router requests. */
	routerToolName: string;
	storageDir: string;
	onUpdate?: () => void;
}

const UPDATE_THROTTLE_MS = 120;
/** Poll rate while the server is decoding. */
const SLOT_POLL_BUSY_MS = 400;
/** Poll rate while it is idle — /slots posts a task to the server queue, so
 *  hammering it when nothing is happening is needless work for llama.cpp. */
const SLOT_POLL_IDLE_MS = 3000;

export class SamplerScope {
	config: ScopeConfig = { ...DEFAULT_SCOPE_CONFIG };
	readonly store = new GenerationStore();

	#options: ScopeOptions;
	#client?: LlamaClient;
	#upstream?: string;
	#proxy?: RecordingProxy;
	#builders = new Map<number, GenerationBuilder>();
	#active?: GenerationBuilder;
	#props?: LlamaProps;
	#support: SamplerSupportEntry[] = [];
	#dropped = new Set<string>();
	#slot?: SlotSnapshot;
	#pollTimer?: ReturnType<typeof setTimeout>;
	#polling = false;
	#lastUpdate = 0;
	#jsonlPath?: string;
	#lastError?: string;
	#backend: "llama.cpp" | "vllm" = "llama.cpp";

	constructor(options: ScopeOptions) {
		this.#options = options;
	}

	// --- server connection ---------------------------------------------------

	get client(): LlamaClient | undefined {
		return this.#client;
	}

	get backend(): "llama.cpp" | "vllm" {
		return this.#backend;
	}

	get props(): LlamaProps | undefined {
		return this.#props;
	}

	get support(): readonly SamplerSupportEntry[] {
		return this.#support;
	}

	get droppedSamplers(): string[] {
		return [...this.#dropped];
	}

	get slot(): SlotSnapshot | undefined {
		return this.#slot;
	}

	get proxyUrl(): string | undefined {
		return this.#proxy?.url;
	}

	get upstream(): string | undefined {
		return this.#upstream;
	}

	get lastError(): string | undefined {
		return this.#lastError;
	}

	/** Point the scope at a llama.cpp server. Safe to call repeatedly. */
	async connect(
		baseUrl: string,
		catalog: readonly { id: string; knobs: readonly { key: string }[] }[],
		backend: "llama.cpp" | "vllm" = "llama.cpp",
	): Promise<void> {
		// Once the proxy is in front of the model, ctx.model.baseUrl points at us;
		// telemetry endpoints must keep talking to the real server.
		if (this.#proxy && baseUrl.startsWith(this.#proxy.url)) return;
		if (this.#upstream === baseUrl && this.#backend === backend && (this.#props || backend === "vllm")) return;
		this.stopPolling();
		this.#backend = backend;
		this.#upstream = baseUrl;
		const client = backend === "vllm" ? undefined : new LlamaClient(baseUrl);
		this.#client = client;
		this.#props = undefined;
		this.#support = [];
		this.#slot = undefined;
		this.#lastError = undefined;
		this.clearDropped();
		// vLLM exposes neither /props nor /slots. Its authenticated completion
		// requests still pass unchanged through the recording proxy.
		if (!client) return;
		try {
			const props = await client.props();
			if (this.#client !== client) return;
			this.#props = props;
			this.#support = inferSamplerSupport(this.#props, catalog);
			this.#lastError = undefined;
		} catch (error) {
			if (this.#client !== client) return;
			this.#lastError = error instanceof Error ? error.message : String(error);
			this.#options.logger.warn("sampler scope could not read /props", {
				error: this.#lastError,
			});
		}
	}

	/** A slot index reserved for probes, when the server has one to spare. */
	spareSlot(): number | undefined {
		const total = this.#props?.total_slots ?? 1;
		return total > 1 ? total - 1 : undefined;
	}

	// --- request instrumentation ---------------------------------------------

	/**
	 * Add probability reporting to an outgoing request. Returns true when the
	 * body was modified.
	 */
	instrument(body: Record<string, unknown>): boolean {
		if (!this.config.capture) return false;
		if (this.#backend === "vllm") {
			body.logprobs = true;
			body.top_logprobs = Math.min(20, this.config.nProbs);
			return true;
		}
		body.n_probs = this.config.nProbs;
		body.post_sampling_probs = this.config.probeMode === "post";
		body.timings_per_token = true;
		return true;
	}

	/** Strip telemetry fields, e.g. when capture is turned off mid-session. */
	deinstrument(body: Record<string, unknown>): void {
		if (this.#backend === "vllm") {
			delete body.logprobs;
			delete body.top_logprobs;
		}
		delete body.n_probs;
		delete body.post_sampling_probs;
		delete body.timings_per_token;
	}

	// --- proxy ---------------------------------------------------------------

	async startProxy(): Promise<string> {
		if (this.#proxy) return this.#proxy.url;
		if (!this.#upstream)
			throw new Error("no upstream llama.cpp server is known yet");
		this.#proxy = await startRecordingProxy({
			upstream: this.#upstream,
			transformRequest: (body) => {
				if (this.#backend === "vllm") this.#options.vllmTransformRequest?.(body);
			},
			hooks: {
				onRequest: (info) => this.#onProxyRequest(info),
				onPayload: (id, payload) => this.#onProxyPayload(id, payload),
				onResponse: (info) => this.#onProxyResponse(info),
				onError: (error) => {
					this.#lastError = error.message;
					this.#options.logger.warn("sampler scope proxy error", {
						error: error.message,
					});
				},
			},
		});
		this.#options.logger.debug("sampler scope proxy listening", {
			url: this.#proxy.url,
			upstream: this.#upstream,
		});
		return this.#proxy.url;
	}

	async stopProxy(): Promise<void> {
		const proxy = this.#proxy;
		this.#proxy = undefined;
		this.#builders.clear();
		this.#active = undefined;
		if (proxy) await proxy.close();
	}

	#onProxyRequest(info: {
		id: number;
		method: string;
		path: string;
		body?: Record<string, unknown>;
		startedAt: number;
	}): void {
		const body = info.body;
		if (!body || info.method !== "POST") return;
		if (
			!/\/(chat\/)?completions$|\/completion$|\/infill$/.test(
				info.path.split("?")[0],
			)
		) {
			return;
		}
		const chain = this.#backend === "vllm" ? vllmSamplerChain(body) : Array.isArray(body.samplers)
			? body.samplers.filter((v): v is string => typeof v === "string")
			: [];
		const params: Record<string, number | boolean> = {};
		const keys = this.#backend === "vllm"
			? ["temperature", "min_p", "top_p", "top_k", "repetition_penalty", "presence_penalty", "frequency_penalty"]
			: chain.length > 0 && this.#options.knobsBySampler
			? chain.flatMap((id) => this.#options.knobsBySampler?.[id] ?? [])
			: this.#options.knobKeys;
		for (const key of keys) {
			const value = body[key];
			if (typeof value === "number" || typeof value === "boolean")
				params[key] = value;
		}
		const custom = this.#backend === "vllm" ? vllmSamplerConfig(body) : undefined;
		if (custom) {
			for (const key of Object.keys(params)) delete params[key];
			for (const [key, value] of Object.entries(custom.params)) {
				if (typeof value === "number" || typeof value === "boolean") params[key] = value;
				else if (key === "temperature" && value === "inf") params.temperature_infinite = true;
			}
		}
		const tools = Array.isArray(body.tools) ? body.tools : [];
		const isRouter = tools.some((tool) => {
			if (typeof tool !== "object" || tool === null) return false;
			const fn = (tool as { function?: { name?: unknown } }).function;
			return fn?.name === this.#options.routerToolName;
		});
		const preview = this.#backend === "vllm" ? body.top_logprobs : body.n_probs;
		const nProbs = typeof preview === "number" ? preview : 0;
		const record: GenerationRecord = {
			id: this.store.nextId(),
			kind: isRouter
				? "route"
				: info.path.includes("completion")
					? "answer"
					: "other",
			startedAt: info.startedAt,
			path: info.path.split("?")[0],
			model: typeof body.model === "string" ? body.model : undefined,
			chain,
			params,
			nProbs,
			mode: body.post_sampling_probs === true ? "post" : "raw",
			tokens: [],
			replay: isRouter
				? undefined
				: {
						messages: body.messages,
						tools: body.tools,
						chat_template_kwargs: body.chat_template_kwargs,
					},
		};
		const builder = new GenerationBuilder(record);
		this.#builders.set(info.id, builder);
		this.#active = builder;
		this.clearDropped();
		// A request just started: switch the slot poller to its busy cadence now
		// instead of waiting out the idle delay.
		if (this.#polling && this.#pollTimer) {
			clearTimeout(this.#pollTimer);
			this.#schedulePoll(0);
		}
		this.#notify(true);
	}

	#onProxyPayload(id: number, payload: string): void {
		const builder = this.#builders.get(id);
		if (!builder) return;
		const chunk = parseChunk(payload);
		if (!chunk) return;
		builder.accept(chunk, Date.now());
		if (chunk.appliedChain !== undefined && this.#active === builder) {
			this.noteRequest(builder.record.chain, chunk.appliedChain);
		}
		this.#notify();
	}

	#onProxyResponse(info: {
		id: number;
		status: number;
		endedAt: number;
		error?: string;
	}): void {
		const builder = this.#builders.get(info.id);
		this.#builders.delete(info.id);
		if (!builder) return;
		const record = builder.finish(
			info.endedAt,
			info.error ?? (info.status >= 400 ? `HTTP ${info.status}` : undefined),
		);
		this.store.push(record);
		if (this.#active === builder) this.#active = undefined;
		this.#appendJsonl(record);
		this.#notify(true);
	}

	// --- slot polling --------------------------------------------------------

	startPolling(): void {
		if (this.#backend === "vllm" || this.#pollTimer || !this.config.slots) return;
		this.#polling = true;
		this.#schedulePoll(SLOT_POLL_IDLE_MS);
	}

	stopPolling(): void {
		this.#polling = false;
		if (this.#pollTimer) clearTimeout(this.#pollTimer);
		this.#pollTimer = undefined;
	}

	#schedulePoll(delay: number): void {
		if (!this.#polling) return;
		this.#pollTimer = setTimeout(() => {
			void this.#pollSlots().finally(() => {
				this.#schedulePoll(
					this.#slot?.processing || this.#active
						? SLOT_POLL_BUSY_MS
						: SLOT_POLL_IDLE_MS,
				);
			});
		}, delay);
		// Never hold the process open for telemetry.
		(this.#pollTimer as unknown as { unref?: () => void }).unref?.();
	}

	async #pollSlots(): Promise<void> {
		const client = this.#client;
		if (!client || !this.config.slots) return;
		try {
			const slots = await client.slots();
			if (this.#client !== client) return;
			const slot = slots.find((s) => s.is_processing) ?? slots[0];
			if (!slot) return;
			const decoded = slot.next_token?.[0]?.n_decoded;
			const previous = this.#slot;
			const now = Date.now();
			let tokPerSec: number | undefined;
			if (
				previous?.processing &&
				previous.decoded !== undefined &&
				decoded !== undefined &&
				decoded > previous.decoded &&
				now > previous.at
			) {
				tokPerSec = ((decoded - previous.decoded) / (now - previous.at)) * 1000;
			}
			this.#slot = {
				at: now,
				processing: slot.is_processing === true,
				decoded,
				promptTokens: slot.n_prompt_tokens,
				cachedTokens: slot.n_prompt_tokens_cache,
				samplers: slotSamplers(slot),
				tokPerSec:
					tokPerSec ?? (slot.is_processing ? previous?.tokPerSec : undefined),
			};
			this.#lastError = undefined;
			if (slot.is_processing === true) this.#notify();
		} catch (error) {
			if (this.#client !== client) return;
			// /slots is opt-in on the server; stop hammering it if it is missing.
			const message = error instanceof Error ? error.message : String(error);
			if (message.includes("501") || message.includes("not support")) {
				this.config.slots = false;
				this.stopPolling();
			}
			this.#lastError = message;
		}
	}

	/**
	 * Compare a request with its own response's generation_settings.samplers.
	 * Never pass /slots here: idle slots retain previous requests, and busy slots
	 * can belong to another client. Neither proves a requested sampler was dropped.
	 */
	noteRequest(chain: readonly string[], applied?: readonly string[]): void {
		if (!applied) return;
		this.#dropped = new Set(diffSamplerChain(chain, applied).dropped);
	}

	clearDropped(): void {
		this.#dropped.clear();
	}

	// --- current generation --------------------------------------------------

	/** The generation currently streaming, if the proxy is watching one. */
	active(): GenerationRecord | undefined {
		return this.#active?.record;
	}

	/** Newest generation with captured tokens, streaming or finished. */
	current(): GenerationRecord | undefined {
		const active = this.#active?.record;
		if (active && active.tokens.length > 0) return active;
		return this.store.latest();
	}

	liveTokensPerSecond(): number | undefined {
		const record = this.active();
		if (record && record.tokens.length > 2) {
			const window = record.tokens.slice(-16);
			const span = window[window.length - 1].atMs - window[0].atMs;
			if (span > 0) return ((window.length - 1) / span) * 1000;
		}
		return this.#slot?.tokPerSec;
	}

	/** Median truncation width over the most recent captured steps. */
	recentWidth(count = 32): number | undefined {
		const record = this.current();
		if (!record) return undefined;
		const widths = record.tokens
			.slice(-count)
			.map(tokenWidth)
			.filter((w): w is number => w !== undefined)
			.sort((a, b) => a - b);
		if (widths.length === 0) return undefined;
		return widths[Math.floor(widths.length / 2)];
	}

	// --- persistence ---------------------------------------------------------

	jsonlPath(): string {
		if (!this.#jsonlPath) {
			this.#jsonlPath = path.join(
				this.#options.storageDir,
				`sampler-scope-${new Date().toISOString().slice(0, 10)}.jsonl`,
			);
		}
		return this.#jsonlPath;
	}

	#appendJsonl(record: GenerationRecord): void {
		if (!this.config.jsonl || record.tokens.length === 0) return;
		try {
			fs.mkdirSync(this.#options.storageDir, { recursive: true });
			const stats = summarizeGeneration(record);
			const line = JSON.stringify({
				schemaVersion: 2,
				id: record.id,
				kind: record.kind,
				startedAt: record.startedAt,
				endedAt: record.endedAt,
				model: record.model,
				chain: record.chain,
				appliedChain: record.appliedChain,
				params: record.params,
				mode: record.mode,
				nProbs: record.nProbs,
				summary: {
					tokens: stats.tokens,
					widthMean: stats.width?.mean,
					widthMedian: stats.width?.median,
					widthP90: stats.width?.p90,
					widthMax: stats.width?.max,
					widthKnown: stats.widthKnown,
					vocabSize: stats.vocabSize,
					forcedRate: stats.forcedRate,
					saturationRate: stats.saturationRate,
					entropyMean: stats.entropy?.mean,
					entropyKnown: stats.entropyKnown,
					rawRank: stats.rawRank,
					postRank: stats.postRank,
					tokPerSec: stats.tokPerSec,
					ttftMs: stats.ttftMs,
				},
				tokens: record.tokens.map((t) => ({
					i: t.index,
					text: t.text,
					id: t.id,
					p: t.prob,
					rawRank: tokenChosenRank(t, "raw"),
					postRank: tokenChosenRank(t, "post"),
					w: tokenWidth(t),
					vocabSize: t.vocabSize,
					entropyBits: tokenEntropy(t),
					varentropyBits2: t.varentropyBits2,
					previewCount: t.candidates.length,
					previewClipped: t.saturated,
					dt: Math.round(t.dtMs),
					top: t.candidates
						.slice(0, 8)
						.map((c) => [c.id ?? c.token, Number(c.p.toFixed(5))]),
				})),
			});
			fs.appendFileSync(this.jsonlPath(), `${line}\n`);
		} catch (error) {
			this.#options.logger.warn("sampler scope could not write jsonl", {
				error: error instanceof Error ? error.message : String(error),
			});
		}
	}

	// --- misc ----------------------------------------------------------------

	#notify(force = false): void {
		const now = Date.now();
		if (!force && now - this.#lastUpdate < UPDATE_THROTTLE_MS) return;
		this.#lastUpdate = now;
		try {
			this.#options.onUpdate?.();
		} catch {
			/* UI refresh is best effort */
		}
	}

	async shutdown(): Promise<void> {
		this.stopPolling();
		await this.stopProxy();
	}
}
