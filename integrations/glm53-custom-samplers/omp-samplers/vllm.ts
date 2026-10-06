import type { SamplerRoute } from "./router";

export function isVllmModel(model: { provider?: string } | undefined): boolean {
	return model?.provider?.toLowerCase().includes("vllm") ?? false;
}

export const VLLM_KNOBS: Record<string, readonly string[]> = {
	dry: ["dry_multiplier", "dry_base", "dry_allowed_length", "dry_penalty_last_n"],
	xtc: ["xtc_probability", "xtc_threshold"],
	top_n_sigma: ["top_n_sigma"],
	p_less: ["p_less_exponent", "p_less_norm"],
	min_k: ["min_k_tau"],
	min_p: ["min_p"], top_p: ["top_p"], top_k: ["top_k"],
	temperature: ["temperature"],
	penalties: ["repeat_penalty", "repeat_last_n", "presence_penalty", "frequency_penalty"],
};
export const VLLM_SAMPLERS = new Set(Object.keys(VLLM_KNOBS));
export const VLLM_CONFIG_KEY = "omp_sampler_config";

export function parseVllmTemperature(raw: string): number {
	if (/^(?:\+?inf(?:inity)?|∞)$/i.test(raw.trim())) return Infinity;
	const n = Number(raw);
	if (!raw.trim() || !Number.isFinite(n) || n < 0) throw new Error("Temperature must be nonnegative or inf");
	return n;
}

/** All stages run in the selected order. Native vLLM sampling remains neutral. */
export function applyVllmSamplerRoute(body: Record<string, unknown>, route: SamplerRoute): void {
	const unsupported = route.chain.filter((id) => !VLLM_SAMPLERS.has(id));
	if (unsupported.length) throw new Error(`Unsupported vLLM samplers: ${unsupported.join(", ")}`);
	if (route.chain.length > 32) throw new Error("At most 32 sampler stages are supported");
	if (route.chain.includes("temperature") && Number(route.params.dynatemp_range ?? 0) !== 0) {
		throw new Error("Dynamic temperature is not ported; set dynatemp_range to 0");
	}
	const params: Record<string, number | boolean | string> = {};
	for (const stage of route.chain) {
		for (const key of VLLM_KNOBS[stage]) {
			const value = route.params[key];
			if (value === undefined) continue;
			if (key === "temperature" && route.params.temperature_infinite === true) params[key] = "inf";
			else if (key === "p_less_norm" && typeof value === "boolean") params[key] = value;
			else if (typeof value === "number" && Number.isFinite(value)) params[key] = value;
			else throw new Error(`Invalid vLLM sampler parameter ${key}`);
		}
	}
	if (route.chain.includes("temperature") && route.params.temperature_infinite === true) params.temperature = "inf";
	const extra = body.vllm_xargs;
	const xargs = extra && typeof extra === "object" && !Array.isArray(extra) ? { ...extra } : {};
	Object.assign(body, {
		temperature: 1, min_p: 0, top_p: 1, top_k: -1,
		repetition_penalty: 1, presence_penalty: 0, frequency_penalty: 0,
		vllm_xargs: { ...xargs, [VLLM_CONFIG_KEY]: JSON.stringify({ version: 1, chain: route.chain, params }) },
	});
	delete body.samplers;
}

export function vllmSamplerConfig(body: Record<string, unknown>): { version: 1; chain: string[]; params: Record<string, number | boolean | string> } | undefined {
	const extra = body.vllm_xargs as Record<string, unknown> | undefined;
	if (!extra || typeof extra[VLLM_CONFIG_KEY] !== "string") return undefined;
	try {
		const parsed = JSON.parse(extra[VLLM_CONFIG_KEY]);
		if (parsed.version === 1 && Array.isArray(parsed.chain) && parsed.params && typeof parsed.params === "object") return parsed;
	} catch { /* A bad request is rejected by the server, not misrepresented in telemetry. */ }
	return undefined;
}

export function vllmSamplerChain(body: Record<string, unknown>): string[] {
	const custom = vllmSamplerConfig(body);
	if (custom) return custom.chain;
	const chain: string[] = [];
	if (Number(body.repetition_penalty ?? 1) !== 1 || Number(body.presence_penalty ?? 0) !== 0 || Number(body.frequency_penalty ?? 0) !== 0) chain.push("penalties");
	if (Number(body.temperature ?? 1) !== 1) chain.push("temperature");
	if (Number(body.top_k ?? -1) > 0) chain.push("top_k");
	if (Number(body.top_p ?? 1) < 1) chain.push("top_p");
	if (Number(body.min_p ?? 0) > 0) chain.push("min_p");
	return chain;
}
