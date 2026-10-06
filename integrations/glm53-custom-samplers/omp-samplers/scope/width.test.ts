import { describe, expect, test } from "bun:test";
import { GenerationBuilder, type GenerationRecord, parseChunk, type TokenRecord } from "./capture";
import { aggregateByChain, renderGenerationReport, renderLiveWidget, renderStatus, renderTokenDetail, summarizeGeneration, tokenEntropy, tokenWidth } from "./report";
import { runProbe } from "./probe";

function record(): GenerationRecord {
	return { id: 1, kind: "answer", startedAt: 0, path: "/completion", chain: ["p_less", "kl_budget"], params: {}, nProbs: 20, mode: "post", tokens: [] };
}

function token(width: number, mode: "raw" | "post" = "post"): TokenRecord {
	const wire = {
		id: 1, token: "x", candidate_count: width, vocab_size: 256000,
		entropy_bits: Math.log2(width), varentropy_bits2: 0,
		[mode === "post" ? "prob" : "logprob"]: mode === "post" ? 1 / width : -Math.log(width),
		[mode === "post" ? "top_probs" : "top_logprobs"]: Array.from({ length: Math.min(width, 20) }, (_, id) => ({
			id, token: String(id), [mode === "post" ? "prob" : "logprob"]: mode === "post" ? 1 / width : -Math.log(width),
		})),
	};
	const builder = new GenerationBuilder(record());
	builder.accept(parseChunk(JSON.stringify({ completion_probabilities: [wire] }))!, 10);
	return builder.record.tokens[0];
}

describe("full-distribution telemetry", () => {
	test.each([1, 20, 64, 40000, 256000])("width %s is independent of the 20-token preview", (width) => {
		const t = token(width);
		expect(tokenWidth(t)).toBe(width);
		expect(t.candidates.length).toBe(Math.min(width, 20));
		expect(t.saturated).toBe(width > 20);
		expect(tokenEntropy(t)).toBe(Math.log2(width));
		expect(t.varentropyBits2).toBe(0);
		expect(t.vocabSize).toBe(256000);
	});

	test("raw capture also carries the full post-chain width", () => {
		expect(tokenWidth(token(40000, "raw"))).toBe(40000);
	});

	test("reports and aggregates use measured widths and full entropy", () => {
		const r = record();
		r.tokens = [token(1), token(40000), token(256000)];
		const stats = summarizeGeneration(r);
		expect(stats.width?.mean).toBe(296001 / 3);
		expect(stats.width?.median).toBe(40000);
		expect(stats.width?.max).toBe(256000);
		expect(stats.widthKnown).toBe(3);
		expect(stats.entropyKnown).toBe(3);
		expect(stats.forcedRate).toBe(1 / 3);
		expect(aggregateByChain([r])[0].medianWidth).toBe(40000);
		const widget = renderLiveWidget({ record: r, chainLabel: "x", mode: "post" }).join("\n");
		expect(widget).toContain("now 256000");
		expect(widget).toContain("med 40000");
		expect(renderGenerationReport(r).join("\n")).toContain("3/3 widths measured");
		expect(renderTokenDetail(r, 1).join("\n")).toContain("Width: 40000 / 256000");
	});

	test("old capped previews cannot masquerade as exact width or entropy", () => {
		const old = token(40000);
		delete old.candidateCount;
		delete old.entropyBits;
		const r = record();
		r.tokens = [old];
		expect(tokenWidth(old)).toBeUndefined();
		expect(tokenEntropy(old)).toBeUndefined();
		expect(summarizeGeneration(r).width).toBeUndefined();
		expect(renderStatus({ record: r, chainLabel: "x", mode: "post" })).toContain("20+ (preview only)");
		r.tokens.push(token(40000));
		expect(summarizeGeneration(r).width?.mean).toBe(40000);
		expect(summarizeGeneration(r).widthKnown).toBe(1);
		expect(renderLiveWidget({ record: r, chainLabel: "x", mode: "post" }).join("\n")).toContain("1/2 measured (partial)");
	});

	test.each([false, true])("probes and each funnel stage use full counts (teacher-forced=%s)", async (forced) => {
		const probe = await runProbe({
			tokenize: async () => ({ tokens: [1] }),
			completion: async (body) => ({ tokens: [1], completion_probabilities: [{
				id: 1, token: "x", candidate_count: body.post_sampling_probs ? 40000 : 1,
				entropy_bits: body.post_sampling_probs ? 12 : 15, varentropy_bits2: 3,
				...(body.post_sampling_probs ? { prob: 0.001, top_probs: [{ id: 1, token: "x", prob: 0.001 }] }
					: { logprob: -8, top_logprobs: [{ id: 1, token: "x", logprob: -8 }] }),
			}] }),
		}, { promptTokens: [1], chain: ["p_less", "kl_budget"], params: {}, steps: 1, nProbs: 1, funnelNProbs: 1, funnel: true, forcedTokens: forced ? [1] : undefined });
		expect(probe.steps[0].comparison.width).toBe(40000);
		expect(probe.steps[0].comparison.saturated).toBe(false);
		expect(probe.steps[0].comparison.entropyBefore).toBe(15);
		expect(probe.steps[0].comparison.entropyAfter).toBe(12);
		expect(probe.steps[0].funnel.map((f) => f.width)).toEqual([40000, 40000]);
		expect(probe.steps[0].funnel.every((f) => !f.saturated)).toBe(true);
	});
});
