/**
 * Per-prompt sampler control for oh-my-pi + local llama.cpp (mink build).
 *
 * Supports both a hand-tuned profile and an automatic "sampling router". In
 * auto mode the active LLM first makes a schema-constrained tool call that
 * chooses, orders, and configures samplers for the prompt. That validated route
 * is then injected into every answer request in the agent run.
 *
 * How it works: llama.cpp's OpenAI-compatible endpoint honors a per-request
 * `samplers` array and individual sampler params. The first normal agent turn is
 * forced to call the internal routing tool; the tool validates and stores the
 * route. omp's `before_provider_request` event then stamps it into the follow-up
 * answer body before serialization.
 *
 * Entry points (type `/` to see them):
 *   /samplers        - open the menu; `/samplers auto|manual|show` also works
 *   /samplers-auto   - toggle model-selected routing per prompt
 *   /samplers-rationale - toggle the optional route explanation
 *   /sampler-preset  - jump straight to the preset picker
 *   /temp            - quick-set temperature (arg or dropdown)
 *   /samplers-off    - toggle the override on/off
 *   /sampler-scope   - live telemetry: truncation width, logprobs, throughput
 *   /sampler-probe   - measure one distribution before and after the chain
 *   /logit-bias      - bias any individual token up, down, or out
 *   /think-less      - upweight the model's end-of-thinking token
 *   /think-cap       - hard-limit tokens inside the reasoning block
 *
 * Config persists to  $PI_CODING_AGENT_DIR/sampler-profile.json  (default
 * ~/.omp/agent/sampler-profile.json) so your choice survives restarts. Detected
 * special tokens are cached beside it in sampler-tokens.json, per model.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { applyVllmSamplerRoute, isVllmModel, VLLM_SAMPLERS, VLLM_KNOBS, parseVllmTemperature } from "./vllm";
import type {
	ExtensionAPI,
	ExtensionCommandContext,
	ExtensionContext,
} from "@oh-my-pi/pi-coding-agent";
import {
	applyLogitBias,
	applyThinkCap,
	BIAS_RUNAWAY_HINT,
	type BiasConfig,
	biasKeyFor,
	biasOddsMultiplier,
	clearBias,
	countCloseTags,
	diffAppliedBias,
	formatBiasAmount,
	loadBiasConfig,
	parseBiasAmount,
	MIN_THINK_CAP,
	parseThinkCap,
	resolveBiasEntries,
	setBias,
	splitReferenceAndAmount,
	summarizeBias,
	THINK_LESS_LEVELS,
	THINK_RUNAWAY_NOTE,
	thinkLessLevel,
	unquote,
} from "./bias";
import {
	applySamplerRoute,
	buildSamplerRouterPrompt,
	buildSamplerRouterSchema,
	DEFAULT_MAX_ROUTED_SAMPLERS,
	parseSamplerRoute,
	prepareSamplerRouterRequest,
	type RouterKnob,
	type RouterSamplerDef,
	removeSamplerRouterTool,
	type SamplerRoute,
} from "./router";
import type { Paint } from "./scope/charts";
import { diffSamplerParams, slotParams } from "./scope/llama";
import {
	estimateProbeRequests,
	type ProbeResult,
	probeSamplerSupport,
	runProbe,
} from "./scope/probe";
import {
	renderAggregate,
	renderCapabilities,
	renderExtremes,
	renderGenerationReport,
	renderLiveWidget,
	renderProbeReport,
	renderProbeStep,
	renderRankSteps,
	renderSessionWidthHistogram,
	renderStatus,
	renderTokenDetail,
	summarizeGeneration,
} from "./scope/report";
import {
	DEFAULT_SCOPE_CONFIG,
	SamplerScope,
	type ScopeConfig,
} from "./scope/runtime";
import {
	detectSpecialTokens,
	findThinkCloseToken,
	resolveLiteralToken,
	resolveTokenReference,
	type SpecialToken,
	type SpecialTokenSet,
	TokenSetCache,
	tokenizeWithPieces,
	tokenSetKey,
	withAddedTokens,
} from "./tokens";

// ---------------------------------------------------------------------------
// Sampler catalog: the vocabulary the mink llama.cpp build accepts in the
// per-request `samplers` array, plus each sampler's tunable knob(s). Knob keys
// and defaults were read from the live server's /props.
// ---------------------------------------------------------------------------

type Knob = RouterKnob;
type SamplerDef = RouterSamplerDef;

export const CATALOG: SamplerDef[] = [
	{
		id: "dry",
		label: "dry — DRY repetition penalty",
		blurb: "Penalizes verbatim n-gram repetition.",
		knobs: [
			{
				key: "dry_multiplier",
				label: "multiplier",
				kind: "float",
				def: 0.8,
				presets: [0, 0.5, 0.8, 1.0],
				min: 0,
				max: 10,
			},
			{
				key: "dry_base",
				label: "base",
				kind: "float",
				def: 1.75,
				presets: [1.5, 1.75, 2.0],
				min: 1,
				max: 10,
			},
			{
				key: "dry_allowed_length",
				label: "allowed length",
				kind: "int",
				def: 15,
				presets: [2, 5, 10, 15],
				min: 0,
				max: 8192,
			},
			{
				key: "dry_penalty_last_n",
				label: "penalty last n",
				kind: "int",
				def: -1,
				presets: [-1, 0, 64, 256],
				min: -1,
				max: 1048576,
			},
		],
	},
	{
		id: "penalties",
		label: "penalties — repeat/freq/presence",
		blurb: "Classic repetition, frequency and presence penalties.",
		knobs: [
			{
				key: "repeat_penalty",
				label: "repeat penalty",
				kind: "float",
				def: 1.0,
				presets: [1.0, 1.05, 1.1, 1.2],
				min: 0,
				max: 10,
			},
			{
				key: "repeat_last_n",
				label: "repeat last n",
				kind: "int",
				def: 64,
				presets: [0, 64, 128, 256],
				min: -1,
				max: 1048576,
			},
			{
				key: "frequency_penalty",
				label: "frequency penalty",
				kind: "float",
				def: 0,
				presets: [0, 0.5, 1.0],
				min: -2,
				max: 2,
			},
			{
				key: "presence_penalty",
				label: "presence penalty",
				kind: "float",
				def: 0,
				presets: [0, 0.5, 1.0],
				min: -2,
				max: 2,
			},
		],
	},
	{
		id: "top_k",
		label: "top_k — keep K most likely",
		blurb: "Hard cap on candidate count. 0 disables.",
		knobs: [
			{
				key: "top_k",
				label: "k",
				kind: "int",
				def: 20,
				presets: [0, 20, 40, 80, 100],
				min: 0,
				max: 10000,
			},
		],
	},
	{
		id: "top_p",
		label: "top_p — nucleus",
		blurb: "Keep smallest set with cumulative prob ≥ p.",
		knobs: [
			{
				key: "top_p",
				label: "p",
				kind: "float",
				def: 0.95,
				presets: [0.8, 0.9, 0.95, 0.99, 1.0],
				min: 0,
				max: 1,
			},
		],
	},
	{
		id: "min_p",
		label: "min_p — relative floor",
		blurb: "Drop tokens below p × top-token prob.",
		knobs: [
			{
				key: "min_p",
				label: "p",
				kind: "float",
				def: 0.05,
				presets: [0, 0.02, 0.05, 0.1],
				min: 0,
				max: 1,
			},
		],
	},
	{
		id: "typ_p",
		label: "typ_p — locally typical",
		blurb: "Keep tokens near the distribution's entropy.",
		knobs: [
			{
				key: "typical_p",
				label: "p",
				kind: "float",
				def: 1.0,
				presets: [0.5, 0.9, 0.95, 1.0],
				min: 0,
				max: 1,
			},
		],
	},
	{
		id: "top_n_sigma",
		label: "top_n_sigma — logit σ gate",
		blurb: "Keep logits within N standard deviations. -1 disables.",
		knobs: [
			{
				key: "top_n_sigma",
				label: "n",
				kind: "float",
				def: -1,
				presets: [-1, 1, 2, 3],
				min: -1,
				max: 20,
			},
		],
	},
	{
		id: "xtc",
		label: "xtc — exclude top choices",
		blurb:
			"Probabilistically drops the most-predictable head (creativity engine).",
		knobs: [
			{
				key: "xtc_probability",
				label: "probability",
				kind: "float",
				def: 0.5,
				presets: [0, 0.25, 0.5, 0.75, 1.0],
				min: 0,
				max: 1,
			},
			{
				key: "xtc_threshold",
				label: "threshold",
				kind: "float",
				def: 0.1,
				presets: [0.05, 0.1, 0.15, 0.2],
				min: 0,
				max: 1,
			},
		],
	},
	{
		id: "min_k",
		label: "min_k — raw-logit cliff (custom)",
		blurb: "Temperature-invariant semantic cliff; tightest gate.",
		knobs: [
			{
				key: "min_k_tau",
				label: "tau",
				kind: "float",
				def: 3.0,
				presets: [1, 2, 3, 4, 5],
				min: 0,
				max: 20,
			},
		],
	},
	{
		id: "p_less",
		label: "p_less — collision-prob gate (custom)",
		blurb: "Keep p ≥ Σpᵢ^q. Higher exponent → wider/more creative.",
		knobs: [
			{
				key: "p_less_exponent",
				label: "exponent q",
				kind: "float",
				def: 2.0,
				presets: [1.5, 2, 3, 4],
				min: 0.1,
				max: 20,
			},
			{
				key: "p_less_norm",
				label: "normalize",
				kind: "bool",
				def: false,
				presets: [true, false],
			},
		],
	},
	{
		id: "top_h",
		label: "top_h — entropy head (custom)",
		blurb:
			"Keep smallest head with entropy ≤ α·H(p). α≈0.45 is the temp-10 sweet spot.",
		knobs: [
			{
				key: "top_h_alpha",
				label: "alpha",
				kind: "float",
				def: 0.4,
				presets: [0.3, 0.4, 0.45, 0.5, 0.6],
				min: 0,
				max: 1,
			},
		],
	},
	{
		id: "hill",
		label: "hill — Hill-number keep (custom)",
		blurb:
			"Keep ⌈D_q⌉ tokens. HIGHER q → FEWER tokens / more restrictive; q≈3 coherent+vivid at temp 10.",
		knobs: [
			{
				key: "hill_order",
				label: "order q",
				kind: "float",
				def: 3.0,
				presets: [1.5, 2, 3, 4, 6, 10],
				min: 0.1,
				max: 100,
			},
		],
	},
	{
		id: "geo_mean",
		label: "geo_mean — geometric-mean gate (custom)",
		blurb: "Keep pᵢ ≥ coeff·e^{-H}. coeff≈0.7 is a good creative width.",
		knobs: [
			{
				key: "geo_mean_coeff",
				label: "coeff",
				kind: "float",
				def: 1.0,
				presets: [0.5, 0.7, 1.0, 1.5],
				min: 0,
				max: 20,
			},
		],
	},
	{
		id: "robust_z",
		label: "robust_z — median+MAD gate (custom)",
		blurb: "Keep logits ≥ median + c·MAD.",
		knobs: [
			{
				key: "robust_z_coeff",
				label: "coeff c",
				kind: "float",
				def: 3.0,
				presets: [1, 2, 3],
				min: 0,
				max: 20,
			},
		],
	},
	{
		id: "otsu",
		label: "otsu — variance-max split (custom)",
		blurb: "Otsu logit bipartition. Wide; better at lower temp.",
		knobs: [],
	},
	{
		id: "kneedle",
		label: "kneedle — elbow cut (custom)",
		blurb: "Max-curvature elbow. Wide; better at lower temp.",
		knobs: [],
	},
	{
		id: "top_gap",
		label: "top_gap — largest logit gap (custom)",
		blurb: "Cut at the biggest logit gap. Tight/borderline.",
		knobs: [],
	},
	{
		id: "kl_budget",
		label: "kl_budget — maximum entropy within a KL budget",
		blurb: "Experimental: flatten the incoming distribution as far as KL(q||p) <= budget allows. Apply LAST after a plausibility gate such as min_p; no temperature afterward.",
		knobs: [
			{ key: "kl_budget", label: "KL budget (nats)", kind: "float", def: 0.1, presets: [0, 0.05, 0.1, 0.2, 0.3, 0.5], min: 0, max: 2 },
		],
	},
	{
		id: "kl_opt",
		label: "kl_opt — KL* adaptive support",
		blurb: "Minimize -lambda*log(k) - mean(log p) over top-k prefixes. Lambda 1 is reverse KL; global=true is the paper's KL*. Put before temperature.",
		knobs: [
			{ key: "kl_opt_lambda", label: "lambda", kind: "float", def: 1, presets: [0.5, 0.75, 1, 1.25, 1.5], min: 0, max: 10 },
			{ key: "kl_opt_global", label: "global minimum", kind: "bool", def: true, presets: [true, false] },
		],
	},
	{
		id: "temperature",
		label: "temperature — softmax scaling",
		blurb: "Scales logits. Put LAST so truncators see cold logits.",
		knobs: [
			{
				key: "temperature",
				label: "temperature",
				kind: "float",
				def: 10.0,
				presets: [0, 0.2, 0.5, 0.7, 1.0, 1.5, 2.0, 5.0, 10.0, 1e6],
				min: 0,
				max: 1e6,
			},
			{
				key: "dynatemp_range",
				label: "dynatemp range",
				kind: "float",
				def: 0,
				presets: [0, 0.5, 1.0],
				min: 0,
				max: 20,
			},
			{
				key: "dynatemp_exponent",
				label: "dynatemp exponent",
				kind: "float",
				def: 1.0,
				presets: [1.0, 1.5],
				min: 0,
				max: 20,
			},
		],
	},
];

const BY_ID = new Map(CATALOG.map((s) => [s.id, s]));
const ALL_KNOBS: Knob[] = CATALOG.flatMap((s) => s.knobs);
const ROUTER_TOOL_NAME = "route_samplers";
const ROUTER_SCHEMA_WITH_RATIONALE = buildSamplerRouterSchema(
	CATALOG,
	DEFAULT_MAX_ROUTED_SAMPLERS,
	true,
);
const ROUTER_SCHEMA_WITHOUT_RATIONALE = buildSamplerRouterSchema(
	CATALOG,
	DEFAULT_MAX_ROUTED_SAMPLERS,
	false,
);
const ROUTER_PROMPT_WITH_RATIONALE = buildSamplerRouterPrompt(
	CATALOG,
	DEFAULT_MAX_ROUTED_SAMPLERS,
	true,
);
const ROUTER_PROMPT_WITHOUT_RATIONALE = buildSamplerRouterPrompt(
	CATALOG,
	DEFAULT_MAX_ROUTED_SAMPLERS,
	false,
);
const ROUTER_MAX_TOKENS_WITH_RATIONALE = 512;
const ROUTER_MAX_TOKENS_WITHOUT_RATIONALE = 384;
const FORCE_AUTO = /^(1|true|yes)$/i.test(process.env.OMP_SAMPLERS_AUTO ?? "");

// ---------------------------------------------------------------------------
// Presets: ready-made chains. First one is the user's stated default.
// ---------------------------------------------------------------------------

interface Preset {
	name: string;
	blurb: string;
	chain: string[];
	params: Record<string, number | boolean>;
}

const PRESETS: Preset[] = [
	{
		name: "hill-creative (default)",
		blurb: "dry → hill → xtc → temperature @ temp 10, hill q=3",
		chain: ["dry", "hill", "xtc", "temperature"],
		params: {
			temperature: 10.0,
			hill_order: 3.0,
			xtc_probability: 0.5,
			xtc_threshold: 0.1,
		},
	},
	{
		name: "toph-creative",
		blurb: "dry → top_h → xtc → temperature @ temp 10, α=0.45",
		chain: ["dry", "top_h", "xtc", "temperature"],
		params: {
			temperature: 10.0,
			top_h_alpha: 0.45,
			xtc_probability: 0.5,
			xtc_threshold: 0.1,
		},
	},
	{
		name: "geomean-creative",
		blurb: "dry → geo_mean → xtc → temperature @ temp 10, coeff 0.7",
		chain: ["dry", "geo_mean", "xtc", "temperature"],
		params: {
			temperature: 10.0,
			geo_mean_coeff: 0.7,
			xtc_probability: 0.5,
			xtc_threshold: 0.1,
		},
	},
	{
		name: "kl-budget",
		blurb: "Experimental: min_p 0.05 → maximum entropy within 0.1 nats of the admitted model distribution",
		chain: ["min_p", "kl_budget"],
		params: { min_p: 0.05, kl_budget: 0.1 },
	},
	{
		name: "kl-budget-creative",
		blurb: "Experimental: DRY → min_p 0.02 → maximum entropy within 0.3 nats",
		chain: ["dry", "min_p", "kl_budget"],
		params: { dry_multiplier: 0.8, dry_base: 1.75, dry_allowed_length: 15, min_p: 0.02, kl_budget: 0.3 },
	},
	{
		name: "kl-star",
		blurb: "KL* (lambda=1, global optimum), then near-uniform sampling at T=1,000,000",
		chain: ["kl_opt", "temperature"],
		params: { kl_opt_lambda: 1, kl_opt_global: true, temperature: 1e6, dynatemp_range: 0 },
	},
	{
		name: "kl-star-local",
		blurb: "Conservative first-local KL* variant, then near-uniform sampling",
		chain: ["kl_opt", "temperature"],
		params: { kl_opt_lambda: 1, kl_opt_global: false, temperature: 1e6, dynatemp_range: 0 },
	},
	{
		name: "balanced",
		blurb: "penalties → top_k → top_p → min_p → temperature @ temp 0.7",
		chain: ["penalties", "top_k", "top_p", "min_p", "temperature"],
		params: {
			temperature: 0.7,
			top_k: 40,
			top_p: 0.95,
			min_p: 0.05,
			repeat_penalty: 1.1,
		},
	},
	{
		name: "coding (reliable tool calls)",
		blurb:
			"top_k → top_p → temperature @ temp 0.3 — low-entropy, keeps tool JSON valid",
		chain: ["top_k", "top_p", "temperature"],
		params: { temperature: 0.3, top_k: 40, top_p: 0.95 },
	},
	{
		name: "greedy",
		blurb: "top_k → temperature @ temp 0 — near-deterministic",
		chain: ["top_k", "temperature"],
		params: { temperature: 0, top_k: 20 },
	},
];

// ---------------------------------------------------------------------------
// State + persistence
// ---------------------------------------------------------------------------

type SamplerMode = "manual" | "auto";

interface Profile {
	enabled: boolean;
	applyToAllModels: boolean; // if false, only apply to llama-ish providers
	mode: SamplerMode;
	includeRationale: boolean;
	chain: string[];
	params: Record<string, number | boolean>;
	/** Telemetry settings; see scope/runtime.ts. */
	scope: ScopeConfig;
	/** Per-token logit bias; see bias.ts. Independent of `enabled`. */
	bias: BiasConfig;
	/**
	 * Hard cap on tokens inside a reasoning block, or null for no cap. Unlike a
	 * bias this is deterministic and cannot run away; see `applyThinkCap`.
	 */
	thinkCap: number | null;
}

const AGENT_DIR =
	process.env.PI_CODING_AGENT_DIR || path.join(os.homedir(), ".omp", "agent");
const STORE = path.join(AGENT_DIR, "sampler-profile.json");
const TOKEN_STORE = path.join(AGENT_DIR, "sampler-tokens.json");

function defaultProfile(): Profile {
	// Seed knob values with every catalog default, then apply the default preset.
	const params: Record<string, number | boolean> = {};
	for (const k of ALL_KNOBS) params[k.key] = k.def;
	Object.assign(params, PRESETS[0].params);
	return {
		enabled: true,
		applyToAllModels: false,
		mode: "manual",
		includeRationale: true,
		chain: [...PRESETS[0].chain],
		params,
		scope: { ...DEFAULT_SCOPE_CONFIG },
		bias: { enabled: false, entries: {} },
		thinkCap: null,
	};
}

function loadScopeConfig(raw: unknown): ScopeConfig {
	const base = { ...DEFAULT_SCOPE_CONFIG };
	if (typeof raw !== "object" || raw === null) return base;
	const value = raw as Record<string, unknown>;
	const bool = (key: keyof ScopeConfig): boolean =>
		typeof value[key] === "boolean"
			? (value[key] as boolean)
			: (base[key] as boolean);
	return {
		capture: bool("capture"),
		proxy: bool("proxy"),
		probeMode: value.probeMode === "raw" ? "raw" : "post",
		nProbs:
			typeof value.nProbs === "number" && value.nProbs > 0
				? Math.min(1000, Math.round(value.nProbs))
				: base.nProbs,
		widget: bool("widget"),
		slots: bool("slots"),
		jsonl: bool("jsonl"),
	};
}

function loadProfile(): Profile {
	try {
		const raw = JSON.parse(fs.readFileSync(STORE, "utf8"));
		const base = defaultProfile();
		return {
			enabled: typeof raw.enabled === "boolean" ? raw.enabled : base.enabled,
			applyToAllModels:
				typeof raw.applyToAllModels === "boolean"
					? raw.applyToAllModels
					: base.applyToAllModels,
			mode: raw.mode === "auto" || raw.mode === "manual" ? raw.mode : base.mode,
			includeRationale:
				typeof raw.includeRationale === "boolean"
					? raw.includeRationale
					: base.includeRationale,
			chain:
				Array.isArray(raw.chain) &&
				raw.chain.every(
					(x: unknown) => typeof x === "string" && BY_ID.has(x as string),
				)
					? raw.chain
					: base.chain,
			params: {
				...base.params,
				...(raw.params && typeof raw.params === "object" ? raw.params : {}),
			},
			scope: loadScopeConfig(raw.scope),
			bias: loadBiasConfig(raw.bias),
			thinkCap:
				typeof raw.thinkCap === "number" &&
				Number.isFinite(raw.thinkCap) &&
				raw.thinkCap >= MIN_THINK_CAP
					? Math.floor(raw.thinkCap)
					: null,
		};
	} catch {
		return defaultProfile();
	}
}

let profile = loadProfile();
/** Special tokens for the connected model; see the detection notes in tokens.ts. */
let tokenSet: SpecialTokenSet | undefined;
let tokenError: string | undefined;
let activeRoute: SamplerRoute | undefined;
let lastRoute: SamplerRoute | undefined;
let lastRouterError: string | undefined;
let routerPending = false;
let routerIncludeRationale = true;
let routerStartedAt = 0;
let pendingRouterUsage:
	| { input: number; output: number; cacheRead: number }
	| undefined;
let lastRouterStats:
	| { durationMs: number; input: number; output: number; cacheRead: number }
	| undefined;

function isAutoMode(): boolean {
	return FORCE_AUTO || profile.mode === "auto";
}

function save(): void {
	try {
		fs.mkdirSync(AGENT_DIR, { recursive: true });
		fs.writeFileSync(STORE, JSON.stringify(profile, null, 2));
	} catch {
		/* best effort */
	}
}

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------

function fmt(v: number | boolean): string {
	if (typeof v === "boolean") return v ? "true" : "false";
	return Number.isInteger(v) ? String(v) : String(v);
}

/** Compact one-line summary of a chain + its live knob values. */
function summarizeChain(
	chain: readonly string[],
	params: Record<string, number | boolean>,
): string {
	const parts = chain.map((id) => {
		const def = BY_ID.get(id);
		if (!def || def.knobs.length === 0) return id;
		const kv = def.knobs
			.filter((k) => k.key in params)
			.map((k) => `${k.label.split(" ")[0]}=${fmt(params[k.key])}`)
			.join(",");
		return kv ? `${id}(${kv})` : id;
	});
	return parts.join(" → ");
}

function manualRoute(): SamplerRoute {
	return {
		chain: [...profile.chain],
		params: { ...profile.params },
		reason: "Manual fallback profile.",
	};
}

function routeForRequest(): SamplerRoute {
	return isAutoMode() ? (activeRoute ?? manualRoute()) : manualRoute();
}

/** Compact one-line summary of the current manual or model-selected mode. */
function summarize(): string {
	const suffix = profile.bias.enabled
		? ` · ${summarizeBias(profile.bias, tokenSet)}`
		: "";
	if (!profile.enabled) return `samplers: OFF (server defaults)${suffix}`;
	if (!isAutoMode())
		return `samplers: ${summarizeChain(profile.chain, profile.params)}${suffix}`;
	const selected = activeRoute ?? lastRoute;
	if (selected) {
		return `samplers: AUTO · ${summarizeChain(selected.chain, selected.params)}${suffix}`;
	}
	return `samplers: AUTO · fallback ${summarizeChain(profile.chain, profile.params)}${suffix}`;
}

/** Injected by the extension factory so the footer can carry live telemetry. */
let statusDecorator: ((base: string) => string) | undefined;

function refreshStatus(ctx: ExtensionContext): void {
	try {
		const base = summarize();
		ctx.ui.setStatus(
			"samplers",
			statusDecorator ? statusDecorator(base) : base,
		);
	} catch {
		/* no UI (print/rpc mode) */
	}
}

// ---------------------------------------------------------------------------
// THE core: select before the agent starts, then inject the resulting chain
// into every provider request in that agent run. llama.cpp fixes a sampler
// stack for the lifetime of one HTTP request, so routing and answering are two
// requests; the answer's very first token uses the routed configuration.
// ---------------------------------------------------------------------------

function looksLikeLlama(ctx: ExtensionContext): boolean {
	if (isVllmModel(ctx.model)) return false;
	const p = (ctx.model?.provider ?? "").toLowerCase();
	const id = (ctx.model?.id ?? "").toLowerCase();
	return (
		p.includes("llama") ||
		p.includes("local") ||
		id.includes("qwen") ||
		id.includes("neo")
	);
}

// ---------------------------------------------------------------------------
// Extension entry point
// ---------------------------------------------------------------------------

export default function (pi: ExtensionAPI): void {
	pi.logger.debug("samplers extension loaded", {
		store: STORE,
		mode: isAutoMode() ? "auto" : "manual",
		chain: profile.chain.join(","),
	});

	// -----------------------------------------------------------------------
	// Telemetry ("scope")
	//
	// Three sources, in order of how much they cost:
	//   /props + /slots   free; effective configuration, cache hits, decode rate
	//   recording proxy   free; per-token probabilities omp's parser discards
	//   /completion probe paid; the raw distribution the chain never reveals
	// -----------------------------------------------------------------------

	const SCOPE_DIR = path.join(AGENT_DIR, "sampler-scope");
	let uiCtx: ExtensionContext | undefined;
	let widgetVisible = false;
	let probeRunning = false;
	let lastProbe: ProbeResult | undefined;

	const scope = new SamplerScope({
		vllmTransformRequest: (body) => {
			if (profile.enabled) applyVllmSamplerRoute(body, manualRoute());
		},
		logger: {
			debug: (message, data) => pi.logger.debug(message, data),
			warn: (message, data) => pi.logger.warn(message, data),
		},
		knobKeys: ALL_KNOBS.map((knob) => knob.key),
		knobsBySampler: Object.fromEntries(CATALOG.map((sampler) => [sampler.id, sampler.knobs.map((knob) => knob.key)])),
		routerToolName: ROUTER_TOOL_NAME,
		storageDir: SCOPE_DIR,
		onUpdate: () => refreshWidget(),
	});
	scope.config = profile.scope;

	statusDecorator = (base) => {
		if (isVllmModel(uiCtx?.model)) {
			base = profile.enabled
				? `samplers: vLLM · ${summarizeChain(profile.chain, profile.params)}${profile.chain.includes("temperature") && profile.params.temperature_infinite ? " · temp=inf" : ""}${isAutoMode() ? " · manual profile" : ""}`
				: "samplers: OFF (model defaults)";
		}
		if (!profile.enabled) return base;
		const state = liveState();
		if (!state.record || state.record.tokens.length === 0) return base;
		return renderStatus({ ...state, chainLabel: base }, paintWith(uiCtx));
	};

	/** Theme-aware colorizer for the chart helpers; identity without a UI. */
	function paintWith(ctx: ExtensionContext | undefined): Paint {
		const theme = ctx?.ui?.theme;
		if (!theme) return (_color, text) => text;
		return (color, text) => {
			try {
				return theme.fg(color, text);
			} catch {
				return text;
			}
		};
	}

	function scopeModeLabel(): string {
		if (scope.backend === "vllm") {
			return profile.scope.capture
				? `vLLM logprobs · preview ${Math.min(20, profile.scope.nProbs)} · full survivor counts unavailable`
				: "vLLM telemetry off";
		}
		if (!profile.scope.capture) return "telemetry: config only";
		if (!scope.proxyUrl)
			return "capture requested · proxy off (no per-token data)";
		return `capture ${profile.scope.probeMode === "post" ? "post-chain" : "raw"} · preview ${
			profile.scope.nProbs
		}`;
	}

	function liveState() {
		return {
			chainLabel: summarize().replace(/^samplers: /, ""),
			mode: scopeModeLabel(),
			record: scope.current(),
			slot: scope.slot
				? {
						decoded: scope.slot.decoded,
						promptTokens: scope.slot.promptTokens,
						cachedTokens: scope.slot.cachedTokens,
						processing: scope.slot.processing,
						tokPerSec: scope.liveTokensPerSecond(),
					}
				: undefined,
			droppedSamplers: scope.droppedSamplers,
			warning: scope.lastError,
		};
	}

	let lastWidgetRender = 0;

	function refreshWidget(force = false): void {
		const ctx = uiCtx;
		if (!ctx?.hasUI) return;
		try {
			// Hiding must never be throttled away, or the widget lingers after
			// the user turns it off.
			if (!profile.scope.widget) {
				if (widgetVisible) {
					ctx.ui.setWidget("sampler-scope", undefined);
					widgetVisible = false;
				}
				return;
			}
			// message_update fires per token; re-rendering that often is wasted work.
			const now = Date.now();
			if (!force && now - lastWidgetRender < 100) return;
			lastWidgetRender = now;
			ctx.ui.setWidget(
				"sampler-scope",
				renderLiveWidget(liveState(), paintWith(ctx)),
				{
					placement: "aboveEditor",
				},
			);
			widgetVisible = true;
		} catch {
			/* no widget surface in print/rpc mode */
		}
	}

	function report(ctx: ExtensionContext, lines: string[]): void {
		ctx.ui.notify(lines.join("\n"), "info");
	}

	/** Connect telemetry to whichever llama.cpp server the session is using. */
	async function connectScope(ctx: ExtensionContext): Promise<void> {
		const model = ctx.models.current() ?? ctx.model;
		if (!model?.baseUrl) return;
		if (isVllmModel(model)) {
			await scope.connect(model.baseUrl, CATALOG, "vllm");
			return;
		}
		if (!profile.applyToAllModels && !looksLikeLlama(ctx)) return;
		await scope.connect(model.baseUrl, CATALOG);
		if (profile.scope.slots) scope.startPolling();
	}

	// -----------------------------------------------------------------------
	// Special-token detection
	//
	// Logit bias is applied by id, and `before_provider_request` is synchronous,
	// so ids have to be known before the first request rather than fetched during
	// it. Detection therefore runs once per model and is cached on disk; a cache
	// hit makes the first turn of a session as biased as the last.
	// -----------------------------------------------------------------------

	const tokenCache = new TokenSetCache(TOKEN_STORE);
	let detecting: Promise<SpecialTokenSet | undefined> | undefined;

	/**
	 * Load the special tokens for the connected model.
	 *
	 * `refresh` forces a re-detect, which is what `/logit-bias scan` does; every
	 * other caller is happy with the cache.
	 */
	async function ensureTokens(
		ctx: ExtensionContext,
		refresh = false,
	): Promise<SpecialTokenSet | undefined> {
		if (isVllmModel(ctx.model)) return undefined;
		if (!refresh && tokenSet) return tokenSet;
		if (!refresh && detecting) return detecting;
		const run = (async (): Promise<SpecialTokenSet | undefined> => {
			try {
				return await detect();
			} catch (error) {
				// Never reject: callers include a fire-and-forget path and a bounded
				// race, and neither should have to defend against this.
				tokenError = error instanceof Error ? error.message : String(error);
				pi.logger.warn("special token detection failed", { error: tokenError });
				return undefined;
			}
		})();
		detecting = run;
		try {
			return await run;
		} finally {
			if (detecting === run) detecting = undefined;
		}

		async function detect(): Promise<SpecialTokenSet | undefined> {
			await connectScope(ctx);
			const client = scope.client;
			if (!client) {
				tokenError = "no llama.cpp server is connected";
				return undefined;
			}
			const props = scope.props;
			const meta = await client.modelMeta();
			const key = tokenSetKey(props?.model_alias, meta?.n_vocab);
			if (!refresh) {
				const cached = tokenCache.get(key);
				if (cached) {
					tokenSet = cached;
					tokenError = undefined;
					return cached;
				}
			}
			try {
				const detected = await detectSpecialTokens({
					client,
					...(props?.model_path !== undefined
						? { modelPath: props.model_path }
						: {}),
					...(props?.model_alias !== undefined
						? { modelAlias: props.model_alias }
						: {}),
					...(meta?.n_vocab !== undefined ? { nVocab: meta.n_vocab } : {}),
					...(typeof props?.bos_token === "string"
						? { bosToken: props.bos_token }
						: {}),
					...(typeof props?.eos_token === "string"
						? { eosToken: props.eos_token }
						: {}),
					...(typeof props?.chat_template === "string"
						? { chatTemplate: props.chat_template }
						: {}),
					// Anything the user already biased is worth confirming even if no
					// builtin candidate covers it.
					extraCandidates: Object.keys(profile.bias.entries),
					log: (message, data) => pi.logger.debug(message, data),
				});
				// A re-scan must not lose the ordinary tokens the user biased by hand,
				// and on a cold start their stored keys have to be resolved somehow.
				const augmented = await augmentWithBiasedLiterals(client, detected);
				tokenSet = augmented;
				tokenError = undefined;
				tokenCache.put(augmented);
				pi.logger.debug("special tokens detected", {
					source: augmented.source,
					count: augmented.tokens.length,
					key: augmented.key,
					thinkClose: findThinkCloseToken(augmented)?.text ?? "none",
				});
				return augmented;
			} catch (error) {
				tokenError = error instanceof Error ? error.message : String(error);
				pi.logger.warn("special token detection failed", { error: tokenError });
				return undefined;
			}
		}
	}

	/**
	 * Resolve stored bias keys that detection did not cover.
	 *
	 * Biases are stored by the text the user typed, and that text is often an
	 * ordinary word rather than a special token — detection has no reason to know
	 * about it. Each such key is tokenized once and, if it is a single token,
	 * folded into the set so request-time resolution stays synchronous. A key that
	 * is several tokens or that the server rejects is left unresolved, which the
	 * status line and `/logit-bias show` both report.
	 */
	async function augmentWithBiasedLiterals(
		client: NonNullable<typeof scope.client>,
		set: SpecialTokenSet,
	): Promise<SpecialTokenSet> {
		const missing = Object.keys(profile.bias.entries).filter(
			(key) => resolveTokenReference(set, key) === undefined,
		);
		if (missing.length === 0) return set;
		const added: SpecialToken[] = [];
		for (const key of missing) {
			try {
				const result = await resolveLiteralToken(client, key);
				if (result.kind === "single") added.push(result.token);
				else {
					pi.logger.warn("a biased key is not a single token, so it is skipped", {
						key,
						tokens: result.pieces.length,
					});
				}
			} catch (error) {
				pi.logger.warn("could not resolve a biased key against the tokenizer", {
					key,
					error: error instanceof Error ? error.message : String(error),
				});
			}
		}
		return added.length > 0 ? withAddedTokens(set, added) : set;
	}

	/** Record a token the user named so later requests can resolve it in sync. */
	function rememberToken(token: SpecialToken): void {
		if (!tokenSet) return;
		tokenSet = withAddedTokens(tokenSet, [token]);
		tokenCache.put(tokenSet);
	}

	/**
	 * Wait for detection, but not for long.
	 *
	 * Bias is applied by id, so a turn that starts before detection finishes goes
	 * out unbiased — which is exactly what happens on the first run against a new
	 * model, where the on-disk cache is empty. Holding the turn for a moment is
	 * the difference between "the bias works" and "the bias works from the second
	 * prompt onward". The wait is bounded so an unreachable server delays a turn
	 * once rather than every time, and only happens when there is a bias to apply.
	 */
	const DETECT_BLOCKING_MS = 3000;

	async function awaitTokensForBias(ctx: ExtensionContext): Promise<void> {
		if (isVllmModel(ctx.model)) return;
		if (!profile.bias.enabled || tokenSet) return;
		if (Object.keys(profile.bias.entries).length === 0) return;
		const started = performance.now();
		await Promise.race([
			ensureTokens(ctx),
			new Promise((resolve) => setTimeout(resolve, DETECT_BLOCKING_MS)),
		]);
		if (!tokenSet) {
			pi.logger.warn(
				"special tokens were not ready in time, so this turn goes out unbiased",
				{ waitedMs: Math.round(performance.now() - started) },
			);
		}
	}

	/** Biases ready to stamp onto a request, with unresolved keys logged once. */
	let warnedUnresolved = "";

	function biasForRequest(): ReturnType<typeof resolveBiasEntries>["resolved"] {
		if (!profile.bias.enabled) return [];
		const { resolved, unresolved } = resolveBiasEntries(profile.bias, tokenSet);
		if (unresolved.length > 0) {
			const signature = unresolved.join(",");
			if (signature !== warnedUnresolved) {
				warnedUnresolved = signature;
				pi.logger.warn("logit bias entries could not be resolved to token ids", {
					unresolved: signature,
					detected: tokenSet ? tokenSet.tokens.length : 0,
					reason: tokenSet
						? "no detected token matches"
						: (tokenError ?? "tokens not detected yet"),
				});
			}
		}
		return resolved;
	}

	/**
	 * Put the recording proxy in front of the model.
	 *
	 * omp's OpenAI-compat parser drops `logprobs`, so the only way to observe
	 * per-token probabilities is to read the wire. The proxy forwards bytes
	 * unchanged; if the redirect cannot be verified it is rolled back rather
	 * than left in a state that could break generation.
	 */
	async function enableProxy(ctx: ExtensionContext): Promise<string> {
		const model = ctx.models.current() ?? ctx.model;
		if (!model?.baseUrl)
			return "No model is selected, so there is nothing to instrument.";
		if (!isVllmModel(model) && !profile.applyToAllModels && !looksLikeLlama(ctx))
			return "Sampler telemetry is available for llama.cpp and vLLM providers.";
		await scope.connect(model.baseUrl, CATALOG, isVllmModel(model) ? "vllm" : "llama.cpp");
		const upstream = scope.upstream ?? model.baseUrl;
		const selector = `${model.provider}/${model.id}`;
		let url: string;
		try {
			url = await scope.startProxy();
		} catch (error) {
			return `Could not start the recording proxy: ${
				error instanceof Error ? error.message : String(error)
			}`;
		}

		const rollback = async (reason: string): Promise<string> => {
			try {
				pi.registerProvider(model.provider, { baseUrl: upstream });
				const original = ctx.models.resolve(selector);
				if (original) await pi.setModel(original);
			} catch {
				/* best effort */
			}
			await scope.stopProxy();
			return reason;
		};

		try {
			pi.registerProvider(model.provider, { baseUrl: url });
			const redirected = ctx.models.resolve(selector);
			if (!redirected)
				return await rollback(
					`Could not re-resolve ${selector} after redirect.`,
				);
			const applied = await pi.setModel(redirected);
			const current = ctx.models.current();
			if (!applied || !current?.baseUrl.startsWith(url)) {
				return await rollback(
					"omp kept the previous model transport, so the proxy was rolled back. Per-token capture is unavailable.",
				);
			}
		} catch (error) {
			return await rollback(
				`Redirect failed: ${error instanceof Error ? error.message : String(error)}`,
			);
		}

		profile.scope.proxy = true;
		save();
		return `Recording proxy on ${url} → ${upstream}. Per-token probabilities are now captured.`;
	}

	async function disableProxy(ctx: ExtensionContext): Promise<string> {
		const model = ctx.models.current() ?? ctx.model;
		const upstream = scope.upstream;
		profile.scope.proxy = false;
		save();
		if (!scope.proxyUrl) return "The recording proxy is already off.";
		if (model && upstream) {
			try {
				pi.registerProvider(model.provider, { baseUrl: upstream });
				const original = ctx.models.resolve(`${model.provider}/${model.id}`);
				if (original) await pi.setModel(original);
			} catch (error) {
				pi.logger.warn("could not restore the original provider baseUrl", {
					error: error instanceof Error ? error.message : String(error),
				});
			}
		}
		await scope.stopProxy();
		return "Recording proxy stopped; requests go straight to the model server again.";
	}

	const Type = pi.typebox.Type;
	const routerToolParameters = Type.Object(
		{
			samplers: Type.Array(
				Type.Object(
					{
						id: Type.String(),
						values: Type.Optional(
							Type.Array(Type.Union([Type.Number(), Type.Boolean()])),
						),
					},
					{ additionalProperties: false },
				),
				{ minItems: 1, maxItems: DEFAULT_MAX_ROUTED_SAMPLERS },
			),
			reason: Type.Optional(Type.String()),
		},
		{ additionalProperties: false },
	);

	async function setRouterToolActive(enabled: boolean): Promise<void> {
		const active = pi.getActiveTools();
		const hasRouter = active.includes(ROUTER_TOOL_NAME);
		if (enabled === hasRouter) return;
		await pi.setActiveTools(
			enabled
				? [...active, ROUTER_TOOL_NAME]
				: active.filter((name) => name !== ROUTER_TOOL_NAME),
		);
	}

	function deactivateRouterTool(): void {
		void setRouterToolActive(false).catch((error) => {
			pi.logger.warn("could not deactivate sampler router tool", {
				error: error instanceof Error ? error.message : String(error),
			});
		});
	}

	function finishRouterStats(): void {
		lastRouterStats = {
			durationMs: Math.round(performance.now() - routerStartedAt),
			input: pendingRouterUsage?.input ?? 0,
			output: pendingRouterUsage?.output ?? 0,
			cacheRead: pendingRouterUsage?.cacheRead ?? 0,
		};
		pi.logger.debug("sampler router response parsed", {
			...lastRouterStats,
		});
	}

	pi.registerTool({
		name: ROUTER_TOOL_NAME,
		label: "Sampler Router",
		description:
			"Internal sampling prelude. Choose and configure the ordered llama.cpp sampler pipeline for the current task.",
		parameters: routerToolParameters,
		hidden: true,
		defaultInactive: true,
		loadMode: "essential",
		approval: "read",
		async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
			if (!routerPending || !profile.enabled || !isAutoMode()) {
				return {
					content: [
						{
							type: "text" as const,
							text: "No sampler routing prelude is active. Continue normally.",
						},
					],
					isError: true,
				};
			}

			const parsed = parseSamplerRoute(
				params,
				CATALOG,
				DEFAULT_MAX_ROUTED_SAMPLERS,
				routerIncludeRationale,
			);
			routerPending = false;
			finishRouterStats();
			await setRouterToolActive(false);

			if (!parsed.ok) {
				lastRouterError = parsed.error;
				activeRoute = {
					...manualRoute(),
					reason: `Manual fallback: ${lastRouterError}`,
				};
				pi.logger.warn("sampler router returned an invalid route", {
					error: lastRouterError,
				});
				ctx.ui.notify(
					`Sampler router returned an invalid route; using the manual fallback. ${lastRouterError}`,
					"warning",
				);
				refreshStatus(ctx);
				return {
					content: [
						{
							type: "text" as const,
							text: "SAMPLER_ROUTE_APPLIED: manual fallback. Routing is complete; now answer the original user's task.",
						},
					],
				};
			}

			activeRoute = parsed.route;
			lastRoute = parsed.route;
			lastRouterError = undefined;
			pi.logger.debug("sampler router selected", {
				chain: parsed.route.chain.join(","),
				params: parsed.route.params,
				...(routerIncludeRationale ? { reason: parsed.route.reason } : {}),
			});
			refreshStatus(ctx);
			const reason =
				routerIncludeRationale && parsed.route.reason
					? ` Reason: ${parsed.route.reason}`
					: "";
			return {
				content: [
					{
						type: "text" as const,
						text: `SAMPLER_ROUTE_APPLIED: ${summarizeChain(parsed.route.chain, parsed.route.params)}.${reason} Routing is complete; now answer the original user's task.`,
					},
				],
				details: {
					chain: parsed.route.chain,
					params: parsed.route.params,
					reason: parsed.route.reason,
				},
			};
		},
	});

	pi.on("before_agent_start", async (_event, ctx) => {
		uiCtx = ctx;
		activeRoute = undefined;
		routerPending = false;
		pendingRouterUsage = undefined;
		if (isVllmModel(ctx.model)) {
			await connectScope(ctx);
			await setRouterToolActive(false);
			refreshStatus(ctx);
			return;
		}
		// Runs regardless of routing mode: bias is a separate axis and applies with
		// the override off entirely.
		await awaitTokensForBias(ctx);
		if (!profile.enabled || !isAutoMode()) {
			await setRouterToolActive(false);
			return;
		}
		if (!profile.applyToAllModels && !looksLikeLlama(ctx)) {
			await setRouterToolActive(false);
			return;
		}

		await setRouterToolActive(true);
		routerPending = true;
		routerIncludeRationale = profile.includeRationale;
		routerStartedAt = performance.now();
		lastRouterError = undefined;
		lastRouterStats = undefined;
		ctx.ui.setStatus("samplers", "samplers: AUTO · choosing…");
	});

	/**
	 * Notice an over-biased close tag and say so.
	 *
	 * A bias is fixed for the request, so one large enough to guarantee an early
	 * close is also large enough to keep winning after the block has closed. The
	 * result is a reasoning channel full of close tags and no answer, which
	 * llama.cpp reports as a perfectly normal generation. Warned once per session
	 * so it is useful rather than nagging.
	 */
	let warnedRunaway = false;

	function checkThinkRunaway(message: {
		content: readonly unknown[];
	}): void {
		if (warnedRunaway || !profile.bias.enabled) return;
		const close = findThinkCloseToken(tokenSet);
		if (!close) return;
		const biased = profile.bias.entries[biasKeyFor(close)];
		if (typeof biased !== "number" || biased <= 0) return;
		let repeats = 0;
		for (const part of message.content) {
			if (typeof part !== "object" || part === null) continue;
			const block = part as { type?: unknown; thinking?: unknown; text?: unknown };
			const text =
				typeof block.thinking === "string"
					? block.thinking
					: typeof block.text === "string"
						? block.text
						: "";
			if (text !== "") repeats += countCloseTags(text, close.text);
		}
		if (repeats < 2) return;
		warnedRunaway = true;
		pi.logger.warn("end-of-thinking token repeated; the bias is too high", {
			token: close.text,
			bias: biased,
			repeats,
		});
		try {
			uiCtx?.ui.notify(
				`${close.text} was emitted ${repeats} times in one turn: the ${formatBiasAmount(
					biased,
				)} bias on it is too high. ${THINK_RUNAWAY_NOTE} A bias under about +${BIAS_RUNAWAY_HINT} stays in the usable range.`,
				"warning",
			);
		} catch {
			/* no UI surface in print/rpc mode */
		}
	}

	pi.on("message_end", (event) => {
		if (event.message.role === "assistant") checkThinkRunaway(event.message);
		if (!routerPending || event.message.role !== "assistant") return;
		const message = event.message as typeof event.message & {
			usage?: { input?: number; output?: number; cacheRead?: number };
		};
		const hasRouterCall = message.content.some(
			(part) => part.type === "toolCall" && part.name === ROUTER_TOOL_NAME,
		);
		if (!hasRouterCall) return;
		pendingRouterUsage = {
			input: Number(message.usage?.input ?? 0),
			output: Number(message.usage?.output ?? 0),
			cacheRead: Number(message.usage?.cacheRead ?? 0),
		};
		const content = message.content as Array<(typeof message.content)[number]>;
		const routeCalls = content.filter(
			(part) => part.type === "toolCall" && part.name === ROUTER_TOOL_NAME,
		);
		if (routeCalls.length !== content.length) {
			pi.logger.warn("discarding content emitted before sampler route", {
				blocksDiscarded: content.length - routeCalls.length,
			});
			content.splice(0, content.length, ...routeCalls);
		}
	});

	pi.on("before_provider_request", (event, ctx) => {
		const body = event.payload as Record<string, unknown> | undefined;
		if (!body || typeof body !== "object") return;
		removeSamplerRouterTool(body, ROUTER_TOOL_NAME);
		if (isVllmModel(ctx.model)) {
			if (profile.enabled) applyVllmSamplerRoute(body, manualRoute());
			scope.instrument(body);
			return body;
		}
		const appliesHere = profile.applyToAllModels || looksLikeLlama(ctx);
		if (!profile.enabled) {
			// Telemetry is still useful with the override off: it then measures
			// whatever chain the server was launched with. Bias is a separate axis
			// with its own switch, so it still applies here — server-default
			// samplers plus one nudged token is a reasonable thing to want.
			if (appliesHere) {
				applyLogitBias(body, biasForRequest());
				applyThinkCap(body, profile.thinkCap);
				scope.instrument(body);
			}
			return body;
		}
		if (!appliesHere) return;
		if (routerPending && isAutoMode()) {
			const schema = routerIncludeRationale
				? ROUTER_SCHEMA_WITH_RATIONALE
				: ROUTER_SCHEMA_WITHOUT_RATIONALE;
			const maxTokens = routerIncludeRationale
				? ROUTER_MAX_TOKENS_WITH_RATIONALE
				: ROUTER_MAX_TOKENS_WITHOUT_RATIONALE;
			const routerPrompt = routerIncludeRationale
				? ROUTER_PROMPT_WITH_RATIONALE
				: ROUTER_PROMPT_WITHOUT_RATIONALE;
			prepareSamplerRouterRequest(
				body,
				ROUTER_TOOL_NAME,
				schema,
				maxTokens,
				`[omp-samplers routing prelude]\n${routerPrompt}`,
			);
			pi.logger.debug("sampler router request prepared", {
				model: `${ctx.model?.provider}/${ctx.model?.id}`,
				maxTokens,
				timeoutMs: "agent-controlled",
				includeRationale: routerIncludeRationale,
			});
			return body;
		}

		const selected = routeForRequest();
		applySamplerRoute(body, selected);
		// The bias sampler runs ahead of the whole chain llama.cpp just built, so
		// this composes with the route rather than competing with it. The reasoning
		// budget sits ahead of both and wins outright when it fires, since it drives
		// every other logit to -infinity and -infinity absorbs any bias.
		applyLogitBias(body, biasForRequest());
		applyThinkCap(body, profile.thinkCap);
		// Probability reporting rides along on the same body; llama.cpp answers
		// with `logprobs` only when it is asked for, and only the proxy can read
		// them back.
		if (scope.instrument(body)) {
			pi.logger.debug("sampler scope instrumented request", {
				nProbs: profile.scope.nProbs,
				postSampling: profile.scope.probeMode === "post",
			});
		}
		return body; // also return, for providers that honor the replacement path
	});

	pi.on("session_start", async (_e, ctx) => {
		uiCtx = ctx;
		refreshStatus(ctx);
		if (profile.scope.proxy && !scope.proxyUrl && (isVllmModel(ctx.model) || profile.applyToAllModels || looksLikeLlama(ctx))) {
			const message = await enableProxy(ctx);
			pi.logger.debug("sampler scope proxy startup", { message });
			if (!scope.proxyUrl) ctx.ui.notify(message, "warning");
		} else {
			// Reaching the server must never delay or fail session start.
			void connectScope(ctx)
				.then(() => refreshWidget())
				.catch((error) =>
					pi.logger.warn("sampler scope could not connect", {
						error: error instanceof Error ? error.message : String(error),
					}),
				);
		}
		// Same rule for detection, which is why the result is cached on disk: this
		// may not finish before the first request, but on any later session it is
		// already there.
		void ensureTokens(ctx)
			.then(() => refreshStatus(ctx))
			.catch((error) =>
				pi.logger.warn("special token detection could not start", {
					error: error instanceof Error ? error.message : String(error),
				}),
			);
		refreshWidget();
	});

	pi.on("message_update", (_event, ctx) => {
		uiCtx = ctx;
		refreshWidget();
	});

	pi.on("agent_end", async (event, ctx) => {
		uiCtx = ctx;
		// Snapshot the route before clearing it. Slot comparisons below are debug
		// hints only; /slots cannot identify the request that just finished.
		void checkAppliedParams(routeForRequest());
		if (!event.willContinue) {
			activeRoute = undefined;
			routerPending = false;
			await setRouterToolActive(false);
		}
		refreshStatus(ctx);
		refreshWidget();
	});

	pi.on("session_shutdown", async () => {
		await scope.shutdown();
	});

	/**
	 * Best-effort debug comparison against a slot with the same chain. An idle
	 * slot may describe a previous request and a busy slot may belong to another
	 * client, so this must not produce dropped-sampler warnings.
	 */
	async function checkAppliedParams(requested: SamplerRoute): Promise<void> {
		const client = scope.client;
		if (!client || !profile.scope.slots) return;
		try {
			const slots = await client.slots();
			if (scope.client !== client) return;
			const slot = slots.find((candidate) => {
				const applied = candidate.params?.samplers;
				return Array.isArray(applied) && applied.length === requested.chain.length &&
					applied.every((id, i) => id === requested.chain[i]);
			});
			if (!slot) return;
			// An out-of-range id is dropped server-side without an error, so the
			// echo is the only place a bias that never happened shows up. Most
			// servers do not echo it at all: `/slots` omits logit_bias unless
			// LLAMA_SERVER_SLOTS_DEBUG is set, and an absent field is not evidence.
			if (profile.bias.enabled) {
				const { reported, missing, mismatched } = diffAppliedBias(
					biasForRequest(),
					slot?.params?.logit_bias,
				);
				if (reported && (missing.length > 0 || mismatched.length > 0)) {
					pi.logger.debug("logit bias differs from the server echo", {
						missing: missing.map((entry) => entry.key).join(", "),
						mismatched: mismatched.map((entry) => entry.key).join(", "),
					});
				}
			}
			const mismatches = diffSamplerParams(
				requested.params,
				slotParams(slot, Object.keys(requested.params)),
			);
			if (mismatches.length > 0) {
				pi.logger.debug("sampler knobs differ from the server echo", {
					mismatches: mismatches
						.map((m) => `${m.key}: want ${m.want}, got ${m.got ?? "absent"}`)
						.join("; "),
				});
			}
		} catch {
			/* /slots is optional */
		}
	}

	// --- helpers bound to a command context (they use the dropdown UI) -------
	function activateManualMode(): void {
		profile.mode = "manual";
		activeRoute = undefined;
		routerPending = false;
		lastRouterError = undefined;
		deactivateRouterTool();
	}

	function setAutoMode(enabled: boolean, ctx: ExtensionContext): void {
		profile.mode = enabled ? "auto" : "manual";
		profile.enabled = true;
		activeRoute = undefined;
		routerPending = false;
		lastRouterError = undefined;
		if (!enabled) deactivateRouterTool();
		save();
		refreshStatus(ctx);
	}

	function setRationale(enabled: boolean, ctx: ExtensionContext): void {
		profile.includeRationale = enabled;
		save();
		refreshStatus(ctx);
	}

	function detailedSummary(): string {
		const lines = [
			summarize(),
			`mode: ${isAutoMode() ? "model-selected per prompt" : "manual"}`,
			`router rationale: ${profile.includeRationale ? "on" : "off (faster)"}`,
			`applies to: ${profile.applyToAllModels ? "all models" : "local llama.cpp only"}`,
		];
		const selected = activeRoute ?? lastRoute;
		if (isAutoMode() && selected && profile.includeRationale)
			lines.push(`router reason: ${selected.reason}`);
		if (lastRouterStats) {
			lines.push(
				`last route: ${(lastRouterStats.durationMs / 1000).toFixed(2)}s; tokens input=${lastRouterStats.input}, cache-read=${lastRouterStats.cacheRead}, output=${lastRouterStats.output}`,
			);
		}
		if (lastRouterError)
			lines.push(
				`last router error: ${lastRouterError}`,
				"fallback: manual profile",
			);
		lines.push("", ...biasSummary());
		lines.push("", ...scopeSummary());
		const captured = scope.current();
		if (captured && captured.tokens.length > 0) {
			const stats = summarizeGeneration(captured);
			lines.push(
				`last generation: ${stats.tokens} steps · width med ${
					stats.width ? stats.width.median : "—"
				} p90 ${stats.width ? stats.width.p90 : "—"} · forced ${(
					stats.forcedRate * 100
				).toFixed(
					0,
				)}% · ${stats.tokPerSec ? `${stats.tokPerSec.toFixed(1)} tok/s` : "—"}`,
			);
		}
		lines.push(`stored at: ${STORE}`);
		return lines.join("\n");
	}

	async function pickFromCatalog(
		ctx: ExtensionCommandContext,
		title: string,
	): Promise<string | undefined> {
		const options = CATALOG.filter((s) => !isVllmModel(ctx.model) || VLLM_SAMPLERS.has(s.id)).map((s) => ({
			label: s.label,
			description: s.blurb,
		}));
		const chosen = await ctx.ui.select(title, options);
		if (!chosen) return undefined;
		return CATALOG.find((s) => s.label === chosen)?.id;
	}

	/** Prompt for a single knob's value: preset dropdown + "Custom…". */
	async function editKnob(
		ctx: ExtensionCommandContext,
		knob: Knob,
	): Promise<void> {
		const cur = isVllmModel(ctx.model) && knob.key === "temperature" && profile.params.temperature_infinite === true ? Infinity : profile.params[knob.key] ?? knob.def;
		if (knob.kind === "bool") {
			const pick = await ctx.ui.select(`${knob.label} (current: ${fmt(cur)})`, [
				"true",
				"false",
			]);
			if (pick === undefined) return;
			profile.params[knob.key] = pick === "true";
		} else {
			const presetLabels = knob.presets.map(
				(v) => `${fmt(v)}${v === cur ? "  (current)" : ""}`,
			);
			const CUSTOM = "Custom…";
			const pick = await ctx.ui.select(`${knob.label} (current: ${fmt(cur)})`, [
				...presetLabels,
				CUSTOM,
			]);
			if (pick === undefined) return;
			let val: number;
			if (pick === CUSTOM) {
				const raw = await ctx.ui.input(`Enter ${knob.label}`, String(cur));
				if (raw === undefined || raw.trim() === "") return;
				try { val = isVllmModel(ctx.model) && knob.key === "temperature" ? parseVllmTemperature(raw) : Number(raw); }
				catch (error) { ctx.ui.notify(String(error), "error"); return; }
				if (!Number.isFinite(val) && !(isVllmModel(ctx.model) && knob.key === "temperature" && val === Infinity)) {
					ctx.ui.notify(`Not a number: ${raw}`, "error");
					return;
				}
			} else {
				val = Number(pick.replace(/\s*\(current\)\s*$/, ""));
			}
			if (knob.key === "temperature") {
				profile.params.temperature_infinite = val === Infinity;
				profile.params.temperature = val === Infinity ? 1 : val;
			} else profile.params[knob.key] = knob.kind === "int" ? Math.round(val) : val;
		}
		activateManualMode();
		save();
	}

	/** Tune every knob of one sampler, one after another. */
	async function tuneSampler(
		ctx: ExtensionCommandContext,
		id: string,
	): Promise<void> {
		const def = BY_ID.get(id);
		if (!def) return;
		if (def.knobs.length === 0) {
			ctx.ui.notify(`${id} has no tunable parameters.`, "info");
			return;
		}
		for (;;) {
			const DONE = "‹ done›";
			const opts = def.knobs.filter((k) => !isVllmModel(ctx.model) || VLLM_KNOBS[id]?.includes(k.key)).map((k) => ({
				label: `${k.label}: ${isVllmModel(ctx.model) && k.key === "temperature" && profile.params.temperature_infinite ? "inf" : fmt(profile.params[k.key] ?? k.def)}`,
				description: `default ${fmt(k.def)}`,
			}));
			const pick = await ctx.ui.select(`Tune ${id} — pick a parameter`, [
				...opts,
				DONE,
			]);
			if (pick === undefined || pick === DONE) return;
			const knob = def.knobs.find((k) => pick.startsWith(`${k.label}:`));
			if (knob) await editKnob(ctx, knob);
		}
	}

	/** Interactive chain editor: add / remove / reorder, looping until done. */
	async function editChain(ctx: ExtensionCommandContext): Promise<void> {
		for (;;) {
			const ADD = "➕ Add a sampler";
			const REMOVE = "➖ Remove a sampler";
			const UP = "⬆️  Move a sampler earlier";
			const DOWN = "⬇️  Move a sampler later";
			const DONE = "✓ Done";
			const action = await ctx.ui.select(
				`Chain: ${profile.chain.join(" → ") || "(empty)"}`,
				[ADD, REMOVE, UP, DOWN, DONE],
			);
			if (action === undefined || action === DONE) {
				save();
				refreshStatus(ctx);
				return;
			}
			if (action === ADD) {
				const id = await pickFromCatalog(
					ctx,
					"Add which sampler? (appended to the end)",
				);
				if (id) {
					activateManualMode();
					profile.chain.push(id);
					save();
				}
			} else if (action === REMOVE) {
				if (profile.chain.length === 0) continue;
				const pick = await ctx.ui.select("Remove which?", profile.chain);
				if (pick) {
					const i = profile.chain.indexOf(pick);
					if (i >= 0) {
						activateManualMode();
						profile.chain.splice(i, 1);
					}
					save();
				}
			} else if (action === UP || action === DOWN) {
				if (profile.chain.length < 2) continue;
				const pick = await ctx.ui.select(
					action === UP ? "Move earlier:" : "Move later:",
					profile.chain,
				);
				if (!pick) continue;
				const i = profile.chain.indexOf(pick);
				const j = action === UP ? i - 1 : i + 1;
				if (i >= 0 && j >= 0 && j < profile.chain.length) {
					activateManualMode();
					[profile.chain[i], profile.chain[j]] = [
						profile.chain[j],
						profile.chain[i],
					];
					save();
				}
			}
		}
	}

	async function applyPreset(ctx: ExtensionCommandContext): Promise<void> {
		const opts = PRESETS.filter((p) => !isVllmModel(ctx.model) || p.chain.every((id) => VLLM_SAMPLERS.has(id))).map((p) => ({ label: p.name, description: p.blurb }));
		const pick = await ctx.ui.select("Apply a preset", opts);
		if (!pick) return;
		const preset = PRESETS.find((p) => p.name === pick);
		if (!preset) return;
		profile.chain = [...preset.chain];
		Object.assign(profile.params, preset.params);
		profile.enabled = true;
		activateManualMode();
		save();
		refreshStatus(ctx);
		ctx.ui.notify(`Applied "${preset.name}". ${summarize()}`, "info");
	}

	// --- /samplers : the main menu ------------------------------------------

	function vllmSummary(): string {
		const body: Record<string, unknown> = {};
		try {
			if (profile.enabled) applyVllmSamplerRoute(body, manualRoute());
		} catch (error) {
			return String(error);
		}
		return [
			`vLLM manual samplers: ${profile.enabled ? profile.chain.join(", ") || "none" : "OFF (model defaults)"}`,
			...Object.entries(body).map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : value}`),
			"Samplers execute in the selected order. Inactive stages are disabled. Temperature supports inf.",
			"Auto routing, token-bias tools and think-cap remain unavailable on this backend.",
			...scopeSummary(),
		].join("\n");
	}

	async function openVllmSamplers(args: string, ctx: ExtensionCommandContext): Promise<void> {
		const arg = args.trim().toLowerCase();
		if (arg === "auto" || arg.startsWith("rationale")) {
			ctx.ui.notify("vLLM uses the manual sampler profile; automatic llama.cpp routing is unavailable.", "info");
			return;
		}
		if (arg.startsWith("chain ")) {
			const chain = arg.slice(6).split(/[;,\s]+/).filter(Boolean);
			if (chain.length > 32 || chain.some((id) => !VLLM_SAMPLERS.has(id))) {
				ctx.ui.notify(`Supported samplers: ${[...VLLM_SAMPLERS].join(", ")}`, "error");
				return;
			}
			profile.chain = chain;
			profile.enabled = true;
			activateManualMode(); save(); refreshStatus(ctx);
			ctx.ui.notify(vllmSummary(), "info");
			return;
		}
		if (arg.startsWith("min_p ")) {
			const value = Number(arg.slice(6).trim());
			if (!Number.isFinite(value) || value < 0 || value > 1) {
				ctx.ui.notify("Usage: /samplers min_p <0..1>", "error");
				return;
			}
			profile.params.min_p = value;
			if (!profile.chain.includes("min_p")) profile.chain.push("min_p");
			profile.enabled = true;
			activateManualMode();
			save();
			refreshStatus(ctx);
			ctx.ui.notify(vllmSummary(), "info");
			return;
		}
		if (arg === "manual") { activateManualMode(); save(); refreshStatus(ctx); }
		if (arg === "preset") return applyPreset(ctx);
		if (arg === "chain") return editChain(ctx);
		if (arg === "show" || arg === "manual" || !ctx.hasUI) {
			ctx.ui.notify(vllmSummary(), "info");
			return;
		}
		for (;;) {
			const choices = ["Tune min_p", "Tune an active sampler", "Edit enabled samplers", "Telemetry", "Show effective settings", "Toggle override", "Close"];
			const pick = await ctx.ui.select(`vLLM · ${profile.chain.join(", ")}`, choices);
			if (!pick || pick === "Close") return;
			if (pick === "Tune min_p") await tuneSampler(ctx, "min_p");
			if (pick === "Tune an active sampler") {
				const id = await ctx.ui.select("Tune which sampler?", profile.chain.filter((id) => VLLM_SAMPLERS.has(id)));
				if (id) await tuneSampler(ctx, id);
			}
			if (pick === "Edit enabled samplers") await editChain(ctx);
			if (pick === "Telemetry") await openScopeMenu(ctx);
			if (pick === "Show effective settings") ctx.ui.notify(vllmSummary(), "info");
			if (pick === "Toggle override") { profile.enabled = !profile.enabled; save(); }
			refreshStatus(ctx);
		}
	}

	pi.registerCommand("samplers", {
		description: "Configure manual or model-selected llama.cpp samplers",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			uiCtx = ctx;
			if (isVllmModel(ctx.model)) return openVllmSamplers(args, ctx);
			// Allow direct subcommands, else open the menu.
			const arg = args.trim().toLowerCase();
			if (arg === "show") {
				ctx.ui.notify(detailedSummary(), "info");
				return;
			}
			if (arg === "auto") {
				setAutoMode(true, ctx);
				ctx.ui.notify(
					"Model-selected sampler routing is ON. The next prompt will be routed before answering.",
					"info",
				);
				return;
			}
			if (arg === "manual") {
				setAutoMode(false, ctx);
				ctx.ui.notify(
					FORCE_AUTO
						? "OMP_SAMPLERS_AUTO forces auto mode for this process."
						: `Manual mode. ${summarize()}`,
					"info",
				);
				return;
			}
			if (arg === "rationale" || arg.startsWith("rationale ")) {
				const setting = arg.split(/\s+/, 2)[1];
				const enabled =
					setting === "on"
						? true
						: setting === "off"
							? false
							: !profile.includeRationale;
				setRationale(enabled, ctx);
				ctx.ui.notify(
					`Router rationale ${enabled ? "ON" : "OFF (faster)"}.`,
					"info",
				);
				return;
			}
			if (arg === "preset") return applyPreset(ctx);
			if (arg === "chain") return editChain(ctx);
			if (!ctx.hasUI) {
				ctx.ui.notify(detailedSummary(), "info");
				return;
			}

			for (;;) {
				const MODE = isAutoMode()
					? "🧑 Use the manual profile"
					: "🤖 Let the model choose per prompt";
				const RATIONALE = profile.includeRationale
					? "💭 Disable router rationale (faster)"
					: "💭 Enable router rationale";
				const CHAIN = "🔗 Edit chain (add / remove / reorder)";
				const TUNE = "🎚️  Tune a sampler's parameters";
				const PRESET = "⭐ Apply a preset";
				const BIAS = `🎯 Logit bias / think less (${
					profile.bias.enabled
						? `${Object.keys(profile.bias.entries).length} token(s)`
						: "off"
				})`;
				const SCOPE = "📊 Telemetry & visualizations";
				const SHOW = "👁️  Show current config";
				const TOGGLE = profile.enabled
					? "⏻ Disable override (use server defaults)"
					: "⏻ Enable override";
				const RESET = "↺ Reset to default (dry → hill → xtc → temperature)";
				const DONE = "✓ Close";
				const choice = await ctx.ui.select(
					summarize(),
					[
						MODE,
						RATIONALE,
						CHAIN,
						TUNE,
						PRESET,
						BIAS,
						SCOPE,
						SHOW,
						TOGGLE,
						RESET,
						DONE,
					],
					{
						helpText: "↑↓ move · enter select · esc close",
					},
				);
				if (choice === undefined || choice === DONE) {
					refreshStatus(ctx);
					return;
				}
				if (choice === MODE) {
					setAutoMode(!isAutoMode(), ctx);
				} else if (choice === RATIONALE) {
					setRationale(!profile.includeRationale, ctx);
				} else if (choice === CHAIN) {
					await editChain(ctx);
				} else if (choice === TUNE) {
					const id = profile.chain.length
						? await ctx.ui.select("Tune which sampler?", profile.chain)
						: await pickFromCatalog(ctx, "Tune which sampler?");
					if (id) await tuneSampler(ctx, BY_ID.has(id) ? id : (id as string));
				} else if (choice === PRESET) {
					await applyPreset(ctx);
				} else if (choice === BIAS) {
					await openBiasMenu(ctx);
				} else if (choice === SCOPE) {
					await openScopeMenu(ctx);
				} else if (choice === SHOW) {
					ctx.ui.notify(detailedSummary(), "info");
				} else if (choice === TOGGLE) {
					profile.enabled = !profile.enabled;
					if (!profile.enabled) {
						routerPending = false;
						deactivateRouterTool();
					}
					save();
					refreshStatus(ctx);
				} else if (choice === RESET) {
					// This resets the chain, not the token biases; those are a separate
					// axis with their own switch and are cleared from their own menu.
					const keptBias = profile.bias;
					profile = defaultProfile();
					profile.bias = keptBias;
					activeRoute = undefined;
					routerPending = false;
					lastRoute = undefined;
					lastRouterError = undefined;
					lastRouterStats = undefined;
					deactivateRouterTool();
					save();
					refreshStatus(ctx);
					ctx.ui.notify(`Reset. ${summarize()}`, "info");
				}
			}
		},
	});

	// --- /samplers-auto : model-selected routing -----------------------------

	pi.registerCommand("samplers-auto", {
		description: "Toggle model-selected sampler routing per prompt",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			if (isVllmModel(ctx.model)) {
				ctx.ui.notify("vLLM uses the manual profile. Automatic llama.cpp sampler routing is unavailable on this backend.", "info");
				return;
			}
			const arg = args.trim().toLowerCase();
			const enable =
				arg === "on" || arg === "auto"
					? true
					: arg === "off" || arg === "manual"
						? false
						: !isAutoMode();
			setAutoMode(enable, ctx);
			ctx.ui.notify(
				enable
					? "Model-selected sampler routing is ON."
					: FORCE_AUTO
						? "OMP_SAMPLERS_AUTO forces auto mode for this process."
						: `Model-selected routing is OFF. ${summarize()}`,
				"info",
			);
		},
	});

	// --- /samplers-rationale : optional router explanation -------------------

	pi.registerCommand("samplers-rationale", {
		description: "Toggle the model router's rationale field",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			const arg = args.trim().toLowerCase();
			const enabled =
				arg === "on" ? true : arg === "off" ? false : !profile.includeRationale;
			setRationale(enabled, ctx);
			ctx.ui.notify(
				`Router rationale ${enabled ? "ON" : "OFF (faster)"}.`,
				"info",
			);
		},
	});

	// --- /sampler-preset : jump straight to the preset picker ----------------

	pi.registerCommand("sampler-preset", {
		description: "Apply a ready-made sampler preset",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			const arg = args.trim().toLowerCase();
			if (arg) {
				const preset = PRESETS.find((p) =>
					p.name.toLowerCase().startsWith(arg),
				);
				if (preset) {
					if (isVllmModel(ctx.model) && preset.chain.some((id) => !VLLM_SAMPLERS.has(id))) {
						ctx.ui.notify("This preset contains samplers not included in the vLLM port. Use /samplers to choose supported stages.", "warning");
						return;
					}
					profile.chain = [...preset.chain];
					Object.assign(profile.params, preset.params);
					profile.enabled = true;
					activateManualMode();
					save();
					refreshStatus(ctx);
					ctx.ui.notify(`Applied "${preset.name}". ${summarize()}`, "info");
					return;
				}
			}
			if (!ctx.hasUI) {
				ctx.ui.notify(
					`Presets: ${PRESETS.map((p) => p.name).join(", ")}`,
					"info",
				);
				return;
			}
			await applyPreset(ctx);
		},
	});

	// --- /temp : quick temperature set --------------------------------------

	pi.registerCommand("temp", {
		description: "Quick-set sampling temperature",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			const arg = args.trim();
			if (arg) {
				let v: number;
				try { v = isVllmModel(ctx.model) ? parseVllmTemperature(arg) : Number(arg); }
				catch (error) { ctx.ui.notify(String(error), "error"); return; }
				if (!Number.isFinite(v) && !(isVllmModel(ctx.model) && v === Infinity)) {
					ctx.ui.notify(`Not a number: ${arg}`, "error");
					return;
				}
				profile.params.temperature = v === Infinity ? 1 : v;
				profile.params.temperature_infinite = v === Infinity;
				if (isVllmModel(ctx.model) && !profile.chain.includes("temperature")) profile.chain.push("temperature");
				profile.enabled = true;
				activateManualMode();
				save();
				refreshStatus(ctx);
				ctx.ui.notify(`temperature = ${v}. ${summarize()}`, "info");
				return;
			}
			if (!ctx.hasUI) return;
			const knob = ALL_KNOBS.find((k) => k.key === "temperature");
			if (!knob) {
				ctx.ui.notify(
					"Temperature is not available in the sampler catalog.",
					"error",
				);
				return;
			}
			await editKnob(ctx, knob);
			refreshStatus(ctx);
			ctx.ui.notify(summarize(), "info");
		},
	});

	// --- /samplers-off : toggle -------------------------------------------------

	pi.registerCommand("samplers-off", {
		description: "Toggle the sampler override on/off (off = server defaults)",
		handler: async (_args: string, ctx: ExtensionCommandContext) => {
			profile.enabled = !profile.enabled;
			if (!profile.enabled) {
				routerPending = false;
				deactivateRouterTool();
			}
			save();
			refreshStatus(ctx);
			ctx.ui.notify(
				profile.enabled
					? `Override ON. ${summarize()}`
					: "Override OFF (server defaults).",
				"info",
			);
		},
	});

	// --- /sampler-scope : telemetry ------------------------------------------

	function scopeSummary(): string[] {
		const lines = [
			`capture: ${profile.scope.capture ? "on" : "off"} (${scopeModeLabel()})`,
			`proxy: ${scope.proxyUrl ? `${scope.proxyUrl} → ${scope.upstream}` : "off"}`,
			`widget: ${profile.scope.widget ? "on" : "off"} · /slots polling: ${
				scope.backend === "vllm" ? "unavailable on vLLM" : profile.scope.slots ? "on" : "off"
			} · jsonl: ${profile.scope.jsonl ? scope.jsonlPath() : "off"}`,
		];
		const props = scope.props;
		if (props) {
			lines.push(
				`server: ${props.model_alias ?? "?"} · ${props.total_slots ?? 1} slot(s) · n_ctx ${
					props.default_generation_settings?.n_ctx ?? "?"
				} · /slots ${props.endpoint_slots ? "enabled" : "disabled"}`,
			);
		} else if (scope.lastError) {
			lines.push(`server: unreachable (${scope.lastError})`);
		}
		const dropped = scope.droppedSamplers;
		if (dropped.length > 0) {
			lines.push(`missing from response's applied chain: ${dropped.join(", ")}`);
		}
		const records = scope.store.all().filter((r) => r.tokens.length > 0);
		lines.push(
			`captured: ${records.length} generation(s), ${records.reduce(
				(acc, r) => acc + r.tokens.length,
				0,
			)} step(s)`,
		);
		return lines;
	}

	function requireCapture(ctx: ExtensionContext): boolean {
		const record = scope.current();
		if (record && record.tokens.length > 0) return true;
		ctx.ui.notify(
			profile.scope.capture && scope.proxyUrl
				? "No per-token data captured yet — run a turn first."
				: "Per-token capture is off. Run `/sampler-scope capture on` (it starts the recording proxy).",
			"warning",
		);
		return false;
	}

	async function inspectToken(ctx: ExtensionCommandContext): Promise<void> {
		const record = scope.current();
		if (!record || record.tokens.length === 0) return;
		const labels = record.tokens.slice(0, 300).map((token) => {
			const width =
				token.mode === "post" ? `w=${token.candidates.length}` : "raw";
			return `#${token.index} ${showTokenLabel(token.text)} ${width} p=${(
				token.prob ?? 0
			).toFixed(3)}`;
		});
		const picked = await ctx.ui.select("Inspect which step?", labels);
		if (!picked) return;
		const index = labels.indexOf(picked);
		if (index < 0) return;
		report(ctx, renderTokenDetail(record, index, paintWith(ctx)));
	}

	function showTokenLabel(text: string): string {
		return JSON.stringify(text.length > 16 ? `${text.slice(0, 15)}…` : text);
	}

	async function runCapabilityProbe(
		ctx: ExtensionCommandContext,
	): Promise<void> {
		const client = scope.client;
		if (!client) {
			ctx.ui.notify("No llama.cpp server is connected.", "warning");
			return;
		}
		const unknown = scope.support.filter(
			(entry) => entry.support === "unknown",
		);
		if (unknown.length === 0) {
			report(ctx, renderCapabilities(scope.support, paintWith(ctx)));
			return;
		}
		const ok = await ctx.ui.confirm(
			"Probe unknown samplers?",
			`${unknown.length} sampler(s) leave no fingerprint in /props. Confirming sends ${unknown.length} one-token requests to the server.${
				(scope.props?.total_slots ?? 1) <= 1
					? " With a single slot this evicts the prompt cache, so the next turn reprocesses its prompt."
					: ""
			}`,
		);
		if (!ok) return;
		ctx.ui.setWorkingMessage("probing sampler support…");
		try {
			const support = await probeSamplerSupport(
				client,
				unknown.map((entry) => entry.id),
				{ idSlot: scope.spareSlot() },
			);
			const merged = scope.support.map((entry) => {
				const probed = support.get(entry.id);
				if (probed === undefined) return entry;
				return {
					id: entry.id,
					support: probed ? ("supported" as const) : ("unsupported" as const),
					evidence: probed
						? "the server echoed it back in generation_settings"
						: "the server dropped it from generation_settings",
				};
			});
			report(ctx, renderCapabilities(merged, paintWith(ctx)));
		} catch (error) {
			ctx.ui.notify(
				`Capability probe failed: ${error instanceof Error ? error.message : String(error)}`,
				"error",
			);
		} finally {
			ctx.ui.setWorkingMessage();
		}
	}

	/**
	 * Measure a distribution before and after the chain.
	 *
	 * Replay mode teacher-forces the tokens the model just produced, so the
	 * numbers describe the real answer rather than a fresh sample.
	 */
	async function runProbeCommand(
		ctx: ExtensionCommandContext,
		args: string,
	): Promise<void> {
		if (probeRunning) {
			ctx.ui.notify("A probe is already running.", "warning");
			return;
		}
		if (!ctx.isIdle()) {
			ctx.ui.notify(
				"Wait for the current turn to finish before probing.",
				"warning",
			);
			return;
		}
		await connectScope(ctx);
		const client = scope.client;
		if (!client) {
			ctx.ui.notify("No llama.cpp server is connected.", "warning");
			return;
		}

		const match = /^(\d+)\s*(.*)$/s.exec(args.trim());
		let steps = match ? Number(match[1]) : 12;
		let promptText = (match ? match[2] : args).trim();
		steps = Math.max(1, Math.min(64, steps));

		const route = routeForRequest();
		const last = scope.store.latest("answer");
		const forced = (last?.tokens ?? []).filter(
			(token) => token.id !== undefined,
		);
		const forcedTokens = forced.map((token) => token.id as number);
		const canReplay =
			promptText === "" &&
			last?.replay !== undefined &&
			forcedTokens.length > 0;

		if (!canReplay && promptText === "") {
			const entered = await ctx.ui.input(
				"Probe prompt",
				"text to sample from (leave empty to cancel)",
			);
			if (!entered || entered.trim() === "") return;
			promptText = entered.trim();
		}

		const funnel =
			route.chain.length > 0 &&
			(await ctx.ui.confirm(
				"Measure the per-sampler funnel?",
				`Adds ${steps * route.chain.length} one-token requests and shows how many candidates survive each stage of ${route.chain.join(
					" → ",
				)}.`,
			));

		const requests = estimateProbeRequests({
			steps,
			chainLength: route.chain.length,
			funnel,
			forced: canReplay,
		});
		const singleSlot = (scope.props?.total_slots ?? 1) <= 1;
		const proceed = await ctx.ui.confirm(
			"Run sampler probe?",
			`${requests} one-token requests against ${scope.upstream}. Each reuses the cached prefix, so the cost is roughly ${requests} decode steps.${
				singleSlot
					? " This server has one slot: the probe replaces the cached prompt, so your next turn reprocesses its prefix."
					: ""
			}`,
		);
		if (!proceed) return;

		probeRunning = true;
		ctx.ui.setWorkingMessage("probing samplers…");
		try {
			let promptTokens: number[];
			if (canReplay && last?.replay) {
				const rendered = await client.applyTemplate({
					...(last.replay.messages !== undefined
						? { messages: last.replay.messages }
						: {}),
					...(last.replay.tools !== undefined
						? { tools: last.replay.tools }
						: {}),
					...(last.replay.chat_template_kwargs !== undefined
						? { chat_template_kwargs: last.replay.chat_template_kwargs }
						: {}),
					add_generation_prompt: true,
				});
				promptTokens = (
					await client.tokenize(rendered.prompt, { parseSpecial: true })
				).tokens;
			} else {
				const rendered = await client.applyTemplate({
					messages: [{ role: "user", content: promptText }],
					add_generation_prompt: true,
				});
				promptTokens = (
					await client.tokenize(rendered.prompt, { parseSpecial: true })
				).tokens;
			}

			const probe = await runProbe(client, {
				promptTokens,
				chain: route.chain,
				params: route.params,
				steps,
				nProbs: Math.max(profile.scope.nProbs, 20),
				funnel,
				forcedTokens: canReplay ? forcedTokens.slice(0, steps) : undefined,
				forcedTexts: canReplay
					? forced.slice(0, steps).map((token) => token.text)
					: undefined,
				idSlot: scope.spareSlot(),
				onProgress: (done, total, label) =>
					ctx.ui.setWorkingMessage(`probing ${done}/${total} · ${label}`),
			});
			lastProbe = probe;
			report(ctx, renderProbeReport(probe, paintWith(ctx)));
			await drillIntoProbe(ctx, probe);
		} catch (error) {
			ctx.ui.notify(
				`Probe failed: ${error instanceof Error ? error.message : String(error)}`,
				"error",
			);
		} finally {
			probeRunning = false;
			ctx.ui.setWorkingMessage();
		}
	}

	async function drillIntoProbe(
		ctx: ExtensionCommandContext,
		probe: ProbeResult,
	): Promise<void> {
		if (!ctx.hasUI || probe.steps.length === 0) return;
		for (;;) {
			const DONE = "✓ Close";
			const labels = probe.steps.map(
				(step) =>
					`#${step.index} ${showTokenLabel(step.text)} w=${step.comparison.width} kept=${(
						step.comparison.keptMass * 100
					).toFixed(0)}%${step.comparison.topDropped ? " ✂top" : ""}`,
			);
			const picked = await ctx.ui.select("Inspect a step (before → after)", [
				...labels,
				DONE,
			]);
			if (!picked || picked === DONE) return;
			const index = labels.indexOf(picked);
			if (index < 0) return;
			report(ctx, renderProbeStep(probe.steps[index], paintWith(ctx)));
		}
	}

	async function setCapture(
		enabled: boolean,
		ctx: ExtensionContext,
	): Promise<string> {
		profile.scope.capture = enabled;
		save();
		if (!enabled) {
			refreshWidget();
			return "Per-token capture off. Requests no longer ask the server for logprobs.";
		}
		await connectScope(ctx);
		const message = scope.proxyUrl
			? "Recording proxy already running."
			: await enableProxy(ctx);
		refreshWidget();
		if (isVllmModel(ctx.model)) return `${scopeModeLabel()}. ${message}`;
		return `Per-token capture on (${profile.scope.probeMode === "post" ? "post-chain" : "raw"}, preview ${profile.scope.nProbs}). The updated server measures rank, survivor count, and entropy across the full distributions, independently of preview depth. Capture disables speculative decoding for these requests. ${message}`;
	}

	pi.registerCommand("sampler-scope", {
		description:
			"Live sampler telemetry: truncation width, logprobs, throughput",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			uiCtx = ctx;
			// Only the subcommand is case-folded; the rest may be probe text.
			const raw = args.trim();
			const split = raw.search(/\s/);
			const command = (split < 0 ? raw : raw.slice(0, split)).toLowerCase();
			const value = split < 0 ? "" : raw.slice(split + 1).trim();
			const flag = value.toLowerCase();
			await connectScope(ctx);
			if (isVllmModel(ctx.model) && ["mode", "slots", "caps", "capabilities", "probe"].includes(command)) {
				ctx.ui.notify("vLLM exposes logprobs previews; llama.cpp slots, post-chain survivor counts and native probes are unavailable.", "info");
				return;
			}

			switch (command) {
				case "on":
				case "capture":
					ctx.ui.notify(await setCapture(flag !== "off", ctx), "info");
					return;
				case "off":
					ctx.ui.notify(await setCapture(false, ctx), "info");
					return;
				case "proxy":
					ctx.ui.notify(
						flag === "off" ? await disableProxy(ctx) : await enableProxy(ctx),
						"info",
					);
					refreshWidget();
					return;
				case "mode":
					profile.scope.probeMode = flag === "raw" ? "raw" : "post";
					save();
					ctx.ui.notify(
						profile.scope.probeMode === "post"
							? "Capturing post-chain survivors: every step reports how many candidates the truncators allowed."
							: "Capturing raw logprobs: every step reports the model's unmodified top-K. No width, and the server pays a full-vocabulary softmax per token.",
						"info",
					);
					refreshWidget();
					return;
				case "nprobs": {
					const parsed = Number(flag);
					if (!Number.isFinite(parsed) || parsed < 1) {
						ctx.ui.notify(`Not a candidate count: ${value}`, "error");
						return;
					}
					profile.scope.nProbs = Math.min(isVllmModel(ctx.model) ? 20 : 1000, Math.round(parsed));
					save();
					ctx.ui.notify(
						isVllmModel(ctx.model) ? `vLLM candidate preview = ${profile.scope.nProbs}; full distribution metrics are unavailable.` : `Candidate preview = ${profile.scope.nProbs}. Full width, entropy, and raw rank are independent of this limit on the updated custom server.`,
						"info",
					);
					return;
				}
				case "widget":
					profile.scope.widget = flag !== "off";
					save();
					refreshWidget();
					ctx.ui.notify(
						`Live widget ${profile.scope.widget ? "on" : "off"}.`,
						"info",
					);
					return;
				case "slots":
					profile.scope.slots = flag !== "off";
					save();
					if (profile.scope.slots) scope.startPolling();
					else scope.stopPolling();
					ctx.ui.notify(
						`/slots polling ${profile.scope.slots ? "on" : "off"}.`,
						"info",
					);
					return;
				case "jsonl":
					profile.scope.jsonl = flag !== "off";
					save();
					ctx.ui.notify(
						profile.scope.jsonl
							? `Appending every generation to ${scope.jsonlPath()}`
							: "JSONL export off.",
						"info",
					);
					return;
				case "report": {
					const record = scope.current();
					if (!record || !requireCapture(ctx)) return;
					report(ctx, renderGenerationReport(record, paintWith(ctx)));
					return;
				}
				case "tokens": {
					const record = scope.current();
					if (!record || !requireCapture(ctx)) return;
					report(ctx, renderExtremes(record, paintWith(ctx)));
					return;
				}
				case "ranks": {
					if (!requireCapture(ctx)) return;
					const record = scope.current();
					if (record) report(ctx, renderRankSteps(record, paintWith(ctx)));
					return;
				}
				case "inspect":
					if (!requireCapture(ctx)) return;
					await inspectToken(ctx);
					return;
				case "stats":
					report(ctx, [
						...renderAggregate(scope.store.all(), paintWith(ctx)),
						"",
						...renderSessionWidthHistogram(scope.store.all(), paintWith(ctx)),
					]);
					return;
				case "caps":
				case "capabilities":
					await runCapabilityProbe(ctx);
					return;
				case "probe":
					await runProbeCommand(ctx, value);
					return;
				case "last":
					if (!lastProbe) {
						ctx.ui.notify("No probe has run yet.", "warning");
						return;
					}
					report(ctx, renderProbeReport(lastProbe, paintWith(ctx)));
					return;
				case "clear":
					scope.store.clear();
					scope.clearDropped();
					refreshWidget();
					ctx.ui.notify("Telemetry history cleared.", "info");
					return;
				case "show":
					ctx.ui.notify(scopeSummary().join("\n"), "info");
					return;
				case "":
					break;
				default:
					ctx.ui.notify(`Unknown subcommand: ${command}`, "error");
					return;
			}

			await openScopeMenu(ctx);
		},
	});

	/** The interactive telemetry menu, shared with `/samplers`. */
	async function openScopeMenu(ctx: ExtensionCommandContext): Promise<void> {
		uiCtx = ctx;
		await connectScope(ctx);
		if (isVllmModel(ctx.model)) {
			if (!ctx.hasUI) { ctx.ui.notify(scopeSummary().join("\n"), "info"); return; }
			for (;;) {
				const pick = await ctx.ui.select(scopeModeLabel(), ["Show telemetry status", "Last generation report", "Inspect token probabilities", "Toggle capture", "Toggle widget", "Close"]);
				if (!pick || pick === "Close") return;
				if (pick === "Show telemetry status") ctx.ui.notify(scopeSummary().join("\n"), "info");
				if (pick === "Toggle capture") ctx.ui.notify(await setCapture(!profile.scope.capture, ctx), "info");
				if (pick === "Toggle widget") { profile.scope.widget = !profile.scope.widget; save(); refreshWidget(); }
				const record = scope.current();
				if (pick === "Last generation report" && record && requireCapture(ctx)) report(ctx, renderGenerationReport(record, paintWith(ctx)));
				if (pick === "Inspect token probabilities" && requireCapture(ctx)) await inspectToken(ctx);
			}
		}
		if (!ctx.hasUI) {
			ctx.ui.notify(scopeSummary().join("\n"), "info");
			return;
		}

		for (;;) {
			const CAPTURE = profile.scope.capture
				? "⏹ Stop per-token capture"
				: "⏺ Start per-token capture (starts the recording proxy)";
			const MODE =
				profile.scope.probeMode === "post"
					? "🔁 Switch to raw logprobs (pre-sampler view)"
					: "🔁 Switch to post-chain survivors (truncation width)";
			const NPROBS = `🔢 Candidate preview (n_probs = ${profile.scope.nProbs})`;
			const WIDGET = profile.scope.widget
				? "👁️  Hide live widget"
				: "👁️  Show live widget";
			const REPORT = "📊 Last generation report";
			const TOKENS = "🔎 Widest / narrowest steps";
			const RANKS = "🔢 Selected-token ranks and averages";
			const INSPECT = "🔬 Inspect one step's candidates";
			const PROBE = "🧪 Probe before/after the chain";
			const STATS = "📈 Session aggregates";
			const CAPS = "🧩 Sampler support on this server";
			const JSONL = profile.scope.jsonl
				? "💾 Stop JSONL export"
				: "💾 Export to JSONL";
			const CLEAR = "🗑️  Clear captured history";
			const DONE = "✓ Close";
			const choice = await ctx.ui.select(
				scopeSummary()[0],
				[
					CAPTURE,
					MODE,
					NPROBS,
					WIDGET,
					REPORT,
					TOKENS,
					RANKS,
					INSPECT,
					PROBE,
					STATS,
					CAPS,
					JSONL,
					CLEAR,
					DONE,
				],
				{ helpText: scopeSummary().slice(1).join(" · ") },
			);
			if (choice === undefined || choice === DONE) return;
			if (choice === CAPTURE) {
				ctx.ui.notify(await setCapture(!profile.scope.capture, ctx), "info");
			} else if (choice === RANKS) {
				if (!requireCapture(ctx)) continue;
				const record = scope.current();
				if (record) report(ctx, renderRankSteps(record, paintWith(ctx)));
			} else if (choice === MODE) {
				profile.scope.probeMode =
					profile.scope.probeMode === "post" ? "raw" : "post";
				save();
				refreshWidget();
			} else if (choice === NPROBS) {
				const entered = await ctx.ui.input(
					"Candidate preview depth (full width is unaffected)",
					String(profile.scope.nProbs),
				);
				const parsed = Number(entered);
				if (Number.isFinite(parsed) && parsed >= 1) {
					profile.scope.nProbs = Math.min(1000, Math.round(parsed));
					save();
				}
			} else if (choice === WIDGET) {
				profile.scope.widget = !profile.scope.widget;
				save();
				refreshWidget();
			} else if (choice === REPORT) {
				const record = scope.current();
				if (record && requireCapture(ctx)) {
					report(ctx, renderGenerationReport(record, paintWith(ctx)));
				}
			} else if (choice === TOKENS) {
				const record = scope.current();
				if (record && requireCapture(ctx)) {
					report(ctx, renderExtremes(record, paintWith(ctx)));
				}
			} else if (choice === INSPECT) {
				if (requireCapture(ctx)) await inspectToken(ctx);
			} else if (choice === PROBE) {
				await runProbeCommand(ctx, "");
			} else if (choice === STATS) {
				report(ctx, [
					...renderAggregate(scope.store.all(), paintWith(ctx)),
					"",
					...renderSessionWidthHistogram(scope.store.all(), paintWith(ctx)),
				]);
			} else if (choice === CAPS) {
				await runCapabilityProbe(ctx);
			} else if (choice === JSONL) {
				profile.scope.jsonl = !profile.scope.jsonl;
				save();
			} else if (choice === CLEAR) {
				scope.store.clear();
				scope.clearDropped();
				refreshWidget();
			}
		}
	}

	// --- /sampler-probe : before/after in one command -------------------------

	pi.registerCommand("sampler-probe", {
		description: "Measure one distribution before and after the sampler chain",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			if (isVllmModel(ctx.model)) {
				ctx.ui.notify("Before/after sampler probes require llama.cpp. Use /sampler-scope for vLLM logprobs.", "info");
				return;
			}
			uiCtx = ctx;
			await runProbeCommand(ctx, args);
		},
	});

	// --- /logit-bias : per-token logit bias ----------------------------------

	function biasSummary(): string[] {
		const lines = [
			`logit bias: ${profile.bias.enabled ? "on" : "off"} · ${thinkCapSummary()}`,
		];
		const { resolved, unresolved } = resolveBiasEntries(profile.bias, tokenSet);
		if (resolved.length === 0 && unresolved.length === 0) {
			lines.push("  (no biased tokens)");
		}
		const finalTemp = finalTemperature();
		for (const entry of resolved) {
			const odds = biasOddsMultiplier(entry.amount, finalTemp);
			const effect =
				odds === undefined
					? ""
					: odds === 0
						? " · never sampled"
						: ` · ×${odds < 10 ? odds.toFixed(2) : odds.toFixed(0)} odds at temp ${finalTemp}`;
			lines.push(
				`  ${entry.text ?? `#${entry.id}`} → ${formatBiasAmount(entry.amount)} (id ${entry.id}${
					entry.role && entry.role !== "other" ? `, ${entry.role}` : ""
				})${effect}`,
			);
		}
		for (const key of unresolved) {
			lines.push(`  ${key} → unresolved on this model, so it is not sent`);
		}
		if (tokenSet) {
			const close = findThinkCloseToken(tokenSet);
			lines.push(
				`tokens: ${tokenSet.tokens.length} special via ${tokenSet.source}${
					tokenSet.architecture ? ` (${tokenSet.architecture})` : ""
				} · end-of-thinking ${close ? `${close.text} = ${close.id}` : "not found"}`,
			);
			if (tokenSet.note) lines.push(`  ${tokenSet.note}`);
		} else {
			lines.push(`tokens: not detected${tokenError ? ` (${tokenError})` : ""}`);
		}
		return lines;
	}

	/**
	 * The temperature the chain ends on, for the effect estimate.
	 *
	 * Bias lands on raw logits and temperature is applied last, so what a bias is
	 * actually worth depends on this number. Reported as undefined-ish (1) when
	 * temperature is not in the chain at all.
	 */
	function finalTemperature(): number {
		const route = routeForRequest();
		if (!route.chain.includes("temperature")) return 1;
		const value = route.params.temperature;
		return typeof value === "number" ? value : 1;
	}

	function tokenLabel(token: SpecialToken): string {
		const biased = profile.bias.entries[biasKeyFor(token)];
		const mark =
			biased === undefined ? "" : `  [${formatBiasAmount(biased)}]`;
		return `${token.text}  id ${token.id}${mark}`;
	}

	function renderTokenList(all: boolean): string[] {
		if (!tokenSet) {
			return [
				`No special tokens detected${tokenError ? `: ${tokenError}` : " yet"}.`,
				"Run `/logit-bias scan` once the llama.cpp server is reachable.",
			];
		}
		const visible = all
			? tokenSet.tokens
			: tokenSet.tokens.filter((token) => token.role !== "unused");
		// Tokens the user named are theirs, not part of the vocabulary's inventory,
		// so they get their own section instead of being scattered through it.
		const shown = visible.filter((token) => !token.added);
		const added = visible.filter((token) => token.added);
		const byRole = new Map<string, SpecialToken[]>();
		for (const token of shown) {
			const list = byRole.get(token.role);
			if (list) list.push(token);
			else byRole.set(token.role, [token]);
		}
		const lines = [
			`${shown.length} special token(s) from ${tokenSet.source}${
				tokenSet.modelAlias ? ` · ${tokenSet.modelAlias}` : ""
			}${tokenSet.nVocab ? ` · n_vocab ${tokenSet.nVocab}` : ""}`,
		];
		// think_close first: it is the one anyone came here for.
		const order = [...byRole.keys()].sort((a, b) => {
			if (a === "think_close") return -1;
			if (b === "think_close") return 1;
			return a.localeCompare(b);
		});
		for (const role of order) {
			const tokens = byRole.get(role) ?? [];
			lines.push(`${role}:`);
			for (const token of tokens) {
				const flag = token.needsParseSpecial === false ? " (merges as text)" : "";
				lines.push(`  ${tokenLabel(token)}  ${token.kind}${flag}`);
			}
		}
		if (added.length > 0) {
			lines.push("added by you (ordinary vocabulary):");
			for (const token of added) {
				lines.push(`  ${tokenLabel(token)}  ${token.kind}`);
			}
		}
		const hiddenCount = tokenSet.tokens.length - visible.length;
		if (hiddenCount > 0) {
			lines.push(
				`(${hiddenCount} unused placeholder slot(s) hidden; \`/logit-bias tokens all\` shows them)`,
			);
		}
		lines.push(
			"Any token can be biased, not only these: `/logit-bias tokenize <text>` shows what a string is made of.",
		);
		return lines;
	}

	/** Apply a bias, switching the feature on so the change actually takes effect. */
	function stampBias(key: string, amount: number | "ban"): void {
		setBias(profile.bias, key, amount);
		profile.bias.enabled = true;
		warnedUnresolved = "";
		save();
	}

	/**
	 * Resolve arbitrary text to one token, explaining itself when it cannot.
	 *
	 * Multi-token text is the common failure and deserves a real answer: show the
	 * breakdown and point at `parts`, which biases each piece deliberately rather
	 * than by accident.
	 */
	async function resolveLiteralInteractive(
		ctx: ExtensionCommandContext,
		text: string,
	): Promise<SpecialToken | undefined> {
		const client = scope.client;
		if (!client) {
			ctx.ui.notify(
				`No token matches ${text}, and there is no llama.cpp server connected to ask about it.`,
				"error",
			);
			return undefined;
		}
		try {
			const result = await resolveLiteralToken(client, text);
			if (result.kind === "single") {
				rememberToken(result.token);
				return result.token;
			}
			// A word is usually one token only with its leading space, because that
			// is how BPE stores it. Worth checking before sending anyone to `parts`.
			let hint = "";
			if (!text.startsWith(" ")) {
				try {
					const spaced = await resolveLiteralToken(client, ` ${text}`);
					if (spaced.kind === "single") {
						hint = ` Note that ${JSON.stringify(` ${text}`)} with a leading space is a single token (id ${spaced.token.id}); quote it to keep the space: \`/logit-bias set " ${text}" <bias>\`.`;
					}
				} catch {
					/* the hint is a nicety */
				}
			}
			ctx.ui.notify(
				`${JSON.stringify(text)} is ${result.pieces.length} tokens, not one: ${describePieces(
					result.pieces,
				)}.${hint} Bias one of them with \`/logit-bias set #<id> <bias>\`, or all of them with \`/logit-bias parts ${text} <bias>\`.`,
				"error",
			);
			return undefined;
		} catch (error) {
			ctx.ui.notify(
				`Could not tokenize ${JSON.stringify(text)}: ${
					error instanceof Error ? error.message : String(error)
				}`,
				"error",
			);
			return undefined;
		}
	}

	/** A server too old for `with_pieces` returns ids only; say so rather than `""`. */
	function describePieces(
		pieces: readonly { id: number; piece: string }[],
	): string {
		return pieces
			.map((piece) =>
				piece.piece === ""
					? `#${piece.id}`
					: `${JSON.stringify(piece.piece)}=${piece.id}`,
			)
			.join(" ");
	}

	async function setBiasFromArgs(
		ctx: ExtensionCommandContext,
		reference: string,
		rawAmount: string,
	): Promise<void> {
		await ensureTokens(ctx);
		const amount = parseBiasAmount(rawAmount);
		if (amount === undefined) {
			ctx.ui.notify(
				`Not a bias: ${rawAmount}. Use a number within ±100, or "ban".`,
				"error",
			);
			return;
		}
		let token = resolveTokenReference(tokenSet, reference);
		if (!token) {
			// Not a special token and not an id, so treat it as literal text: any
			// token in the vocabulary is biasable, not just the markup.
			const literal = await resolveLiteralInteractive(ctx, reference);
			if (!literal) return;
			token = literal;
		}
		if (tokenSet?.nVocab !== undefined && token.id >= tokenSet.nVocab) {
			ctx.ui.notify(
				`Token id ${token.id} is outside this model's vocabulary of ${tokenSet.nVocab}; llama.cpp would discard it silently.`,
				"error",
			);
			return;
		}
		const key = biasKeyFor(token);
		stampBias(key, amount);
		refreshStatus(ctx);
		// A huge positive bias on a close tag is the one case where the value the
		// user asked for misbehaves in a non-obvious way. Apply it anyway and say so.
		const close = findThinkCloseToken(tokenSet);
		const runaway =
			typeof amount === "number" &&
			amount >= BIAS_RUNAWAY_HINT &&
			close !== undefined &&
			close.id === token.id;
		ctx.ui.notify(
			`${key} (id ${token.id}) → ${formatBiasAmount(amount)}. ${summarizeBias(
				profile.bias,
				tokenSet,
			)}${runaway ? `\n\n${THINK_RUNAWAY_NOTE}` : ""}`,
			runaway ? "warning" : "info",
		);
	}

	/**
	 * Bias every token of a multi-token string.
	 *
	 * This is what llama.cpp does when handed a string in `logit_bias`, and it is
	 * a legitimate thing to want — it suppresses a word the way `presence_penalty`
	 * suppresses everything — but the semantics are surprising enough to deserve
	 * its own verb. Each piece becomes its own entry, so the listing shows exactly
	 * what is being biased and any one of them can be removed on its own.
	 */
	async function biasPartsFromArgs(
		ctx: ExtensionCommandContext,
		text: string,
		rawAmount: string,
	): Promise<void> {
		const amount = parseBiasAmount(rawAmount);
		if (amount === undefined) {
			ctx.ui.notify(
				`Not a bias: ${rawAmount}. Use a number within ±100, or "ban".`,
				"error",
			);
			return;
		}
		await ensureTokens(ctx);
		const client = scope.client;
		if (!client) {
			ctx.ui.notify("No llama.cpp server is connected.", "warning");
			return;
		}
		let pieces: { id: number; piece: string }[];
		try {
			pieces = await tokenizeWithPieces(client, text);
		} catch (error) {
			ctx.ui.notify(
				`Could not tokenize ${JSON.stringify(text)}: ${
					error instanceof Error ? error.message : String(error)
				}`,
				"error",
			);
			return;
		}
		if (pieces.length === 0) {
			ctx.ui.notify(`${JSON.stringify(text)} is not any tokens at all.`, "error");
			return;
		}
		const keys: string[] = [];
		for (const piece of pieces) {
			// Key by text only when the piece stands alone as the same token;
			// otherwise by id, because a BPE fragment need not round-trip.
			let key = `#${piece.id}`;
			if (piece.piece !== "") {
				try {
					const round = await client.tokenize(piece.piece, {
						addSpecial: false,
						parseSpecial: true,
					});
					if (round.tokens.length === 1 && round.tokens[0] === piece.id) {
						key = piece.piece;
					}
				} catch {
					/* keep the id form */
				}
			}
			rememberToken({
				id: piece.id,
				text: piece.piece === "" ? key : piece.piece,
				role: "other",
				kind: "normal",
				added: true,
			});
			stampBias(key, amount);
			keys.push(key);
		}
		refreshStatus(ctx);
		ctx.ui.notify(
			`Biased ${pieces.length} token(s) of ${JSON.stringify(text)} by ${formatBiasAmount(
				amount,
			)}: ${describePieces(pieces)}. Remove one with \`/logit-bias clear <token>\`.`,
			"info",
		);
	}

	/** Show how the server tokenizes text, so a bias can be aimed properly. */
	async function showTokenization(
		ctx: ExtensionCommandContext,
		text: string,
	): Promise<void> {
		await ensureTokens(ctx);
		const client = scope.client;
		if (!client) {
			ctx.ui.notify("No llama.cpp server is connected.", "warning");
			return;
		}
		try {
			const pieces = await tokenizeWithPieces(client, text);
			const lines = [
				`${JSON.stringify(text)} is ${pieces.length} token(s):`,
				...pieces.map((piece, index) => {
					const known = tokenSet?.tokens.find((token) => token.id === piece.id);
					const biased = known ? profile.bias.entries[biasKeyFor(known)] : undefined;
					return `  ${String(index).padStart(3)}  id ${String(piece.id).padStart(6)}  ${
						piece.piece === "" ? "(piece unavailable)" : JSON.stringify(piece.piece)
					}${known && known.role !== "other" ? `  ${known.role}` : ""}${
						biased === undefined ? "" : `  [${formatBiasAmount(biased)}]`
					}`;
				}),
				pieces.length === 1
					? `Bias it with \`/logit-bias set ${text} <bias>\`.`
					: `Bias one with \`/logit-bias set #<id> <bias>\`, or all with \`/logit-bias parts ${text} <bias>\`.`,
			];
			report(ctx, lines);
		} catch (error) {
			ctx.ui.notify(
				`Could not tokenize ${JSON.stringify(text)}: ${
					error instanceof Error ? error.message : String(error)
				}`,
				"error",
			);
		}
	}

	/**
	 * Measure how far a bias on the end-of-thinking token actually moves
	 * reasoning length.
	 *
	 * Each level is one `/completion` that stops at the close tag, so
	 * `tokens_predicted` is exactly the length of the reasoning block. The prompt
	 * prefix is shared across levels, so with `cache_prompt` only the decode is
	 * paid for. The right bias is model- and chain-specific; this is the way to
	 * find it rather than guessing.
	 */
	async function runBiasMeasure(
		ctx: ExtensionCommandContext,
		args: string,
	): Promise<void> {
		if (!ctx.isIdle()) {
			ctx.ui.notify(
				"Wait for the current turn to finish before measuring.",
				"warning",
			);
			return;
		}
		await ensureTokens(ctx);
		const client = scope.client;
		if (!client) {
			ctx.ui.notify("No llama.cpp server is connected.", "warning");
			return;
		}
		const close = findThinkCloseToken(tokenSet);
		if (!close) {
			ctx.ui.notify(
				"This model has no single end-of-thinking token, so there is nothing to measure. `/logit-bias tokens` shows what was detected.",
				"warning",
			);
			return;
		}

		// A leading comma-separated list overrides the default levels, matching the
		// `[n] [text]` shape of /sampler-probe.
		const levelMatch = /^([\d.,\s-]+?)(?:\s+(.*))?$/s.exec(args.trim());
		let levels = [0, ...THINK_LESS_LEVELS.map((level) => level.amount)];
		let promptText = args.trim();
		if (levelMatch && levelMatch[1].includes(",")) {
			const parsed = levelMatch[1]
				.split(",")
				.map((part) => Number(part.trim()))
				.filter((value) => Number.isFinite(value));
			if (parsed.length > 0) {
				levels = parsed;
				promptText = (levelMatch[2] ?? "").trim();
			}
		}
		if (promptText === "") {
			promptText =
				"A farmer has 17 sheep and all but 9 run away. How many are left? Answer with just the number.";
		}
		levels = [...new Set(levels)].slice(0, 8);

		const maxTokens = 600;
		const proceed = await ctx.ui.confirm(
			"Measure reasoning length?",
			`${levels.length} generation(s) of up to ${maxTokens} tokens each against ${scope.upstream}, one per bias level (${levels.join(", ")}). Each stops at ${close.text}, so only the reasoning block is decoded.${
				(scope.props?.total_slots ?? 1) <= 1
					? " This server has one slot, so your next turn reprocesses its prompt."
					: ""
			}`,
		);
		if (!proceed) return;

		const route = routeForRequest();
		ctx.ui.setWorkingMessage("measuring reasoning length…");
		try {
			const rendered = await client.applyTemplate({
				messages: [{ role: "user", content: promptText }],
				add_generation_prompt: true,
			});
			// Only a prompt already inside the reasoning block measures the block.
			// Templates that force thinking open (Qwen3, DeepSeek-R1) end with the
			// open tag already; the rest need it teacher-forced.
			const open = tokenSet?.tokens.find(
				(token) => token.role === "think_open",
			);
			let prompt = rendered.prompt;
			let forcedOpen = false;
			if (open && !prompt.trimEnd().endsWith(open.text)) {
				prompt = `${prompt}${open.text}\n`;
				forcedOpen = true;
			}

			const rows: {
				level: number;
				tokens: number;
				hitCap: boolean;
			}[] = [];
			for (const level of levels) {
				ctx.ui.setWorkingMessage(
					`measuring bias ${formatBiasAmount(level)} (${rows.length + 1}/${levels.length})…`,
				);
				const body: Record<string, unknown> = {
					prompt,
					n_predict: maxTokens,
					stop: [close.text],
					cache_prompt: true,
					// A fixed seed keeps the comparison about the bias rather than luck.
					seed: 1234,
					samplers: [...route.chain],
					...route.params,
				};
				if (level !== 0) body.logit_bias = [[close.id, level]];
				const result = await client.completion(body);
				const predicted = Number(result.tokens_predicted ?? 0);
				rows.push({
					level,
					tokens: predicted,
					hitCap: result.stop_type !== "word",
				});
			}

			const baseline = rows.find((row) => row.level === 0)?.tokens;
			const lines = [
				`Reasoning length vs bias on ${close.text} (id ${close.id})`,
				`prompt: ${promptText.length > 70 ? `${promptText.slice(0, 69)}…` : promptText}`,
				`chain: ${summarizeChain(route.chain, route.params)}`,
				...(forcedOpen
					? [
							`note: the template does not force thinking open, so ${open?.text} was appended to the prompt`,
						]
					: []),
				"",
			];
			const widest = Math.max(...rows.map((row) => row.tokens), 1);
			for (const row of rows) {
				const bar = "█".repeat(Math.max(1, Math.round((row.tokens / widest) * 28)));
				const delta =
					baseline === undefined || row.level === 0
						? ""
						: ` (${row.tokens < baseline ? "−" : "+"}${Math.round(
								(Math.abs(row.tokens - baseline) / Math.max(1, baseline)) * 100,
							)}%)`;
				lines.push(
					`${formatBiasAmount(row.level).padStart(7)}  ${String(row.tokens).padStart(4)} tok ${bar}${delta}${
						row.hitCap ? "  ⚠ hit the token cap, never closed" : ""
					}`,
				);
			}
			lines.push(
				"",
				"One sample per level, so read the trend rather than any single number.",
			);
			report(ctx, lines);
		} catch (error) {
			ctx.ui.notify(
				`Measurement failed: ${error instanceof Error ? error.message : String(error)}`,
				"error",
			);
		} finally {
			ctx.ui.setWorkingMessage();
		}
	}

	/** Pick one detected token, grouped so the useful ones are reachable. */
	async function pickToken(
		ctx: ExtensionCommandContext,
		title: string,
	): Promise<SpecialToken | undefined> {
		if (!tokenSet || tokenSet.tokens.length === 0) {
			ctx.ui.notify(
				`No special tokens detected${tokenError ? `: ${tokenError}` : " yet"}.`,
				"warning",
			);
			return undefined;
		}
		const candidates = tokenSet.tokens.filter(
			(token) => token.role !== "unused",
		);
		const TYPED = "⌨️  Type any token or text…";
		const options = [
			{
				label: TYPED,
				description: "bias an ordinary word or a raw id, not just a special token",
			},
			...candidates.map((token) => ({
				label: tokenLabel(token),
				description: `${token.role} · ${token.kind}`,
			})),
		];
		const picked = await ctx.ui.select(title, options);
		if (!picked) return undefined;
		if (picked === TYPED) {
			const entered = await ctx.ui.input(
				"Token text, or #id",
				"e.g. </think>, #248069, or a word",
			);
			if (entered === undefined || entered.trim() === "") return undefined;
			const reference = entered.trim();
			const known = resolveTokenReference(tokenSet, reference);
			if (known && "text" in known) return known;
			if (known) {
				// A bare id with no detected token behind it is still biasable.
				const bare: SpecialToken = {
					id: known.id,
					text: `#${known.id}`,
					role: "other",
					kind: "normal",
					added: true,
				};
				rememberToken(bare);
				return bare;
			}
			return await resolveLiteralInteractive(ctx, reference);
		}
		return candidates.find((token) => tokenLabel(token) === picked);
	}

	async function promptForAmount(
		ctx: ExtensionCommandContext,
		token: SpecialToken,
	): Promise<void> {
		const current = profile.bias.entries[biasKeyFor(token)];
		const BAN = "ban (never sample)";
		const CUSTOM = "Custom…";
		const presets = ["1.5", "3", "5", "8", "-2", "-5"];
		const picked = await ctx.ui.select(
			`Bias for ${token.text}${current === undefined ? "" : ` (now ${formatBiasAmount(current)})`}`,
			[...presets, BAN, CUSTOM],
		);
		if (!picked) return;
		let raw = picked;
		if (picked === BAN) raw = "ban";
		else if (picked === CUSTOM) {
			const entered = await ctx.ui.input(
				`Bias for ${token.text} (raw logit offset, or "ban")`,
				current === undefined ? "3" : String(current),
			);
			if (entered === undefined || entered.trim() === "") return;
			raw = entered;
		}
		const amount = parseBiasAmount(raw);
		if (amount === undefined) {
			ctx.ui.notify(`Not a bias: ${raw}`, "error");
			return;
		}
		stampBias(biasKeyFor(token), amount);
		refreshStatus(ctx);
		ctx.ui.notify(
			`${token.text} → ${formatBiasAmount(amount)}. ${summarizeBias(profile.bias, tokenSet)}`,
			"info",
		);
	}

	async function openBiasMenu(ctx: ExtensionCommandContext): Promise<void> {
		uiCtx = ctx;
		await ensureTokens(ctx);
		if (!ctx.hasUI) {
			ctx.ui.notify(biasSummary().join("\n"), "info");
			return;
		}
		for (;;) {
			const TOGGLE = profile.bias.enabled
				? "⏻ Disable logit bias"
				: "⏻ Enable logit bias";
			const THINK = "🧠 Think less (bias the end-of-thinking token)";
			const CAP = `⏱️  Hard cap on reasoning tokens (${
				profile.thinkCap === null ? "off" : profile.thinkCap
			})`;
			const ADD = "➕ Bias a token";
			const EDIT = "✏️  Change or remove a bias";
			const TOKENS = "🔤 Show detected special tokens";
			const TOKENIZE = "🔍 Tokenize some text";
			const MEASURE = "📏 Measure reasoning length vs bias";
			const SCAN = "🔄 Re-detect special tokens";
			const SHOW = "👁️  Show current biases";
			const CLEAR = "🗑️  Clear all biases";
			const DONE = "✓ Close";
			const choice = await ctx.ui.select(
				summarizeBias(profile.bias, tokenSet),
				[
					TOGGLE,
					THINK,
					CAP,
					ADD,
					EDIT,
					TOKENS,
					TOKENIZE,
					MEASURE,
					SCAN,
					SHOW,
					CLEAR,
					DONE,
				],
				{ helpText: biasSummary().slice(-1).join("") },
			);
			if (choice === undefined || choice === DONE) {
				refreshStatus(ctx);
				return;
			}
			if (choice === TOGGLE) {
				profile.bias.enabled = !profile.bias.enabled;
				save();
				refreshStatus(ctx);
			} else if (choice === THINK) {
				await pickThinkLessLevel(ctx);
			} else if (choice === CAP) {
				await pickThinkCap(ctx);
			} else if (choice === ADD) {
				const token = await pickToken(ctx, "Bias which token?");
				if (token) await promptForAmount(ctx, token);
			} else if (choice === EDIT) {
				const keys = Object.keys(profile.bias.entries);
				if (keys.length === 0) {
					ctx.ui.notify("Nothing is biased yet.", "info");
					continue;
				}
				const REMOVE = "‹remove›";
				const labels = keys.map(
					(key) => `${key} → ${formatBiasAmount(profile.bias.entries[key])}`,
				);
				const picked = await ctx.ui.select("Which bias?", labels);
				if (!picked) continue;
				const key = keys[labels.indexOf(picked)];
				const action = await ctx.ui.select(key, ["change", REMOVE]);
				if (action === REMOVE) {
					clearBias(profile.bias, key);
					warnedUnresolved = "";
					save();
					refreshStatus(ctx);
					ctx.ui.notify(`Removed the bias on ${key}.`, "info");
				} else if (action === "change") {
					const token = resolveTokenReference(tokenSet, key);
					if (token && "text" in token) await promptForAmount(ctx, token);
					else {
						const entered = await ctx.ui.input(
							`Bias for ${key}`,
							String(profile.bias.entries[key]),
						);
						const amount =
							entered === undefined ? undefined : parseBiasAmount(entered);
						if (amount !== undefined) {
							stampBias(key, amount);
							refreshStatus(ctx);
						}
					}
				}
			} else if (choice === TOKENS) {
				report(ctx, renderTokenList(false));
			} else if (choice === TOKENIZE) {
				const entered = await ctx.ui.input("Tokenize which text?", "");
				if (entered !== undefined && entered.trim() !== "") {
					await showTokenization(ctx, entered);
				}
			} else if (choice === MEASURE) {
				await runBiasMeasure(ctx, "");
			} else if (choice === SCAN) {
				ctx.ui.setWorkingMessage("detecting special tokens…");
				await ensureTokens(ctx, true);
				ctx.ui.setWorkingMessage();
				report(ctx, renderTokenList(false));
			} else if (choice === SHOW) {
				report(ctx, biasSummary());
			} else if (choice === CLEAR) {
				profile.bias.entries = {};
				warnedUnresolved = "";
				save();
				refreshStatus(ctx);
				ctx.ui.notify("All logit biases cleared.", "info");
			}
		}
	}

	async function pickThinkLessLevel(
		ctx: ExtensionCommandContext,
	): Promise<void> {
		await ensureTokens(ctx);
		const close = findThinkCloseToken(tokenSet);
		if (!close) {
			ctx.ui.notify(thinkCloseMissingMessage(), "warning");
			return;
		}
		const OFF = "off — remove the bias";
		const options = [
			...THINK_LESS_LEVELS.map((level) => ({
				label: `${level.name} (${formatBiasAmount(level.amount)})`,
				description: level.blurb,
			})),
			{ label: OFF, description: `stop biasing ${close.text}` },
		];
		const picked = await ctx.ui.select(
			`Bias ${close.text} (id ${close.id})`,
			options,
		);
		if (!picked) return;
		if (picked === OFF) {
			clearBias(profile.bias, biasKeyFor(close));
			warnedUnresolved = "";
			save();
			refreshStatus(ctx);
			ctx.ui.notify(`No longer biasing ${close.text}.`, "info");
			return;
		}
		const level = THINK_LESS_LEVELS.find((entry) =>
			picked.startsWith(`${entry.name} `),
		);
		if (!level) return;
		stampBias(biasKeyFor(close), level.amount);
		refreshStatus(ctx);
		ctx.ui.notify(thinkLessAppliedMessage(close, level.amount), "info");
	}

	function thinkCloseMissingMessage(): string {
		if (!tokenSet) {
			return `No special tokens detected yet${tokenError ? ` (${tokenError})` : ""}. Run \`/logit-bias scan\` with the llama.cpp server up.`;
		}
		return `This model has no single end-of-thinking token, so there is nothing to upweight. Some models (gpt-oss) leave the reasoning channel with a header rather than a close tag. \`/logit-bias tokens\` lists what was found.`;
	}

	function thinkLessAppliedMessage(
		close: SpecialToken,
		amount: number,
	): string {
		const temp = finalTemperature();
		const odds = biasOddsMultiplier(amount, temp);
		return [
			`${close.text} (id ${close.id}) biased ${formatBiasAmount(amount)}.`,
			odds === undefined || odds === 0
				? ""
				: `After the final temperature of ${temp} that is roughly ×${odds < 10 ? odds.toFixed(2) : odds.toFixed(0)} on its odds, though the bias lands before truncation so most of the effect is on whether it survives the gate at all.`,
			amount >= BIAS_RUNAWAY_HINT
				? `That is past the usable range: ${THINK_RUNAWAY_NOTE}`
				: "Use `/logit-bias measure` to see what it does to reasoning length.",
		]
			.filter(Boolean)
			.join(" ");
	}

	pi.registerCommand("logit-bias", {
		description:
			"Bias individual token logits; auto-detects the model's special tokens",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			uiCtx = ctx;
			if (isVllmModel(ctx.model)) {
				ctx.ui.notify("This extension's token-bias and think-cap tools require llama.cpp; they are not sent to vLLM.", "info");
				return;
			}
			const raw = args.trim();
			const split = raw.search(/\s/);
			const command = (split < 0 ? raw : raw.slice(0, split)).toLowerCase();
			const rest = split < 0 ? "" : raw.slice(split + 1).trim();

			switch (command) {
				case "on":
				case "off":
					profile.bias.enabled = command === "on";
					save();
					refreshStatus(ctx);
					ctx.ui.notify(
						profile.bias.enabled
							? `Logit bias ON. ${summarizeBias(profile.bias, tokenSet)}`
							: "Logit bias OFF; requests no longer carry logit_bias.",
						"info",
					);
					return;
				case "show":
				case "list":
					await ensureTokens(ctx);
					report(ctx, biasSummary());
					return;
				case "tokens":
					await ensureTokens(ctx);
					report(ctx, renderTokenList(rest.toLowerCase() === "all"));
					return;
				case "scan":
				case "detect": {
					ctx.ui.setWorkingMessage("detecting special tokens…");
					const detected = await ensureTokens(ctx, true);
					ctx.ui.setWorkingMessage();
					refreshStatus(ctx);
					if (!detected) {
						ctx.ui.notify(
							`Detection failed${tokenError ? `: ${tokenError}` : ""}.`,
							"error",
						);
						return;
					}
					report(ctx, renderTokenList(rest.toLowerCase() === "all"));
					return;
				}
				case "set": {
					const split2 = splitReferenceAndAmount(rest);
					if (!split2) {
						ctx.ui.notify(
							'Usage: /logit-bias set <token|text|#id|role> <bias>. Quote the token to keep a leading space: `set " delve" -4`.',
							"error",
						);
						return;
					}
					await setBiasFromArgs(ctx, split2.reference, split2.amount);
					return;
				}
				case "ban":
					if (rest === "") {
						ctx.ui.notify("Usage: /logit-bias ban <token|text|#id|role>", "error");
						return;
					}
					await setBiasFromArgs(ctx, unquote(rest), "ban");
					return;
				case "parts": {
					const split2 = splitReferenceAndAmount(rest);
					if (!split2) {
						ctx.ui.notify(
							"Usage: /logit-bias parts <text> <bias> — biases every token the text is made of",
							"error",
						);
						return;
					}
					await biasPartsFromArgs(ctx, split2.reference, split2.amount);
					return;
				}
				case "tokenize":
					if (rest === "") {
						ctx.ui.notify("Usage: /logit-bias tokenize <text>", "error");
						return;
					}
					await showTokenization(ctx, unquote(rest));
					return;
				case "clear":
				case "unset": {
					if (rest === "" || rest.toLowerCase() === "all") {
						profile.bias.entries = {};
						warnedUnresolved = "";
						save();
						refreshStatus(ctx);
						ctx.ui.notify("All logit biases cleared.", "info");
						return;
					}
					await ensureTokens(ctx);
					const reference = unquote(rest);
					const token = resolveTokenReference(tokenSet, reference);
					const key =
						token && clearBias(profile.bias, biasKeyFor(token))
							? biasKeyFor(token)
							: clearBias(profile.bias, reference)
								? reference
								: undefined;
					warnedUnresolved = "";
					save();
					refreshStatus(ctx);
					ctx.ui.notify(
						key
							? `Removed the bias on ${key}.`
							: `Nothing was biased under ${rest}.`,
						key ? "info" : "warning",
					);
					return;
				}
				case "measure":
					await runBiasMeasure(ctx, rest);
					return;
				case "":
					break;
				default:
					ctx.ui.notify(
						`Unknown subcommand: ${command}. Try show, tokens, tokenize, scan, set, parts, ban, clear, measure, on, off.`,
						"error",
					);
					return;
			}

			await openBiasMenu(ctx);
		},
	});

	// --- /think-less : the end-of-thinking nudge ------------------------------

	// --- /think-cap : a hard limit that cannot run away --------------------------

	function thinkCapSummary(): string {
		if (profile.thinkCap === null) return "think cap: off";
		if (profile.thinkCap === MIN_THINK_CAP) {
			return `think cap: ${MIN_THINK_CAP} (no reasoning at all)`;
		}
		return `think cap: ${profile.thinkCap} tokens`;
	}

	function setThinkCap(cap: number | null, ctx: ExtensionContext): void {
		profile.thinkCap = cap;
		save();
		refreshStatus(ctx);
	}

	/** Interactive budget picker, shared by `/think-cap` and the bias menu. */
	async function pickThinkCap(ctx: ExtensionCommandContext): Promise<void> {
		if (!ctx.hasUI) {
			ctx.ui.notify(thinkCapSummary(), "info");
			return;
		}
		const OFF = "off — no limit";
		const CUSTOM = "Custom…";
		const options = [
			{ label: "1", description: "no reasoning at all (0 would be a no-op)" },
			{ label: "64", description: "a sentence or two of reasoning" },
			{ label: "128", description: "short reasoning" },
			{ label: "256", description: "moderate reasoning" },
			{ label: "512", description: "generous, still bounded" },
			{ label: OFF, description: "let the model reason as long as it likes" },
			{ label: CUSTOM, description: "enter a token count" },
		];
		const picked = await ctx.ui.select(thinkCapSummary(), options);
		if (!picked) return;
		if (picked === OFF) {
			setThinkCap(null, ctx);
			ctx.ui.notify("Think cap off.", "info");
			return;
		}
		let raw = picked;
		if (picked === CUSTOM) {
			const entered = await ctx.ui.input(
				"Reasoning token budget",
				String(profile.thinkCap ?? 128),
			);
			if (entered === undefined || entered.trim() === "") return;
			raw = entered;
		}
		const parsed = parseThinkCap(raw);
		if (!parsed.ok) {
			ctx.ui.notify(parsed.reason, "error");
			return;
		}
		setThinkCap(parsed.cap, ctx);
		ctx.ui.notify(
			parsed.cap === null ? "Think cap off." : await thinkCapAppliedMessage(ctx),
			"info",
		);
	}

	pi.registerCommand("think-cap", {
		description:
			"Hard-limit tokens inside the reasoning block (forces the close tag once)",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			uiCtx = ctx;
			if (isVllmModel(ctx.model)) {
				ctx.ui.notify("This extension's token-bias and think-cap tools require llama.cpp; they are not sent to vLLM.", "info");
				return;
			}
			const arg = args.trim().toLowerCase();

			if (arg === "show") {
				await ensureTokens(ctx);
				report(ctx, biasSummary());
				return;
			}

			if (arg === "") {
				await pickThinkCap(ctx);
				return;
			}

			const parsed = parseThinkCap(arg);
			if (!parsed.ok) {
				ctx.ui.notify(
					`${parsed.reason} Usage: /think-cap <tokens|off>.`,
					"error",
				);
				return;
			}
			setThinkCap(parsed.cap, ctx);
			ctx.ui.notify(
				parsed.cap === null ? "Think cap off." : await thinkCapAppliedMessage(ctx),
				"info",
			);
		},
	});

	/**
	 * Explain the cap, including whether this server can actually honor it.
	 *
	 * The budget sampler only exists in builds that carry it, and only arms when
	 * the server recognizes the model's thinking tags from its chat template. If
	 * neither holds, the field is accepted and ignored, which is worth saying.
	 */
	async function thinkCapAppliedMessage(
		ctx: ExtensionCommandContext,
	): Promise<string> {
		await ensureTokens(ctx);
		const close = findThinkCloseToken(tokenSet);
		const supported =
			scope.props?.default_generation_settings?.params !== undefined &&
			"reasoning_budget_tokens" in
				(scope.props.default_generation_settings.params as Record<string, unknown>);
		const parts = [thinkCapSummary()];
		if (profile.thinkCap === MIN_THINK_CAP) {
			parts.push(
				`The close tag${close ? ` ${close.text}` : ""} is forced at the first token of the block, so there is effectively no reasoning.`,
			);
		} else {
			parts.push(
				`At the budget the server forces the close tag${
					close ? ` ${close.text}` : ""
				} once and then stops interfering, so it cannot repeat the way a large bias does.`,
			);
		}
		if (!supported) {
			parts.push(
				"Note: this server's /props does not mention reasoning_budget_tokens, so the build may ignore the cap. `/logit-bias measure` will show whether reasoning length actually changes.",
			);
		}
		return parts.join(" ");
	}

	pi.registerCommand("think-less", {
		description: "Upweight the model's end-of-thinking token to shorten reasoning",
		handler: async (args: string, ctx: ExtensionCommandContext) => {
			uiCtx = ctx;
			if (isVllmModel(ctx.model)) {
				ctx.ui.notify("This extension's token-bias and think-cap tools require llama.cpp; they are not sent to vLLM.", "info");
				return;
			}
			const arg = args.trim().toLowerCase();
			await ensureTokens(ctx);
			const close = findThinkCloseToken(tokenSet);

			if (arg === "show" || (arg === "" && !ctx.hasUI)) {
				report(ctx, biasSummary());
				return;
			}
			if (!close) {
				ctx.ui.notify(thinkCloseMissingMessage(), "warning");
				return;
			}
			if (arg === "off" || arg === "none") {
				clearBias(profile.bias, biasKeyFor(close));
				warnedUnresolved = "";
				save();
				refreshStatus(ctx);
				ctx.ui.notify(
					`No longer biasing ${close.text}. Reasoning length is back to the model's own.`,
					"info",
				);
				return;
			}
			if (arg === "") {
				await pickThinkLessLevel(ctx);
				return;
			}

			const named = thinkLessLevel(arg);
			const amount = named ?? parseBiasAmount(arg);
			if (amount === undefined || amount === "ban") {
				ctx.ui.notify(
					`Not a level: ${arg}. Use a number, off, or one of ${THINK_LESS_LEVELS.map(
						(level) => level.name,
					).join(", ")}.`,
					"error",
				);
				return;
			}
			if (amount <= 0) {
				ctx.ui.notify(
					`A bias of ${formatBiasAmount(amount)} makes the model think *more*. Use \`/logit-bias set ${close.text} ${amount}\` if that is what you meant.`,
					"warning",
				);
				return;
			}
			stampBias(biasKeyFor(close), amount);
			refreshStatus(ctx);
			ctx.ui.notify(thinkLessAppliedMessage(close, amount), "info");
		},
	});
}
