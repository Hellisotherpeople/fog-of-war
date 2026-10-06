/**
 * Minimal client for llama.cpp's native HTTP API.
 *
 * The OpenAI-compatible endpoint omp talks to is deliberately not used here.
 * The native endpoints expose things the compat layer hides: an uncapped
 * `n_probs`, `post_sampling_probs`, token-id prompts (exact teacher forcing),
 * the effective per-slot sampler configuration, and the server's echo of the
 * parameters it actually parsed.
 */

export interface LlamaProps {
	default_generation_settings?: {
		params?: Record<string, unknown>;
		n_ctx?: number;
	};
	total_slots?: number;
	model_alias?: string;
	model_path?: string;
	endpoint_slots?: boolean;
	endpoint_metrics?: boolean;
	build_info?: string;
	[key: string]: unknown;
}

export interface LlamaModelMeta {
	n_vocab?: number;
	n_ctx?: number;
	n_ctx_train?: number;
	n_embd?: number;
	n_params?: number;
	size?: number;
	vocab_type?: number;
}

export interface LlamaSlot {
	id: number;
	n_ctx?: number;
	is_processing?: boolean;
	id_task?: number;
	n_prompt_tokens?: number;
	n_prompt_tokens_processed?: number;
	n_prompt_tokens_cache?: number;
	params?: Record<string, unknown>;
	next_token?: Array<{
		has_next_token?: boolean;
		has_new_line?: boolean;
		n_remain?: number;
		n_decoded?: number;
	}>;
}

export interface CompletionResult {
	content?: string;
	tokens?: number[];
	completion_probabilities?: unknown;
	generation_settings?: Record<string, unknown>;
	timings?: Record<string, number>;
	tokens_cached?: number;
	tokens_evaluated?: number;
	tokens_predicted?: number;
	[key: string]: unknown;
}

export class LlamaHttpError extends Error {
	constructor(
		readonly status: number,
		readonly body: string,
		url: string,
	) {
		super(`llama.cpp ${status} for ${url}: ${body.slice(0, 200)}`);
		this.name = "LlamaHttpError";
	}
}

/**
 * Strip an OpenAI-compat suffix so native routes resolve. `…:8080/v1` and
 * `…:8080` both become `…:8080`.
 */
export function nativeBaseUrl(baseUrl: string): string {
	return baseUrl.replace(/\/+$/, "").replace(/\/v1$/, "");
}

export class LlamaClient {
	readonly baseUrl: string;

	constructor(
		baseUrl: string,
		private readonly headers: Record<string, string> = {},
	) {
		this.baseUrl = nativeBaseUrl(baseUrl);
	}

	/**
	 * A caller-supplied signal wins; otherwise metadata calls get a deadline so
	 * an unresponsive server can never stall a session lifecycle handler.
	 */
	static #deadline(
		signal: AbortSignal | undefined,
		timeoutMs: number,
	): AbortSignal | undefined {
		if (signal) return signal;
		const timeout = (AbortSignal as { timeout?: (ms: number) => AbortSignal })
			.timeout;
		return timeout ? timeout(timeoutMs) : undefined;
	}

	async #json<T>(
		path: string,
		init: {
			method: "GET" | "POST";
			body?: unknown;
			signal?: AbortSignal;
			timeoutMs?: number;
		},
	): Promise<T> {
		const url = `${this.baseUrl}${path}`;
		const response = await fetch(url, {
			method: init.method,
			headers: {
				...(init.body === undefined
					? {}
					: { "content-type": "application/json" }),
				...this.headers,
			},
			body: init.body === undefined ? undefined : JSON.stringify(init.body),
			signal:
				init.timeoutMs === undefined
					? init.signal
					: LlamaClient.#deadline(init.signal, init.timeoutMs),
		});
		const text = await response.text();
		if (!response.ok) throw new LlamaHttpError(response.status, text, url);
		return JSON.parse(text) as T;
	}

	props(signal?: AbortSignal): Promise<LlamaProps> {
		return this.#json<LlamaProps>("/props", {
			method: "GET",
			signal,
			timeoutMs: 5000,
		});
	}

	slots(signal?: AbortSignal): Promise<LlamaSlot[]> {
		return this.#json<LlamaSlot[]>("/slots", {
			method: "GET",
			signal,
			timeoutMs: 5000,
		});
	}

	/**
	 * Vocabulary and dimension metadata, which `/props` does not carry.
	 *
	 * `n_vocab` is what makes a token id checkable before it is sent: llama.cpp
	 * discards out-of-range ids in `logit_bias` without an error.
	 */
	async modelMeta(signal?: AbortSignal): Promise<LlamaModelMeta | undefined> {
		try {
			const response = await this.#json<{
				data?: { id?: string; meta?: LlamaModelMeta }[];
			}>("/v1/models", { method: "GET", signal, timeoutMs: 5000 });
			return response.data?.[0]?.meta;
		} catch {
			return undefined;
		}
	}

	tokenize(
		content: string,
		options: { addSpecial?: boolean; parseSpecial?: boolean } = {},
		signal?: AbortSignal,
	): Promise<{ tokens: number[] }> {
		return this.#json("/tokenize", {
			method: "POST",
			body: {
				content,
				add_special: options.addSpecial ?? false,
				parse_special: options.parseSpecial ?? true,
			},
			signal,
			timeoutMs: 20000,
		});
	}

	/**
	 * Tokenize and report each token's rendered piece.
	 *
	 * Needed to bias an ordinary word rather than a special token: the user types
	 * text, and this says whether it is one token and which one. A piece that is
	 * not valid UTF-8 on its own comes back as raw byte values, which is why the
	 * piece type is wider than a string.
	 */
	async tokenizePieces(
		content: string,
		options: { addSpecial?: boolean; parseSpecial?: boolean } = {},
		signal?: AbortSignal,
	): Promise<{ tokens: { id: number; piece: string }[] }> {
		const response = await this.#json<{
			tokens?: { id?: number; piece?: string | number[] }[];
		}>("/tokenize", {
			method: "POST",
			body: {
				content,
				add_special: options.addSpecial ?? false,
				parse_special: options.parseSpecial ?? true,
				with_pieces: true,
			},
			signal,
			timeoutMs: 20000,
		});
		const tokens: { id: number; piece: string }[] = [];
		for (const entry of response.tokens ?? []) {
			if (!Number.isInteger(entry.id)) continue;
			tokens.push({
				id: entry.id as number,
				piece: Array.isArray(entry.piece)
					? Buffer.from(entry.piece).toString("utf8")
					: (entry.piece ?? ""),
			});
		}
		return { tokens };
	}

	detokenize(
		tokens: readonly number[],
		signal?: AbortSignal,
	): Promise<{ content: string }> {
		return this.#json("/detokenize", {
			method: "POST",
			body: { tokens },
			signal,
			timeoutMs: 20000,
		});
	}

	/** Render an OpenAI-shaped chat body through the server's own chat template. */
	applyTemplate(
		body: Record<string, unknown>,
		signal?: AbortSignal,
	): Promise<{ prompt: string }> {
		return this.#json("/apply-template", {
			method: "POST",
			body,
			signal,
			timeoutMs: 20000,
		});
	}

	completion(
		body: Record<string, unknown>,
		signal?: AbortSignal,
	): Promise<CompletionResult> {
		return this.#json<CompletionResult>("/completion", {
			method: "POST",
			body: { ...body, stream: false },
			signal,
			// Probe requests decode a single token but may queue behind a real
			// generation; generous, yet still bounded.
			timeoutMs: 120000,
		});
	}
}

// ---------------------------------------------------------------------------
// Capability inference
// ---------------------------------------------------------------------------

export type SamplerSupport = "supported" | "unsupported" | "unknown";

export interface SamplerSupportEntry {
	id: string;
	support: SamplerSupport;
	/** How the verdict was reached, shown in the capability report. */
	evidence: string;
}

/**
 * Infer sampler support from `/props` at zero generation cost.
 *
 * llama.cpp serializes every sampling knob it knows about into
 * `default_generation_settings.params`, so a build that lacks `hill` also lacks
 * `hill_order`. Knobless samplers (otsu, kneedle, top_gap) leave no fingerprint
 * there and stay "unknown" until a live request confirms them.
 */
export function inferSamplerSupport(
	props: LlamaProps,
	catalog: readonly { id: string; knobs: readonly { key: string }[] }[],
): SamplerSupportEntry[] {
	const params = props.default_generation_settings?.params ?? {};
	return catalog.map((sampler) => {
		if (sampler.knobs.length === 0) {
			return {
				id: sampler.id,
				support: "unknown" as const,
				evidence: "no knob to probe; confirmed only by a live request",
			};
		}
		const missing = sampler.knobs.filter((knob) => !(knob.key in params));
		if (missing.length === 0) {
			return {
				id: sampler.id,
				support: "supported" as const,
				evidence: `/props exposes ${sampler.knobs.map((k) => k.key).join(", ")}`,
			};
		}
		if (missing.length === sampler.knobs.length) {
			return {
				id: sampler.id,
				support: "unsupported" as const,
				evidence: `/props has no ${missing.map((k) => k.key).join(", ")}`,
			};
		}
		return {
			id: sampler.id,
			support: "unknown" as const,
			evidence: `/props is missing ${missing.map((k) => k.key).join(", ")}`,
		};
	});
}

/** The `samplers` array a slot reports, normalized to strings. */
export function slotSamplers(
	slot: LlamaSlot | undefined,
): string[] | undefined {
	const raw = slot?.params?.samplers;
	if (!Array.isArray(raw)) return undefined;
	return raw.filter((v): v is string => typeof v === "string");
}

/**
 * Compare what a request asked for against what the server reports it applied.
 * A name that vanishes was silently dropped by `common_sampler_types_from_names`
 * — the classic "this build does not have that sampler" failure, which is
 * otherwise invisible because llama.cpp does not error on unknown names.
 */
export function diffSamplerChain(
	requested: readonly string[],
	applied: readonly string[],
): { dropped: string[]; reordered: boolean; added: string[] } {
	const appliedSet = new Set(applied);
	const requestedSet = new Set(requested);
	const dropped = requested.filter((id) => !appliedSet.has(id));
	const added = applied.filter((id) => !requestedSet.has(id));
	const shared = requested.filter((id) => appliedSet.has(id));
	const sharedApplied = applied.filter((id) => requestedSet.has(id));
	const reordered = shared.join(",") !== sharedApplied.join(",");
	return { dropped, reordered, added };
}

/** Knob values a slot reports, restricted to the keys the caller cares about. */
export function slotParams(
	slot: LlamaSlot | undefined,
	keys: readonly string[],
): Record<string, number | boolean> {
	const out: Record<string, number | boolean> = {};
	const params = slot?.params;
	if (!params) return out;
	for (const key of keys) {
		const value = params[key];
		if (typeof value === "number" || typeof value === "boolean")
			out[key] = value;
	}
	return out;
}

/** Knob values that differ between the request and the server's echo. */
export function diffSamplerParams(
	requested: Record<string, number | boolean>,
	applied: Record<string, number | boolean>,
	tolerance = 1e-4,
): {
	key: string;
	want: number | boolean;
	got: number | boolean | undefined;
}[] {
	const out: {
		key: string;
		want: number | boolean;
		got: number | boolean | undefined;
	}[] = [];
	for (const [key, want] of Object.entries(requested)) {
		const got = applied[key];
		if (got === undefined) {
			out.push({ key, want, got: undefined });
			continue;
		}
		if (typeof want === "number" && typeof got === "number") {
			if (Math.abs(want - got) > tolerance * Math.max(1, Math.abs(want))) {
				out.push({ key, want, got });
			}
			continue;
		}
		if (want !== got) out.push({ key, want, got });
	}
	return out;
}
