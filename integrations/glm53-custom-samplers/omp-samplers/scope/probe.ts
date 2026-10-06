/**
 * Before/after sampler probing.
 *
 * A single llama.cpp request can report probabilities in exactly one flavor —
 * raw model logits *or* the post-chain candidate set — so measuring both sides
 * of the intervention takes two evaluations of the same position. The probe
 * teacher-forces a token sequence and re-asks the server one step at a time:
 *
 *   pass 1  chain + post_sampling_probs → survivors, their renormalized probs,
 *           and the token the chain actually sampled
 *   pass 2  greedy + raw probs           → the model's unmodified distribution
 *   pass 3  chain prefixes + post probs  → survivor count after each stage,
 *           i.e. which sampler in the chain is doing the cutting
 *
 * Every request shares the same growing prefix, so with `cache_prompt` the KV
 * cache is reused and each step costs one token of decode rather than a full
 * prefill. The expensive part is request count, not compute.
 *
 * Caveat worth knowing while reading a funnel: `dry` and `penalties` score the
 * tokens generated *within a request*. A one-token forced step has no such
 * history, so those stages under-report. They are flagged in the output.
 */

import { type DistributionStats, parseProbEntries } from "./capture";
import type { CompletionResult } from "./llama";
import { type Candidate, compareStep, type StepComparison } from "./metrics";

/** The slice of {@link LlamaClient} the probe needs; keeps tests server-free. */
export interface ProbeClient {
	completion(
		body: Record<string, unknown>,
		signal?: AbortSignal,
	): Promise<CompletionResult>;
	tokenize(
		content: string,
		options?: { addSpecial?: boolean; parseSpecial?: boolean },
		signal?: AbortSignal,
	): Promise<{ tokens: number[] }>;
}

/** Samplers whose behavior depends on tokens generated earlier in the request. */
export const HISTORY_DEPENDENT = new Set(["dry", "penalties"]);

export interface FunnelMeasurement {
	sampler: string;
	width: number;
	saturated: boolean;
	historyDependent: boolean;
}

export interface ProbeStep {
	index: number;
	tokenId?: number;
	text: string;
	/** Raw model distribution, best first. */
	raw: Candidate[];
	/** Post-chain survivors, best first. */
	post: Candidate[];
	/** Survivor count after each chain prefix; empty when the funnel was skipped. */
	funnel: FunnelMeasurement[];
	comparison: StepComparison;
}

export interface ProbeResult {
	steps: ProbeStep[];
	chain: string[];
	params: Record<string, number | boolean>;
	/** Text of the analyzed tokens, concatenated. */
	text: string;
	promptTokenCount: number;
	nProbs: number;
	funnelNProbs: number;
	requests: number;
	durationMs: number;
	/** Caveats worth showing next to the numbers. */
	notes: string[];
}

export interface ProbeOptions {
	/** Exact prefix. Takes precedence over `promptText`. */
	promptTokens?: readonly number[];
	promptText?: string;
	chain: readonly string[];
	params: Record<string, number | boolean>;
	/** Decode positions to analyze. */
	steps: number;
	/** Top-K depth for the raw and post distributions. */
	nProbs?: number;
	/** Ceiling used when measuring per-stage survivor counts. */
	funnelNProbs?: number;
	funnel?: boolean;
	/**
	 * Teacher-force these token ids instead of letting the chain generate. Pass
	 * the tokens a real generation produced to analyze that exact answer.
	 */
	forcedTokens?: readonly number[];
	/**
	 * Detokenized pieces for `forcedTokens`. Supplying them keeps step labels
	 * readable even when a stochastic sampler cuts the forced token on replay,
	 * in which case the survivor list cannot name it.
	 */
	forcedTexts?: readonly string[];
	/** Pin probes to a spare slot so the agent's KV cache survives. */
	idSlot?: number;
	signal?: AbortSignal;
	onProgress?(done: number, total: number, label: string): void;
}

function chainParams(
	chain: readonly string[],
	params: Record<string, number | boolean>,
): Record<string, unknown> {
	return { samplers: [...chain], ...params };
}

function firstStepCandidates(result: CompletionResult): DistributionStats & {
	chosen?: { id?: number; text: string; p?: number };
	candidates: Candidate[];
} {
	const steps = parseProbEntries(result.completion_probabilities);
	const step = steps[0];
	if (!step) return { candidates: [] };
	return {
		...step,
		chosen: { id: step.id, text: step.text, p: step.prob },
		candidates: step.candidates,
	};
}

/**
 * Run a before/after probe. Returns one {@link ProbeStep} per analyzed decode
 * position, in order.
 */
export async function runProbe(
	client: ProbeClient,
	options: ProbeOptions,
): Promise<ProbeResult> {
	const startedAt = Date.now();
	const nProbs = options.nProbs ?? 20;
	const funnelNProbs = options.funnelNProbs ?? 256;
	const wantFunnel = options.funnel ?? false;
	const chain = [...options.chain];
	const notes: string[] = [];
	let requests = 0;

	let promptTokens: number[];
	if (options.promptTokens && options.promptTokens.length > 0) {
		promptTokens = [...options.promptTokens];
	} else {
		const tokenized = await client.tokenize(
			options.promptText ?? "",
			{ addSpecial: false, parseSpecial: true },
			options.signal,
		);
		requests += 1;
		promptTokens = tokenized.tokens;
	}

	const base = {
		cache_prompt: true,
		...(options.idSlot !== undefined ? { id_slot: options.idSlot } : {}),
	};

	// ---- pass 1: what the chain leaves alive, and what it picks --------------
	const forced: number[] = [];
	const postByStep: Candidate[][] = [];
	const postStats: DistributionStats[] = [];
	const chosenByStep: { id?: number; text: string; p?: number }[] = [];

	const total =
		options.steps * (1 + (wantFunnel ? chain.length : 0)) +
		(options.forcedTokens ? options.steps : 1);
	const progress = (label: string): void => {
		options.onProgress?.(requests, total, label);
	};

	if (options.forcedTokens && options.forcedTokens.length > 0) {
		// Analyze an existing generation: ask for the survivor set at each of its
		// positions without letting the chain choose the continuation.
		const limit = Math.min(options.steps, options.forcedTokens.length);
		for (let i = 0; i < limit; i += 1) {
			progress(`survivors ${i + 1}/${limit}`);
			const result = await client.completion(
				{
					...base,
					prompt: [...promptTokens, ...options.forcedTokens.slice(0, i)],
					n_predict: 1,
					n_probs: nProbs,
					post_sampling_probs: true,
					response_fields: ["completion_probabilities"],
					...chainParams(chain, options.params),
				},
				options.signal,
			);
			requests += 1;
			const stats = firstStepCandidates(result);
			const { candidates } = stats;
			postStats.push(stats);
			postByStep.push(candidates);
			const tokenId = options.forcedTokens[i];
			forced.push(tokenId);
			const survivor = candidates.find((c) => c.id === tokenId);
			chosenByStep.push({
				id: tokenId,
				text: options.forcedTexts?.[i] ?? survivor?.token ?? "",
				p: survivor?.p,
			});
		}
		notes.push(
			"Survivor sets were measured per position with a one-token request; stochastic samplers (xtc) resample each time.",
		);
	} else {
		progress("generating");
		const result = await client.completion(
			{
				...base,
				prompt: promptTokens,
				n_predict: options.steps,
				n_probs: nProbs,
				post_sampling_probs: true,
				return_tokens: true,
				response_fields: ["completion_probabilities", "tokens", "timings"],
				...chainParams(chain, options.params),
			},
			options.signal,
		);
		requests += 1;
		const steps = parseProbEntries(result.completion_probabilities);
		const tokens = Array.isArray(result.tokens) ? result.tokens : [];
		for (let i = 0; i < steps.length; i += 1) {
			postStats.push(steps[i]);
			postByStep.push(steps[i].candidates);
			const id = steps[i].id ?? tokens[i];
			chosenByStep.push({ id, text: steps[i].text, p: steps[i].prob });
			if (id !== undefined) forced.push(id);
		}
	}

	// ---- pass 2: the model's own distribution at the same positions ----------
	const rawByStep: Candidate[][] = [];
	const rawStats: DistributionStats[] = [];
	for (let i = 0; i < postByStep.length; i += 1) {
		progress(`raw logprobs ${i + 1}/${postByStep.length}`);
		const result = await client.completion(
			{
				...base,
				prompt: [...promptTokens, ...forced.slice(0, i)],
				n_predict: 1,
				n_probs: nProbs,
				post_sampling_probs: false,
				response_fields: ["completion_probabilities"],
				// The raw distribution comes from the model logits, so the chain here
				// only decides which token gets sampled — keep it cheap and greedy.
				samplers: ["top_k"],
				top_k: 1,
				temperature: 1,
			},
			options.signal,
		);
		requests += 1;
		const stats = firstStepCandidates(result);
		rawByStep.push(stats.candidates);
		rawStats.push(stats);
	}

	// ---- pass 3: survivor count after each chain prefix ----------------------
	const funnelByStep: FunnelMeasurement[][] = [];
	if (wantFunnel && chain.length > 0) {
		for (let i = 0; i < postByStep.length; i += 1) {
			const measurements: FunnelMeasurement[] = [];
			for (let stage = 1; stage <= chain.length; stage += 1) {
				progress(`funnel ${i + 1}/${postByStep.length} · ${chain[stage - 1]}`);
				const prefix = chain.slice(0, stage);
				const result = await client.completion(
					{
						...base,
						prompt: [...promptTokens, ...forced.slice(0, i)],
						n_predict: 1,
						n_probs: funnelNProbs,
						post_sampling_probs: true,
						response_fields: ["completion_probabilities"],
						...chainParams(prefix, options.params),
					},
					options.signal,
				);
				requests += 1;
				const stats = firstStepCandidates(result);
				const width = stats.candidateCount ?? stats.candidates.length;
				measurements.push({
					sampler: chain[stage - 1],
					width,
					saturated: stats.candidateCount === undefined && width >= funnelNProbs,
					historyDependent: HISTORY_DEPENDENT.has(chain[stage - 1]),
				});
			}
			funnelByStep.push(measurements);
		}
		if (chain.some((id) => HISTORY_DEPENDENT.has(id))) {
			notes.push(
				"dry/penalties stages are measured without generation history and therefore under-report.",
			);
		}
	}

	const steps: ProbeStep[] = postByStep.map((post, index) => {
		const raw = rawByStep[index] ?? [];
		const chosen = chosenByStep[index];
		const chosenCandidate =
			chosen === undefined
				? undefined
				: ({
						id: chosen.id,
						token: chosen.text,
						p: chosen.p ?? 0,
					} satisfies Candidate);
		return {
			index,
			tokenId: chosen?.id,
			text: chosen?.text ?? "",
			raw,
			post,
			funnel: funnelByStep[index] ?? [],
			comparison: compareStep(raw, post, {
				chosen: chosenCandidate, nProbs,
				candidateCount: postStats[index]?.candidateCount,
				entropyBefore: rawStats[index]?.entropyBits,
				entropyAfter: postStats[index]?.entropyBits,
				varentropyBefore: rawStats[index]?.varentropyBits2,
			}),
		};
	});

	if (steps.some((step) => step.comparison.saturated)) {
		notes.push(
			`Some steps hit the n_probs=${nProbs} ceiling; their true width is larger than reported.`,
		);
	}
	if (steps.some((step) => step.comparison.previewPartial)) {
		notes.push("Mass and KL comparisons use candidate previews only; they are not full-vocabulary measurements. Width and entropy use full server measurements when present.");
	}

	return {
		steps,
		chain,
		params: options.params,
		text: steps.map((s) => s.text).join(""),
		promptTokenCount: promptTokens.length,
		nProbs,
		funnelNProbs,
		requests,
		durationMs: Date.now() - startedAt,
		notes,
	};
}

/**
 * Cost estimate for a probe, so the UI can warn before spending decode time.
 */
export function estimateProbeRequests(options: {
	steps: number;
	chainLength: number;
	funnel: boolean;
	forced: boolean;
}): number {
	const survivors = options.forced ? options.steps : 1;
	const raw = options.steps;
	const funnel = options.funnel ? options.steps * options.chainLength : 0;
	return survivors + raw + funnel;
}

/**
 * Confirm which samplers a build honors by sending a one-token request per name
 * and reading back the server's own echo of the parsed chain. llama.cpp drops
 * unknown sampler names with only a log warning, so the echo is the only
 * reliable signal.
 */
export async function probeSamplerSupport(
	client: ProbeClient,
	ids: readonly string[],
	options: {
		promptTokens?: readonly number[];
		idSlot?: number;
		signal?: AbortSignal;
	} = {},
): Promise<Map<string, boolean>> {
	const support = new Map<string, boolean>();
	for (const id of ids) {
		try {
			const result = await client.completion(
				{
					prompt: options.promptTokens ? [...options.promptTokens] : "\n",
					n_predict: 1,
					cache_prompt: true,
					samplers: [id],
					response_fields: ["generation_settings"],
					...(options.idSlot !== undefined ? { id_slot: options.idSlot } : {}),
				},
				options.signal,
			);
			const applied = result.generation_settings?.samplers;
			support.set(id, Array.isArray(applied) && applied.includes(id));
		} catch {
			support.set(id, false);
		}
	}
	return support;
}
