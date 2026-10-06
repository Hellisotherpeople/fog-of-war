import { afterEach, describe, expect, test } from "bun:test";
import http from "node:http";
import type { AddressInfo } from "node:net";
import { startRecordingProxy } from "./proxy";

interface Upstream {
	url: string;
	requests: { path: string; body: string; headers: http.IncomingHttpHeaders }[];
	close(): Promise<void>;
}

async function startUpstream(
	handler: (
		req: http.IncomingMessage,
		res: http.ServerResponse,
		body: string,
	) => void,
): Promise<Upstream> {
	const requests: Upstream["requests"] = [];
	const server = http.createServer((req, res) => {
		const chunks: Buffer[] = [];
		req.on("data", (chunk: Buffer) => chunks.push(chunk));
		req.on("end", () => {
			const body = Buffer.concat(chunks).toString("utf8");
			requests.push({ path: req.url ?? "", body, headers: req.headers });
			handler(req, res, body);
		});
	});
	await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
	const { port } = server.address() as AddressInfo;
	return {
		url: `http://127.0.0.1:${port}`,
		requests,
		close: () => new Promise<void>((resolve) => server.close(() => resolve())),
	};
}

const cleanups: (() => Promise<void>)[] = [];
afterEach(async () => {
	for (const cleanup of cleanups.splice(0)) await cleanup();
});

describe("recording proxy", () => {
	test("forwards a streamed response verbatim while capturing every payload", async () => {
		const upstream = await startUpstream((_req, res) => {
			res.writeHead(200, { "content-type": "text/event-stream" });
			res.write('data: {"a":1}\n\n');
			res.write('data: {"b":');
			res.write("2}\n\ndata: [DONE]\n\n");
			res.end();
		});
		cleanups.push(upstream.close);

		const payloads: string[] = [];
		const requests: string[] = [];
		let responded: { status: number; streamed: boolean } | undefined;
		const proxy = await startRecordingProxy({
			upstream: upstream.url,
			hooks: {
				onRequest: (info) => requests.push(info.path),
				onPayload: (_id, payload) => payloads.push(payload),
				onResponse: (info) => {
					responded = { status: info.status, streamed: info.streamed };
				},
			},
		});
		cleanups.push(proxy.close);

		const response = await fetch(`${proxy.url}/v1/chat/completions`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ model: "m", samplers: ["hill"], n_probs: 20 }),
		});
		const text = await response.text();

		expect(response.status).toBe(200);
		expect(text).toBe('data: {"a":1}\n\ndata: {"b":2}\n\ndata: [DONE]\n\n');
		expect(payloads).toEqual(['{"a":1}', '{"b":2}', "[DONE]"]);
		expect(requests).toEqual(["/v1/chat/completions"]);
		expect(responded).toEqual({ status: 200, streamed: true });
		expect(upstream.requests[0].path).toBe("/v1/chat/completions");
		expect(JSON.parse(upstream.requests[0].body).samplers).toEqual(["hill"]);
	});

	test("exposes the parsed request body to the recorder", async () => {
		const upstream = await startUpstream((_req, res) => {
			res.writeHead(200, { "content-type": "application/json" });
			res.end(JSON.stringify({ content: "hi" }));
		});
		cleanups.push(upstream.close);

		let seen: Record<string, unknown> | undefined;
		const bodies: string[] = [];
		const proxy = await startRecordingProxy({
			upstream: upstream.url,
			hooks: {
				onRequest: (info) => {
					seen = info.body;
				},
				onPayload: (_id, payload) => bodies.push(payload),
			},
		});
		cleanups.push(proxy.close);

		await fetch(`${proxy.url}/completion`, {
			method: "POST",
			body: JSON.stringify({ prompt: "x", post_sampling_probs: true }),
			headers: { "content-type": "application/json" },
		});

		expect(seen?.post_sampling_probs).toBe(true);
		// Non-streamed bodies arrive as one payload.
		expect(bodies).toEqual(['{"content":"hi"}']);
	});

	test("a recording hook that throws never breaks the response", async () => {
		const upstream = await startUpstream((_req, res) => {
			res.writeHead(200, { "content-type": "text/event-stream" });
			res.end("data: ok\n\n");
		});
		cleanups.push(upstream.close);

		const errors: string[] = [];
		const proxy = await startRecordingProxy({
			upstream: upstream.url,
			hooks: {
				onPayload: () => {
					throw new Error("recorder exploded");
				},
				onError: (error) => errors.push(error.message),
			},
		});
		cleanups.push(proxy.close);

		const response = await fetch(`${proxy.url}/v1/chat/completions`, {
			method: "POST",
		});
		expect(await response.text()).toBe("data: ok\n\n");
		expect(errors).toEqual(["recorder exploded"]);
	});

	test("upstream failures surface as a readable 502 instead of a hang", async () => {
		const proxy = await startRecordingProxy({ upstream: "http://127.0.0.1:1" });
		cleanups.push(proxy.close);
		const response = await fetch(`${proxy.url}/v1/chat/completions`, {
			method: "POST",
			body: "{}",
		});
		expect(response.status).toBe(502);
		expect(await response.text()).toContain("omp-samplers proxy");
	});

	test("upstream status and headers are preserved", async () => {
		const upstream = await startUpstream((_req, res) => {
			res.writeHead(429, {
				"content-type": "application/json",
				"x-thing": "yes",
			});
			res.end('{"error":"slow down"}');
		});
		cleanups.push(upstream.close);
		const proxy = await startRecordingProxy({ upstream: upstream.url });
		cleanups.push(proxy.close);

		const response = await fetch(`${proxy.url}/v1/chat/completions`, {
			method: "POST",
		});
		expect(response.status).toBe(429);
		expect(response.headers.get("x-thing")).toBe("yes");
	});
});
