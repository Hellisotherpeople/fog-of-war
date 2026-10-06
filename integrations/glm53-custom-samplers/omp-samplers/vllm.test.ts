import { describe, expect, test } from "bun:test";
import { applyVllmSamplerRoute, isVllmModel, vllmSamplerConfig, parseVllmTemperature } from "./vllm";

describe("vLLM sampler translation", () => {
	test("a min-p-only profile ignores every inactive saved knob", () => {
		const body: Record<string, unknown> = { messages: [], min_p: 0.05, top_p: 0.9 };
		applyVllmSamplerRoute(body, { chain: ["min_p"], params: {
			min_p: 0.1, top_p: 0.95, top_k: 20, temperature: 1e6,
			repeat_penalty: 1.2, dry_multiplier: 0.8, top_n_sigma: 1,
		}, reason: "test" });
		expect(body.temperature).toBe(1);
		expect(body.min_p).toBe(0);
		expect(body.top_p).toBe(1);
		expect(body.top_k).toBe(-1);
		expect(vllmSamplerConfig(body)).toEqual({version: 1, chain: ["min_p"], params: { min_p: 0.1 }});
	});

	test("only selected native stages translate, including the penalty spelling", () => {
		const body: Record<string, unknown> = {};
		applyVllmSamplerRoute(body, { chain: ["penalties", "temperature", "top_k"],
			params: { repeat_penalty: 1.2, temperature: 0.7, top_k: 0, min_p: 0.5 }, reason: "test" });
		expect(body.repetition_penalty).toBe(1);
		expect(body.temperature).toBe(1);
		expect(body.top_k).toBe(-1);
		expect(body.min_p).toBe(0);
		expect(vllmSamplerConfig(body)?.params).toEqual({ repeat_penalty: 1.2, temperature: 0.7, top_k: 0 });
		expect(vllmSamplerConfig(body)?.chain).toEqual(["penalties", "temperature", "top_k"]);
	});

	test("unsupported custom samplers fail explicitly", () => {
		expect(() => applyVllmSamplerRoute({}, { chain: ["hill"], params: {}, reason: "test" })).toThrow("Unsupported vLLM samplers");
	});

	test("backend identity does not depend on the proxy port or model family", () => {
		expect(isVllmModel({ provider: "glm53-vllm" })).toBe(true);
		expect(isVllmModel({ provider: "llama.cpp" })).toBe(false);
	});
});


test("custom sampler chain and exact infinity survive JSON serialization", () => {
 const body: Record<string, unknown> = { vllm_xargs: { unrelated: 7 }, max_tokens: 17 };
 const chain = ["dry", "top_n_sigma", "min_k", "p_less", "xtc", "temperature"];
 applyVllmSamplerRoute(body, {chain, reason: "test", params: {
  dry_multiplier: 0.8, top_n_sigma: 1, min_k_tau: 3, p_less_exponent: 3,
  p_less_norm: true, xtc_probability: 0.5, temperature: 1, temperature_infinite: true,
  top_p: 0.9, top_k: 20, min_p: 0.1,
 }});
 const roundtrip = JSON.parse(JSON.stringify(body));
 expect(vllmSamplerConfig(roundtrip)?.params.temperature).toBe("inf");
 expect(vllmSamplerConfig(roundtrip)?.chain).toEqual(chain);
 expect(vllmSamplerConfig(roundtrip)?.params.top_p).toBeUndefined();
 expect(roundtrip.vllm_xargs.unrelated).toBe(7);
 expect(roundtrip.max_tokens).toBe(17);
 for (const raw of ["inf", "Infinity", "∞", "+inf"]) expect(parseVllmTemperature(raw)).toBe(Infinity);
 for (const n of [2, 10, 1e6, 1e300]) expect(parseVllmTemperature(String(n))).toBe(n);
 for (const raw of ["NaN", "-1", "1e999", ""]) expect(() => parseVllmTemperature(raw)).toThrow();
});
