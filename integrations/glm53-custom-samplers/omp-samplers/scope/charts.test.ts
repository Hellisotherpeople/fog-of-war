import { describe, expect, test } from "bun:test";
import {
	bar,
	beforeAfterLines,
	clip,
	funnelLines,
	histogramLines,
	num,
	pct,
	showToken,
	sparkline,
	table,
} from "./charts";

describe("sparkline", () => {
	test("maps the range onto the block ramp", () => {
		expect(sparkline([0, 1, 2, 3, 4, 5, 6, 7])).toBe("▁▂▃▄▅▆▇█");
	});

	test("a flat series renders flat rather than dividing by zero", () => {
		expect(sparkline([3, 3, 3])).toBe("▁▁▁");
	});

	test("an explicit scale keeps several sparklines comparable", () => {
		expect(sparkline([0, 7], { min: 0, max: 7 })).toBe("▁█");
		expect(sparkline([0, 7], { min: 0, max: 70 })).toBe("▁▂");
	});

	test("empty input produces no output", () => {
		expect(sparkline([])).toBe("");
	});
});

describe("bar", () => {
	test("clamps out-of-range fractions", () => {
		expect(bar(2, 4)).toBe("████");
		expect(bar(-1, 4)).toBe("    ");
	});

	test("always fills exactly `width` cells", () => {
		for (const fraction of [0, 0.13, 0.5, 0.77, 1]) {
			expect(bar(fraction, 10)).toHaveLength(10);
		}
	});
});

describe("formatting", () => {
	test("non-finite numbers render as a dash", () => {
		expect(num(Number.NaN)).toBe("—");
		expect(num(undefined)).toBe("—");
		expect(pct(Number.POSITIVE_INFINITY)).toBe("—");
	});

	test("token pieces stay legible and bounded", () => {
		expect(showToken(" the")).toBe("·the");
		expect(showToken("\n")).toBe("⏎");
		expect(showToken("")).toBe("∅");
		expect(showToken("abcdefghijklmnop", 8)).toHaveLength(8);
	});

	test("clip never exceeds the requested width", () => {
		expect(clip("abcdef", 4)).toBe("abc…");
		expect(clip("ab", 4)).toBe("ab");
	});
});

describe("composite charts", () => {
	test("the funnel marks how many candidates each stage removed", () => {
		const lines = funnelLines([
			{ label: "dry", width: 100 },
			{ label: "hill", width: 8 },
			{ label: "temperature", width: 8 },
		]);
		expect(lines).toHaveLength(3);
		expect(lines[1]).toContain("−92");
		expect(lines[2]).toContain("·");
	});

	test("saturated stages are marked with a plus", () => {
		expect(
			funnelLines([{ label: "top_k", width: 256, saturated: true }])[0],
		).toContain("256+");
	});

	test("the before/after table marks cut candidates and the sampled token", () => {
		const raw = [
			{ id: 1, token: " the", p: 0.5 },
			{ id: 2, token: " a", p: 0.3 },
			{ id: 3, token: " an", p: 0.2 },
		];
		const post = [
			{ id: 1, token: " the", p: 0.62 },
			{ id: 2, token: " a", p: 0.38 },
		];
		const lines = beforeAfterLines(raw, post, { chosenKey: 2 });
		expect(lines[3]).toContain("✂ cut");
		expect(lines[2]).toContain("▶");
	});

	test("survivors outside the raw top-K are disclosed, not hidden", () => {
		const lines = beforeAfterLines(
			[{ id: 1, token: "a", p: 0.9 }],
			[
				{ id: 1, token: "a", p: 0.5 },
				{ id: 9, token: "z", p: 0.5 },
			],
		);
		expect(lines.at(-1)).toContain("1 survivor(s) below the raw top-1");
	});

	test("histogram rows carry counts and shares", () => {
		const lines = histogramLines([
			{ label: "1", count: 3 },
			{ label: "2-3", count: 1 },
		]);
		expect(lines[0]).toContain("3");
		expect(lines[0]).toContain("75%");
	});

	test("tables align on the widest cell", () => {
		const lines = table(
			[
				["a", "1"],
				["bbb", "22"],
			],
			{ header: ["name", "n"] },
		);
		expect(lines).toHaveLength(3);
		expect(lines[1].startsWith("a   ")).toBe(true);
	});
});
