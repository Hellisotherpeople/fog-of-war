import { describe, expect, test } from "bun:test";
import type { CompletionResult } from "./llama";
import {
	estimateProbeRequests,
	type ProbeClient,
	probeSamplerSupport,
	runProbe,
} from "./probe";

/** Records every request body so the probe's wire behavior can be asserted. */
class FakeClient implements ProbeClient {
	readonly bodies: Record<string, unknown>[] = [];

	constructor(
		private readonly respond: (
			body: Record<string, unknown>,
			index: number,
		) => CompletionResult,
	) {}

	async completion(body: Record<string, unknown>): Promise<CompletionResult> {
		this.bodies.push(body);
		return this.respond(body, this.bodies.length - 1);
	}

	async tokenize(content: string): Promise<{ tokens: number[] }> {
		return { tokens: content.split("").map((_, index) => index + 900) };
	}
}

function probsEntry(
	token: string,
	id: number,
	post: boolean,
	candidates: [string, number, number][],
): unknown {
	const key = post ? "prob" : "logprob";
	const topKey = post ? "top_probs" : "top_logprobs";
	const encode = (p: number): number => (post ? p : Math.log(p));
	return {
		id,
		token,
		[key]: encode(candidates[0][1]),
		[topKey]: candidates.map(([t, p, cid]) => ({
			id: cid,
			token: t,
			[key]: encode(p),
		})),
	};
}

describe("runProbe", () => {
	test("generates, then re-measures each position with raw probabilities", async () => {
		const client = new FakeClient((body) => {
			if (body.post_sampling_probs === true) {
				// Pass 1: two generated tokens, each with two survivors.
				return {
					tokens: [11, 22],
					completion_probabilities: [
						probsEntry("A", 11, true, [
							["A", 0.7, 11],
							["B", 0.3, 22],
						]),
						probsEntry("B", 22, true, [
							["B", 0.8, 22],
							["C", 0.2, 33],
						]),
					],
				};
			}
			return {
				completion_probabilities: [
					probsEntry("A", 11, false, [
						["A", 0.5, 11],
						["B", 0.25, 22],
						["C", 0.15, 33],
					]),
				],
			};
		});

		const probe = await runProbe(client, {
			promptTokens: [1, 2, 3],
			chain: ["hill", "temperature"],
			params: { temperature: 10, hill_order: 3 },
			steps: 2,
			nProbs: 8,
		});

		expect(probe.steps).toHaveLength(2);
		expect(probe.requests).toBe(3); // one generation + one raw pass per step
		expect(probe.text).toBe("AB");

		// The raw passes must teacher-force the tokens pass 1 produced.
		expect(client.bodies[1].prompt).toEqual([1, 2, 3]);
		expect(client.bodies[2].prompt).toEqual([1, 2, 3, 11]);
		expect(client.bodies[1].post_sampling_probs).toBe(false);
		expect(client.bodies[1].samplers).toEqual(["top_k"]);

		// Pass 1 carries the chain and its knobs.
		expect(client.bodies[0].samplers).toEqual(["hill", "temperature"]);
		expect(client.bodies[0].temperature).toBe(10);
		expect(client.bodies[0].cache_prompt).toBe(true);

		const first = probe.steps[0].comparison;
		expect(first.width).toBe(2);
		expect(first.keptMass).toBeCloseTo(0.75, 6);
		expect(first.chosenRawRank).toBe(1);
	});

	test("teacher-forces supplied tokens and measures survivors per position", async () => {
		const client = new FakeClient((body) =>
			body.post_sampling_probs === true
				? {
						completion_probabilities: [
							probsEntry("x", 55, true, [
								["x", 0.9, 55],
								["y", 0.1, 66],
							]),
						],
					}
				: {
						completion_probabilities: [
							probsEntry("x", 55, false, [
								["x", 0.4, 55],
								["y", 0.3, 66],
							]),
						],
					},
		);

		const probe = await runProbe(client, {
			promptTokens: [7],
			chain: ["min_p"],
			params: { min_p: 0.05 },
			steps: 3,
			forcedTokens: [55, 66, 77],
		});

		expect(probe.steps).toHaveLength(3);
		expect(probe.requests).toBe(6); // survivors + raw, per forced position
		expect(client.bodies[0].prompt).toEqual([7]);
		expect(client.bodies[1].prompt).toEqual([7, 55]);
		expect(client.bodies[2].prompt).toEqual([7, 55, 66]);
		expect(probe.notes.some((note) => note.includes("xtc"))).toBe(true);
	});

	test("the funnel walks chain prefixes and flags history-dependent stages", async () => {
		const widths: Record<string, number> = { dry: 40, hill: 6, temperature: 6 };
		const client = new FakeClient((body) => {
			const samplers = body.samplers as string[];
			if (body.post_sampling_probs === false) {
				return {
					completion_probabilities: [
						probsEntry("A", 11, false, [["A", 0.6, 11]]),
					],
				};
			}
			if (body.return_tokens === true) {
				// Pass 1 is the only request that asks for the generated token ids.
				return {
					tokens: [11],
					completion_probabilities: [probsEntry("A", 11, true, [["A", 1, 11]])],
				};
			}
			const width = widths[samplers[samplers.length - 1]] ?? 1;
			return {
				completion_probabilities: [
					probsEntry(
						"A",
						11,
						true,
						Array.from(
							{ length: width },
							(_, index) =>
								[`t${index}`, 1 / width, index] as [string, number, number],
						),
					),
				],
			};
		});

		const probe = await runProbe(client, {
			promptTokens: [1],
			chain: ["dry", "hill", "temperature"],
			params: {},
			steps: 1,
			funnel: true,
			funnelNProbs: 128,
		});

		const funnel = probe.steps[0].funnel;
		expect(funnel.map((stage) => stage.sampler)).toEqual([
			"dry",
			"hill",
			"temperature",
		]);
		expect(funnel.map((stage) => stage.width)).toEqual([40, 6, 6]);
		expect(funnel[0].historyDependent).toBe(true);
		expect(funnel[1].historyDependent).toBe(false);
		expect(probe.notes.some((note) => note.includes("dry/penalties"))).toBe(
			true,
		);
	});

	test("saturated widths are called out rather than reported as exact", async () => {
		const client = new FakeClient((body) =>
			body.post_sampling_probs === true
				? {
						tokens: [1],
						completion_probabilities: [
							probsEntry(
								"A",
								1,
								true,
								Array.from(
									{ length: 4 },
									(_, i) => [`t${i}`, 0.25, i] as [string, number, number],
								),
							),
						],
					}
				: {
						completion_probabilities: [
							probsEntry("A", 1, false, [["A", 0.5, 1]]),
						],
					},
		);
		const probe = await runProbe(client, {
			promptTokens: [1],
			chain: ["top_k"],
			params: { top_k: 4 },
			steps: 1,
			nProbs: 4,
		});
		expect(probe.steps[0].comparison.saturated).toBe(true);
		expect(probe.notes.some((note) => note.includes("n_probs=4"))).toBe(true);
	});

	test("progress is reported for every request", async () => {
		const seen: string[] = [];
		const client = new FakeClient(() => ({
			tokens: [1],
			completion_probabilities: [probsEntry("A", 1, true, [["A", 1, 1]])],
		}));
		await runProbe(client, {
			promptTokens: [1],
			chain: ["top_k"],
			params: {},
			steps: 1,
			onProgress: (_done, _total, label) => seen.push(label),
		});
		expect(seen[0]).toBe("generating");
		expect(seen.some((label) => label.startsWith("raw logprobs"))).toBe(true);
	});
});

describe("estimateProbeRequests", () => {
	test("counts one generation plus a raw pass per step", () => {
		expect(
			estimateProbeRequests({
				steps: 10,
				chainLength: 4,
				funnel: false,
				forced: false,
			}),
		).toBe(11);
	});

	test("forced replay costs a survivor request per step", () => {
		expect(
			estimateProbeRequests({
				steps: 10,
				chainLength: 4,
				funnel: false,
				forced: true,
			}),
		).toBe(20);
	});

	test("the funnel multiplies by chain length", () => {
		expect(
			estimateProbeRequests({
				steps: 10,
				chainLength: 4,
				funnel: true,
				forced: true,
			}),
		).toBe(60);
	});
});

describe("probeSamplerSupport", () => {
	test("trusts the server's echo of the parsed chain", async () => {
		const client = new FakeClient((body) => {
			const [id] = body.samplers as string[];
			return {
				generation_settings: { samplers: id === "otsu" ? [] : [id] },
			};
		});
		const support = await probeSamplerSupport(client, ["kneedle", "otsu"]);
		expect(support.get("kneedle")).toBe(true);
		expect(support.get("otsu")).toBe(false);
	});

	test("a failing request counts as unsupported instead of throwing", async () => {
		const client: ProbeClient = {
			completion: async () => {
				throw new Error("500");
			},
			tokenize: async () => ({ tokens: [] }),
		};
		const support = await probeSamplerSupport(client, ["hill"]);
		expect(support.get("hill")).toBe(false);
	});
});
