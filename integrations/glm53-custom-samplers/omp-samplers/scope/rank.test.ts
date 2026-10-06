import { describe, expect, test } from "bun:test";
import { GenerationBuilder, parseChunk, type GenerationRecord, type TokenRecord } from "./capture";
import { aggregateByChain, renderGenerationReport, renderLiveWidget, renderRankSteps, summarizeGeneration, tokenChosenRank } from "./report";

function token(rank?: number): TokenRecord {
	return { index: 0, text: "chosen", id: 7, rawRank: rank, candidates: [], mode: "post", saturated: true, atMs: 0, dtMs: 0 };
}
function generation(tokens: TokenRecord[]): GenerationRecord {
	return { id: 1, kind: "answer", startedAt: 0, path: "/completion", chain: ["kl_opt", "temperature"], params: { kl_opt_lambda: 1, temperature: 1e6 }, nProbs: 2, mode: "post", tokens };
}

describe("selected-token ranks", () => {
	test("preserves exact ranks outside the candidate window in streaming and native responses", () => {
		const wire = { id: 7, token: "chosen", prob: 0.1, raw_rank: 603, post_rank: 4, top_probs: [{ id: 1, token: "other", prob: 0.4 }] };
		for (const body of [{ completion_probabilities: [wire] }, { choices: [{ logprobs: { content: [wire] } }] }]) {
			const builder = new GenerationBuilder(generation([]));
			builder.accept(parseChunk(JSON.stringify(body))!, 10);
			expect(tokenChosenRank(builder.record.tokens[0], "raw")).toBe(603);
			expect(tokenChosenRank(builder.record.tokens[0], "post")).toBe(4);
		}
	});
	test("4th and 6th average to 5, with missing values excluded and coverage disclosed", () => {
		const record = generation([token(4), token(6), token()]);
		const stats = summarizeGeneration(record);
		expect(stats.rawRank.stats?.mean).toBe(5);
		expect(stats.rawRank.known).toBe(2);
		expect(stats.rawRank.total).toBe(3);
		expect(renderGenerationReport(record).join("\n")).toContain("mean 5.00");
		expect(renderRankSteps(record).join("\n")).toContain("2/3 measured (partial mean)");
		expect(renderLiveWidget({ chainLabel: "KL*", mode: "post", record }).join("\n")).toContain("mean 5.00");
	});
	test("fallback ranks count higher probabilities, with shared ranks for ties", () => {
		const t = token();
		t.candidates = [{ id: 7, token: "chosen", p: 0.2 }, { id: 8, token: "tie", p: 0.2 }, { id: 9, token: "top", p: 0.6 }];
		expect(tokenChosenRank(t, "post")).toBe(2);
		expect(tokenChosenRank(t, "raw")).toBeUndefined();
		t.mode = "raw";
		expect(tokenChosenRank(t, "raw")).toBe(2);
		expect(tokenChosenRank(t, "post")).toBeUndefined();
	});
	test("IDs distinguish tokens that decode to the same text", () => {
		const t = token();
		t.candidates = [{ id: 8, token: "chosen", p: 0.9 }, { id: 7, token: "chosen", p: 0.1 }];
		expect(tokenChosenRank(t)).toBe(2);
	});
	test("invalid server ranks are not counted", () => {
		for (const rank of [null, -1, 0, 1.5, "3"]) {
			const chunk = parseChunk(JSON.stringify({ completion_probabilities: [{ token: "chosen", prob: 1, raw_rank: rank, top_probs: [] }] }))!;
			expect(chunk.steps[0].rawRank).toBeUndefined();
		}
	});
	test("session means weight tokens, and separate knob settings and routing", () => {
		const a = generation([token(1)]);
		const b = generation([token(7), token(7), token(7)]);
		const c = { ...a, params: { ...a.params, kl_opt_lambda: 1.5 } };
		const route = { ...a, kind: "route" as const };
		const aggregates = aggregateByChain([a, b, c, route]);
		expect(aggregates).toHaveLength(3);
		expect(aggregates[0].rawRank.stats?.mean).toBe(5.5);
	});
});
