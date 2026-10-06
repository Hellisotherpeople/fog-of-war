import { describe, expect, test } from "bun:test";
import {
	bucketize,
	type Candidate,
	compareStep,
	entropyBits,
	perplexity,
	quantileSorted,
	summarize,
	tailMass,
	varentropyBits,
} from "./metrics";

const c = (token: string, p: number, id?: number): Candidate => ({
	token,
	p,
	id,
});

describe("entropy", () => {
	test("a uniform distribution over 4 tokens is 2 bits", () => {
		expect(entropyBits([0.25, 0.25, 0.25, 0.25])).toBeCloseTo(2, 10);
	});

	test("a deterministic distribution is 0 bits", () => {
		expect(entropyBits([1])).toBeCloseTo(0, 10);
	});

	test("zero probabilities are skipped rather than producing NaN", () => {
		expect(entropyBits([0.5, 0.5, 0])).toBeCloseTo(1, 10);
	});

	test("perplexity inverts entropy into an effective choice count", () => {
		expect(perplexity(entropyBits([0.25, 0.25, 0.25, 0.25]))).toBeCloseTo(4, 8);
	});

	test("varentropy is zero when every listed token is equally surprising", () => {
		expect(varentropyBits([0.25, 0.25, 0.25, 0.25])).toBeCloseTo(0, 10);
	});

	test("varentropy grows when a confident head sits above a flat tail", () => {
		expect(varentropyBits([0.9, 0.02, 0.02, 0.02, 0.02, 0.02])).toBeGreaterThan(
			0.5,
		);
	});

	test("tail mass reports what a truncated top-K does not cover", () => {
		expect(tailMass([0.5, 0.2])).toBeCloseTo(0.3, 10);
		expect(tailMass([0.6, 0.5])).toBe(0);
	});
});

describe("compareStep", () => {
	const raw = [
		c("the", 0.5, 1),
		c("a", 0.25, 2),
		c("an", 0.15, 3),
		c("some", 0.1, 4),
	];

	test("width is the survivor count and kept mass sums their raw probability", () => {
		const post = [c("the", 0.667, 1), c("a", 0.333, 2)];
		const result = compareStep(raw, post, { nProbs: 20 });
		expect(result.width).toBe(2);
		expect(result.keptMass).toBeCloseTo(0.75, 6);
		expect(result.droppedMass).toBeCloseTo(0.25, 6);
		expect(result.topDropped).toBe(false);
	});

	test("dropping the raw argmax is flagged — the xtc signature", () => {
		const post = [c("a", 0.6, 2), c("an", 0.4, 3)];
		expect(compareStep(raw, post).topDropped).toBe(true);
	});

	test("truncation lowers entropy and KL measures the reshaping", () => {
		const post = [c("the", 0.667, 1), c("a", 0.333, 2)];
		const result = compareStep(raw, post);
		expect(result.entropyAfter).toBeLessThan(result.entropyBefore);
		expect(result.klBits).toBeGreaterThan(0);
	});

	test("an identity chain reshapes nothing", () => {
		const result = compareStep(raw, raw);
		expect(result.klBits).toBeCloseTo(0, 6);
		expect(result.keptMass).toBeCloseTo(1, 6);
	});

	test("saturation is only reported when the survivor list hits n_probs", () => {
		const post = [c("the", 0.5, 1), c("a", 0.5, 2)];
		expect(compareStep(raw, post, { nProbs: 2 }).saturated).toBe(true);
		expect(compareStep(raw, post, { nProbs: 20 }).saturated).toBe(false);
	});

	test("survivors missing from the raw top-K are counted, not silently dropped", () => {
		const post = [c("the", 0.5, 1), c("rare", 0.5, 99)];
		const result = compareStep(raw, post);
		expect(result.unmatchedSurvivors).toBe(1);
		expect(result.keptMass).toBeCloseTo(0.5, 6);
	});

	test("the sampled token's raw rank is reported", () => {
		const post = [c("the", 0.6, 1), c("a", 0.4, 2)];
		const result = compareStep(raw, post, { chosen: c("a", 0.4, 2) });
		expect(result.chosenRawRank).toBe(2);
		expect(result.chosenRawProb).toBeCloseTo(0.25, 6);
	});
});

describe("summaries", () => {
	test("quantiles use nearest rank on a sorted array", () => {
		const sorted = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
		expect(quantileSorted(sorted, 0.5)).toBe(5);
		expect(quantileSorted(sorted, 0.9)).toBe(9);
		expect(quantileSorted(sorted, 1)).toBe(10);
		expect(quantileSorted(sorted, 0)).toBe(1);
	});

	test("summarize reports the whole spread", () => {
		const summary = summarize([1, 1, 2, 3, 5, 8, 13]);
		expect(summary).toBeDefined();
		expect(summary?.n).toBe(7);
		expect(summary?.min).toBe(1);
		expect(summary?.max).toBe(13);
		expect(summary?.median).toBe(3);
	});

	test("summarize returns undefined rather than NaN for no data", () => {
		expect(summarize([])).toBeUndefined();
	});

	test("width bucketing is log-spaced and totals the input", () => {
		const buckets = bucketize([1, 1, 2, 4, 9, 40, 5000]);
		expect(buckets.reduce((acc, b) => acc + b.count, 0)).toBe(7);
		expect(buckets[0].label).toBe("1");
		expect(buckets[0].count).toBe(2);
		expect(buckets[buckets.length - 1].label).toBe("1024+");
		expect(buckets[buckets.length - 1].count).toBe(1);
	});
});
