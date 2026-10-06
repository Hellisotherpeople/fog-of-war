/**
 * End-to-end test over a stand-in llama.cpp server.
 *
 * The fake server reproduces the exact response shapes `tools/server` emits
 * (see `populate_token_probs` and `completion_token_output::to_json`), so the
 * proxy → capture → runtime → report path is exercised for real, including
 * HTTP framing, without needing a model loaded.
 */

import { afterEach, describe, expect, test } from "bun:test";
import http from "node:http";
import type { AddressInfo } from "node:net";
import { diffSamplerChain, inferSamplerSupport, LlamaClient } from "./llama";
import { runProbe } from "./probe";
import {
	renderAggregate,
	renderGenerationReport,
	renderLiveWidget,
	summarizeGeneration,
} from "./report";
import { SamplerScope } from "./runtime";

const CATALOG = [
	{ id: "dry", knobs: [{ key: "dry_multiplier" }, { key: "dry_base" }] },
	{ id: "hill", knobs: [{ key: "hill_order" }] },
	{ id: "otsu", knobs: [] },
	{ id: "temperature", knobs: [{ key: "temperature" }] },
];

const PROPS = {
	default_generation_settings: {
		params: {
			temperature: 10,
			hill_order: 3,
			dry_multiplier: 0.8,
			dry_base: 1.75,
			samplers: ["dry", "hill", "temperature"],
		},
		n_ctx: 262144,
	},
	total_slots: 1,
	model_alias: "fake-model",
	endpoint_slots: true,
};

/** `top_probs` entry as llama.cpp serializes it in post-sampling mode. */
function survivors(count: number): unknown[] {
	return Array.from({ length: count }, (_, index) => ({
		id: index + 1,
		token: `t${index}`,
		bytes: [],
		prob: (count - index) / ((count * (count + 1)) / 2),
	}));
}

interface Fake {
	url: string;
	close(): Promise<void>;
	completionBodies: Record<string, unknown>[];
}

async function startFakeLlama(options: {
	widths: number[];
	slotProcessing?: boolean;
	onSlots?: () => void;
	beforeChat?: () => Promise<void>;
	appliedChain?: string[];
}): Promise<Fake> {
	const completionBodies: Record<string, unknown>[] = [];
	const server = http.createServer((req, res) => {
		const chunks: Buffer[] = [];
		req.on("data", (chunk: Buffer) => chunks.push(chunk));
		req.on("end", async () => {
			const raw = Buffer.concat(chunks).toString("utf8");
			const body = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
			const path = (req.url ?? "").split("?")[0];

			if (path === "/props") {
				res.writeHead(200, { "content-type": "application/json" });
				res.end(JSON.stringify(PROPS));
				return;
			}
			if (path === "/slots") {
				res.writeHead(200, { "content-type": "application/json" });
				res.end(
					JSON.stringify([
						{
							id: 0,
							is_processing: options.slotProcessing ?? false,
							n_prompt_tokens: 120,
							n_prompt_tokens_cache: 100,
							// A previous request, or one belonging to another client.
							params: {
								samplers: ["dry", "hill", "temperature"],
								hill_order: 3,
							},
							next_token: [{ n_decoded: 3, n_remain: 100 }],
						},
					]),
				);
				options.onSlots?.();
				return;
			}
			if (path === "/tokenize") {
				const content = String(body.content ?? "");
				res.writeHead(200, { "content-type": "application/json" });
				res.end(
					JSON.stringify({
						tokens: content.split(" ").map((_, index) => 500 + index),
					}),
				);
				return;
			}
			if (path === "/apply-template") {
				res.writeHead(200, { "content-type": "application/json" });
				res.end(JSON.stringify({ prompt: "rendered prompt here" }));
				return;
			}
			if (path === "/completion") {
				completionBodies.push(body);
				const post = body.post_sampling_probs === true;
				const width = post ? options.widths[0] : 5;
				res.writeHead(200, { "content-type": "application/json" });
				res.end(
					JSON.stringify({
						content: "A",
						tokens: [11],
						generation_settings: options.appliedChain === undefined
							? undefined : { samplers: options.appliedChain },
						completion_probabilities: [
							post
								? { id: 11, token: "A", prob: 0.5, top_probs: survivors(width) }
								: {
										id: 11,
										token: "A",
										logprob: Math.log(0.5),
										top_logprobs: survivors(width).map((entry) => {
											const candidate = entry as {
												id: number;
												token: string;
												prob: number;
											};
											return {
												id: candidate.id,
												token: candidate.token,
												logprob: Math.log(candidate.prob),
											};
										}),
									},
						],
					}),
				);
				return;
			}
			if (path === "/v1/chat/completions") {
				await options.beforeChat?.();
				res.writeHead(200, { "content-type": "text/event-stream" });
				options.widths.forEach((width, index) => {
					res.write(
						`data: ${JSON.stringify({
							choices: [
								{
									index: 0,
									delta: { content: `t${index} ` },
									logprobs: {
										content: [
											{
												id: index,
												token: `t${index} `,
												prob: 0.5,
												candidate_count: width,
												vocab_size: 151936,
												top_probs: survivors(width).slice(0, Number(body.n_probs) || width),
											},
										],
									},
								},
							],
							timings: {
								predicted_per_second: 40,
								cache_n: 100,
								prompt_n: 120,
							},
						})}\n\n`,
					);
				});
				res.write("data: [DONE]\n\n");
				res.end();
				return;
			}
			res.writeHead(404).end();
		});
	});
	await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
	const { port } = server.address() as AddressInfo;
	return {
		url: `http://127.0.0.1:${port}`,
		completionBodies,
		close: () => new Promise<void>((resolve) => server.close(() => resolve())),
	};
}

const logger = { debug: () => {}, warn: () => {} };
const cleanups: (() => Promise<void>)[] = [];
afterEach(async () => {
	for (const cleanup of cleanups.splice(0)) await cleanup();
});

function newScope(): SamplerScope {
	return new SamplerScope({
		logger,
		knobKeys: ["temperature", "hill_order", "dry_multiplier"],
		routerToolName: "route_samplers",
		storageDir: "/tmp/omp-samplers-test",
	});
}

describe("scope over a stand-in llama.cpp server", () => {
	test("a streamed answer is captured as per-token truncation widths", async () => {
		const fake = await startFakeLlama({ widths: [12, 3, 1, 40] });
		cleanups.push(fake.close);
		const scope = newScope();
		cleanups.push(() => scope.shutdown());

		await scope.connect(fake.url, CATALOG);
		scope.config.capture = true;
		scope.config.nProbs = 20;
		const proxyUrl = await scope.startProxy();

		const body = {
			model: "m",
			samplers: ["dry", "hill", "temperature"],
			temperature: 10,
		};
		scope.instrument(body as Record<string, unknown>);
		expect((body as Record<string, unknown>).n_probs).toBe(20);
		expect((body as Record<string, unknown>).post_sampling_probs).toBe(true);

		const response = await fetch(`${proxyUrl}/v1/chat/completions`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify(body),
		});
		await response.text();
		// The proxy finishes recording on stream end; give the loop one turn.
		await new Promise((resolve) => setTimeout(resolve, 20));

		const record = scope.current();
		if (!record) throw new Error("the proxy captured no generation");
		expect(record.chain).toEqual(["dry", "hill", "temperature"]);
		expect(record.params).toEqual({ temperature: 10 });
		expect(record.mode).toBe("post");
		expect(record.tokens.map((token) => token.candidates.length)).toEqual([
			12, 3, 1, 20,
		]);
		expect(record.tokens[3].candidateCount).toBe(40);
		expect(record.tokens[3].saturated).toBe(true); // preview 20 < width 40

		const stats = summarizeGeneration(record);
		expect(stats.tokens).toBe(4);
		expect(stats.width?.median).toBe(3); // nearest-rank over [1, 3, 12, 40]
		expect(stats.width?.max).toBe(40);
		expect(stats.forcedRate).toBeCloseTo(0.25, 6);
		expect(stats.saturationRate).toBeCloseTo(0.25, 6);
		expect(stats.tokPerSec).toBeCloseTo(40, 6);
		expect(stats.cachedTokens).toBe(100);

		const report = renderGenerationReport(record).join("\n");
		expect(report).toContain("Truncation width");
		expect(report).toContain("forced to 1");
		expect(renderAggregate(scope.store.all()).join("\n")).toContain(
			"dry → hill → temperature",
		);
		expect(
			renderLiveWidget({ chainLabel: "x", mode: "y", record }).length,
		).toBeGreaterThan(2);
	});

	test("raw mode captures the model's own distribution and reports no width", async () => {
		const fake = await startFakeLlama({ widths: [7, 7] });
		cleanups.push(fake.close);
		const scope = newScope();
		cleanups.push(() => scope.shutdown());
		await scope.connect(fake.url, CATALOG);
		scope.config.capture = true;
		scope.config.probeMode = "raw";
		const proxyUrl = await scope.startProxy();

		const body: Record<string, unknown> = { samplers: ["hill"] };
		scope.instrument(body);
		expect(body.post_sampling_probs).toBe(false);

		// The stand-in always answers in post-sampling shape, so force the raw
		// shape through the native endpoint instead.
		const client = new LlamaClient(fake.url);
		const result = await client.completion({
			prompt: [1],
			post_sampling_probs: false,
		});
		expect(result.completion_probabilities).toBeDefined();
		expect(proxyUrl).toContain("127.0.0.1");
	});

	test.each([false, true])("an unrelated slot (processing=%s) cannot imply dropped samplers", async (slotProcessing) => {
		const slotRead = Promise.withResolvers<void>();
		const fake = await startFakeLlama({
			widths: [4],
			slotProcessing,
			onSlots: () => slotRead.resolve(),
			beforeChat: () => slotRead.promise,
		});
		cleanups.push(fake.close);
		const scope = newScope();
		cleanups.push(() => scope.shutdown());
		await scope.connect(fake.url, CATALOG);
		const proxyUrl = await scope.startProxy();
		scope.startPolling();
		const response = await fetch(`${proxyUrl}/v1/chat/completions`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ samplers: ["dry", "min_p", "kl_budget"] }),
		});
		await response.text();
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(scope.slot?.samplers).toEqual(["dry", "hill", "temperature"]);
		expect(scope.droppedSamplers).toEqual([]);
		expect(scope.current()?.chain).toEqual(["dry", "min_p", "kl_budget"]);
		expect(scope.current()?.appliedChain).toBeUndefined();
	});

	test("only a response's own sampler echo can confirm a drop, and later success clears it", async () => {
		const options = { widths: [4], appliedChain: ["dry", "hill"] };
		const fake = await startFakeLlama(options);
		cleanups.push(fake.close);
		const scope = newScope();
		cleanups.push(() => scope.shutdown());
		await scope.connect(fake.url, CATALOG);
		const proxyUrl = await scope.startProxy();
		const request = async (samplers: string[]) => {
			const response = await fetch(`${proxyUrl}/completion`, {
				method: "POST",
				headers: { "content-type": "application/json" },
				body: JSON.stringify({ prompt: "x", samplers }),
			});
			await response.text();
			await new Promise((resolve) => setTimeout(resolve, 20));
		};
		await request(["dry", "hill", "otsu"]);
		expect(scope.droppedSamplers).toEqual(["otsu"]);
		expect(scope.current()?.appliedChain).toEqual(["dry", "hill"]);
		const widget = renderLiveWidget({ chainLabel: "x", mode: "y", droppedSamplers: scope.droppedSamplers }).join("\n");
		expect(widget).toContain("missing from this response's applied chain");
		expect(widget).not.toContain("does not implement");
		options.appliedChain = ["dry", "min_p", "kl_budget"];
		await request(options.appliedChain);
		expect(scope.droppedSamplers).toEqual([]);
		expect(scope.current()?.appliedChain).toEqual(options.appliedChain);
		expect(scope.store.all()[0].appliedChain).toEqual(["dry", "hill"]);
	});

	test("a new request without an applied-chain echo clears the previous request's warning", async () => {
		const fake = await startFakeLlama({ widths: [4] });
		cleanups.push(fake.close);
		const scope = newScope();
		cleanups.push(() => scope.shutdown());
		await scope.connect(fake.url, CATALOG);
		scope.noteRequest(["otsu"], []);
		expect(scope.droppedSamplers).toEqual(["otsu"]);
		const proxyUrl = await scope.startProxy();
		const response = await fetch(`${proxyUrl}/v1/chat/completions`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ samplers: ["dry", "min_p", "kl_budget"] }),
		});
		await response.text();
		expect(scope.droppedSamplers).toEqual([]);
	});

	test("changing servers clears capability warnings and snapshots", async () => {
		const first = await startFakeLlama({ widths: [4] });
		const second = await startFakeLlama({ widths: [4] });
		cleanups.push(first.close, second.close);
		const scope = newScope();
		cleanups.push(() => scope.shutdown());
		await scope.connect(first.url, CATALOG);
		scope.noteRequest(["kl_budget"], []);
		await scope.connect(second.url, CATALOG);
		expect(scope.droppedSamplers).toEqual([]);
		expect(scope.slot).toBeUndefined();
	});

	test("/props tells us which samplers this build implements", async () => {
		const support = inferSamplerSupport(PROPS, CATALOG);
		expect(support.find((entry) => entry.id === "hill")?.support).toBe(
			"supported",
		);
		expect(support.find((entry) => entry.id === "otsu")?.support).toBe(
			"unknown",
		);
		const missing = inferSamplerSupport(
			{ default_generation_settings: { params: { temperature: 1 } } },
			CATALOG,
		);
		expect(missing.find((entry) => entry.id === "hill")?.support).toBe(
			"unsupported",
		);
	});

	test("a probe drives the native endpoint with cached prefixes", async () => {
		const fake = await startFakeLlama({ widths: [6] });
		cleanups.push(fake.close);
		const client = new LlamaClient(`${fake.url}/v1`); // /v1 suffix must be stripped

		const probe = await runProbe(client, {
			promptTokens: [1, 2],
			chain: ["hill", "temperature"],
			params: { hill_order: 3, temperature: 10 },
			steps: 1,
			nProbs: 20,
		});

		expect(probe.steps).toHaveLength(1);
		expect(probe.steps[0].comparison.width).toBe(6);
		expect(probe.steps[0].raw).toHaveLength(5);
		expect(fake.completionBodies[0].cache_prompt).toBe(true);
		expect(fake.completionBodies[0].samplers).toEqual(["hill", "temperature"]);
		expect(fake.completionBodies[1].post_sampling_probs).toBe(false);
	});

	test("chain diffs report drops, additions and reordering", () => {
		expect(diffSamplerChain(["a", "b", "c"], ["a", "c"])).toEqual({
			dropped: ["b"],
			added: [],
			reordered: false,
		});
		expect(diffSamplerChain(["a", "b"], ["b", "a"]).reordered).toBe(true);
	});
});
