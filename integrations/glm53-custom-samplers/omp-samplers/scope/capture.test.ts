import { describe, expect, test } from "bun:test";
import {
	GenerationBuilder,
	type GenerationRecord,
	GenerationStore,
	type ParsedChunk,
	parseChunk,
	parseProbEntries,
	SseSplitter,
} from "./capture";

function chatChunk(
	token: string,
	post: boolean,
	candidates: [string, number][],
	extra: Record<string, unknown> = {},
): string {
	const key = post ? "prob" : "logprob";
	const topKey = post ? "top_probs" : "top_logprobs";
	const encode = (p: number): number => (post ? p : Math.log(p));
	return JSON.stringify({
		choices: [
			{
				index: 0,
				delta: { content: token },
				logprobs: {
					content: [
						{
							id: 1,
							token,
							[key]: encode(candidates[0][1]),
							[topKey]: candidates.map(([t, p], index) => ({
								id: index + 1,
								token: t,
								[key]: encode(p),
							})),
						},
					],
				},
			},
		],
		...extra,
	});
}

describe("SseSplitter", () => {
	test("reassembles payloads across arbitrary chunk boundaries", () => {
		const splitter = new SseSplitter();
		expect(splitter.feed('data: {"a"')).toEqual([]);
		expect(splitter.feed(':1}\n\ndata: {"b":2}\n\n')).toEqual([
			'{"a":1}',
			'{"b":2}',
		]);
	});

	test("handles CRLF framing", () => {
		const splitter = new SseSplitter();
		expect(splitter.feed("data: one\r\n\r\ndata: two\r\n\r\n")).toEqual([
			"one",
			"two",
		]);
	});

	test("ignores comment and event lines", () => {
		const splitter = new SseSplitter();
		expect(splitter.feed(": keepalive\n\nevent: ping\ndata: x\n\n")).toEqual([
			"x",
		]);
	});

	test("flush surfaces a frame that never got its blank line", () => {
		const splitter = new SseSplitter();
		expect(splitter.feed("data: partial")).toEqual([]);
		expect(splitter.flush()).toEqual(["partial"]);
	});
});

describe("parseChunk", () => {
	test("reads post-sampling survivors from a chat chunk", () => {
		const parsed = parseChunk(
			chatChunk(" the", true, [
				[" the", 0.6],
				[" a", 0.4],
			]),
		);
		expect(parsed?.steps).toHaveLength(1);
		expect(parsed?.steps[0].mode).toBe("post");
		expect(parsed?.steps[0].candidates).toHaveLength(2);
		expect(parsed?.steps[0].candidates[0].p).toBeCloseTo(0.6, 6);
		expect(parsed?.text).toBe(" the");
	});

	test("converts raw logprobs back into probabilities", () => {
		const parsed = parseChunk(
			chatChunk(" the", false, [
				[" the", 0.5],
				[" a", 0.25],
			]),
		);
		expect(parsed?.steps[0].mode).toBe("raw");
		expect(parsed?.steps[0].candidates[1].p).toBeCloseTo(0.25, 6);
	});

	test("reads the native /completion shape", () => {
		const parsed = parseChunk(
			JSON.stringify({
				content: "x",
				completion_probabilities: [
					{
						id: 7,
						token: "x",
						prob: 1,
						top_probs: [{ id: 7, token: "x", prob: 1 }],
					},
				],
				timings: { predicted_per_second: 42.5, cache_n: 100, prompt_n: 120 },
			}),
		);
		expect(parsed?.steps[0].candidates).toHaveLength(1);
		expect(parsed?.timings?.predictedPerSecond).toBeCloseTo(42.5, 6);
		expect(parsed?.timings?.cacheN).toBe(100);
	});

	test("recognizes the stream terminator and ignores junk", () => {
		expect(parseChunk("[DONE]")?.done).toBe(true);
		expect(parseChunk("not json")).toBeUndefined();
		expect(parseChunk("   ")).toBeUndefined();
	});

	test("distinguishes an explicit empty sampler echo from missing or malformed settings", () => {
		const parseSettings = (generation_settings: unknown) =>
			parseChunk(JSON.stringify({ generation_settings }))?.appliedChain;
		expect(parseSettings({ samplers: [] })).toEqual([]);
		expect(parseSettings({ samplers: ["min_p", "kl_budget"] })).toEqual(["min_p", "kl_budget"]);
		for (const settings of [undefined, null, {}, { samplers: "min_p" }, { samplers: ["min_p", null] }]) {
			expect(parseSettings(settings)).toBeUndefined();
		}
	});

	test("a chunk with no logprobs yields no steps", () => {
		const parsed = parseChunk(
			JSON.stringify({
				choices: [{ delta: { content: "hi" }, logprobs: null }],
			}),
		);
		expect(parsed?.steps).toEqual([]);
		expect(parsed?.text).toBe("hi");
	});
});

describe("parseProbEntries", () => {
	test("drops malformed candidates instead of throwing", () => {
		const steps = parseProbEntries([
			{
				id: 1,
				token: "a",
				prob: 0.5,
				top_probs: [{ token: "a", prob: 0.5 }, { token: "b" }, 7],
			},
		]);
		expect(steps[0].candidates).toHaveLength(1);
	});

	test("non-array input is tolerated", () => {
		expect(parseProbEntries(undefined)).toEqual([]);
		expect(parseProbEntries("nope")).toEqual([]);
	});
});

function emptyRecord(nProbs: number): GenerationRecord {
	return {
		id: 1,
		kind: "answer",
		startedAt: 1000,
		path: "/v1/chat/completions",
		chain: ["hill", "temperature"],
		params: { temperature: 10 },
		nProbs,
		mode: "post",
		tokens: [],
	};
}

/** parseChunk returns undefined only for unparseable input, which tests never feed it. */
function chunk(payload: string): ParsedChunk {
	const parsed = parseChunk(payload);
	if (!parsed) throw new Error(`test fixture did not parse: ${payload}`);
	return parsed;
}

describe("GenerationBuilder", () => {
	test("stamps arrival times and marks saturation at the n_probs ceiling", () => {
		const builder = new GenerationBuilder(emptyRecord(2));
		builder.accept(
			chunk(
				chatChunk("a", true, [
					["a", 0.6],
					["b", 0.4],
				]),
			),
			1200,
		);
		builder.accept(chunk(chatChunk("b", true, [["b", 1]])), 1250);
		const record = builder.finish(1300);

		expect(record.tokens).toHaveLength(2);
		expect(record.ttftMs).toBe(200);
		expect(record.tokens[0].saturated).toBe(true);
		expect(record.tokens[1].saturated).toBe(false);
		expect(record.tokens[1].dtMs).toBe(50);
		expect(record.tokens[1].atMs).toBe(250);
		expect(builder.text).toBe("ab");
	});

	test("timings and usage from later chunks are merged in", () => {
		const builder = new GenerationBuilder(emptyRecord(20));
		builder.accept(
			chunk(chatChunk("a", true, [["a", 1]], { timings: { predicted_n: 1 } })),
			1100,
		);
		builder.accept(
			chunk(
				JSON.stringify({ usage: { prompt_tokens: 12, completion_tokens: 1 } }),
			),
			1150,
		);
		const record = builder.finish(1200);
		expect(record.timings?.predictedN).toBe(1);
		expect(record.usage?.prompt).toBe(12);
	});
});

describe("GenerationStore", () => {
	test("keeps a bounded history and only reports generations with tokens", () => {
		const store = new GenerationStore(2);
		const withTokens = (id: number): GenerationRecord => ({
			...emptyRecord(20),
			id,
			tokens: [
				{
					index: 0,
					text: "x",
					candidates: [],
					mode: "post",
					saturated: false,
					atMs: 0,
					dtMs: 0,
				},
			],
		});
		store.push(emptyRecord(20));
		store.push(withTokens(2));
		store.push(withTokens(3));
		expect(store.all()).toHaveLength(2);
		expect(store.latest()?.id).toBe(3);
	});

	test("replay bodies are pruned from all but the newest records", () => {
		const store = new GenerationStore(8);
		for (let i = 0; i < 4; i += 1) {
			store.push({
				...emptyRecord(20),
				id: i,
				replay: { messages: [{ role: "user" }] },
			});
		}
		const kept = store.all().filter((record) => record.replay !== undefined);
		expect(kept).toHaveLength(2);
		expect(kept.map((record) => record.id)).toEqual([2, 3]);
	});
});
