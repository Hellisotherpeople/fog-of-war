/**
 * Pure statistics for sampler telemetry.
 *
 * Everything here operates on plain candidate lists so it can be unit tested
 * without a server, a session, or a terminal. Two candidate flavors show up:
 *
 * - **raw**: llama.cpp's `post_sampling_probs: false` output — a softmax over
 *   the model's unmodified logits, truncated to the top `n_probs`. The listed
 *   probabilities do not sum to 1; the remainder is tail mass.
 * - **post**: `post_sampling_probs: true` — the candidate array left over after
 *   the whole sampler chain ran, renormalized by the final dist sampler. Its
 *   length is the number of tokens the truncators actually allowed at that
 *   step, capped by the requested `n_probs`.
 */

export interface Candidate {
	/** Vocabulary id. Absent only for providers that omit it. */
	id?: number;
	/** Detokenized piece, exactly as the server sent it. */
	token: string;
	/** Probability in [0,1]. Raw candidates are un-normalized; post are normalized. */
	p: number;
}

const LOG2 = Math.log(2);

/** Shannon entropy in bits. Ignores non-positive probabilities. */
export function entropyBits(ps: readonly number[]): number {
	let h = 0;
	for (const p of ps) {
		if (p > 0) h -= p * (Math.log(p) / LOG2);
	}
	return h;
}

/**
 * Variance of the surprise -log2(p) under p. High varentropy means the step
 * mixes a confident head with a long uncertain tail — the situation adaptive
 * gates (hill, top_h, geo_mean) are supposed to handle differently from a
 * flat-but-narrow step with the same entropy.
 */
export function varentropyBits(ps: readonly number[]): number {
	const mass = sum(ps);
	if (mass <= 0) return 0;
	let mean = 0;
	for (const p of ps) {
		if (p > 0) mean += (p / mass) * (-Math.log(p) / LOG2);
	}
	let variance = 0;
	for (const p of ps) {
		if (p > 0) {
			const surprise = -Math.log(p) / LOG2;
			variance += (p / mass) * (surprise - mean) ** 2;
		}
	}
	return variance;
}

/** 2^H — the "effective number of choices" implied by an entropy in bits. */
export function perplexity(entropy: number): number {
	return 2 ** entropy;
}

/** Probability mass the listed candidates do not account for. */
export function tailMass(ps: readonly number[]): number {
	return Math.max(0, 1 - sum(ps));
}

export function sum(values: readonly number[]): number {
	let total = 0;
	for (const v of values) total += v;
	return total;
}

export function probs(candidates: readonly Candidate[]): number[] {
	return candidates.map((c) => c.p);
}

/** Index a candidate list by vocabulary id (falling back to token text). */
export function byKey(
	candidates: readonly Candidate[],
): Map<string | number, Candidate> {
	const map = new Map<string | number, Candidate>();
	for (const c of candidates) map.set(c.id ?? c.token, c);
	return map;
}

export function candidateKey(candidate: Candidate): string | number {
	return candidate.id ?? candidate.token;
}

/** Competition rank: 1 + the number of strictly more likely tokens. Ties share a rank. */
export function selectedRank(
	candidates: readonly Candidate[],
	chosen: { id?: number; token: string },
): number | undefined {
	const candidate = candidates.find((c) =>
		chosen.id !== undefined && c.id !== undefined
			? c.id === chosen.id
			: chosen.token !== "" && c.token === chosen.token,
	);
	if (!candidate) return undefined;
	return 1 + candidates.filter((c) => c.p > candidate.p).length;
}

// ---------------------------------------------------------------------------
// Per-step comparison: what the sampler chain did to one distribution
// ---------------------------------------------------------------------------

export interface StepComparison {
	/** Candidates the chain left alive (post-chain array length). */
	width: number;
	/** True when `width` hit the requested n_probs and the real width is larger. */
	saturated: boolean;
	/** Cross-distribution mass/KL values describe previews, not the full distributions. */
	previewPartial: boolean;
	entropyBeforeExact: boolean;
	entropyAfterExact: boolean;
	/** Sum of raw probability over the surviving candidates. */
	keptMass: number;
	/** Raw mass the truncators threw away, as far as the raw top-K can see. */
	droppedMass: number;
	/** Survivors that were not present in the raw top-K, so keptMass is a lower bound. */
	unmatchedSurvivors: number;
	/** Entropy of the raw distribution over its listed candidates. */
	entropyBefore: number;
	/** Entropy of the post-chain distribution. */
	entropyAfter: number;
	/** Raw varentropy — pairs with entropy to characterize the step's shape. */
	varentropyBefore: number;
	/** KL(post ‖ raw) in bits over matched survivors: how hard the chain reshaped it. */
	klBits: number;
	/** True when the raw argmax did not survive — the XTC / top-gap signature. */
	topDropped: boolean;
	/** Rank of the sampled token in the raw distribution (1-based), if visible. */
	chosenRawRank?: number;
	chosenRawProb?: number;
	chosenPostProb?: number;
}

/**
 * Compare the model's raw distribution against what the sampler chain left,
 * for a single decode step. `raw` and `post` must describe the same position.
 */
export function compareStep(
	raw: readonly Candidate[],
	post: readonly Candidate[],
	options: {
		chosen?: Candidate; nProbs?: number; candidateCount?: number;
		entropyBefore?: number; entropyAfter?: number; varentropyBefore?: number;
	} = {},
): StepComparison {
	const rawIndex = byKey(raw);
	const rawProbs = probs(raw);
	const postProbs = probs(post);
	const postMass = sum(postProbs) || 1;

	let keptMass = 0;
	let unmatchedSurvivors = 0;
	let klBits = 0;
	for (const survivor of post) {
		const source = rawIndex.get(candidateKey(survivor));
		if (!source) {
			unmatchedSurvivors += 1;
			continue;
		}
		keptMass += source.p;
		const q = survivor.p / postMass;
		if (q > 0 && source.p > 0) klBits += q * (Math.log(q / source.p) / LOG2);
	}

	const chosen = options.chosen;
	const chosenRawIndex = chosen
		? raw.findIndex((c) => candidateKey(c) === candidateKey(chosen))
		: -1;
	const survivors = new Set(post.map(candidateKey));

	return {
		width: options.candidateCount ?? post.length,
		saturated:
			options.candidateCount === undefined &&
			options.nProbs !== undefined &&
			post.length >= options.nProbs &&
			post.length > 0,
		previewPartial: Math.abs(sum(rawProbs) - 1) > 1e-5 || Math.abs(sum(postProbs) - 1) > 1e-5,
		entropyBeforeExact: options.entropyBefore !== undefined || Math.abs(sum(rawProbs) - 1) < 1e-5,
		entropyAfterExact: options.entropyAfter !== undefined || Math.abs(sum(postProbs) - 1) < 1e-5,
		keptMass,
		droppedMass: Math.max(0, sum(rawProbs) - keptMass),
		unmatchedSurvivors,
		entropyBefore: options.entropyBefore ?? entropyBits(rawProbs),
		entropyAfter: options.entropyAfter ?? entropyBits(postProbs.map((p) => p / postMass)),
		varentropyBefore: options.varentropyBefore ?? varentropyBits(rawProbs),
		klBits,
		topDropped: raw.length > 0 && !survivors.has(candidateKey(raw[0])),
		chosenRawRank: chosen ? selectedRank(raw, chosen) : undefined,
		chosenRawProb: chosenRawIndex >= 0 ? raw[chosenRawIndex].p : undefined,
		chosenPostProb: chosen?.p,
	};
}

// ---------------------------------------------------------------------------
// Distribution summaries
// ---------------------------------------------------------------------------

export interface Summary {
	n: number;
	min: number;
	p10: number;
	p25: number;
	median: number;
	p75: number;
	p90: number;
	max: number;
	mean: number;
}

/** Nearest-rank quantile over an already-sorted ascending array. */
export function quantileSorted(sorted: readonly number[], q: number): number {
	if (sorted.length === 0) return Number.NaN;
	const rank = Math.min(
		sorted.length - 1,
		Math.max(0, Math.ceil(q * sorted.length) - 1),
	);
	return sorted[rank];
}

export function summarize(values: readonly number[]): Summary | undefined {
	if (values.length === 0) return undefined;
	const sorted = [...values].sort((a, b) => a - b);
	return {
		n: sorted.length,
		min: sorted[0],
		p10: quantileSorted(sorted, 0.1),
		p25: quantileSorted(sorted, 0.25),
		median: quantileSorted(sorted, 0.5),
		p75: quantileSorted(sorted, 0.75),
		p90: quantileSorted(sorted, 0.9),
		max: sorted[sorted.length - 1],
		mean: sum(sorted) / sorted.length,
	};
}

export function mean(values: readonly number[]): number {
	return values.length === 0 ? Number.NaN : sum(values) / values.length;
}

export function fraction(values: readonly boolean[]): number {
	if (values.length === 0) return Number.NaN;
	let hits = 0;
	for (const v of values) if (v) hits += 1;
	return hits / values.length;
}

/**
 * Log-spaced bucket edges for truncation widths. Width distributions span
 * "always 1 token" to "thousands", so linear bins are useless.
 */
export const WIDTH_BUCKETS: readonly number[] = [
	1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 256, 512, 1024,
];

export interface Bucket {
	label: string;
	from: number;
	to: number;
	count: number;
}

/**
 * Bucket values into half-open ranges [edge, nextEdge). The final bucket is
 * closed on the right at Infinity.
 */
export function bucketize(
	values: readonly number[],
	edges: readonly number[] = WIDTH_BUCKETS,
): Bucket[] {
	const buckets: Bucket[] = edges.map((from, index) => {
		const to =
			index + 1 < edges.length ? edges[index + 1] : Number.POSITIVE_INFINITY;
		return {
			label:
				to === Number.POSITIVE_INFINITY
					? `${from}+`
					: to - from === 1
						? String(from)
						: `${from}-${to - 1}`,
			from,
			to,
			count: 0,
		};
	});
	for (const value of values) {
		for (let i = buckets.length - 1; i >= 0; i -= 1) {
			if (value >= buckets[i].from) {
				buckets[i].count += 1;
				break;
			}
		}
	}
	return buckets;
}
