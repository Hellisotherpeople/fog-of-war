import { expect, test } from "bun:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { vllmSamplerConfig } from "./vllm";

test("real extension command handlers preserve infinity and ordered custom controls without network", async () => {
 const dir = fs.mkdtempSync(path.join(os.tmpdir(), "omp-vllm-command-"));
 fs.writeFileSync(path.join(dir, "sampler-profile.json"), JSON.stringify({
  enabled: true, mode: "manual", chain: ["min_p"], params: {min_p: 0.1},
  scope: {proxy: false, capture: false, slots: false, jsonl: false},
 }));
 const model = {provider: "glm53-vllm", id: "glm53", baseUrl: "http://127.0.0.1:8800/v1"};
 const listeners = new Map<string, ((e: any, c: any) => any)[]>();
 const commands = new Map<string, (a: string, c: any) => any>();
 const notifications: string[] = [];
 const ctx = {model, models: {current: () => model, resolve: () => model}, hasUI: false,
  ui: {notify: (s: string) => notifications.push(s), setStatus() {}, setWidget() {}}};
 const pi = {logger: {debug() {}, warn() {}},
  on(name: string, fn: (e: any, c: any) => any) {listeners.set(name, [...listeners.get(name) ?? [], fn]);},
  registerCommand(name: string, options: any) {commands.set(name, options.handler);},
  registerTool() {}, getActiveTools: () => [], async setActiveTools() {},
  registerProvider() {throw new Error("Offline command test must not create a proxy");},
  async setModel() {return true;},
  typebox: {Type: new Proxy({}, {get: () => (...args: unknown[]) => ({args})})},
 };
 const before = process.env.PI_CODING_AGENT_DIR;
 process.env.PI_CODING_AGENT_DIR = dir;
 try {
  const entry = "./index.ts?offline-vllm-commands";
  (await import(entry)).default(pi);
 } finally {
  if (before === undefined) delete process.env.PI_CODING_AGENT_DIR;
  else process.env.PI_CODING_AGENT_DIR = before;
 }
 const emit = async (event: string, data = {}) => {
  for (const fn of listeners.get(event) ?? []) await fn(data, ctx);
 };
 try {
  await emit("session_start");
  await commands.get("samplers")!("chain dry top_n_sigma xtc p_less min_k temperature", ctx);
  await commands.get("temp")!("inf", ctx);
  const body: Record<string, unknown> = {model: "glm53", messages: []};
  await emit("before_provider_request", {payload: body});
  expect(vllmSamplerConfig(body)?.chain).toEqual(["dry", "top_n_sigma", "xtc", "p_less", "min_k", "temperature"]);
  expect(vllmSamplerConfig(body)?.params.temperature).toBe("inf");
  expect(body.temperature).toBe(1);
  expect(body.max_tokens).toBeUndefined();
  const saved = JSON.parse(fs.readFileSync(path.join(dir, "sampler-profile.json"), "utf8"));
  expect(saved.params.temperature_infinite).toBe(true);
  expect(saved.params.temperature).toBe(1);
  await commands.get("temp")!("-1", ctx);
  expect(notifications.at(-1)).toContain("nonnegative");
  for (const temp of [10, 1e6, 1e300]) {
   await commands.get("temp")!(String(temp), ctx);
   await emit("before_provider_request", {payload: body});
   expect(vllmSamplerConfig(body)?.params.temperature).toBe(temp);
  }
  await commands.get("samplers")!("show", ctx);
  expect(notifications.at(-1)).toContain("selected order");
 } finally {
  await emit("session_shutdown");
  fs.rmSync(dir, {recursive: true, force: true});
 }
});
