/** Run the real omp extension, recording KL* requests and rank telemetry. */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { startRecordingProxy } from "../scope/proxy";

const upstream = process.env.LLAMA_URL ?? "http://127.0.0.1:8080";
const budgetMode = process.env.SAMPLER_METHOD === "kl_budget";
const chain = budgetMode ? ["min_p", "kl_budget"] : ["kl_opt", "temperature"];
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "omp-ranks-live-"));
fs.mkdirSync(path.join(dir, "extensions"));
fs.symlinkSync(path.join(import.meta.dir, ".."), path.join(dir, "extensions", "omp-samplers"));
const extensionArgs = process.env.E2E_AUTOLOAD === "1" ? [] : ["--no-extensions", "--extension", path.join(import.meta.dir, "..", "index.ts")];
const bodies: Record<string, unknown>[] = [];
const proxy = await startRecordingProxy({ upstream, hooks: { onRequest(info) { if (info.path.endsWith("/chat/completions") && info.body) bodies.push(info.body); } } });
fs.writeFileSync(path.join(dir, "models.yml"), `providers:
  llama.cpp-e2e:
    baseUrl: ${proxy.url}/v1
    api: openai-completions
    auth: none
    models:
      - id: rank-test
        name: Rank test
        api: openai-completions
        reasoning: false
        input: [text]
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }
        contextWindow: 32768
        maxTokens: 32
`);
fs.writeFileSync(path.join(dir, "config.yml"), "modelRoles:\n  default: llama.cpp-e2e/rank-test\ncompaction:\n  strategy: off\n");
fs.writeFileSync(path.join(dir, "sampler-profile.json"), JSON.stringify({ enabled: true, applyToAllModels: true, mode: "manual", chain, params: { kl_opt_lambda: 1, kl_opt_global: true, temperature: 1e6, min_p: 0.05, kl_budget: 0.1 }, thinkCap: 1, scope: { capture: true, proxy: true, probeMode: "post", nProbs: 2, widget: false, slots: false, jsonl: true } }));
try {
	const child = Bun.spawn([process.env.OMP_BIN ?? "omp", "-p", "--no-session", ...extensionArgs, "--no-tools", "--allow-home", "Say hello. One short sentence."], { cwd: dir, env: { ...process.env, PI_CODING_AGENT_DIR: dir, OMP_SAMPLERS_AUTO: "0" }, stdout: "pipe", stderr: "pipe" });
	const timer = setTimeout(() => child.kill(), 120_000);
	const [stdout, stderr, code] = await Promise.all([new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited]);
	clearTimeout(timer);
	fs.writeFileSync(path.join(dir, "output.log"), stdout + stderr);
	assert.equal(code, 0, stdout + stderr);
	assert.ok(bodies.length > 0, "no provider requests");
	for (const body of bodies) {
		assert.deepEqual(body.samplers, chain);
		assert.equal(body.kl_opt_lambda, 1);
		assert.equal(body.kl_opt_global, true);
		assert.equal(body.n_probs, 2);
	}
	const telemetryDir = path.join(dir, "sampler-scope");
	const files = fs.readdirSync(telemetryDir).filter((f) => f.endsWith(".jsonl"));
	assert.ok(files.length > 0, "no JSONL telemetry");
	const records = files.flatMap((file) => fs.readFileSync(path.join(telemetryDir, file), "utf8").trim().split("\n").map((l) => JSON.parse(l)));
	for (const record of records) {
		assert.equal(record.schemaVersion, 2);
		assert.ok(record.tokens.length > 0);
		assert.equal(record.summary.widthKnown, record.tokens.length);
		assert.equal(record.summary.entropyKnown, record.tokens.length);
		const meanWidth = record.tokens.reduce((sum: number, token: any) => sum + token.w, 0) / record.tokens.length;
		assert.equal(record.summary.widthMean, meanWidth);
		assert.ok(record.tokens.every((t: any) => t.w >= t.previewCount && t.vocabSize >= t.w && Number.isFinite(t.entropyBits)));
		assert.equal(record.summary.rawRank.known, record.tokens.length);
		const expected = record.tokens.reduce((sum: number, token: any) => sum + token.rawRank, 0) / record.tokens.length;
		assert.equal(record.summary.rawRank.stats.mean, expected);
	}
	console.log(`PASS real omp: ${bodies.length} ${budgetMode ? "KL-budget" : "KL*"} request(s), ${records.reduce((n, r) => n + r.tokens.length, 0)} ranked tokens; artifacts: ${dir}`);
} finally {
	await proxy.close();
}
