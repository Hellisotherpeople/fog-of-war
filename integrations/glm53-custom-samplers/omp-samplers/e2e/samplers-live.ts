/** LLAMA_URL=http://127.0.0.1:8091 bun run e2e/samplers-live.ts */
import assert from "node:assert/strict";
import { parseProbEntries, parseChunk, SseSplitter } from "../scope/capture";
import { LlamaClient } from "../scope/llama";
import { runProbe } from "../scope/probe";

const base = (process.env.LLAMA_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
async function post(endpoint: string, body: object) {
	const response = await fetch(`${base}${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(120_000) });
	assert.equal(response.status, 200, await response.clone().text().then((s) => s.slice(0, 400)));
	return response.json() as Promise<any>;
}
const defaults = { prompt: "The quick brown fox", n_predict: 1, seed: 123, cache_prompt: true, n_probs: 8, post_sampling_probs: true, temperature: 1 };
const samplers: Record<string, Record<string, number | boolean>> = {
	dry: { dry_multiplier: 0.8, dry_base: 1.75, dry_allowed_length: 2, dry_penalty_last_n: 128 },
	penalties: { repeat_penalty: 1.1, repeat_last_n: 64, frequency_penalty: 0.1, presence_penalty: 0.1 },
	top_k: { top_k: 4 }, top_p: { top_p: 0.8 }, min_p: { min_p: 0.1 }, typ_p: { typical_p: 0.8 },
	top_n_sigma: { top_n_sigma: 1 }, xtc: { xtc_probability: 0.5, xtc_threshold: 0.1 },
	min_k: { min_k_tau: 3 }, p_less: { p_less_exponent: 2, p_less_norm: true }, top_h: { top_h_alpha: 0.4 },
	hill: { hill_order: 3 }, geo_mean: { geo_mean_coeff: 1 }, robust_z: { robust_z_coeff: 3 },
	otsu: {}, kneedle: {}, top_gap: {}, kl_opt: { kl_opt_lambda: 1, kl_opt_global: true }, kl_budget: { kl_budget: 0.1 }, temperature: { temperature: 0.7 },
};
for (const [id, params] of Object.entries(samplers)) {
	const result = await post("/completion", { ...defaults, ...params, samplers: [id] });
	assert.deepEqual(result.generation_settings.samplers, [id], `${id} must not be silently dropped`);
	for (const [key, value] of Object.entries(params)) {
		const actual = result.generation_settings[key];
		if (typeof value === "boolean") assert.equal(actual, value, key);
		else assert.ok(Math.abs(actual - value) < 1e-5, `${key}: ${actual} != ${value}`);
	}
	const step = parseProbEntries(result.completion_probabilities)[0];
	assert.ok(step?.rawRank && step.postRank, `${id}: exact ranks missing`);
	assert.ok(step.candidates.length > 0, `${id}: candidates missing`);
	assert.ok(step.candidateCount! >= step.candidates.length, `${id}: full width missing`);
	assert.ok(step.vocabSize! >= step.candidateCount!, `${id}: invalid vocabulary size`);
	assert.ok(Number.isFinite(step.entropyBits), `${id}: full entropy missing`);
	console.log(`PASS ${id}: raw rank ${step.rawRank}, post rank ${step.postRank}`);
}

// Compare the live KL* support with the research's exhaustive objective.
const rawResult = await post("/completion", { ...defaults, n_probs: 1024, post_sampling_probs: false, samplers: ["top_k"], top_k: 1 });
const raw = parseProbEntries(rawResult.completion_probabilities)[0];
for (const lambda of [0.5, 1, 1.25]) {
	let sum = 0, best = Infinity, kBest = 1;
	for (let i = 0; i < raw.candidates.length; ++i) {
		sum += Math.log(raw.candidates[i].p);
		const j = -lambda * Math.log(i + 1) - sum / (i + 1);
		if (j < best) { best = j; kBest = i + 1; }
	}
	const result = await post("/completion", { ...defaults, n_probs: 1024, samplers: ["kl_opt", "temperature"], kl_opt_lambda: lambda, kl_opt_global: true, temperature: 1e6 });
	const step = parseProbEntries(result.completion_probabilities)[0];
	assert.ok(kBest < 1024, "reference window saturated");
	assert.equal(step.candidates.length, kBest, `KL* support at lambda=${lambda}`);
	assert.ok(step.candidates.every((c) => Math.abs(c.p - 1 / kBest) < 1e-4), "near-uniform draw");
	console.log(`PASS KL* lambda=${lambda}: k=${kBest} matches research objective over top 1024`);
}

// Deliberately pick a token below the reporting window, and change its final rank.

// Fixed support isolates the adaptive-temperature solver from admission changes.
const supportResult = await post("/completion", { ...defaults, samplers: ["top_k"], top_k: 32, n_probs: 32 });
const support = parseProbEntries(supportResult.completion_probabilities)[0].candidates;
const ref = new Map(support.map((c) => [c.id, c.p]));
let lastEntropy = -Infinity;
for (const budget of [0, 0.05, 0.1, 0.3, 1]) {
	const result = await post("/completion", { ...defaults, samplers: ["top_k", "kl_budget"], top_k: 32, kl_budget: budget, n_probs: 32 });
	const measured = parseProbEntries(result.completion_probabilities)[0];
	const q = measured.candidates;
	assert.equal(q.length, support.length);
	const kl = q.reduce((n, c) => n + c.p * Math.log(c.p / ref.get(c.id)!), 0);
	const entropy = q.reduce((n, c) => n - c.p * Math.log(c.p), 0);
	const entropyBits = entropy / Math.log(2);
	const variance = q.reduce((n, c) => n + c.p * (-Math.log2(c.p) - entropyBits) ** 2, 0);
	assert.ok(Math.abs(measured.entropyBits! - entropyBits) < 1e-5, "full entropy must match the entire nonuniform distribution");
	assert.ok(Math.abs(measured.varentropyBits2! - variance) < 1e-4, "full varentropy must match the entire nonuniform distribution");
	assert.ok(kl <= budget + 1e-5, `KL-budget exceeded: ${kl} > ${budget}`);
	assert.ok(entropy >= lastEntropy - 1e-5, "entropy should increase with budget");
	lastEntropy = entropy;
	console.log(`PASS KL-budget ${budget}: KL=${kl.toFixed(5)}, H=${entropy.toFixed(5)} nats`);
}

const target = raw.candidates[40];
const forced = await post("/completion", { ...defaults, n_probs: 2, samplers: ["top_k"], top_k: 1, logit_bias: [[target.id, 100]] });
const step = parseProbEntries(forced.completion_probabilities)[0];
const expected = 1 + raw.candidates.filter((c) => c.p > target.p).length;
assert.equal(step.id, target.id);
assert.equal(step.rawRank, expected);
assert.equal(step.postRank, 1);
console.log(`PASS out-of-window rank: raw=${expected}, post=1, n_probs=2`);

// Exact measurements must not depend on how many candidate details are returned.
const wide = parseProbEntries((await post("/completion", { ...defaults, samplers: ["temperature"], temperature: 1e6, n_probs: 2 })).completion_probabilities)[0];
assert.equal(wide.candidateCount, wide.vocabSize, "untruncated width must cover the entire vocabulary");
assert.equal(wide.candidates.length, 2);
assert.ok(Math.abs(wide.entropyBits! - Math.log2(wide.vocabSize!)) < 1e-6, "full-vocabulary uniform entropy");
const banned = parseProbEntries((await post("/completion", { ...defaults, samplers: ["temperature"], temperature: 1e6, n_probs: 2, logit_bias: [[raw.candidates[0].id, false], [raw.candidates[1].id, false]] })).completion_probabilities)[0];
assert.equal(banned.candidateCount, wide.vocabSize! - 2, "banned tokens must not count as survivors");
assert.ok(Math.abs(banned.entropyBits! - Math.log2(banned.candidateCount!)) < 1e-6);
for (const preview of [2, 64]) {
	const full = parseProbEntries((await post("/completion", { ...defaults, samplers: ["top_k", "temperature"], top_k: 64, temperature: 1e6, n_probs: preview })).completion_probabilities)[0];
	assert.equal(full.candidateCount, 64);
	assert.equal(full.candidates.length, preview);
	assert.ok(Math.abs(full.entropyBits! - 6) < 1e-7);
	assert.ok(full.varentropyBits2! < 1e-7);
}
const underflow = parseProbEntries((await post("/completion", { ...defaults, samplers: ["top_k"], top_k: 64, n_probs: 2, logit_bias: [[target.id, 1000]] })).completion_probabilities)[0];
assert.equal(underflow.candidateCount, 64, "finite logits still count when probabilities underflow");
assert.equal(underflow.candidates.length, 1);
const rawForced = parseProbEntries((await post("/completion", { ...defaults, samplers: ["top_k"], top_k: 1, n_probs: 2, post_sampling_probs: false, logit_bias: [[target.id, 100]] })).completion_probabilities)[0];
assert.equal(rawForced.candidateCount, 1, "raw mode also carries post-chain width");
assert.equal(rawForced.rawRank, expected);
assert.ok(Math.abs(rawForced.prob! - target.p) < 1e-7, "raw selected probability must be correct outside preview");
console.log(`PASS full vocabulary (${wide.vocabSize}), banned tokens, underflow, raw mode, and preview-independent width/entropy`);
const probe = await runProbe(new LlamaClient(base), { promptText: defaults.prompt, chain: ["top_k", "temperature"], params: { top_k: 64, temperature: 1e6 }, steps: 1, nProbs: 2, funnelNProbs: 2, funnel: true });
assert.equal(probe.steps[0].comparison.width, 64);
assert.equal(probe.steps[0].comparison.saturated, false);
assert.deepEqual(probe.steps[0].funnel.map((f) => f.width), [64, 64]);
assert.ok(Math.abs(probe.steps[0].comparison.entropyAfter - 6) < 1e-7);
console.log("PASS full-width probe and per-stage funnel with preview=2");

// Native multi-token and OpenAI streaming both retain the rank fields.
const result = await post("/completion", { ...defaults, n_predict: 12, samplers: ["kl_opt", "temperature"], temperature: 1e6 });
const steps = parseProbEntries(result.completion_probabilities);
assert.equal(steps.length, result.tokens_predicted);
assert.ok(steps.every((s) => s.rawRank && s.postRank));
assert.ok(steps.every((s) => s.candidateCount && s.vocabSize && Number.isFinite(s.entropyBits)));
const response = await fetch(`${base}/v1/chat/completions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: [{ role: "user", content: "Say hello in five words." }], max_tokens: 12, stream: true, samplers: ["kl_opt", "temperature"], temperature: 1e6, n_probs: 2, post_sampling_probs: true, chat_template_kwargs: { enable_thinking: false } }), signal: AbortSignal.timeout(120_000) });
assert.equal(response.status, 200);
const frames = new SseSplitter().feed(await response.text());
const streamed = frames.flatMap((f) => parseChunk(f)?.steps ?? []);
assert.ok(streamed.length > 0);
assert.ok(streamed.every((s) => s.rawRank && s.postRank));
assert.ok(streamed.every((s) => s.candidateCount && s.vocabSize && Number.isFinite(s.entropyBits)));
console.log(`PASS native (${steps.length} tokens) and OpenAI streaming (${streamed.length} tokens)`);
