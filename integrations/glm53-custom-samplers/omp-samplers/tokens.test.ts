import { describe, expect, test } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
	classifyTokenRole,
	detectSpecialTokens,
	findThinkCloseToken,
	type GgufTokenizer,
	harvestTemplateCandidates,
	looksLikeSpecialToken,
	probeSpecialTokens,
	readGgufTokenizer,
	resolveTokenReference,
	type SpecialTokenSet,
	specialTokensFromGguf,
	type TokenRole,
	TokenSetCache,
	tokenSetKey,
} from "./tokens";

// ---------------------------------------------------------------------------
// A minimal gguf writer, so the binary reader is tested against bytes rather
// than against a mock of itself.
// ---------------------------------------------------------------------------

type KvValue =
	| { type: "string"; value: string }
	| { type: "u32"; value: number }
	| { type: "f32"; value: number }
	| { type: "bool"; value: boolean }
	| { type: "string[]"; value: string[] }
	| { type: "i32[]"; value: number[] }
	| { type: "f32[]"; value: number[] };

const TYPE_ID = {
	u32: 4,
	i32: 5,
	f32: 6,
	bool: 7,
	string: 8,
	array: 9,
} as const;

function u64(value: number): Buffer {
	const buf = Buffer.alloc(8);
	buf.writeBigUInt64LE(BigInt(value));
	return buf;
}

function u32(value: number): Buffer {
	const buf = Buffer.alloc(4);
	buf.writeUInt32LE(value);
	return buf;
}

function ggufString(value: string): Buffer {
	const bytes = Buffer.from(value, "utf8");
	return Buffer.concat([u64(bytes.length), bytes]);
}

function ggufValue(value: KvValue): Buffer {
	switch (value.type) {
		case "string":
			return Buffer.concat([u32(TYPE_ID.string), ggufString(value.value)]);
		case "u32":
			return Buffer.concat([u32(TYPE_ID.u32), u32(value.value)]);
		case "f32": {
			const buf = Buffer.alloc(4);
			buf.writeFloatLE(value.value);
			return Buffer.concat([u32(TYPE_ID.f32), buf]);
		}
		case "bool":
			return Buffer.concat([
				u32(TYPE_ID.bool),
				Buffer.from([value.value ? 1 : 0]),
			]);
		case "string[]":
			return Buffer.concat([
				u32(TYPE_ID.array),
				u32(TYPE_ID.string),
				u64(value.value.length),
				...value.value.map(ggufString),
			]);
		case "i32[]": {
			const body = Buffer.alloc(4 * value.value.length);
			value.value.forEach((entry, index) => body.writeInt32LE(entry, index * 4));
			return Buffer.concat([
				u32(TYPE_ID.array),
				u32(TYPE_ID.i32),
				u64(value.value.length),
				body,
			]);
		}
		case "f32[]": {
			const body = Buffer.alloc(4 * value.value.length);
			value.value.forEach((entry, index) => body.writeFloatLE(entry, index * 4));
			return Buffer.concat([
				u32(TYPE_ID.array),
				u32(TYPE_ID.f32),
				u64(value.value.length),
				body,
			]);
		}
	}
}

function writeGguf(entries: [string, KvValue][], tensorCount = 0): string {
	const header = Buffer.concat([
		Buffer.from("GGUF", "latin1"),
		u32(3),
		u64(tensorCount),
		u64(entries.length),
	]);
	const body = entries.map(([key, value]) =>
		Buffer.concat([ggufString(key), ggufValue(value)]),
	);
	const file = path.join(
		fs.mkdtempSync(path.join(os.tmpdir(), "omp-samplers-gguf-")),
		"model.gguf",
	);
	// Trailing bytes stand in for the tensor payload the reader must never touch.
	fs.writeFileSync(file, Buffer.concat([header, ...body, Buffer.alloc(4096, 7)]));
	return file;
}

const QWEN_LIKE_ENTRIES: [string, KvValue][] = [
	["general.architecture", { type: "string", value: "qwen35" }],
	["general.sampling.top_k", { type: "u32", value: 20 }],
	["general.sampling.temp", { type: "f32", value: 1 }],
	["some.flag", { type: "bool", value: true }],
	["some.floats", { type: "f32[]", value: [1, 2, 3] }],
	[
		"tokenizer.ggml.tokens",
		{
			type: "string[]",
			value: [
				"hello",
				" world",
				"<|endoftext|>",
				"<|im_start|>",
				"<|im_end|>",
				"<think>",
				"</think>",
				"<tool_call>",
				"[PAD8]",
			],
		},
	],
	[
		"tokenizer.ggml.token_type",
		{ type: "i32[]", value: [1, 1, 3, 3, 3, 4, 4, 4, 5] },
	],
	// Sits between the tokens and the ids, exactly where the real file puts it,
	// so the reader has to skip a large string array to reach what follows.
	[
		"tokenizer.ggml.merges",
		{ type: "string[]", value: Array.from({ length: 500 }, (_, i) => `a${i} b`) },
	],
	["tokenizer.ggml.eos_token_id", { type: "u32", value: 4 }],
	["tokenizer.ggml.bos_token_id", { type: "u32", value: 2 }],
	["tokenizer.chat_template", { type: "string", value: "{{ '<|im_start|>' }}" }],
];

describe("readGgufTokenizer", () => {
	test("reads the tokenizer block past a large skipped array", () => {
		const file = writeGguf(QWEN_LIKE_ENTRIES, 866);
		const parsed = readGgufTokenizer(file);
		expect(parsed.architecture).toBe("qwen35");
		expect(parsed.tokens).toHaveLength(9);
		expect(parsed.tokens[6]).toBe("</think>");
		expect(parsed.tokenTypes).toEqual([1, 1, 3, 3, 3, 4, 4, 4, 5]);
		expect(parsed.specialIds).toEqual({ eos: 4, bos: 2 });
		expect(parsed.chatTemplate).toBe("{{ '<|im_start|>' }}");
	});

	test("rejects a file that is not a gguf", () => {
		const file = path.join(
			fs.mkdtempSync(path.join(os.tmpdir(), "omp-samplers-notgguf-")),
			"model.gguf",
		);
		fs.writeFileSync(file, Buffer.from("this is not a model"));
		expect(() => readGgufTokenizer(file)).toThrow(/not a gguf/);
	});

	test("rejects a truncated file instead of returning half a vocabulary", () => {
		const file = writeGguf(QWEN_LIKE_ENTRIES);
		const full = fs.readFileSync(file);
		fs.writeFileSync(file, full.subarray(0, 64));
		expect(() => readGgufTokenizer(file)).toThrow(/end of gguf/);
	});
});

describe("specialTokensFromGguf", () => {
	const tokenizer: GgufTokenizer = {
		tokens: [
			"hello",
			" world",
			"<|endoftext|>",
			"<|im_start|>",
			"<|im_end|>",
			"<think>",
			"</think>",
			"<tool_call>",
			"[PAD8]",
		],
		tokenTypes: [1, 1, 3, 3, 3, 4, 4, 4, 5],
		specialIds: { eos: 4, bos: 2 },
	};

	test("keeps control and user-defined tokens and drops ordinary text", () => {
		const tokens = specialTokensFromGguf(tokenizer, {
			bosToken: "<|endoftext|>",
			eosToken: "<|im_end|>",
		});
		expect(tokens.map((token) => token.id)).toEqual([2, 3, 4, 5, 6, 7]);
		expect(tokens.find((token) => token.id === 6)).toEqual({
			id: 6,
			text: "</think>",
			role: "think_close",
			kind: "user_defined",
		});
	});

	test("hides unused placeholder slots unless asked for", () => {
		expect(
			specialTokensFromGguf(tokenizer, {}, false).some(
				(token) => token.text === "[PAD8]",
			),
		).toBe(false);
		const withUnused = specialTokensFromGguf(tokenizer, {}, true);
		expect(withUnused.find((token) => token.text === "[PAD8]")?.role).toBe(
			"unused",
		);
	});

	test("keeps a token the converter typed NORMAL but named as an id", () => {
		const tokens = specialTokensFromGguf({
			tokens: ["a", "b", "weird_eos"],
			tokenTypes: [1, 1, 1],
			specialIds: { eos: 2 },
		});
		expect(tokens.map((token) => token.id)).toEqual([2]);
	});
});

describe("classifyTokenRole", () => {
	test.each([
		["</think>", "think_close"],
		["</thinking>", "think_close"],
		["</thought>", "think_close"],
		["</reasoning>", "think_close"],
		["</seed:think>", "think_close"],
		["<|end_thinking|>", "think_close"],
		["<|END_THINKING|>", "think_close"],
		["◁/think▷", "think_close"],
		["[/think]", "think_close"],
		["<think>", "think_open"],
		["<|start_thinking|>", "think_open"],
		["◁think▷", "think_open"],
		["<|im_start|>", "turn_start"],
		["<|im_end|>", "eot"],
		["<|eot_id|>", "eot"],
		["<end_of_turn>", "eot"],
		["<|endoftext|>", "eos"],
		["<tool_call>", "tool_call_start"],
		["</tool_call>", "tool_call_end"],
		["<tool_response>", "tool_response_start"],
		["<|vision_start|>", "vision"],
		["<|audio_pad|>", "audio"],
		["<|fim_prefix|>", "fim"],
		["<unk>", "unk"],
		["[PAD248260]", "unused"],
		["<|reserved_special_token_3|>", "unused"],
	])("%s is %s", (text, role) => {
		expect(classifyTokenRole(text)).toBe(role as TokenRole);
	});

	test("an opening tag is never mistaken for a closing one", () => {
		for (const text of ["<think>", "<thinking>", "<|start_thinking|>"]) {
			expect(classifyTokenRole(text)).not.toBe("think_close");
		}
	});

	test("falls back to the server's named bos and eos", () => {
		expect(
			classifyTokenRole("<|weird_end|>", { eosToken: "<|weird_end|>" }),
		).toBe("eos");
		expect(classifyTokenRole("<|weird_start|>", { bosToken: "<|weird_start|>" })).toBe(
			"bos",
		);
	});

	test("a structural match beats the server's naming", () => {
		// Qwen reports <|endoftext|> as its bos, but it is an eos by shape.
		expect(classifyTokenRole("<|endoftext|>", { bosToken: "<|endoftext|>" })).toBe(
			"eos",
		);
	});
});

describe("looksLikeSpecialToken", () => {
	test.each([
		["<|im_end|>", true],
		["</think>", true],
		["[INST]", true],
		["◁/think▷", true],
		["<｜end▁of▁sentence｜>", true],
		["hello", false],
		["<a", false],
		["<| spaced |>", false],
		["<>", false],
	])("%s -> %p", (text, expected) => {
		expect(looksLikeSpecialToken(text)).toBe(expected);
	});
});

describe("harvestTemplateCandidates", () => {
	test("pulls token literals out of a chat template", () => {
		const template =
			"{%- if x %}<|im_start|>{{ role }}\n{%- endif %}<think>\n</think><|vision_start|><|image_pad|>[gMASK]";
		const found = harvestTemplateCandidates(template);
		expect(found).toContain("<|im_start|>");
		expect(found).toContain("<think>");
		expect(found).toContain("</think>");
		expect(found).toContain("<|image_pad|>");
		expect(found).toContain("[gMASK]");
	});
});

// ---------------------------------------------------------------------------
// Probe tier
// ---------------------------------------------------------------------------

/** A tokenizer that knows a fixed set of single-token strings. */
function fakeClient(
	single: Record<string, number>,
	mergesWithoutSpecial: Set<string> = new Set(),
) {
	let calls = 0;
	return {
		get calls() {
			return calls;
		},
		async tokenize(
			content: string,
			options?: { parseSpecial?: boolean },
		): Promise<{ tokens: number[] }> {
			calls += 1;
			const id = single[content];
			if (id === undefined) return { tokens: [1, 2, 3] };
			if (options?.parseSpecial === false && !mergesWithoutSpecial.has(content)) {
				return { tokens: [4, 5, 6] };
			}
			return { tokens: [id] };
		},
	};
}

describe("probeSpecialTokens", () => {
	test("keeps single-token candidates and drops the rest", async () => {
		const client = fakeClient({ "</think>": 42, "<|im_end|>": 7 });
		const tokens = await probeSpecialTokens(client, [
			"</think>",
			"<|im_end|>",
			"<|not_a_token|>",
			"plain text",
		]);
		expect(tokens.map((token) => [token.text, token.id])).toEqual([
			["<|im_end|>", 7],
			["</think>", 42],
		]);
	});

	test("a token that merges without special parsing is kept, not filtered", async () => {
		// This is the Qwen3 case: </think> is USER_DEFINED, so parse_special makes
		// no difference and the naive "is it special?" test would reject it.
		const client = fakeClient({ "</think>": 42 }, new Set(["</think>"]));
		const tokens = await probeSpecialTokens(client, ["</think>"]);
		expect(tokens).toHaveLength(1);
		expect(tokens[0].needsParseSpecial).toBe(false);
		expect(tokens[0].role).toBe("think_close");
	});

	test("does not ask about the same candidate twice", async () => {
		const client = fakeClient({ "</think>": 42 });
		await probeSpecialTokens(client, ["</think>", "</think>", "</think>"]);
		expect(client.calls).toBe(2);
	});
});

describe("detectSpecialTokens", () => {
	test("prefers the model file and spot-checks it against the server", async () => {
		const file = writeGguf(QWEN_LIKE_ENTRIES);
		const client = fakeClient({
			"<|endoftext|>": 2,
			"<|im_start|>": 3,
			"<|im_end|>": 4,
			"<think>": 5,
			"</think>": 6,
			"<tool_call>": 7,
		});
		const set = await detectSpecialTokens({
			client,
			modelPath: file,
			modelAlias: "test",
			nVocab: 9,
		});
		expect(set.source).toBe("gguf");
		expect(set.architecture).toBe("qwen35");
		expect(findThinkCloseToken(set)?.id).toBe(6);
	});

	test("falls back to probing when the file disagrees with the server", async () => {
		const file = writeGguf(QWEN_LIKE_ENTRIES);
		// Same texts, different ids: a stale model_path pointing at another quant.
		const client = fakeClient({
			"<|endoftext|>": 100,
			"<|im_start|>": 101,
			"<|im_end|>": 102,
			"<think>": 103,
			"</think>": 104,
		});
		const set = await detectSpecialTokens({
			client,
			modelPath: file,
			modelAlias: "test",
		});
		expect(set.source).toBe("probe");
		expect(findThinkCloseToken(set)?.id).toBe(104);
	});

	test("falls back to probing when there is no readable file", async () => {
		const client = fakeClient({ "</think>": 9 });
		const set = await detectSpecialTokens({
			client,
			modelPath: "/nonexistent/model.gguf",
			chatTemplate: "<|im_start|>",
		});
		expect(set.source).toBe("probe");
		expect(set.tokens.map((token) => token.text)).toEqual(["</think>"]);
	});

	test("throws when there is nothing at all to inspect", async () => {
		await expect(detectSpecialTokens({})).rejects.toThrow(/no server to probe/);
	});
});

describe("resolveTokenReference", () => {
	const set: SpecialTokenSet = {
		source: "gguf",
		key: "test:9",
		nVocab: 9,
		tokens: [
			{ id: 6, text: "</think>", role: "think_close", kind: "user_defined" },
			{ id: 4, text: "<|im_end|>", role: "eot", kind: "control" },
		],
	};

	test("resolves exact text, case-insensitive text, ids and roles", () => {
		expect(resolveTokenReference(set, "</think>")?.id).toBe(6);
		expect(resolveTokenReference(set, "</THINK>")?.id).toBe(6);
		expect(resolveTokenReference(set, "think_close")?.id).toBe(6);
		expect(resolveTokenReference(set, "#4")?.id).toBe(4);
		expect(resolveTokenReference(set, "4")?.id).toBe(4);
	});

	test("accepts a raw id that is not in the detected set", () => {
		expect(resolveTokenReference(set, "#1234")).toEqual({ id: 1234 });
	});

	test("returns nothing for an unknown name", () => {
		expect(resolveTokenReference(set, "</reasoning>")).toBeUndefined();
		expect(resolveTokenReference(undefined, "</think>")).toBeUndefined();
	});

	test("matches a token whose own text carries whitespace", () => {
		const withWord: SpecialTokenSet = {
			...set,
			tokens: [
				...set.tokens,
				{ id: 78926, text: " delve", role: "other", kind: "normal", added: true },
			],
		};
		expect(resolveTokenReference(withWord, " delve")?.id).toBe(78926);
	});

	test("never trims a reference into a neighbouring token", () => {
		// " delve" and "delve" are different tokens, so a reference carrying
		// whitespace must not be normalized onto the one without it.
		const withWord: SpecialTokenSet = {
			...set,
			tokens: [
				...set.tokens,
				{ id: 40, text: "delve", role: "other", kind: "normal", added: true },
			],
		};
		expect(resolveTokenReference(withWord, " delve")).toBeUndefined();
		expect(resolveTokenReference(withWord, "delve")?.id).toBe(40);
		// An id is unambiguous, so the whitespace convenience still applies there.
		expect(resolveTokenReference(withWord, " #40 ")?.id).toBe(40);
	});
});

describe("TokenSetCache", () => {
	test("round-trips a detection result through disk", () => {
		const file = path.join(
			fs.mkdtempSync(path.join(os.tmpdir(), "omp-samplers-cache-")),
			"sampler-tokens.json",
		);
		const set: SpecialTokenSet = {
			source: "gguf",
			key: tokenSetKey("qwen", 248320),
			modelAlias: "qwen",
			nVocab: 248320,
			tokens: [
				{
					id: 248069,
					text: "</think>",
					role: "think_close",
					kind: "user_defined",
					needsParseSpecial: false,
				},
			],
		};
		new TokenSetCache(file).put(set);
		const reloaded = new TokenSetCache(file).get("qwen:248320");
		expect(reloaded).toEqual(set);
	});

	test("survives a corrupt cache file", () => {
		const file = path.join(
			fs.mkdtempSync(path.join(os.tmpdir(), "omp-samplers-cache-")),
			"sampler-tokens.json",
		);
		fs.writeFileSync(file, "{ not json");
		expect(new TokenSetCache(file).get("anything")).toBeUndefined();
	});
});
