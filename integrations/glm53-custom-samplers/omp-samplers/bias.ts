/**
 * Per-token logit bias for a llama.cpp request.
 *
 * llama.cpp accepts `logit_bias` as `[[token, bias], …]`, where a `false` bias
 * means -infinity, and it inserts that sampler at the very front of the chain:
 * the bias lands on raw logits, before dry, before every truncation gate, before
 * temperature. Two consequences that drive the design here:
 *
 *   - Because the bias precedes the truncators, a modest bias mostly decides
 *     whether a token *survives* the gate at all. That is the whole mechanism
 *     behind biasing an end-of-thinking token: it does not have to beat the
 *     model's preferred continuation outright, it only has to stay in the
 *     candidate set often enough to be chosen.
 *   - Because temperature is applied last, the same bias is worth less as
 *     temperature rises. After a final temperature T the odds multiplier is
 *     exp(bias / T), so a +2 bias at temp 10 shifts probabilities by 22%, while
 *     at temp 0.7 it shifts them by a factor of 17.
 *
 * The one thing never to do is hand llama.cpp a *string* in `logit_bias`.
 * Server-side it is tokenized with `parse_special = false`, so `"</think>"`
 * becomes six ordinary text tokens and each of them gets the bias — silently
 * doing something entirely different from what was asked. Everything here
 * resolves to integer ids first.
 */

import type { SpecialToken, SpecialTokenSet, TokenRole } from "./tokens";
import { resolveTokenReference } from "./tokens";

/** A bias in raw-logit units, or a hard ban (-infinity). */
export type BiasAmount = number | "ban";

export interface BiasConfig {
	enabled: boolean;
	/**
	 * Token reference -> bias. Keyed by token *text* (or `#<id>`) rather than by
	 * id, because ids are model-specific and a profile outlives the model that
	 * was loaded when it was written. `</think>` means the same thing on every
	 * model that has it.
	 */
	entries: Record<string, BiasAmount>;
}

export const DEFAULT_BIAS_CONFIG: BiasConfig = { enabled: false, entries: {} };

/**
 * Where a positive bias stops being a nudge and starts being a decree.
 *
 * Advisory only — any finite value is accepted. Past roughly this much, a token
 * wins every step for the whole request, which for an end-of-thinking token
 * means it is emitted over and over instead of once. That is inherent to a bias
 * that is fixed for the request; see `THINK_RUNAWAY_NOTE`.
 */
export const BIAS_RUNAWAY_HINT = 20;

/** Why a very large bias on a close tag misbehaves, and what to use instead. */
export const THINK_RUNAWAY_NOTE =
	"A logit bias is fixed for the whole request, so it keeps applying after the reasoning block closes and the token is emitted again and again. Adding a cap does not repair this — the tag wins at the first step, the block ends, and the bias then dominates the answer. Lower the bias and use `/think-cap <tokens>` for the hard limit instead: the server forces the close tag exactly once, at the budget, then stops.";

/**
 * Smallest reasoning budget llama.cpp actually acts on.
 *
 * A budget of 0 is accepted and then does nothing: measured on b9610, `0` leaves
 * reasoning identical to no cap at all (44 tokens either way on a fixed greedy
 * prompt), while `1` skips the block entirely (4 tokens, empty reasoning). So 1,
 * not 0, is "do not reason", and 0 must never be put on the wire.
 */
export const MIN_THINK_CAP = 1;

export interface ResolvedBias {
	/** The key as stored, for display and for removal. */
	key: string;
	id: number;
	amount: BiasAmount;
	text?: string;
	role?: TokenRole;
}

export interface ResolvedBiasSet {
	resolved: ResolvedBias[];
	/** Keys no detected token matched; skipped rather than guessed at. */
	unresolved: string[];
}

// ---------------------------------------------------------------------------
// Parsing and formatting
// ---------------------------------------------------------------------------

const BAN_WORDS = new Set(["ban", "banned", "never", "false", "-inf", "-infinity"]);

/**
 * Parse a user-typed bias amount. Returns undefined when it is not one.
 *
 * Any finite value is allowed, including absurd ones: a bias is a raw logit
 * offset and clamping it would just hide what the model is being told. The only
 * rejects are values that cannot be put on the wire — `NaN` and `Infinity`
 * serialize to JSON `null`, which llama.cpp discards silently, so a positive
 * infinity has to be spelled as a large finite number. Negative infinity has its
 * own encoding (`false`), which is what `ban` produces.
 */
export function parseBiasAmount(raw: string): BiasAmount | undefined {
	const trimmed = raw.trim().toLowerCase();
	if (trimmed === "") return undefined;
	if (BAN_WORDS.has(trimmed)) return "ban";
	const value = Number(trimmed);
	if (!Number.isFinite(value)) return undefined;
	return value;
}

/**
 * Split `<token> <bias>` where the token may be quoted.
 *
 * Quoting is not decoration here. On a BPE vocabulary the leading space is part
 * of the token — `" delve"` is one token and `delve` is two — so an argument
 * parser that normalizes whitespace makes the most common ordinary-word bias
 * impossible to express.
 */
export function splitReferenceAndAmount(
	rest: string,
): { reference: string; amount: string } | undefined {
	const trimmed = rest.trim();
	if (trimmed === "") return undefined;
	const quote = trimmed[0];
	if (quote === '"' || quote === "'") {
		const end = trimmed.indexOf(quote, 1);
		if (end > 0) {
			const amount = trimmed.slice(end + 1).trim();
			if (amount === "") return undefined;
			return { reference: trimmed.slice(1, end), amount };
		}
	}
	const match = /^(.*\S)\s+(\S+)$/s.exec(trimmed);
	if (!match) return undefined;
	return { reference: match[1], amount: match[2] };
}

/** Strip one layer of matching quotes, so whitespace inside them is kept. */
export function unquote(value: string): string {
	const trimmed = value.trim();
	if (trimmed.length >= 2) {
		const quote = trimmed[0];
		if ((quote === '"' || quote === "'") && trimmed.endsWith(quote)) {
			return trimmed.slice(1, -1);
		}
	}
	return value;
}

export function formatBiasAmount(amount: BiasAmount): string {
	if (amount === "ban") return "banned";
	const sign = amount > 0 ? "+" : "";
	return `${sign}${Number.isInteger(amount) ? amount : amount.toFixed(2)}`;
}

/**
 * What a bias is worth after a final temperature.
 *
 * Only meaningful when temperature runs last in the chain, which is the normal
 * arrangement and what every bundled preset does.
 */
export function biasOddsMultiplier(
	amount: BiasAmount,
	temperature: number,
): number | undefined {
	if (amount === "ban") return 0;
	if (!Number.isFinite(temperature) || temperature <= 0) return undefined;
	return Math.exp(amount / temperature);
}

// ---------------------------------------------------------------------------
// Configuration edits
// ---------------------------------------------------------------------------

/** Normalize whatever was in the profile file into a usable config. */
export function loadBiasConfig(raw: unknown): BiasConfig {
	if (typeof raw !== "object" || raw === null) return { ...DEFAULT_BIAS_CONFIG };
	const value = raw as Record<string, unknown>;
	const entries: Record<string, BiasAmount> = {};
	const stored = value.entries;
	if (typeof stored === "object" && stored !== null) {
		for (const [key, amount] of Object.entries(
			stored as Record<string, unknown>,
		)) {
			if (key.trim() === "") continue;
			if (amount === "ban" || amount === false) {
				entries[key] = "ban";
			} else if (typeof amount === "number" && Number.isFinite(amount)) {
				// No magnitude ceiling: any finite offset is a legitimate thing to ask
				// for. Non-finite values are dropped because they cannot be sent.
				entries[key] = amount;
			}
		}
	}
	return {
		enabled: typeof value.enabled === "boolean" ? value.enabled : false,
		entries,
	};
}

export function setBias(
	config: BiasConfig,
	key: string,
	amount: BiasAmount,
): void {
	config.entries[key] = amount;
}

/** Remove one bias. Returns false when there was nothing stored under `key`. */
export function clearBias(config: BiasConfig, key: string): boolean {
	if (key in config.entries) {
		delete config.entries[key];
		return true;
	}
	// Be forgiving about case, since the key may have been typed by hand.
	const folded = key.trim().toLowerCase();
	for (const stored of Object.keys(config.entries)) {
		if (stored.toLowerCase() === folded) {
			delete config.entries[stored];
			return true;
		}
	}
	return false;
}

/** The key a token should be stored under: its text, or `#id` when unnamed. */
export function biasKeyFor(token: SpecialToken | { id: number }): string {
	return "text" in token && token.text ? token.text : `#${token.id}`;
}

// ---------------------------------------------------------------------------
// Resolution
// ---------------------------------------------------------------------------

/**
 * Turn stored keys into token ids against the currently detected vocabulary.
 *
 * A key that resolves to nothing is reported, not dropped silently and not
 * guessed at: biasing the wrong id is worse than biasing nothing.
 */
export function resolveBiasEntries(
	config: BiasConfig,
	set: SpecialTokenSet | undefined,
): ResolvedBiasSet {
	const resolved: ResolvedBias[] = [];
	const unresolved: string[] = [];
	for (const [key, amount] of Object.entries(config.entries)) {
		const token = resolveTokenReference(set, key);
		if (!token) {
			unresolved.push(key);
			continue;
		}
		if (set?.nVocab !== undefined && token.id >= set.nVocab) {
			unresolved.push(key);
			continue;
		}
		resolved.push({
			key,
			id: token.id,
			amount,
			...("text" in token && token.text !== undefined
				? { text: token.text }
				: {}),
			...("role" in token && token.role !== undefined
				? { role: token.role }
				: {}),
		});
	}
	resolved.sort((a, b) => a.id - b.id);
	return { resolved, unresolved };
}

// ---------------------------------------------------------------------------
// Request application
// ---------------------------------------------------------------------------

/** llama.cpp's wire form: a token id paired with a bias, or with false to ban. */
export type LogitBiasPair = [number, number | false];

/** Existing pairs on a request body, ignoring anything malformed. */
function existingPairs(value: unknown): LogitBiasPair[] {
	if (!Array.isArray(value)) return [];
	const out: LogitBiasPair[] = [];
	for (const entry of value) {
		if (!Array.isArray(entry) || entry.length !== 2) continue;
		const [id, bias] = entry;
		if (!Number.isInteger(id)) continue;
		if (bias === false) out.push([id as number, false]);
		else if (typeof bias === "number" && Number.isFinite(bias)) {
			out.push([id as number, bias]);
		}
	}
	return out;
}

/**
 * Stamp resolved biases onto a provider request.
 *
 * Any `logit_bias` already on the body is preserved and merged, with these
 * entries winning per token id, so this composes with another extension that
 * had the same idea. Integer ids only, for the reason in the module comment.
 */
export function applyLogitBias(
	target: Record<string, unknown>,
	resolved: readonly ResolvedBias[],
): Record<string, unknown> {
	const byId = new Map<number, number | false>();
	for (const [id, bias] of existingPairs(target.logit_bias)) byId.set(id, bias);
	for (const entry of resolved) {
		if (entry.amount === "ban") {
			byId.set(entry.id, false);
			continue;
		}
		// JSON.stringify turns Infinity and NaN into null, which llama.cpp drops
		// without a word. Nothing upstream should produce one, but a bias that
		// silently vanishes is the worst possible failure here.
		if (!Number.isFinite(entry.amount)) continue;
		byId.set(entry.id, entry.amount);
	}
	if (byId.size === 0) {
		delete target.logit_bias;
		return target;
	}
	target.logit_bias = [...byId.entries()]
		.sort((a, b) => a[0] - b[0])
		.map(([id, bias]): LogitBiasPair => [id, bias]);
	return target;
}

/**
 * Compare what a request asked for against what a slot reports it applied.
 *
 * When llama.cpp does report the parsed biases it does so as `[{token, bias}, …]`,
 * and it drops ids outside the vocabulary without complaint, so this is the only
 * way to notice that a bias never took effect.
 *
 * Usually it does not report them. `/slots` serializes a slot's params with
 * `only_metrics` unless `LLAMA_SERVER_SLOTS_DEBUG` is set on the server, and that
 * shorter form omits `logit_bias` entirely. An absent field therefore says
 * nothing about the request, which is why `reported` is separate from `missing`:
 * treating "not reported" as "not applied" would flag every bias on every turn.
 */
export function diffAppliedBias(
	resolved: readonly ResolvedBias[],
	applied: unknown,
): { reported: boolean; missing: ResolvedBias[]; mismatched: ResolvedBias[] } {
	if (!Array.isArray(applied)) {
		return { reported: false, missing: [], mismatched: [] };
	}
	const echo = new Map<number, number>();
	for (const entry of applied) {
		if (typeof entry !== "object" || entry === null) continue;
		const { token, bias } = entry as { token?: unknown; bias?: unknown };
		if (Number.isInteger(token) && typeof bias === "number") {
			echo.set(token as number, bias);
		}
	}
	const missing: ResolvedBias[] = [];
	const mismatched: ResolvedBias[] = [];
	for (const entry of resolved) {
		const got = echo.get(entry.id);
		if (got === undefined) {
			missing.push(entry);
			continue;
		}
		if (entry.amount === "ban") {
			if (Number.isFinite(got)) mismatched.push(entry);
		} else if (Math.abs(got - entry.amount) > 1e-3) {
			mismatched.push(entry);
		}
	}
	return { reported: true, missing, mismatched };
}

// ---------------------------------------------------------------------------
// Think-less presets
// ---------------------------------------------------------------------------

/**
 * Bias strengths for the end-of-thinking token.
 *
 * Raw-logit offsets. Measured on Qwen3.8-27B at temp 10 with hill q=10, three
 * prompts per level, median tokens inside the reasoning block:
 *
 *   bias    0    +1    +2    +3    +5    +8
 *   tokens 165   165   160   103    91    71
 *
 * So +1 is indistinguishable from nothing, the curve bends between +2 and +3,
 * and past +8 it flattens as the block starts closing almost immediately. Those
 * numbers do not transfer: the same offset is worth exp(bias/T) after a final
 * temperature T, so a +4 that is mild at temp 10 is overwhelming at temp 0.7.
 * `/logit-bias measure` re-runs that sweep on the actual model and chain.
 */
export const THINK_LESS_LEVELS: { name: string; amount: number; blurb: string }[] =
	[
		{ name: "nudge", amount: 2, blurb: "barely moves a high-temperature chain" },
		{ name: "firm", amount: 4, blurb: "roughly halves reasoning length at temp 10" },
		{ name: "hard", amount: 6, blurb: "short reasoning, occasionally none" },
		{
			name: "skip",
			amount: 12,
			blurb: "effectively closes the block immediately",
		},
	];

/**
 * Count how often a reasoning block closed itself.
 *
 * More than once is the signature of an over-biased close tag: the bias does not
 * switch off when the block ends, so the token keeps winning and the reasoning
 * channel fills up with `</think></think></think>…` while the answer never
 * arrives. Cheap to check on every finished message and the only way the user
 * finds out, since llama.cpp reports nothing unusual.
 */
export function countCloseTags(text: string, closeText: string): number {
	if (closeText === "") return 0;
	let count = 0;
	let index = text.indexOf(closeText);
	while (index >= 0) {
		count += 1;
		index = text.indexOf(closeText, index + closeText.length);
	}
	return count;
}

/**
 * A hard cap on reasoning length, expressed the way llama.cpp wants it.
 *
 * This is the non-statistical counterpart to biasing the close tag. The server's
 * reasoning-budget sampler counts tokens inside the block and, at the budget,
 * forces the close sequence by driving every other logit to negative infinity —
 * once, and then it goes back to passthrough. That "once, then stop" is exactly
 * what a fixed bias cannot express.
 *
 * Over the OpenAI-compatible endpoint the field is `thinking_budget_tokens`, and
 * the server derives the tags from the model's own chat template. Anything below
 * `MIN_THINK_CAP` is treated as no cap rather than sent, since 0 on the wire is a
 * silent no-op.
 */
export function applyThinkCap(
	target: Record<string, unknown>,
	cap: number | null,
): Record<string, unknown> {
	if (cap === null || !Number.isFinite(cap) || cap < MIN_THINK_CAP) {
		delete target.thinking_budget_tokens;
		return target;
	}
	target.thinking_budget_tokens = Math.floor(cap);
	return target;
}

export type ThinkCapParse =
	| { ok: true; cap: number | null }
	| { ok: false; reason: string };

/**
 * Parse a `/think-cap` argument.
 *
 * 0 is rejected with an explanation rather than accepted and quietly ignored, or
 * quietly rewritten to 1 — silently changing the number someone typed is how a
 * knob stops being trustworthy.
 */
export function parseThinkCap(raw: string): ThinkCapParse {
	const trimmed = raw.trim().toLowerCase();
	if (trimmed === "") return { ok: false, reason: "no budget given" };
	if (trimmed === "off" || trimmed === "none" || trimmed === "-1") {
		return { ok: true, cap: null };
	}
	const value = Number(trimmed);
	if (!Number.isFinite(value) || value < 0) {
		return { ok: false, reason: `not a token budget: ${raw.trim()}` };
	}
	const floored = Math.floor(value);
	if (floored < MIN_THINK_CAP) {
		return {
			ok: false,
			reason:
				"llama.cpp treats a budget of 0 as no cap at all, so it would do nothing. Use 1 to skip reasoning entirely.",
		};
	}
	return { ok: true, cap: floored };
}

export function thinkLessLevel(name: string): number | undefined {
	return THINK_LESS_LEVELS.find(
		(level) => level.name === name.trim().toLowerCase(),
	)?.amount;
}

/** One-line summary for the footer and status line. */
export function summarizeBias(
	config: BiasConfig,
	set: SpecialTokenSet | undefined,
): string {
	if (!config.enabled) return "bias: off";
	const { resolved, unresolved } = resolveBiasEntries(config, set);
	if (resolved.length === 0 && unresolved.length === 0) return "bias: on (empty)";
	const parts = resolved.map(
		(entry) =>
			`${entry.text ?? `#${entry.id}`} ${formatBiasAmount(entry.amount)}`,
	);
	if (unresolved.length > 0) parts.push(`${unresolved.length} unresolved`);
	return `bias: ${parts.join(", ")}`;
}
