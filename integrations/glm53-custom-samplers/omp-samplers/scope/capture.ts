/**
 * Wire-level capture: turn llama.cpp responses into per-token telemetry.
 *
 * llama.cpp reports token probabilities in two mutually exclusive flavors and
 * signals which one it used purely through field names:
 *
 *   post_sampling_probs: true  →  { "prob": …, "top_probs":    [...] }
 *   post_sampling_probs: false →  { "logprob": …, "top_logprobs": [...] }
 *
 * Candidate previews are capped by n_probs. Full-distribution summary fields
 * from the custom server report width and entropy independently of that cap.
 *
 * These functions are pure so they can be tested against recorded fixtures.
 */

import type { Candidate } from "./metrics";

export type ProbMode = "post" | "raw";

export interface DistributionStats {
	/** Count of finite post-chain logits, independent of preview size and mode. */
	candidateCount?: number;
	vocabSize?: number;
	/** Full-distribution moments in the reported probability mode. */
	entropyBits?: number;
	varentropyBits2?: number;
}

export interface TokenRecord extends DistributionStats {
	/** 0-based decode index within the generation. */
	index: number;
	/** Detokenized piece for the sampled token. */
	text: string;
	id?: number;
	/** Probability of the sampled token in whichever distribution was reported. */
	prob?: number;
	/** Full-vocabulary rank before any samplers (server extension), 1-based. */
	rawRank?: number;
	/** Rank among survivors after the chain, 1-based. Equal logits share a rank. */
	postRank?: number;
	/** Candidates reported for this step, best first. */
	candidates: Candidate[];
	mode: ProbMode;
	/** True when the candidate list was clipped by the requested n_probs. */
	saturated: boolean;
	/** Wall-clock offset from the start of the generation, in ms. */
	atMs: number;
	/** Gap since the previous captured token, in ms. */
	dtMs: number;
}

export interface WireTimings {
	cacheN?: number;
	promptN?: number;
	promptMs?: number;
	predictedN?: number;
	predictedMs?: number;
	predictedPerSecond?: number;
	draftN?: number;
	draftAccepted?: number;
}

export interface GenerationRecord {
	id: number;
	/** Which omp request this was, as far as the extension can tell. */
	kind: "answer" | "route" | "other";
	startedAt: number;
	endedAt?: number;
	path: string;
	model?: string;
	/** Sampler chain the request asked for. */
	chain: string[];
	/** Sampler knob values the request carried. */
	params: Record<string, number | boolean>;
	/** n_probs the request asked for; 0 when telemetry was off. */
	nProbs: number;
	mode: ProbMode;
	tokens: TokenRecord[];
	/** Time from request start to the first captured token. */
	ttftMs?: number;
	timings?: WireTimings;
	usage?: { prompt?: number; completion?: number; cached?: number };
	/** Sampler chain the server reported back through /slots, when observed. */
	appliedChain?: string[];
	/**
	 * Enough of the request to replay it through `/apply-template` for a probe.
	 * Kept only for the newest few records so history stays small.
	 */
	replay?: {
		messages?: unknown;
		tools?: unknown;
		chat_template_kwargs?: unknown;
	};
	error?: string;
}

// ---------------------------------------------------------------------------
// SSE framing
// ---------------------------------------------------------------------------

/**
 * Incremental `text/event-stream` splitter. Feed it arbitrary chunk boundaries;
 * it yields complete `data:` payloads in order.
 */
export class SseSplitter {
	#buffer = "";

	feed(chunk: string): string[] {
		this.#buffer += chunk;
		const payloads: string[] = [];
		// Frames are separated by a blank line; tolerate CRLF from proxies.
		let boundary = this.#findBoundary();
		while (boundary >= 0) {
			const frame = this.#buffer.slice(0, boundary);
			this.#buffer = this.#buffer.slice(this.#skipBoundary(boundary));
			const data = frameData(frame);
			if (data !== undefined) payloads.push(data);
			boundary = this.#findBoundary();
		}
		return payloads;
	}

	/** Flush a trailing frame that never got its blank line (stream aborted). */
	flush(): string[] {
		const rest = this.#buffer;
		this.#buffer = "";
		const data = frameData(rest);
		return data === undefined ? [] : [data];
	}

	#findBoundary(): number {
		const lf = this.#buffer.indexOf("\n\n");
		const crlf = this.#buffer.indexOf("\r\n\r\n");
		if (lf < 0) return crlf;
		if (crlf < 0) return lf;
		return Math.min(lf, crlf);
	}

	#skipBoundary(index: number): number {
		return this.#buffer.startsWith("\r\n\r\n", index) ? index + 4 : index + 2;
	}
}

function frameData(frame: string): string | undefined {
	const lines = frame.split(/\r?\n/);
	const data: string[] = [];
	for (const line of lines) {
		if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
	}
	if (data.length === 0) return undefined;
	return data.join("\n");
}

// ---------------------------------------------------------------------------
// Payload parsing
// ---------------------------------------------------------------------------

interface WireCandidate {
	id?: number;
	token?: string;
	prob?: number;
	logprob?: number;
	raw_rank?: number;
	post_rank?: number;
	candidate_count?: number;
	vocab_size?: number;
	entropy_bits?: number;
	varentropy_bits2?: number;
	top_probs?: WireCandidate[];
	top_logprobs?: WireCandidate[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toCandidate(entry: unknown): Candidate | undefined {
	if (!isRecord(entry)) return undefined;
	const wire = entry as WireCandidate;
	const token = typeof wire.token === "string" ? wire.token : undefined;
	if (token === undefined) return undefined;
	const p =
		typeof wire.prob === "number"
			? wire.prob
			: typeof wire.logprob === "number"
				? Math.exp(wire.logprob)
				: undefined;
	if (p === undefined || !Number.isFinite(p)) return undefined;
	return { id: typeof wire.id === "number" ? wire.id : undefined, token, p };
}

/** One decode step as reported by the server, before timing is attached. */
export interface RawStep extends DistributionStats {
	text: string;
	id?: number;
	prob?: number;
	rawRank?: number;
	postRank?: number;
	candidates: Candidate[];
	mode: ProbMode;
}

/** Parse a `completion_probabilities` / `logprobs.content` array. */
export function parseProbEntries(entries: unknown): RawStep[] {
	if (!Array.isArray(entries)) return [];
	const steps: RawStep[] = [];
	for (const entry of entries) {
		if (!isRecord(entry)) continue;
		const wire = entry as WireCandidate;
		const mode: ProbMode =
			wire.top_probs !== undefined || wire.prob !== undefined ? "post" : "raw";
		const top = wire.top_probs ?? wire.top_logprobs ?? [];
		const candidates: Candidate[] = [];
		for (const item of top) {
			const candidate = toCandidate(item);
			if (candidate) candidates.push(candidate);
		}
		const self = toCandidate(wire);
		const rank = (value: unknown): number | undefined =>
			typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value : undefined;
		const moment = (value: unknown): number | undefined =>
			typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
		steps.push({
			text: typeof wire.token === "string" ? wire.token : "",
			id: typeof wire.id === "number" ? wire.id : undefined,
			prob: self?.p,
			rawRank: rank(wire.raw_rank),
			postRank: rank(wire.post_rank),
			candidateCount: rank(wire.candidate_count),
			vocabSize: rank(wire.vocab_size),
			entropyBits: moment(wire.entropy_bits),
			varentropyBits2: moment(wire.varentropy_bits2),
			candidates,
			mode,
		});
	}
	return steps;
}

export interface ParsedChunk {
	steps: RawStep[];
	/** Sampler chain echoed in this response, never inferred from /slots. */
	appliedChain?: string[];
	timings?: WireTimings;
	usage?: { prompt?: number; completion?: number; cached?: number };
	/** Text delta, used only to keep a readable transcript of the generation. */
	text?: string;
	done: boolean;
}

function parseTimings(value: unknown): WireTimings | undefined {
	if (!isRecord(value)) return undefined;
	const pick = (key: string): number | undefined => {
		const v = value[key];
		return typeof v === "number" && Number.isFinite(v) ? v : undefined;
	};
	const timings: WireTimings = {
		cacheN: pick("cache_n"),
		promptN: pick("prompt_n"),
		promptMs: pick("prompt_ms"),
		predictedN: pick("predicted_n"),
		predictedMs: pick("predicted_ms"),
		predictedPerSecond: pick("predicted_per_second"),
		draftN: pick("draft_n"),
		draftAccepted: pick("draft_n_accepted"),
	};
	return Object.values(timings).some((v) => v !== undefined)
		? timings
		: undefined;
}

function parseUsage(
	value: unknown,
): { prompt?: number; completion?: number; cached?: number } | undefined {
	if (!isRecord(value)) return undefined;
	const prompt = value.prompt_tokens;
	const completion = value.completion_tokens;
	const details = isRecord(value.prompt_tokens_details)
		? value.prompt_tokens_details
		: undefined;
	const cached = details?.cached_tokens;
	return {
		prompt: typeof prompt === "number" ? prompt : undefined,
		completion: typeof completion === "number" ? completion : undefined,
		cached: typeof cached === "number" ? cached : undefined,
	};
}

/**
 * Parse one SSE payload or one non-streamed response body. Handles the chat,
 * legacy-completions and native `/completion` shapes in one pass because the
 * probability payload is identical in all three.
 */
export function parseChunk(payload: string): ParsedChunk | undefined {
	const trimmed = payload.trim();
	if (trimmed === "") return undefined;
	if (trimmed === "[DONE]") return { steps: [], done: true };
	let json: unknown;
	try {
		json = JSON.parse(trimmed);
	} catch {
		return undefined;
	}
	if (!isRecord(json)) return undefined;

	const steps: RawStep[] = [];
	let text: string | undefined;

	const choices = json.choices;
	if (Array.isArray(choices)) {
		for (const choice of choices) {
			if (!isRecord(choice)) continue;
			const logprobs = choice.logprobs;
			if (isRecord(logprobs)) steps.push(...parseProbEntries(logprobs.content));
			const delta = isRecord(choice.delta) ? choice.delta : undefined;
			const content = delta?.content ?? choice.text;
			if (typeof content === "string" && content !== "")
				text = (text ?? "") + content;
			const message = isRecord(choice.message) ? choice.message : undefined;
			if (typeof message?.content === "string" && message.content !== "") {
				text = (text ?? "") + message.content;
			}
		}
	}
	if (json.completion_probabilities !== undefined) {
		steps.push(...parseProbEntries(json.completion_probabilities));
	}
	if (typeof json.content === "string" && json.content !== "") {
		text = (text ?? "") + json.content;
	}
	const settings = isRecord(json.generation_settings) ? json.generation_settings : undefined;
	const samplers = settings?.samplers;
	const appliedChain = Array.isArray(samplers) && samplers.every((id) => typeof id === "string")
		? samplers as string[]
		: undefined;

	return {
		steps,
		appliedChain,
		timings: parseTimings(json.timings),
		usage: parseUsage(json.usage),
		text,
		done: json.stop === true,
	};
}

// ---------------------------------------------------------------------------
// Generation assembly
// ---------------------------------------------------------------------------

/**
 * Accumulates parsed chunks into a single {@link GenerationRecord}, stamping
 * arrival times so inter-token latency survives even when the server does not
 * send `timings_per_token`.
 */
export class GenerationBuilder {
	readonly record: GenerationRecord;
	#lastAt: number;
	#text = "";

	constructor(record: GenerationRecord) {
		this.record = record;
		this.#lastAt = record.startedAt;
	}

	get text(): string {
		return this.#text;
	}

	/** @param now monotonic-ish timestamp in ms (injected so tests stay deterministic). */
	accept(chunk: ParsedChunk, now: number): void {
		if (chunk.text) this.#text += chunk.text;
		if (chunk.appliedChain !== undefined) this.record.appliedChain = chunk.appliedChain;
		if (chunk.timings)
			this.record.timings = { ...this.record.timings, ...chunk.timings };
		if (chunk.usage)
			this.record.usage = { ...this.record.usage, ...chunk.usage };
		for (const step of chunk.steps) {
			const index = this.record.tokens.length;
			if (index === 0) this.record.ttftMs = now - this.record.startedAt;
			this.record.tokens.push({
				index,
				text: step.text,
				id: step.id,
				prob: step.prob,
				rawRank: step.rawRank,
				postRank: step.postRank,
				candidateCount: step.candidateCount,
				vocabSize: step.vocabSize,
				entropyBits: step.entropyBits,
				varentropyBits2: step.varentropyBits2,
				candidates: step.candidates,
				mode: step.mode,
				saturated: step.mode === "post" && step.candidateCount !== undefined
					? step.candidates.length < step.candidateCount
					: this.record.nProbs > 0 && step.candidates.length >= this.record.nProbs,
				atMs: now - this.record.startedAt,
				dtMs: now - this.#lastAt,
			});
			this.record.mode = step.mode;
			this.#lastAt = now;
		}
	}

	finish(now: number, error?: string): GenerationRecord {
		this.record.endedAt = now;
		if (error) this.record.error = error;
		return this.record;
	}
}

/** Bounded history of generations, newest last. */
export class GenerationStore {
	#records: GenerationRecord[] = [];
	#nextId = 1;
	#limit: number;

	constructor(limit = 64) {
		this.#limit = limit;
	}

	nextId(): number {
		return this.#nextId++;
	}

	push(record: GenerationRecord): void {
		this.#records.push(record);
		while (this.#records.length > this.#limit) this.#records.shift();
		// Replay bodies are the only large payload we hold; keep just the tail.
		for (let i = 0; i < this.#records.length - 2; i += 1) {
			this.#records[i].replay = undefined;
		}
	}

	all(): readonly GenerationRecord[] {
		return this.#records;
	}

	/** Most recent generation that actually captured tokens. */
	latest(kind?: GenerationRecord["kind"]): GenerationRecord | undefined {
		for (let i = this.#records.length - 1; i >= 0; i -= 1) {
			const record = this.#records[i];
			if (kind && record.kind !== kind) continue;
			if (record.tokens.length > 0) return record;
		}
		return undefined;
	}

	clear(): void {
		this.#records = [];
	}
}
