/**
 * A pass-through recording proxy for the local llama.cpp server.
 *
 * omp's provider layer parses the OpenAI-compatible stream and discards
 * anything it does not model — including `logprobs`. The extension therefore
 * cannot read per-token probabilities from any event it receives. Sitting a
 * loopback proxy between omp and llama-server solves that without touching
 * omp's parsing: response bytes are forwarded verbatim and a copy of
 * the response stream is fed to the telemetry parser.
 *
 * An optional vLLM transform applies the sampler profile to compaction requests.
 * Transform errors reject the request; telemetry hooks are isolated so recording
 * failures never change the model response. Without a transform, request bytes
 * pass through unchanged.
 */

import http from "node:http";
import https from "node:https";
import type { AddressInfo } from "node:net";

export interface ProxyRequestInfo {
	id: number;
	method: string;
	path: string;
	/** Parsed JSON request body, when the body was JSON. */
	body?: Record<string, unknown>;
	startedAt: number;
}

export interface ProxyResponseInfo {
	id: number;
	status: number;
	/** True when the response was `text/event-stream`. */
	streamed: boolean;
	endedAt: number;
	error?: string;
}

export interface ProxyHooks {
	onRequest?(info: ProxyRequestInfo): void;
	/** One SSE `data:` payload, or the whole body for non-streamed responses. */
	onPayload?(id: number, payload: string): void;
	onResponse?(info: ProxyResponseInfo): void;
	onError?(error: Error): void;
}

export interface RecordingProxy {
	/** Base URL callers should point the provider at. */
	url: string;
	port: number;
	upstream: string;
	close(): Promise<void>;
}

const HOP_BY_HOP = new Set([
	"connection",
	"keep-alive",
	"proxy-authenticate",
	"proxy-authorization",
	"te",
	"trailer",
	"transfer-encoding",
	"upgrade",
	"host",
	"content-length",
]);

function filterHeaders(
	headers: http.IncomingHttpHeaders,
): Record<string, string | string[]> {
	const out: Record<string, string | string[]> = {};
	for (const [key, value] of Object.entries(headers)) {
		if (value === undefined) continue;
		if (HOP_BY_HOP.has(key.toLowerCase())) continue;
		out[key] = value;
	}
	return out;
}

/**
 * Split a possibly-partial SSE buffer into complete `data:` payloads. Kept
 * local to the proxy so the hot path does no allocation beyond the payloads
 * themselves; {@link ../capture.SseSplitter} is the reusable version.
 */
class DataFramer {
	#buffer = "";

	push(chunk: string, emit: (payload: string) => void): void {
		this.#buffer += chunk;
		for (;;) {
			const lf = this.#buffer.indexOf("\n\n");
			const crlf = this.#buffer.indexOf("\r\n\r\n");
			const at = lf < 0 ? crlf : crlf < 0 ? lf : Math.min(lf, crlf);
			if (at < 0) return;
			const frame = this.#buffer.slice(0, at);
			this.#buffer = this.#buffer.slice(
				this.#buffer.startsWith("\r\n\r\n", at) ? at + 4 : at + 2,
			);
			const data: string[] = [];
			for (const line of frame.split(/\r?\n/)) {
				if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
			}
			if (data.length > 0) emit(data.join("\n"));
		}
	}
}

/**
 * Start the proxy on an ephemeral loopback port.
 *
 * @param upstream Base URL of the real llama.cpp server, e.g. `http://127.0.0.1:8080`.
 */
export async function startRecordingProxy(options: {
	upstream: string;
	hooks?: ProxyHooks;
	/** Optional sampler transform; unlike telemetry hooks, errors reject the request. */
	transformRequest?: (body: Record<string, unknown>) => void;
	/** Maximum buffered request size. Oversize requests receive HTTP 413. */
	maxBodyBytes?: number;
}): Promise<RecordingProxy> {
	const upstream = new URL(options.upstream);
	const hooks = options.hooks ?? {};
	const maxBodyBytes = options.maxBodyBytes ?? 64 * 1024 * 1024;
	const transport = upstream.protocol === "https:" ? https : http;
	let nextId = 1;

	const safe = (fn: () => void): void => {
		try {
			fn();
		} catch (error) {
			hooks.onError?.(
				error instanceof Error ? error : new Error(String(error)),
			);
		}
	};

	const server = http.createServer((req, res) => {
		const id = nextId++;
		const startedAt = Date.now();
		const chunks: Buffer[] = [];
		let bodyBytes = 0;

		req.on("data", (chunk: Buffer) => {
			bodyBytes += chunk.length;
			if (bodyBytes <= maxBodyBytes) chunks.push(chunk);
		});

		req.on("error", () => {
			// Client hung up mid-upload; nothing to forward.
			res.destroy();
		});

		req.on("end", () => {
			if (bodyBytes > maxBodyBytes) {
				res.writeHead(413, { "content-type": "application/json" });
				res.end(JSON.stringify({ error: "Request exceeds sampler proxy buffer limit" }));
				return;
			}
			let body = Buffer.concat(chunks);
			let parsedBody: Record<string, unknown> | undefined;
			if (body.length > 0 && body.length <= maxBodyBytes) {
				try {
					const parsed: unknown = JSON.parse(body.toString("utf8"));
					if (
						typeof parsed === "object" &&
						parsed !== null &&
						!Array.isArray(parsed)
					) {
						parsedBody = parsed as Record<string, unknown>;
					}
				} catch {
					/* not JSON — forwarded untouched, just not recorded */
				}
			}
			if (parsedBody && req.method === "POST" && /\/(chat\/)?completions(?:\?|$)/.test(req.url ?? "")) {
				try {
					if (options.transformRequest) {
						options.transformRequest(parsedBody);
						body = Buffer.from(JSON.stringify(parsedBody));
					}
				} catch (error) {
					res.writeHead(400, { "content-type": "application/json" });
					res.end(JSON.stringify({ error: error instanceof Error ? error.message : String(error) }));
					return;
				}
			}
			safe(() =>
				hooks.onRequest?.({
					id,
					method: req.method ?? "GET",
					path: req.url ?? "/",
					body: parsedBody,
					startedAt,
				}),
			);

			const headers = filterHeaders(req.headers);
			if (body.length > 0) headers["content-length"] = String(body.length);

			const basePath = upstream.pathname.replace(/\/$/, "");
			const upstreamRequest = transport.request(
				{
					protocol: upstream.protocol,
					hostname: upstream.hostname,
					port: upstream.port || (upstream.protocol === "https:" ? 443 : 80),
					method: req.method,
					path: `${basePath}${req.url ?? "/"}`,
					headers,
				},
				(upstreamResponse) => {
					const status = upstreamResponse.statusCode ?? 502;
					res.writeHead(status, upstreamResponse.headers);
					const contentType = String(
						upstreamResponse.headers["content-type"] ?? "",
					);
					const streamed = contentType.includes("text/event-stream");
					const framer = new DataFramer();
					const buffered: Buffer[] = [];
					let bufferedBytes = 0;

					upstreamResponse.on("data", (chunk: Buffer) => {
						res.write(chunk);
						safe(() => {
							if (streamed) {
								framer.push(chunk.toString("utf8"), (payload) =>
									hooks.onPayload?.(id, payload),
								);
							} else if (bufferedBytes + chunk.length <= maxBodyBytes) {
								buffered.push(chunk);
								bufferedBytes += chunk.length;
							}
						});
					});

					upstreamResponse.on("end", () => {
						res.end();
						safe(() => {
							if (!streamed && buffered.length > 0) {
								hooks.onPayload?.(id, Buffer.concat(buffered).toString("utf8"));
							}
							hooks.onResponse?.({ id, status, streamed, endedAt: Date.now() });
						});
					});

					upstreamResponse.on("error", (error) => {
						res.destroy();
						safe(() =>
							hooks.onResponse?.({
								id,
								status,
								streamed,
								endedAt: Date.now(),
								error: error.message,
							}),
						);
					});
				},
			);

			upstreamRequest.on("error", (error) => {
				if (!res.headersSent) {
					res.writeHead(502, { "content-type": "application/json" });
					res.end(
						JSON.stringify({
							error: {
								message: `omp-samplers proxy: upstream request failed: ${error.message}`,
								type: "proxy_error",
							},
						}),
					);
				} else {
					res.destroy();
				}
				safe(() =>
					hooks.onResponse?.({
						id,
						status: 502,
						streamed: false,
						endedAt: Date.now(),
						error: error.message,
					}),
				);
			});

			// Propagate client aborts upstream so llama.cpp frees its slot.
			res.on("close", () => {
				if (!res.writableEnded) upstreamRequest.destroy();
			});

			if (body.length > 0) upstreamRequest.write(body);
			upstreamRequest.end();
		});
	});

	server.on("clientError", (_error, socket) => {
		socket.destroy();
	});

	await new Promise<void>((resolve, reject) => {
		server.once("error", reject);
		server.listen(0, "127.0.0.1", () => {
			server.off("error", reject);
			resolve();
		});
	});

	const address = server.address() as AddressInfo;
	const port = address.port;
	// Never let the proxy keep the process alive on shutdown.
	server.unref();

	return {
		url: `http://127.0.0.1:${port}`,
		port,
		upstream: options.upstream,
		close: () =>
			new Promise<void>((resolve) => {
				server.closeAllConnections?.();
				server.close(() => resolve());
			}),
	};
}
