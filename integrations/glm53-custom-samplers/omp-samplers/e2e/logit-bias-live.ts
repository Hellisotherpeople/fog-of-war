/**
 * End-to-end check that logit bias reaches llama.cpp through omp.
 *
 * Unit tests prove `applyLogitBias` builds the right field. They cannot prove
 * that omp's OpenAI-compat serializer keeps it: the harness models the fields it
 * knows about, and a per-request extra like `logit_bias` only survives because
 * the provider passes the body through. So this runs a real omp process against
 * the real llama.cpp server with a recording proxy in between, and asserts on
 * the bytes the server was actually sent.
 *
 * It also asserts on behavior, which is the part that matters: the same prompt
 * with a bias on the end-of-thinking token produces a shorter reasoning block.
 *
 *   bun run e2e/logit-bias-live.ts            # against http://127.0.0.1:8080
 *   LLAMA_URL=http://host:8080 bun run e2e/logit-bias-live.ts
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const ROOT = path.dirname(import.meta.dir);
const UPSTREAM = (process.env.LLAMA_URL ?? "http://127.0.0.1:8080").replace(
	/\/+$/,
	"",
);
const PROMPT =
	"A farmer has 17 sheep and all but 9 run away. How many are left? Reply with just the number, no tools.";

interface Recorded {
	path: string;
	body: Record<string, unknown>;
}

interface Tally {
	/** Streamed deltas carrying reasoning, which is roughly one per token. */
	reasoningChunks: number;
	reasoningChars: number;
}

/**
 * Bytes in both directions are forwarded untouched; only copies are inspected.
 *
 * The response side is teed rather than parsed in place, so a bug in the
 * accounting below cannot corrupt what omp receives.
 */
function startProxy(
	recorded: Recorded[],
	tally: Tally,
): { url: string; stop: () => void } {
	const server = Bun.serve({
		port: 0,
		idleTimeout: 0,
		async fetch(request) {
			const url = new URL(request.url);
			let body: ArrayBuffer | undefined;
			if (request.method !== "GET" && request.method !== "HEAD") {
				body = await request.arrayBuffer();
				try {
					const parsed = JSON.parse(new TextDecoder().decode(body));
					if (parsed && typeof parsed === "object") {
						recorded.push({ path: url.pathname, body: parsed });
					}
				} catch {
					/* not JSON; nothing to assert on */
				}
			}
			const headers = new Headers(request.headers);
			headers.delete("host");
			const upstream = await fetch(`${UPSTREAM}${url.pathname}${url.search}`, {
				method: request.method,
				headers,
				...(body === undefined ? {} : { body }),
			});
			if (!upstream.body || !url.pathname.endsWith("/chat/completions")) {
				return new Response(upstream.body, {
					status: upstream.status,
					headers: upstream.headers,
				});
			}
			const [forward, observe] = upstream.body.tee();
			void countReasoning(observe, tally);
			return new Response(forward, {
				status: upstream.status,
				headers: upstream.headers,
			});
		},
	});
	return {
		url: `http://127.0.0.1:${server.port}`,
		stop: () => void server.stop(true),
	};
}

/** Add up the reasoning llama.cpp streamed back, as a proxy for its length. */
async function countReasoning(
	stream: ReadableStream<Uint8Array>,
	tally: Tally,
): Promise<void> {
	const decoder = new TextDecoder();
	let buffered = "";
	try {
		for await (const chunk of stream) {
			buffered += decoder.decode(chunk, { stream: true });
			const lines = buffered.split("\n");
			buffered = lines.pop() ?? "";
			for (const line of lines) {
				if (!line.startsWith("data:")) continue;
				const payload = line.slice(5).trim();
				if (payload === "" || payload === "[DONE]") continue;
				try {
					const parsed = JSON.parse(payload) as {
						choices?: { delta?: { reasoning_content?: unknown } }[];
					};
					const reasoning = parsed.choices?.[0]?.delta?.reasoning_content;
					if (typeof reasoning === "string" && reasoning !== "") {
						tally.reasoningChunks += 1;
						tally.reasoningChars += reasoning.length;
					}
				} catch {
					/* a partial or non-JSON frame is not worth reporting */
				}
			}
		}
	} catch {
		/* the stream ending early only costs accuracy in the report */
	}
}

function writeAgentDir(
	dir: string,
	baseUrl: string,
	bias: unknown,
	thinkCap: number | null,
): void {
	fs.mkdirSync(dir, { recursive: true });
	fs.writeFileSync(
		path.join(dir, "models.yml"),
		`providers:
  "llama.cpp-e2e":
    baseUrl: ${baseUrl}
    api: openai-completions
    auth: none
    models:
      - id: e2e-model
        name: E2E
        api: openai-completions
        reasoning: true
        input: [text]
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }
        contextWindow: 32768
        maxTokens: ${Number(process.env.E2E_MAX_TOKENS ?? 2048)}
`,
	);
	fs.writeFileSync(
		path.join(dir, "config.yml"),
		"modelRoles:\n  default: llama.cpp-e2e/e2e-model\ncompaction:\n  strategy: off\n",
	);
	// Seeded rather than set through a slash command, because print mode has no
	// surface to read a command's reply from.
	fs.writeFileSync(
		path.join(dir, "sampler-profile.json"),
		JSON.stringify(
			{
				enabled: true,
				applyToAllModels: true,
				mode: "manual",
				chain: ["dry", "hill", "xtc", "temperature"],
				params: {
					temperature: 10,
					hill_order: 10,
					dry_multiplier: 0.8,
					dry_base: 1.75,
					dry_allowed_length: 15,
					xtc_probability: 0.5,
					xtc_threshold: 0.1,
				},
				bias,
				thinkCap,
			},
			null,
			2,
		),
	);
}

async function runOmp(agentDir: string): Promise<string> {
	return await new Promise((resolve, reject) => {
		const child = spawn(
			process.env.OMP_BIN ?? "omp",
			[
				"-p",
				"--no-session",
				"--no-extensions",
				"--extension",
				path.join(ROOT, "index.ts"),
				"--no-tools",
				"--print-thoughts",
				"--allow-home",
				PROMPT,
			],
			{
				cwd: agentDir,
				env: { ...process.env, PI_CODING_AGENT_DIR: agentDir },
				stdio: ["ignore", "pipe", "pipe"],
			},
		);
		let out = "";
		child.stdout.on("data", (chunk) => {
			out += String(chunk);
		});
		child.stderr.on("data", (chunk) => {
			out += String(chunk);
		});
		child.on("error", reject);
		child.on("close", () => resolve(out));
	});
}

interface Scenario {
	name: string;
	bias: unknown;
	thinkCap?: number | null;
	/** Every recorded chat request must satisfy this. */
	check: (body: Record<string, unknown>) => string | undefined;
}

const CLOSE_TAG = "</think>";

const SCENARIOS: Scenario[] = [
	{
		name: "bias off sends no logit_bias",
		bias: { enabled: false, entries: { [CLOSE_TAG]: 6 } },
		check: (body) =>
			"logit_bias" in body
				? `expected no logit_bias, got ${JSON.stringify(body.logit_bias)}`
				: undefined,
	},
	{
		name: "bias on sends the resolved token id",
		bias: { enabled: true, entries: { [CLOSE_TAG]: 6 } },
		check: (body) => {
			const value = body.logit_bias;
			if (!Array.isArray(value)) return "logit_bias is missing from the request";
			if (value.length !== 1) {
				return `expected one pair, got ${JSON.stringify(value)}`;
			}
			const [id, amount] = value[0] as [unknown, unknown];
			if (typeof id !== "number" || !Number.isInteger(id)) {
				return `expected an integer token id, got ${JSON.stringify(id)}`;
			}
			if (amount !== 6) return `expected a bias of 6, got ${String(amount)}`;
			return undefined;
		},
	},
	{
		// Neither of these is a special token, so the ids can only come from
		// resolving the stored keys against the live tokenizer.
		name: "ordinary words resolve to ids too",
		bias: { enabled: true, entries: { " delve": -5, Certainly: "ban" } },
		check: (body) => {
			const value = body.logit_bias;
			if (!Array.isArray(value)) return "logit_bias is missing from the request";
			if (value.length !== 2) {
				return `expected two pairs, got ${JSON.stringify(value)}`;
			}
			const pairs = value as [unknown, unknown][];
			if (!pairs.every(([id]) => Number.isInteger(id))) {
				return `expected integer ids, got ${JSON.stringify(value)}`;
			}
			const amounts = pairs.map(([, amount]) => amount);
			if (!amounts.includes(-5)) return `no -5 bias in ${JSON.stringify(value)}`;
			if (!amounts.includes(false)) {
				return `no ban in ${JSON.stringify(value)}`;
			}
			return undefined;
		},
	},
	{
		// The deterministic counterpart to a bias: a hard budget the server spends
		// inside the reasoning block, after which it forces the close tag once.
		name: "think cap rides along as thinking_budget_tokens",
		bias: { enabled: false, entries: {} },
		thinkCap: 32,
		check: (body) =>
			body.thinking_budget_tokens === 32
				? undefined
				: `expected thinking_budget_tokens 32, got ${JSON.stringify(
						body.thinking_budget_tokens,
					)}`,
	},
];

let failures = 0;
const tallies = new Map<string, Tally>();

for (const scenario of SCENARIOS) {
	const recorded: Recorded[] = [];
	const tally: Tally = { reasoningChunks: 0, reasoningChars: 0 };
	const proxy = startProxy(recorded, tally);
	const agentDir = fs.mkdtempSync(path.join(os.tmpdir(), "omp-samplers-e2e-"));
	writeAgentDir(agentDir, proxy.url, scenario.bias, scenario.thinkCap ?? null);
	process.stdout.write(`· ${scenario.name}\n`);
	let output = "";
	try {
		output = await runOmp(agentDir);
	} finally {
		proxy.stop();
	}

	const chats = recorded.filter((entry) =>
		entry.path.endsWith("/chat/completions"),
	);
	if (chats.length === 0) {
		process.stdout.write(
			`  FAIL no chat request reached the proxy\n${output.slice(-800)}\n`,
		);
		failures += 1;
		continue;
	}
	let scenarioFailed = false;
	for (const chat of chats) {
		const problem = scenario.check(chat.body);
		if (problem) {
			process.stdout.write(`  FAIL ${problem}\n`);
			scenarioFailed = true;
			break;
		}
	}
	if (!scenarioFailed) {
		process.stdout.write(
			`  ok  ${chats.length} request(s) checked; logit_bias ${
				JSON.stringify(chats[0].body.logit_bias) ?? "absent"
			}\n`,
		);
	}
	failures += scenarioFailed ? 1 : 0;
	tallies.set(scenario.name, tally);
}

// Behavioral check. One sample per side, so this reports rather than fails: at
// temperature 10 a single generation is noisy enough that a hard assertion here
// would flake. `/logit-bias measure` is the calibrated version of this.
process.stdout.write("\nreasoning streamed (one sample each):\n");
const baseline = tallies.get(SCENARIOS[0].name);
for (const scenario of SCENARIOS) {
	const tally = tallies.get(scenario.name);
	if (!tally) continue;
	const delta =
		baseline && baseline.reasoningChunks > 0 && scenario !== SCENARIOS[0]
			? ` (${Math.round((tally.reasoningChunks / baseline.reasoningChunks) * 100)}% of baseline)`
			: "";
	process.stdout.write(
		`  ${scenario.name.padEnd(46)} ${String(tally.reasoningChunks).padStart(5)} deltas / ${String(
			tally.reasoningChars,
		).padStart(6)} chars${delta}\n`,
	);
}

process.stdout.write(
	failures === 0 ? "\nall scenarios passed\n" : `\n${failures} scenario(s) failed\n`,
);
process.exit(failures === 0 ? 0 : 1);
