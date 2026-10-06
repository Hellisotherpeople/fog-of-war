import { describe, expect, test } from "bun:test";
import {
	applyLogitBias,
	applyThinkCap,
	type BiasConfig,
	biasKeyFor,
	biasOddsMultiplier,
	clearBias,
	countCloseTags,
	diffAppliedBias,
	formatBiasAmount,
	loadBiasConfig,
	parseBiasAmount,
	parseThinkCap,
	resolveBiasEntries,
	setBias,
	splitReferenceAndAmount,
	summarizeBias,
	THINK_LESS_LEVELS,
	thinkLessLevel,
	unquote,
} from "./bias";
import type { SpecialTokenSet } from "./tokens";

const set: SpecialTokenSet = {
	source: "gguf",
	key: "qwen:248320",
	modelAlias: "qwen",
	nVocab: 248320,
	tokens: [
		{ id: 248046, text: "<|im_end|>", role: "eot", kind: "control" },
		{
			id: 248069,
			text: "</think>",
			role: "think_close",
			kind: "user_defined",
		},
	],
};

describe("parseBiasAmount", () => {
	test.each([
		["3", 3],
		["-2.5", -2.5],
		["+4", 4],
		["ban", "ban"],
		["never", "ban"],
		["-inf", "ban"],
		["false", "ban"],
		["BAN", "ban"],
	])("%s -> %p", (raw, expected) => {
		expect(parseBiasAmount(raw)).toBe(expected as number | "ban");
	});

	test.each(["", "   ", "abc", "NaN", "Infinity", "3,4"])("rejects %p", (raw) => {
		expect(parseBiasAmount(raw)).toBeUndefined();
	});

	test("negative infinity is a ban, which is the one form the wire has", () => {
		// llama.cpp encodes -inf as `false`. There is no encoding for +inf, so
		// "Infinity" above is rejected while this is accepted.
		expect(parseBiasAmount("-Infinity")).toBe("ban");
	});

	test("accepts any finite value, however large", () => {
		// A bias is a raw logit offset; clamping it would hide what the model is
		// being told. Only values that cannot be serialized are refused.
		expect(parseBiasAmount("1e9")).toBe(1e9);
		expect(parseBiasAmount("-1e9")).toBe(-1e9);
		expect(parseBiasAmount("250.5")).toBe(250.5);
		expect(parseBiasAmount(String(Number.MAX_SAFE_INTEGER))).toBe(
			Number.MAX_SAFE_INTEGER,
		);
	});
});

describe("splitReferenceAndAmount", () => {
	test("splits on the last field", () => {
		expect(splitReferenceAndAmount("</think> 4")).toEqual({
			reference: "</think>",
			amount: "4",
		});
		expect(splitReferenceAndAmount("  #248069   ban ")).toEqual({
			reference: "#248069",
			amount: "ban",
		});
	});

	test("keeps whitespace inside quotes, which is part of the token", () => {
		// " delve" is one token on a BPE vocabulary; "delve" is two.
		expect(splitReferenceAndAmount('" delve" -4')).toEqual({
			reference: " delve",
			amount: "-4",
		});
		expect(splitReferenceAndAmount("' testament to' -2")).toEqual({
			reference: " testament to",
			amount: "-2",
		});
	});

	test("an unquoted multi-word reference keeps its inner spaces", () => {
		expect(splitReferenceAndAmount("testament to -2")).toEqual({
			reference: "testament to",
			amount: "-2",
		});
	});

	test("rejects input with nothing to split", () => {
		for (const raw of ["", "   ", "</think>", '" delve"']) {
			expect(splitReferenceAndAmount(raw)).toBeUndefined();
		}
	});
});

describe("unquote", () => {
	test("strips one matching pair and leaves everything else alone", () => {
		expect(unquote('" delve"')).toBe(" delve");
		expect(unquote("'</think>'")).toBe("</think>");
		expect(unquote("</think>")).toBe("</think>");
		expect(unquote('"unbalanced')).toBe('"unbalanced');
	});
});

describe("formatBiasAmount", () => {
	test.each([
		[3, "+3"],
		[-2, "-2"],
		[1.5, "+1.50"],
		[0, "0"],
		["ban" as const, "banned"],
	])("%p -> %s", (amount, expected) => {
		expect(formatBiasAmount(amount)).toBe(expected);
	});
});

describe("biasOddsMultiplier", () => {
	test("a bias is worth exp(bias/T) after a final temperature T", () => {
		expect(biasOddsMultiplier(2, 10)).toBeCloseTo(Math.exp(0.2), 6);
		expect(biasOddsMultiplier(2, 0.5)).toBeCloseTo(Math.exp(4), 6);
	});

	test("a ban is a multiplier of zero and temp 0 is undefined", () => {
		expect(biasOddsMultiplier("ban", 1)).toBe(0);
		expect(biasOddsMultiplier(2, 0)).toBeUndefined();
	});
});

describe("loadBiasConfig", () => {
	test("defaults to off and empty for junk", () => {
		for (const raw of [undefined, null, 3, "x", []]) {
			expect(loadBiasConfig(raw)).toEqual({ enabled: false, entries: {} });
		}
	});

	test("keeps valid entries and drops the rest", () => {
		const config = loadBiasConfig({
			enabled: true,
			entries: {
				"</think>": 3,
				"<|im_end|>": false,
				banned: "ban",
				nope: "lots",
				huge: 1e9,
				nan: Number.NaN,
				"": 1,
			},
		});
		expect(config).toEqual({
			enabled: true,
			entries: {
				"</think>": 3,
				"<|im_end|>": "ban",
				banned: "ban",
				// Kept: large is not the same as invalid.
				huge: 1e9,
			},
		});
	});
});

describe("setBias and clearBias", () => {
	test("clear is forgiving about case", () => {
		const config: BiasConfig = { enabled: true, entries: {} };
		setBias(config, "</think>", 3);
		expect(clearBias(config, "</THINK>")).toBe(true);
		expect(config.entries).toEqual({});
	});

	test("clear reports when there was nothing to remove", () => {
		expect(clearBias({ enabled: true, entries: {} }, "</think>")).toBe(false);
	});
});

describe("biasKeyFor", () => {
	test("prefers the token text and falls back to an id literal", () => {
		expect(biasKeyFor(set.tokens[1])).toBe("</think>");
		expect(biasKeyFor({ id: 1234 })).toBe("#1234");
	});
});

describe("resolveBiasEntries", () => {
	test("resolves stored text keys to ids", () => {
		const { resolved, unresolved } = resolveBiasEntries(
			{ enabled: true, entries: { "</think>": 4, "<|im_end|>": "ban" } },
			set,
		);
		expect(unresolved).toEqual([]);
		expect(resolved).toEqual([
			{
				key: "<|im_end|>",
				id: 248046,
				amount: "ban",
				text: "<|im_end|>",
				role: "eot",
			},
			{
				key: "</think>",
				id: 248069,
				amount: 4,
				text: "</think>",
				role: "think_close",
			},
		]);
	});

	test("reports a key this model has no token for instead of guessing", () => {
		const { resolved, unresolved } = resolveBiasEntries(
			{ enabled: true, entries: { "</reasoning>": 4 } },
			set,
		);
		expect(resolved).toEqual([]);
		expect(unresolved).toEqual(["</reasoning>"]);
	});

	test("rejects a raw id outside the vocabulary", () => {
		const { resolved, unresolved } = resolveBiasEntries(
			{ enabled: true, entries: { "#999999": 4 } },
			set,
		);
		expect(resolved).toEqual([]);
		expect(unresolved).toEqual(["#999999"]);
	});

	test("everything is unresolved before detection has run", () => {
		const { unresolved } = resolveBiasEntries(
			{ enabled: true, entries: { "</think>": 4 } },
			undefined,
		);
		expect(unresolved).toEqual(["</think>"]);
	});
});

describe("applyLogitBias", () => {
	test("writes integer id pairs, never strings", () => {
		const body: Record<string, unknown> = { samplers: ["temperature"] };
		applyLogitBias(body, [
			{ key: "</think>", id: 248069, amount: 4 },
			{ key: "<|im_end|>", id: 248046, amount: "ban" },
		]);
		expect(body.logit_bias).toEqual([
			[248046, false],
			[248069, 4],
		]);
		// llama.cpp tokenizes a string entry with parse_special off, which would
		// bias six ordinary text tokens instead of the one that was asked for.
		for (const [id] of body.logit_bias as [unknown, unknown][]) {
			expect(typeof id).toBe("number");
		}
	});

	test("removes the field entirely when nothing is biased", () => {
		const body: Record<string, unknown> = { logit_bias: [[1, 2]] };
		applyLogitBias(body, []);
		expect(body.logit_bias).toEqual([[1, 2]]);
		const empty: Record<string, unknown> = {};
		applyLogitBias(empty, []);
		expect("logit_bias" in empty).toBe(false);
	});

	test("merges with an existing logit_bias, winning per id", () => {
		const body: Record<string, unknown> = {
			logit_bias: [
				[10, 1],
				[248069, -5],
				["bogus", 1],
				[11],
			],
		};
		applyLogitBias(body, [{ key: "</think>", id: 248069, amount: 4 }]);
		expect(body.logit_bias).toEqual([
			[10, 1],
			[248069, 4],
		]);
	});

	test("the last resolved entry for an id wins", () => {
		const body: Record<string, unknown> = {};
		applyLogitBias(body, [
			{ key: "#5", id: 5, amount: 1 },
			{ key: "</think>", id: 5, amount: 9 },
		]);
		expect(body.logit_bias).toEqual([[5, 9]]);
	});
});

describe("diffAppliedBias", () => {
	const resolved = [
		{ key: "</think>", id: 248069, amount: 4 },
		{ key: "<|im_end|>", id: 248046, amount: "ban" as const },
	];

	test("accepts an echo that matches", () => {
		expect(
			diffAppliedBias(resolved, [
				{ token: 248069, bias: 4 },
				{ token: 248046, bias: -Infinity },
			]),
		).toEqual({ reported: true, missing: [], mismatched: [] });
	});

	test("reports a bias the server dropped", () => {
		const { reported, missing } = diffAppliedBias(resolved, [
			{ token: 248069, bias: 4 },
		]);
		expect(reported).toBe(true);
		expect(missing.map((entry) => entry.key)).toEqual(["<|im_end|>"]);
	});

	test("reports a bias the server changed", () => {
		const { mismatched } = diffAppliedBias(resolved, [
			{ token: 248069, bias: 1 },
			{ token: 248046, bias: -Infinity },
		]);
		expect(mismatched.map((entry) => entry.key)).toEqual(["</think>"]);
	});

	test("an absent echo is not evidence of anything", () => {
		// /slots omits logit_bias unless LLAMA_SERVER_SLOTS_DEBUG is set on the
		// server. Reading that as "no bias applied" would flag every single turn.
		for (const applied of [undefined, null, {}, 3]) {
			expect(diffAppliedBias(resolved, applied)).toEqual({
				reported: false,
				missing: [],
				mismatched: [],
			});
		}
	});
});

describe("loadBiasConfig keeps large values", () => {
	test("a stored bias is not clamped on the way back in", () => {
		expect(
			loadBiasConfig({ enabled: true, entries: { "</think>": 5000 } }).entries,
		).toEqual({ "</think>": 5000 });
	});

	test("but a non-finite stored value is dropped, since it cannot be sent", () => {
		// JSON cannot carry Infinity, so this can only arrive via a hand-edited
		// file; sending it would serialize to null and be discarded server-side.
		expect(
			loadBiasConfig({ enabled: true, entries: { a: Number.POSITIVE_INFINITY } })
				.entries,
		).toEqual({});
	});
});

describe("applyLogitBias with extreme values", () => {
	test("a huge finite bias goes out unchanged", () => {
		const body: Record<string, unknown> = {};
		applyLogitBias(body, [{ key: "</think>", id: 204, amount: 1e6 }]);
		expect(body.logit_bias).toEqual([[204, 1e6]]);
	});

	test("a non-finite bias is dropped rather than serialized to null", () => {
		const body: Record<string, unknown> = {};
		applyLogitBias(body, [
			{ key: "a", id: 1, amount: Number.POSITIVE_INFINITY },
			{ key: "b", id: 2, amount: 3 },
		]);
		expect(body.logit_bias).toEqual([[2, 3]]);
		expect(JSON.stringify(body)).not.toContain("null");
	});
});

describe("countCloseTags", () => {
	test("counts non-overlapping occurrences", () => {
		expect(countCloseTags("a</think>b", "</think>")).toBe(1);
		expect(countCloseTags("</think></think></think>", "</think>")).toBe(3);
		expect(countCloseTags("nothing here", "</think>")).toBe(0);
		expect(countCloseTags("</think>", "")).toBe(0);
	});

	test("more than one is the over-biased signature", () => {
		// What an over-biased close tag actually produces: the bias does not switch
		// off when the block ends, so the token keeps winning.
		const runaway = "Let me think.".concat("</think>".repeat(40));
		expect(countCloseTags(runaway, "</think>")).toBe(40);
	});
});

describe("parseThinkCap", () => {
	test.each([
		["1", 1],
		["64", 64],
		["512", 512],
		["128.9", 128],
	])("%s -> %p", (raw, expected) => {
		expect(parseThinkCap(raw)).toEqual({ ok: true, cap: expected as number });
	});

	test.each(["off", "none", "-1", "OFF"])("%s means no cap", (raw) => {
		expect(parseThinkCap(raw)).toEqual({ ok: true, cap: null });
	});

	test.each(["", "abc", "-5", "NaN"])("rejects %p", (raw) => {
		expect(parseThinkCap(raw).ok).toBe(false);
	});

	test("rejects 0 with the reason, since llama.cpp ignores it", () => {
		// Measured: budget 0 leaves reasoning byte-identical to no cap, while 1
		// skips the block. Accepting 0 would be a knob that silently does nothing.
		const parsed = parseThinkCap("0");
		expect(parsed.ok).toBe(false);
		if (!parsed.ok) expect(parsed.reason).toContain("Use 1");
	});
});

describe("applyThinkCap", () => {
	test("sets the field llama.cpp's OAI endpoint reads", () => {
		const body: Record<string, unknown> = {};
		applyThinkCap(body, 64);
		expect(body).toEqual({ thinking_budget_tokens: 64 });
	});

	test("1 is the smallest budget that does anything", () => {
		const body: Record<string, unknown> = {};
		applyThinkCap(body, 1);
		expect(body.thinking_budget_tokens).toBe(1);
	});

	test("never puts a no-op 0 on the wire", () => {
		const body: Record<string, unknown> = { thinking_budget_tokens: 64 };
		applyThinkCap(body, 0);
		expect("thinking_budget_tokens" in body).toBe(false);
	});

	test("no cap removes the field instead of sending -1", () => {
		const body: Record<string, unknown> = { thinking_budget_tokens: 64 };
		applyThinkCap(body, null);
		expect("thinking_budget_tokens" in body).toBe(false);
	});
});

describe("thinkLessLevel", () => {
	test("maps every level name to its amount", () => {
		for (const level of THINK_LESS_LEVELS) {
			expect(thinkLessLevel(level.name)).toBe(level.amount);
			expect(thinkLessLevel(level.name.toUpperCase())).toBe(level.amount);
		}
	});

	test("every level is a positive bias, since the point is to think less", () => {
		for (const level of THINK_LESS_LEVELS) expect(level.amount).toBeGreaterThan(0);
	});

	test("returns nothing for an unknown name", () => {
		expect(thinkLessLevel("gentle")).toBeUndefined();
	});
});

describe("summarizeBias", () => {
	test("reads off when disabled", () => {
		expect(summarizeBias({ enabled: false, entries: { "</think>": 4 } }, set)).toBe(
			"bias: off",
		);
	});

	test("names the biased tokens and counts what did not resolve", () => {
		expect(
			summarizeBias(
				{ enabled: true, entries: { "</think>": 4, "</reasoning>": 2 } },
				set,
			),
		).toBe("bias: </think> +4, 1 unresolved");
	});

	test("says so when it is on with nothing in it", () => {
		expect(summarizeBias({ enabled: true, entries: {} }, set)).toBe(
			"bias: on (empty)",
		);
	});
});
