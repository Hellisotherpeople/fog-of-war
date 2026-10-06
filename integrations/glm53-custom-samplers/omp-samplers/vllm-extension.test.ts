import { expect, test } from "bun:test";
import { vllmSamplerConfig } from "./vllm";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

test("vLLM extension commands, authenticated telemetry, and native request settings", async () => {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), "omp-vllm-extension-"));
	fs.writeFileSync(path.join(dir, "sampler-profile.json"), JSON.stringify({
		enabled: true, mode: "manual", applyToAllModels: false, chain: ["min_p"],
		params: { min_p: 0.1, top_p: 0.95, top_k: 20, temperature: 1e6 },
		scope: { proxy: true, capture: true, nProbs: 20, slots: true, jsonl: true },
		thinkCap: 512,
	}));
	const requests: string[] = [];
	const bodies: Record<string, unknown>[] = [];
	const server = Bun.serve({ port: 0, hostname: "127.0.0.1", async fetch(req) {
		const url = new URL(req.url);
		requests.push(url.pathname);
		if (req.headers.get("authorization") !== "Bearer test-credential") return new Response("Unauthorized", { status: 401 });
		if (url.pathname !== "/v1/chat/completions") return new Response("Not found", { status: 404 });
		bodies.push(await req.json() as Record<string, unknown>);
		const data = { choices: [{ delta: { content: "OK" }, logprobs: { content: [{ token: "OK", logprob: -0.2, top_logprobs: [{ token: "OK", logprob: -0.2 }] }] } }] };
		return new Response(`data: ${JSON.stringify(data)}\n\ndata: [DONE]\n\n`, { headers: { "Content-Type": "text/event-stream" } });
	} });
	const model = { provider: "glm53-vllm", id: "glm53", baseUrl: `http://127.0.0.1:${server.port}/v1` };
	const listeners = new Map<string, ((event: any, ctx: any) => any)[]>();
	const commands = new Map<string, (args: string, ctx: any) => any>();
	const notifications: string[] = [];
	const ctx = { model, models: { current: () => model, resolve: () => model }, hasUI: false,
		ui: { notify: (message: string) => notifications.push(message), setStatus() {}, setWidget() {} } };
	const pi = { logger: { debug() {}, warn() {} },
		on(name: string, fn: (e: any, c: any) => any) { listeners.set(name, [...(listeners.get(name) ?? []), fn]); },
		registerCommand(name: string, options: any) { commands.set(name, options.handler); },
		registerTool() {}, getActiveTools: () => [], async setActiveTools() {},
		registerProvider(_provider: string, options: { baseUrl: string }) { model.baseUrl = options.baseUrl; },
		async setModel() { return true; },
		typebox: { Type: new Proxy({}, { get: () => (...args: unknown[]) => ({ args }) }) },
	};
	const previousDir = process.env.PI_CODING_AGENT_DIR;
	process.env.PI_CODING_AGENT_DIR = dir;
	try {
		const entry = "./index.ts?vllm-integration";
		(await import(entry)).default(pi);
	} finally {
		if (previousDir === undefined) delete process.env.PI_CODING_AGENT_DIR;
		else process.env.PI_CODING_AGENT_DIR = previousDir;
	}
	const emit = async (name: string, event = {}) => {
		for (const handler of listeners.get(name) ?? []) await handler(event, ctx);
	};
	try {
		await emit("session_start");
		expect(requests).toEqual([]); // Neither /props nor tokenizer detection is valid here.
		await emit("before_agent_start");
		const body: Record<string, unknown> = { model: "glm53", messages: [], min_p: 0.05 };
		await emit("before_provider_request", { payload: body });
		expect(vllmSamplerConfig(body)?.params.min_p).toBe(0.1);
		expect(body.min_p).toBe(0);
		expect(body.top_p).toBe(1);
		expect(body.top_k).toBe(-1);
		expect(body.temperature).toBe(1);
		expect(body.logprobs).toBe(true);
		expect(body.top_logprobs).toBe(20);
		for (const key of ["samplers", "n_probs", "thinking_budget_tokens", "post_sampling_probs"]) expect(body[key]).toBeUndefined();
		const response = await fetch(`${model.baseUrl}/chat/completions`, {
			method: "POST", headers: { Authorization: "Bearer test-credential", "Content-Type": "application/json" }, body: JSON.stringify(body),
		});
		expect(response.status).toBe(200);
		await response.text();
		await commands.get("samplers")!("min_p 0.23", ctx);
		await emit("before_provider_request", { payload: body });
		expect(vllmSamplerConfig(body)?.params.min_p).toBe(0.23);
		await commands.get("samplers")!("show", ctx);
		expect(notifications.join("\n")).toContain('\\"min_p\\":0.23');
		await commands.get("sampler-scope")!("slots on", ctx);
		expect(notifications.at(-1)).toContain("unavailable");
		await commands.get("sampler-scope")!("show", { ...ctx, hasUI: true,
			ui: { ...ctx.ui, select() { throw new Error("show must not open a dialog"); } } });
		expect(notifications.at(-1)).toContain("vLLM logprobs");
		await commands.get("think-cap")!("128", ctx);
		expect(notifications.at(-1)).toContain("not sent to vLLM");
		await commands.get("samplers")!("chain dry top_n_sigma xtc p_less min_k temperature", ctx);
		await commands.get("temp")!("inf", ctx);
		const stored = JSON.parse(fs.readFileSync(path.join(dir, "sampler-profile.json"), "utf8"));
		expect(stored.params.temperature_infinite).toBe(true);
		expect(stored.params.temperature).toBe(1);
		// Compaction bypasses before_provider_request. The proxy must apply the live profile.
		const compaction = await fetch(`${model.baseUrl}/chat/completions`, {
			method: "POST", headers: { Authorization: "Bearer test-credential", "Content-Type": "application/json" },
			body: JSON.stringify({ model: "glm53", messages: [], min_p: 0.05 }),
		});
		expect(compaction.status).toBe(200); await compaction.text();
		expect(vllmSamplerConfig(bodies.at(-1)!)?.params.temperature).toBe("inf");
		expect(vllmSamplerConfig(bodies.at(-1)!)?.chain).toEqual(["dry", "top_n_sigma", "xtc", "p_less", "min_k", "temperature"]);
		expect(bodies.at(-1)!.max_tokens).toBeUndefined();
		await commands.get("temp")!("10", ctx);
		const finite: Record<string, unknown> = {};
		await emit("before_provider_request", {payload: finite});
		expect(vllmSamplerConfig(finite)?.params.temperature).toBe(10);
		await commands.get("samplers-off")!("", ctx);
		const defaults: Record<string, unknown> = { min_p: 0.05 };
		await emit("before_provider_request", { payload: defaults });
		expect(defaults.min_p).toBe(0.05);
		expect(requests).toEqual(["/v1/chat/completions", "/v1/chat/completions"]);
		const logs = fs.readdirSync(path.join(dir, "sampler-scope")).filter((name) => name.endsWith(".jsonl"));
		const record = JSON.parse(fs.readFileSync(path.join(dir, "sampler-scope", logs[0]), "utf8").trim().split("\n")[0]);
		expect(record.chain).toEqual(["min_p"]);
		expect(record.nProbs).toBe(20);
		expect(record.mode).toBe("raw");
		expect(record.tokens.length).toBe(1);
		expect(record.tokens[0].candidateCount).toBeUndefined();
	} finally {
		await emit("session_shutdown");
		server.stop(true);
		fs.rmSync(dir, { recursive: true, force: true });
	}
});
