/**
 * The extension's command and request wiring, against a stub llama.cpp.
 *
 * Everything here loads the real `index.ts` and calls the handlers it registers,
 * so it covers the layer between the pure helpers and omp: that `/think-less`
 * finds the model's own end-of-thinking token, that a bias survives to disk, and
 * that `before_provider_request` really stamps `logit_bias` onto an outgoing
 * body. Driving a live omp process for this would mean a 27B generation per
 * command; the stub answers `/props` and `/tokenize` in microseconds.
 */
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// index.ts resolves its storage paths at module load, so this has to be set
// before the dynamic import below.
const AGENT_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "omp-samplers-cmd-"));
process.env.PI_CODING_AGENT_DIR = AGENT_DIR;

/** Single-token strings the stub tokenizer knows, mirroring a Qwen3 vocabulary. */
const VOCAB: Record<string, number> = {
	"<|endoftext|>": 200,
	"<|im_start|>": 201,
	"<|im_end|>": 202,
	"<think>": 203,
	"</think>": 204,
	"<tool_call>": 205,
	"</tool_call>": 206,
	"<|vision_start|>": 207,
};

/** Ordinary words the stub treats as one token each, as a real BPE would. */
const WORDS: Record<string, number> = {
	delve: 40,
	" delve": 41,
	Certainly: 42,
	Hmm: 43,
	" wait": 44,
	// Two of the three fragments below stand alone as the same token; the
	// BPE-internal one does not, which is the case `parts` has to handle.
	un: 60,
	ment: 62,
};

const CHAT_TEMPLATE =
	"{%- for m in messages %}<|im_start|>{{ m.role }}\n{{ m.content }}<|im_end|>\n{%- endfor %}<|im_start|>assistant\n<think>\n";

/**
 * A tokenizer just real enough to be worth testing against: known strings are
 * one token, and anything else splits into three fragments, one of which does
 * not round-trip on its own.
 */
function tokenizeStub(content: string): { id: number; piece: string }[] {
	const single = VOCAB[content] ?? WORDS[content];
	if (single !== undefined) return [{ id: single, piece: content }];
	if (content === "Ġfrag") return [{ id: 61, piece: "Ġfrag" }, { id: 62, piece: "x" }];
	return [
		{ id: 60, piece: "un" },
		{ id: 61, piece: "Ġfrag" },
		{ id: 62, piece: "ment" },
	];
}

function startStub(): { url: string; stop: () => void } {
	const server = Bun.serve({
		port: 0,
		idleTimeout: 0,
		async fetch(request) {
			const url = new URL(request.url);
			const json = (value: unknown) => Response.json(value);
			switch (url.pathname) {
				case "/props":
					return json({
						// Deliberately unreadable, so detection falls through to the
						// probe tier and this test covers it.
						model_path: "/nonexistent/stub.gguf",
						model_alias: "qwen-stub",
						bos_token: "<|endoftext|>",
						eos_token: "<|im_end|>",
						chat_template: CHAT_TEMPLATE,
						total_slots: 1,
						endpoint_slots: true,
						default_generation_settings: {
							n_ctx: 4096,
							params: {
								temperature: 1,
								top_k: 20,
								top_p: 0.95,
								min_p: 0.05,
								hill_order: 3,
								xtc_probability: 0.5,
								xtc_threshold: 0.1,
								dry_multiplier: 0.8,
								dry_base: 1.75,
								dry_allowed_length: 15,
								dry_penalty_last_n: -1,
								typical_p: 1,
								top_n_sigma: -1,
								repeat_penalty: 1,
								repeat_last_n: 64,
								presence_penalty: 0,
								frequency_penalty: 0,
								dynatemp_range: 0,
								dynatemp_exponent: 1,
							},
						},
					});
				case "/v1/models":
					return json({ data: [{ id: "qwen-stub", meta: { n_vocab: 300 } }] });
				case "/slots":
					return json([]);
				case "/tokenize": {
					const body = (await request.json()) as {
						content?: string;
						with_pieces?: boolean;
					};
					const pieces = tokenizeStub(body.content ?? "");
					return json({
						tokens: body.with_pieces ? pieces : pieces.map((p) => p.id),
					});
				}
				default:
					return new Response("not found", { status: 404 });
			}
		},
	});
	return {
		url: `http://127.0.0.1:${server.port}`,
		stop: () => void server.stop(true),
	};
}

// ---------------------------------------------------------------------------
// Stub host
// ---------------------------------------------------------------------------

type Handler = (args: string, ctx: unknown) => Promise<void> | void;

const commands = new Map<string, Handler>();
const listeners = new Map<string, ((event: unknown, ctx: unknown) => unknown)[]>();
const notifications: string[] = [];

/** typebox is only used to describe the router tool, which is never called here. */
const typeStub = new Proxy(
	{},
	{ get: () => (...args: unknown[]) => ({ args }) },
) as Record<string, unknown>;

const pi = {
	logger: { debug() {}, warn() {}, info() {}, error() {} },
	registerCommand(name: string, options: { handler: Handler }) {
		commands.set(name, options.handler);
	},
	registerTool() {},
	registerProvider() {},
	async setModel() {
		return true;
	},
	getActiveTools(): string[] {
		return [];
	},
	async setActiveTools() {},
	on(name: string, fn: (event: unknown, ctx: unknown) => unknown) {
		const list = listeners.get(name);
		if (list) list.push(fn);
		else listeners.set(name, [fn]);
	},
	typebox: { Type: typeStub },
};

const stub = startStub();

const model = {
	provider: "llama.cpp",
	id: "qwen-stub",
	baseUrl: stub.url,
};

const ctx = {
	hasUI: false,
	isIdle: () => true,
	model,
	models: { current: () => model, resolve: () => model },
	ui: {
		notify: (message: string) => notifications.push(message),
		setStatus() {},
		setWidget() {},
		setWorkingMessage() {},
		async select() {
			return undefined;
		},
		async input() {
			return undefined;
		},
		async confirm() {
			return false;
		},
		theme: undefined,
	},
};

async function run(command: string, args = ""): Promise<string> {
	notifications.length = 0;
	const handler = commands.get(command);
	if (!handler) throw new Error(`no such command: ${command}`);
	await handler(args, ctx);
	return notifications.join("\n");
}

async function emit(name: string, event: unknown): Promise<unknown[]> {
	const results: unknown[] = [];
	for (const listener of listeners.get(name) ?? []) {
		results.push(await listener(event, ctx));
	}
	return results;
}

function storedBias(): { enabled: boolean; entries: Record<string, unknown> } {
	const raw = JSON.parse(
		fs.readFileSync(path.join(AGENT_DIR, "sampler-profile.json"), "utf8"),
	);
	return raw.bias;
}

beforeAll(async () => {
	const factory = (await import("./index")).default;
	factory(pi as never);
	await emit("session_start", {});
	// session_start starts detection without awaiting it.
	await run("logit-bias", "scan");
});

afterAll(async () => {
	await emit("session_shutdown", {});
	stub.stop();
});

describe("detection through the extension", () => {
	test("finds the stub's special tokens by probing", async () => {
		const output = await run("logit-bias", "tokens");
		expect(output).toContain("</think>");
		expect(output).toContain("id 204");
		expect(output).toContain("think_close");
		// The probe tier only reports what it thought to ask about, and says so.
		expect(output).toContain("probe");
	});

	test("caches the result so a later session does not re-probe", () => {
		const cache = JSON.parse(
			fs.readFileSync(path.join(AGENT_DIR, "sampler-tokens.json"), "utf8"),
		);
		expect(cache["qwen-stub:300"].tokens).toContainEqual({
			id: 204,
			text: "</think>",
			role: "think_close",
			kind: "user_defined",
			needsParseSpecial: false,
		});
	});
});

describe("/think-less", () => {
	test("biases the model's own end-of-thinking token", async () => {
		const output = await run("think-less", "firm");
		expect(output).toContain("</think>");
		expect(output).toContain("id 204");
		expect(storedBias()).toEqual({ enabled: true, entries: { "</think>": 4 } });
	});

	test("takes a bare number", async () => {
		await run("think-less", "6.5");
		expect(storedBias().entries).toEqual({ "</think>": 6.5 });
	});

	test("refuses a negative amount, since that means thinking more", async () => {
		const output = await run("think-less", "-3");
		expect(output).toContain("think *more*");
		expect(storedBias().entries).toEqual({ "</think>": 6.5 });
	});

	test("off removes just that bias", async () => {
		// An id that names a detected token is stored under its text, so the entry
		// still means something after a model swap.
		await run("logit-bias", "set #202 -2");
		await run("think-less", "off");
		expect(storedBias().entries).toEqual({ "<|im_end|>": -2 });
	});
});

describe("/logit-bias", () => {
	test("set resolves a token name to its id", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", "set </think> 3");
		expect(output).toContain("id 204");
		expect(storedBias().entries).toEqual({ "</think>": 3 });
	});

	test("set accepts a role name", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "set think_close 2");
		expect(storedBias().entries).toEqual({ "</think>": 2 });
	});

	test("ban stores a hard ban", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "ban <|vision_start|>");
		expect(storedBias().entries).toEqual({ "<|vision_start|>": "ban" });
	});

	test("multi-token text is reported rather than silently collapsed", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", "set </reasoning> 3");
		expect(output).toContain("is 3 tokens, not one");
		expect(output).toContain("/logit-bias parts");
		expect(storedBias().entries).toEqual({});
	});

	test("biases an ordinary word that detection never saw", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", "set delve -4");
		expect(output).toContain("id 40");
		expect(storedBias().entries).toEqual({ delve: -4 });
	});

	test("a quoted leading space survives to the tokenizer", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", 'set " delve" -4');
		expect(output).toContain("id 41");
		expect(storedBias().entries).toEqual({ " delve": -4 });
		// And the stored key with its space still resolves onto a request.
		expect(await run("logit-bias", "show")).toContain("id 41");
	});

	test("clear finds a key whose leading space was quoted", async () => {
		await run("logit-bias", 'clear " delve"');
		expect(storedBias().entries).toEqual({});
	});

	test("suggests the leading-space form when the bare word is two tokens", async () => {
		const output = await run("logit-bias", "set Certainly? 2");
		expect(output).toContain("is 3 tokens, not one");
	});

	test("an added word is listed apart from the vocabulary's own markup", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "set delve -4");
		const output = await run("logit-bias", "tokens");
		expect(output).toContain("added by you");
		expect(output).toContain("delve  id 40");
		// And is still resolvable, so it reaches a request.
		expect(await run("logit-bias", "show")).toContain("delve → -4");
	});

	test("an added word survives a re-scan", async () => {
		await run("logit-bias", "scan");
		expect(await run("logit-bias", "show")).toContain("delve → -4");
	});

	test("parts biases every token of a multi-token string", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", "parts unfragment -2");
		expect(output).toContain("Biased 3 token(s)");
		// "un" and "ment" round-trip so they key by text; the BPE-internal
		// fragment does not, so it keys by id.
		expect(storedBias().entries).toEqual({
			un: -2,
			"#61": -2,
			ment: -2,
		});
	});

	test("tokenize shows the breakdown without changing anything", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", "tokenize unfragment");
		expect(output).toContain("is 3 token(s)");
		expect(output).toContain("id     60");
		expect(storedBias().entries).toEqual({});
	});

	test("rejects an id past the vocabulary", async () => {
		const output = await run("logit-bias", "set #999999 3");
		expect(output).toContain("outside this model's vocabulary");
		expect(storedBias().entries).toEqual({});
	});

	test("rejects a bias that is not a number", async () => {
		const output = await run("logit-bias", "set </think> loads");
		expect(output).toContain("Not a bias");
		expect(storedBias().entries).toEqual({});
	});

	test("reports an unknown subcommand", async () => {
		const output = await run("logit-bias", "frobnicate");
		expect(output).toContain("Unknown subcommand");
	});

	test("show reports the effect after the final temperature", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "set </think> 4");
		const output = await run("logit-bias", "show");
		expect(output).toContain("</think> → +4");
		expect(output).toContain("odds at temp");
	});

	test("measure declines cleanly when the confirmation is refused", async () => {
		// ui.confirm returns false in this harness, so this asserts it does not
		// throw and sends nothing.
		await expect(run("logit-bias", "measure")).resolves.toBeString();
	});

	test("off stops sending logit_bias without forgetting the entries", async () => {
		await run("logit-bias", "off");
		expect(storedBias()).toEqual({
			enabled: false,
			entries: { "</think>": 4 },
		});
		await run("logit-bias", "on");
		expect(storedBias().enabled).toBe(true);
	});
});

describe("/think-cap", () => {
	function storedCap(): unknown {
		return JSON.parse(
			fs.readFileSync(path.join(AGENT_DIR, "sampler-profile.json"), "utf8"),
		).thinkCap;
	}

	test("sets a token budget", async () => {
		const output = await run("think-cap", "64");
		expect(output).toContain("64 tokens");
		expect(storedCap()).toBe(64);
	});

	test("1 means no reasoning at all", async () => {
		await run("think-cap", "1");
		expect(storedCap()).toBe(1);
	});

	test("rejects 0, which llama.cpp would silently ignore", async () => {
		await run("think-cap", "64");
		const output = await run("think-cap", "0");
		expect(output).toContain("Use 1");
		expect(storedCap()).toBe(64);
	});

	test("off clears it", async () => {
		await run("think-cap", "off");
		expect(storedCap()).toBeNull();
	});

	test("rejects a nonsense budget", async () => {
		const output = await run("think-cap", "loads");
		expect(output).toContain("not a token budget");
		expect(storedCap()).toBeNull();
	});
});

describe("runaway guidance", () => {
	test("a large bias on the close tag is applied but flagged", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", "set </think> 100");
		// Applied as asked — no clamping.
		expect(
			JSON.parse(
				fs.readFileSync(path.join(AGENT_DIR, "sampler-profile.json"), "utf8"),
			).bias.entries,
		).toEqual({ "</think>": 100 });
		// And the failure mode is explained rather than left to be discovered.
		expect(output).toContain("emitted again and again");
		expect(output).toContain("/think-cap");
	});

	test("/think-less warns past the usable range", async () => {
		const output = await run("think-less", "50");
		expect(output).toContain("past the usable range");
	});

	test("an ordinary large bias on some other token is not flagged", async () => {
		await run("logit-bias", "clear");
		const output = await run("logit-bias", "set delve 100");
		expect(output).not.toContain("/think-cap");
	});
});

describe("before_provider_request", () => {
	async function stamp(
		body: Record<string, unknown>,
	): Promise<Record<string, unknown>> {
		await emit("before_agent_start", {});
		await emit("before_provider_request", { payload: body });
		return body;
	}

	test("stamps the resolved id onto the outgoing body", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "set </think> 4");
		const body = await stamp({ messages: [], model: "qwen-stub" });
		expect(body.logit_bias).toEqual([[204, 4]]);
		// The route is still applied; bias does not replace it.
		expect(body.samplers).toBeArray();
	});

	test("KL presets survive persistence and reach the request with the correct order", async () => {
		for (const [preset, chain, fields] of [
			["kl-star", ["kl_opt", "temperature"], { kl_opt_lambda: 1, kl_opt_global: true, temperature: 1e6 }],
			["kl-star-local", ["kl_opt", "temperature"], { kl_opt_global: false }],
			["kl-budget", ["min_p", "kl_budget"], { min_p: 0.05, kl_budget: 0.1 }],
			["kl-budget-creative", ["dry", "min_p", "kl_budget"], { min_p: 0.02, kl_budget: 0.3 }],
		] as const) {
			await run("sampler-preset", preset);
			const body = await stamp({ messages: [] });
			expect(body.samplers).toEqual([...chain]);
			for (const [key, value] of Object.entries(fields)) expect(body[key]).toBe(value);
			const saved = JSON.parse(fs.readFileSync(path.join(AGENT_DIR, "sampler-profile.json"), "utf8"));
			expect(saved.chain).toEqual([...chain]);
		}
		await run("sampler-preset", "balanced");
	});

	test("auto routing supports both KL methods and enforces the final KL-budget stage", async () => {
		const { CATALOG } = await import("./index");
		const { parseSamplerRoute, buildSamplerRouterSchema } = await import("./router");
		expect(JSON.stringify(buildSamplerRouterSchema(CATALOG))).toContain("kl_budget");
		const valid = parseSamplerRoute({ samplers: [{ id: "kl_opt", values: [1.25, false] }, { id: "temperature", values: [1e6] }], reason: "test" }, CATALOG);
		expect(valid.ok).toBe(true);
		if (valid.ok) expect(valid.route.params.kl_opt_global).toBe(false);
		expect(parseSamplerRoute({ samplers: [{ id: "kl_budget" }, { id: "temperature" }], reason: "test" }, CATALOG).ok).toBe(false);
		expect(parseSamplerRoute({ samplers: [{ id: "min_p" }, { id: "kl_budget", values: [0.2] }], reason: "test" }, CATALOG).ok).toBe(true);
		expect(parseSamplerRoute({ samplers: [{ id: "kl_opt", values: [-1] }], reason: "test" }, CATALOG).ok).toBe(false);
	});

	test("sends nothing once bias is switched off", async () => {
		await run("logit-bias", "off");
		const body = await stamp({ messages: [] });
		expect("logit_bias" in body).toBe(false);
		await run("logit-bias", "on");
	});

	test("a ban goes out as false, which llama.cpp reads as -infinity", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "ban </think>");
		const body = await stamp({ messages: [] });
		expect(body.logit_bias).toEqual([[204, false]]);
	});

	test("applies with the sampler override off, since bias is a separate axis", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "set </think> 5");
		await run("samplers-off", "");
		const body = await stamp({ messages: [] });
		expect(body.logit_bias).toEqual([[204, 5]]);
		expect(body.samplers).toBeUndefined();
		await run("samplers-off", "");
	});

	test("the think cap rides along as thinking_budget_tokens", async () => {
		await run("logit-bias", "clear");
		await run("think-cap", "48");
		const body = await stamp({ messages: [] });
		expect(body.thinking_budget_tokens).toBe(48);
		await run("think-cap", "off");
		const after = await stamp({ messages: [] });
		expect("thinking_budget_tokens" in after).toBe(false);
	});

	test("cap and bias are independent and compose", async () => {
		await run("logit-bias", "clear");
		await run("logit-bias", "set </think> 3");
		await run("think-cap", "128");
		const body = await stamp({ messages: [] });
		expect(body.logit_bias).toEqual([[204, 3]]);
		expect(body.thinking_budget_tokens).toBe(128);
		await run("think-cap", "off");
	});

	test("leaves a non-llama provider alone", async () => {
		const other = { provider: "anthropic", id: "claude", baseUrl: "https://x" };
		const body: Record<string, unknown> = { messages: [] };
		for (const listener of listeners.get("before_provider_request") ?? []) {
			await listener({ payload: body }, { ...ctx, model: other, models: {
				current: () => other,
				resolve: () => other,
			} });
		}
		expect("logit_bias" in body).toBe(false);
	});
});
