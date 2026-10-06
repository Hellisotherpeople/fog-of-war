/**
 * Turning captured telemetry into things a human can read.
 *
 * Everything here is pure: it takes records plus a `paint` callback and returns
 * lines. The extension decides where those lines go (footer, widget, notify).
 */

import type { GenerationRecord, TokenRecord } from "./capture";
import {
	barRow,
	beforeAfterLines,
	clip,
	funnelLines,
	heatLegend,
	heatText,
	histogramLines,
	noPaint,
	num,
	type Paint,
	padEnd,
	pct,
	showToken,
	sparkline,
	table,
} from "./charts";
import type { SamplerSupportEntry } from "./llama";
import {
	type Bucket,
	bucketize,
	entropyBits,
	fraction,
	mean,
	probs,
	selectedRank,
	type Summary,
	summarize,
} from "./metrics";
import type { ProbeResult, ProbeStep } from "./probe";

// ---------------------------------------------------------------------------
// Per-token derivations
// ---------------------------------------------------------------------------

/** Full survivor count; a capped preview is not a width measurement. */
export function tokenWidth(token: TokenRecord): number | undefined {
	return token.candidateCount ?? (token.mode === "post" && !token.saturated ? token.candidates.length : undefined);
}

export function tokenEntropy(token: TokenRecord): number | undefined {
	if (token.entropyBits !== undefined) return token.entropyBits;
	const ps = probs(token.candidates);
	const total = ps.reduce((acc, p) => acc + p, 0);
	// Older servers do not report full moments. Only use a complete probability list.
	return total > 0 && Math.abs(total - 1) < 1e-5 ? entropyBits(ps.map((p) => p / total)) : undefined;
}

function measured(values: (number | undefined)[]): number[] {
	return values.filter((v): v is number => v !== undefined && Number.isFinite(v));
}

function widthLabel(token: TokenRecord): string {
	const width = tokenWidth(token);
	return width !== undefined ? String(width) : token.mode === "post" ? `${token.candidates.length}+ (preview only)` : "unavailable";
}

/** Prefer full-distribution server ranks; never treat a post-chain rank as a raw rank. */
export function tokenChosenRank(token: TokenRecord, mode = token.mode): number | undefined {
	const exact = mode === "raw" ? token.rawRank : token.postRank;
	if (exact !== undefined) return exact;
	if (token.mode !== mode) return undefined;
	return selectedRank(token.candidates, { id: token.id, token: token.text });
}

export interface RankSummary {
	stats?: Summary;
	known: number;
	total: number;
}

export function summarizeRanks(tokens: readonly TokenRecord[], mode: "raw" | "post"): RankSummary {
	const ranks = tokens.map((t) => tokenChosenRank(t, mode)).filter((r): r is number => r !== undefined);
	return { stats: summarize(ranks), known: ranks.length, total: tokens.length };
}

function rankSummaryText(label: string, rank: RankSummary): string {
	const coverage = `${rank.known}/${rank.total} measured`;
	return rank.stats
		? `${label} rank: mean ${num(rank.stats.mean, 2)} · median ${num(rank.stats.median, 0)} · p90 ${num(rank.stats.p90, 0)} · ${coverage}${rank.known < rank.total ? " (partial mean)" : ""}`
		: `${label} rank: unavailable · ${coverage}`;
}

export interface GenerationSummary {
	tokens: number;
	mode: TokenRecord["mode"];
	nProbs: number;
	width?: Summary;
	widthKnown: number;
	entropyKnown: number;
	vocabSize?: number;
	widthBuckets: Bucket[];
	/** Share of steps with incomplete candidate previews; exact width may still be known. */
	saturationRate: number;
	/** Share of steps where the chain left exactly one candidate. */
	forcedRate: number;
	/** Share of steps where the sampled token was the top candidate. */
	topPickRate: number;
	entropy?: Summary;
	chosenProb?: Summary;
	rawRank: RankSummary;
	postRank: RankSummary;
	tokPerSec?: number;
	ttftMs?: number;
	medianGapMs?: number;
	promptTokens?: number;
	cachedTokens?: number;
}

export function summarizeGeneration(
	record: GenerationRecord,
): GenerationSummary {
	const tokens = record.tokens;
	const widths = tokens
		.map(tokenWidth)
		.filter((w): w is number => w !== undefined && w > 0);
	const entropies = measured(tokens.map(tokenEntropy));
	const chosen = tokens
		.map((t) => t.prob)
		.filter((p): p is number => p !== undefined && Number.isFinite(p));
	const ranks = tokens.map((t) => tokenChosenRank(t));
	const gaps = tokens.slice(1).map((t) => t.dtMs);

	const elapsedMs =
		record.timings?.predictedMs ??
		(record.endedAt !== undefined && record.ttftMs !== undefined
			? record.endedAt - record.startedAt - record.ttftMs
			: undefined);

	return {
		tokens: tokens.length,
		mode: record.mode,
		nProbs: record.nProbs,
		width: summarize(widths),
		widthKnown: widths.length,
		entropyKnown: entropies.length,
		vocabSize: tokens.find((t) => t.vocabSize !== undefined)?.vocabSize,
		widthBuckets: bucketize(widths),
		saturationRate: fraction(tokens.map((t) => t.saturated)),
		forcedRate: fraction(widths.map((w) => w === 1)),
		topPickRate: fraction(ranks.filter((r) => r !== undefined).map((r) => r === 1)),
		entropy: summarize(entropies),
		chosenProb: summarize(chosen),
		rawRank: summarizeRanks(tokens, "raw"),
		postRank: summarizeRanks(tokens, "post"),
		tokPerSec:
			record.timings?.predictedPerSecond ??
			(elapsedMs && elapsedMs > 0
				? (tokens.length / elapsedMs) * 1000
				: undefined),
		ttftMs: record.ttftMs,
		medianGapMs: summarize(gaps)?.median,
		promptTokens: record.timings?.promptN ?? record.usage?.prompt,
		cachedTokens: record.timings?.cacheN ?? record.usage?.cached,
	};
}

function summaryCells(summary: Summary | undefined, digits = 1): string {
	if (!summary) return "—";
	return `min ${num(summary.min, digits)} · med ${num(summary.median, digits)} · p90 ${num(
		summary.p90,
		digits,
	)} · max ${num(summary.max, digits)}`;
}

// ---------------------------------------------------------------------------
// Live widget
// ---------------------------------------------------------------------------

export interface LiveState {
	chainLabel: string;
	mode: string;
	record?: GenerationRecord;
	/** Live slot readout, when /slots is available. */
	slot?: {
		decoded?: number;
		promptTokens?: number;
		cachedTokens?: number;
		processing?: boolean;
		tokPerSec?: number;
	};
	/** Samplers the request asked for that the server did not apply. */
	droppedSamplers?: string[];
	warning?: string;
}

/**
 * Three compact lines for the editor widget: what is configured, how wide the
 * truncation is running right now, and how fast tokens are arriving.
 */
export function renderLiveWidget(
	state: LiveState,
	paint: Paint = noPaint,
): string[] {
	const lines: string[] = [];
	lines.push(
		`${paint("accent", "◈ samplers")} ${clip(state.chainLabel, 88)} ${paint("dim", state.mode)}`,
	);

	const record = state.record;
	if (record && record.tokens.length > 0) {
		const widths = record.tokens
			.map(tokenWidth)
			.filter((w): w is number => w !== undefined);
		const recent = widths.slice(-48);
		const summary = summarize(widths);
		if (recent.length > 0 && summary) {
			const spark = sparkline(recent.map((w) => Math.log2(Math.max(1, w))));
			lines.push(
				`  ${paint("dim", "width")} ${paint("accent", spark)} ${paint(
					"text",
					`now ${widthLabel(record.tokens[record.tokens.length - 1])}`,
				)} ${paint(
					"dim",
					`avg ${num(summary.mean, 1)} med ${num(summary.median, 0)} p90 ${num(summary.p90, 0)} max ${num(summary.max, 0)}${record.tokens[0].vocabSize ? ` / ${record.tokens[0].vocabSize} vocab` : ""}${widths.length < record.tokens.length ? ` · ${widths.length}/${record.tokens.length} measured (partial)` : ""}`,
				)}`,
			);
		} else {
			const entropies = measured(record.tokens.slice(-48).map(tokenEntropy));
			lines.push(
				`  ${paint("dim", "entropy")} ${paint("accent", sparkline(entropies))} ${paint(
					"dim",
					`${num(entropies.length ? mean(entropies) : undefined, 2)} bits avg · width ${widthLabel(record.tokens[record.tokens.length - 1])}`,
				)}`,
			);
		}

		const stats = summarizeGeneration(record);
		const latestRank = tokenChosenRank(record.tokens[record.tokens.length - 1], "raw");
		lines.push(`  ${paint("accent", `raw rank now ${num(latestRank, 0)}`)} · ${paint("dim", rankSummaryText("raw", stats.rawRank))}`);
		const speed = stats.tokPerSec ? `${num(stats.tokPerSec, 1)} tok/s` : "—";
		const cache =
			stats.cachedTokens !== undefined && stats.promptTokens
				? ` cache ${stats.cachedTokens}/${stats.promptTokens} (${pct(
						stats.cachedTokens / Math.max(1, stats.promptTokens),
						0,
					)})`
				: "";
		lines.push(
			`  ${paint("dim", "speed")} ${paint("text", speed)} ${paint(
				"dim",
				`ttft ${stats.ttftMs === undefined ? "—" : `${Math.round(stats.ttftMs)}ms`} · ${
					stats.tokens
				} tok${cache}`,
			)}`,
		);
	} else if (state.slot?.processing) {
		lines.push(
			`  ${paint("dim", "decoding")} ${paint("text", `${state.slot.decoded ?? 0} tok`)} ${paint(
				"dim",
				state.slot.tokPerSec ? `${num(state.slot.tokPerSec, 1)} tok/s` : "",
			)}`,
		);
	}

	if (state.droppedSamplers && state.droppedSamplers.length > 0) {
		lines.push(
			`  ${paint("error", "⚠ dropped by server")} ${paint(
				"warning",
				state.droppedSamplers.join(", "),
			)} ${paint("dim", "— missing from this response's applied chain")}`,
		);
	}
	if (state.warning) lines.push(`  ${paint("warning", state.warning)}`);
	return lines;
}

/** One-line footer status. */
export function renderStatus(state: LiveState, paint: Paint = noPaint): string {
	const record = state.record;
	if (!record || record.tokens.length === 0) return state.chainLabel;
	const widths = record.tokens
		.map(tokenWidth)
		.filter((w): w is number => w !== undefined);
	const summary = summarize(widths);
	const stats = summarizeGeneration(record);
	const bits: string[] = [state.chainLabel];
	if (stats.rawRank.stats) bits.push(paint("accent", `rank avg ${num(stats.rawRank.stats.mean, 2)}${stats.rawRank.known < stats.rawRank.total ? "*" : ""}`));
	if (summary) bits.push(paint("accent", `w~${num(summary.median, 0)}${widths.length < record.tokens.length ? "*" : ""}`));
	else if (record.mode === "post") bits.push(`w ${widthLabel(record.tokens[record.tokens.length - 1])}`);
	if (stats.tokPerSec)
		bits.push(paint("dim", `${num(stats.tokPerSec, 0)} tok/s`));
	return bits.join(" · ");
}

// ---------------------------------------------------------------------------
// Turn report
// ---------------------------------------------------------------------------

/** Full statistics for one captured generation. */
export function renderGenerationReport(
	record: GenerationRecord,
	paint: Paint = noPaint,
): string[] {
	const stats = summarizeGeneration(record);
	const lines: string[] = [];
	lines.push(
		paint(
			"accent",
			`Generation #${record.id} · ${record.kind} · ${record.path}`,
		),
	);
	lines.push(
		paint("dim", `chain: `) +
			(record.chain.length ? record.chain.join(" → ") : "(server default)"),
	);
	if (
		record.appliedChain &&
		record.appliedChain.join(",") !== record.chain.join(",")
	) {
		lines.push(paint("warning", `applied: ${record.appliedChain.join(" → ")}`));
	}
	lines.push(
		paint(
			"dim",
			`${stats.tokens} tokens · probs ${record.mode === "post" ? "post-sampling" : "raw"} · n_probs ${
				record.nProbs
			}`,
		),
	);

	if (record.tokens.length === 0) {
		lines.push(
			paint(
				"muted",
				"No per-token probabilities were captured for this request.",
			),
		);
		return lines;
	}

	lines.push("");
	if (stats.width) {
		lines.push(
			paint("accent", "Truncation width (candidates allowed per step)"),
		);
		lines.push(
			`  ${summaryCells(stats.width, 0)} · mean ${num(stats.width.mean, 1)}`,
		);
		lines.push(`  ${stats.widthKnown}/${stats.tokens} widths measured${stats.widthKnown < stats.tokens ? " (partial; unknown widths excluded)" : ""}${stats.vocabSize ? ` · vocabulary ${stats.vocabSize}` : ""}`);
		lines.push(
			`  ${paint("dim", "forced to 1")} ${pct(stats.forcedRate)}   ${paint(
				"dim",
				`preview clipped at n_probs=${record.nProbs}`,
			)} ${pct(stats.saturationRate)}`,
		);
		lines.push(
			`  ${paint("accent", sparkline(record.tokens.map((t) => Math.log2(Math.max(1, tokenWidth(t) ?? 1)))))}`,
		);
		lines.push("");
		lines.push(paint("accent", "Width distribution"));
		lines.push(
			...histogramLines(
				stats.widthBuckets.filter((b) => b.count > 0),
				{ paint },
			),
		);
	} else {
		lines.push(
			paint(
				"muted",
				"Exact width is unavailable. Update the custom server for full survivor counts; capped previews are excluded from width statistics.",
			),
		);
	}

	lines.push("");
	lines.push(...renderRankReport(record, paint));
	lines.push("");
	lines.push(paint("accent", "Distribution shape"));
	lines.push(
		`  ${padEnd("entropy (bits)", 18)} ${summaryCells(stats.entropy, 2)}`,
	);
	lines.push(`  ${stats.entropyKnown}/${stats.tokens} full-distribution entropies measured${stats.entropyKnown < stats.tokens ? " (partial; truncated previews excluded)" : ""}`);
	lines.push(
		`  ${padEnd("chosen p", 18)} ${summaryCells(stats.chosenProb, 3)}`,
	);
	lines.push(
		`  ${padEnd("sampled the top candidate", 18)} ${pct(stats.topPickRate)}`,
	);

	lines.push("");
	lines.push(paint("accent", "Throughput"));
	lines.push(
		`  ${num(stats.tokPerSec, 1)} tok/s · ttft ${
			stats.ttftMs === undefined ? "—" : `${Math.round(stats.ttftMs)}ms`
		} · median gap ${num(stats.medianGapMs, 1)}ms`,
	);
	if (stats.promptTokens !== undefined) {
		const cached = stats.cachedTokens ?? 0;
		lines.push(
			`  prompt ${stats.promptTokens} tok · cache hit ${cached} (${pct(
				cached / Math.max(1, stats.promptTokens),
				0,
			)})`,
		);
	}

	const heat = record.tokens
		.map((t) => ({ text: t.text, value: tokenWidth(t) ?? 0 }))
		.filter((t) => t.text !== "");
	if (stats.width && heat.length > 0) {
		lines.push("");
		lines.push(
			paint(
				"accent",
				"Output, colored by how many candidates the chain allowed",
			),
		);
		lines.push(`  ${heatLegend(undefined, paint)}`);
		lines.push(...heatText(heat.slice(0, 400), { paint }).map((l) => `  ${l}`));
	}
	return lines;
}

/** Ranked table of the widest and narrowest steps — the ones worth inspecting. */
export function renderExtremes(
	record: GenerationRecord,
	paint: Paint = noPaint,
	count = 8,
): string[] {
	const scored = record.tokens
		.map((token) => ({ token, width: tokenWidth(token) }))
		.filter(
			(entry): entry is { token: TokenRecord; width: number } =>
				entry.width !== undefined,
		);
	if (scored.length === 0) return [];
	const byWidth = [...scored].sort((a, b) => b.width - a.width);
	const rows = (entries: typeof scored): string[][] =>
		entries.map(({ token, width }) => [
			`#${token.index}`,
			showToken(token.text),
			String(width),
			num(token.prob, 3),
			num(tokenEntropy(token), 2),
		]);
	return [
		paint("accent", "Widest steps (most sampler freedom)"),
		...table(rows(byWidth.slice(0, count)), {
			header: ["step", "token", "width", "p", "H"],
			paint,
		}),
		"",
		paint("accent", "Narrowest steps (chain nearly decided the token)"),
		...table(rows(byWidth.slice(-count).reverse()), {
			header: ["step", "token", "width", "p", "H"],
			paint,
		}),
	];
}

/** Candidate list for one captured step. */
export function renderTokenDetail(
	record: GenerationRecord,
	index: number,
	paint: Paint = noPaint,
): string[] {
	const token = record.tokens[index];
	if (!token)
		return [paint("error", `No step #${index} in generation #${record.id}.`)];
	const lines: string[] = [
		paint(
			"accent",
			`Step #${token.index} · sampled ${showToken(token.text, 24)} · p=${num(token.prob, 4)}`,
		),
		paint(
			"dim",
			`${token.mode === "post" ? "post-chain preview" : "raw model preview"}: ${
				token.candidates.length
			}${token.saturated ? " (ceiling reached)" : ""} · +${Math.round(token.atMs)}ms`,
		),
		"",
	];
	lines.push(`Width: ${widthLabel(token)}${token.vocabSize ? ` / ${token.vocabSize} vocabulary tokens` : ""} · entropy: ${num(tokenEntropy(token), 3)} bits`, "");
	lines.push(`Raw model rank: ${num(tokenChosenRank(token, "raw"), 0)} · post-chain rank: ${num(tokenChosenRank(token, "post"), 0)}`, "");
	const max = Math.max(...token.candidates.map((c) => c.p), 0.000001);
	for (const [rank, candidate] of token.candidates.slice(0, 24).entries()) {
		const isChosen =
			token.id !== undefined
				? candidate.id === token.id
				: candidate.token === token.text;
		lines.push(
			`${isChosen ? paint("accent", "▶") : " "} ${barRow(
				`${rank + 1} ${showToken(candidate.token)}`,
				candidate.p,
				max,
				{ paint, color: isChosen ? "success" : "accent", labelWidth: 18 },
			)}`,
		);
	}
	return lines;
}

/** Rank report also works in raw mode, without truncation widths. */
export function renderRankReport(record: GenerationRecord, paint: Paint = noPaint): string[] {
	const raw = summarizeRanks(record.tokens, "raw");
	const post = summarizeRanks(record.tokens, "post");
	const lines = [
		paint("accent", "Selected-token rank (1 = most likely; ties share a rank)"),
		`  ${rankSummaryText("raw model", raw)}`,
		`  ${rankSummaryText("post-chain", post)}`,
	];
	if (raw.known < raw.total) lines.push(paint("dim", "  Missing ranks are excluded, never counted as zero. Exact raw ranks require the updated server; raw capture on older servers is limited to n_probs."));
	return lines;
}

export function renderRankSteps(record: GenerationRecord, paint: Paint = noPaint): string[] {
	return [...renderRankReport(record, paint), "", ...table(record.tokens.slice(-100).map((t) => [
		String(t.index), showToken(t.text, 24), num(tokenChosenRank(t, "raw"), 0), num(tokenChosenRank(t, "post"), 0),
		widthLabel(t), num(tokenEntropy(t), 3),
	]), { header: ["step (last 100)", "token", "raw rank", "post rank", "width", "H (bits)"], paint })];
}

// ---------------------------------------------------------------------------
// Probe report
// ---------------------------------------------------------------------------

export function renderProbeStep(
	step: ProbeStep,
	paint: Paint = noPaint,
): string[] {
	const c = step.comparison;
	const lines: string[] = [
		paint(
			"accent",
			`Step #${step.index} · sampled ${showToken(step.text, 24)}${
				c.chosenRawRank ? ` (raw rank ${c.chosenRawRank})` : ""
			}`,
		),
		paint(
			"dim",
			`width ${c.width}${c.saturated ? "+" : ""} · H ${num(c.entropyBefore, 2)}${c.entropyBeforeExact ? "" : " (preview)"} → ${num(c.entropyAfter, 2)}${c.entropyAfterExact ? "" : " (preview)"} bits · ` +
				`${c.previewPartial ? "preview mass" : "kept raw mass"} ${pct(c.keptMass)} · ${c.previewPartial ? "preview KL" : "KL"} ${num(c.klBits, 2)} bits` +
				(c.topDropped ? c.previewPartial ? " · raw top absent from preview" : " · top candidate dropped" : ""),
		),
	];
	if (step.funnel.length > 0) {
		lines.push("");
		lines.push(
			...funnelLines(
				step.funnel.map((stage) => ({
					label: stage.sampler,
					width: stage.width,
					saturated: stage.saturated,
					note: stage.historyDependent ? "(no history)" : undefined,
				})),
				{ paint },
			),
		);
	}
	lines.push("");
	lines.push(
		...beforeAfterLines(step.raw, step.post, {
			paint,
			chosenKey: step.tokenId ?? step.text,
		}),
	);
	return lines;
}

export function renderProbeReport(
	probe: ProbeResult,
	paint: Paint = noPaint,
): string[] {
	const widths = probe.steps.filter((s) => !s.comparison.saturated).map((s) => s.comparison.width);
	const kept = probe.steps.map((s) => s.comparison.keptMass);
	const drops = probe.steps.filter((s) => s.comparison.topDropped).length;
	const widthSummary = summarize(widths);
	const lines: string[] = [
		paint(
			"accent",
			`Sampler probe · ${probe.steps.length} steps · ${probe.chain.join(" → ")}`,
		),
		paint(
			"dim",
			`${probe.requests} requests · ${(probe.durationMs / 1000).toFixed(1)}s · prompt ${
				probe.promptTokenCount
			} tok · n_probs ${probe.nProbs}`,
		),
		"",
		paint("accent", "Per-step survivors"),
		`  ${paint("accent", sparkline(widths.map((w) => Math.log2(Math.max(1, w)))))}`,
		`  ${summaryCells(widthSummary, 0)} · ${widths.length}/${probe.steps.length} widths measured`,
		`  ${paint("dim", probe.steps.some((s) => s.comparison.previewPartial) ? "preview raw mass" : "raw mass kept")} ${pct(mean(kept))} avg · ${paint(
			"dim",
			probe.steps.some((s) => s.comparison.previewPartial) ? "raw top absent from preview" : "top candidate dropped",
		)} ${drops}/${probe.steps.length} steps`,
	];
	if (probe.steps.some((s) => s.funnel.length > 0)) {
		lines.push("");
		lines.push(paint("accent", "Average survivors after each stage"));
		const stageNames = probe.steps[0].funnel.map((f) => f.sampler);
		const averages = stageNames.map((_name, stage) =>
			mean(probe.steps.map((s) => s.funnel[stage]?.width ?? Number.NaN)),
		);
		lines.push(
			...funnelLines(
				stageNames.map((name, index) => ({
					label: name,
					width: Math.round(averages[index]),
					saturated: probe.steps.some((s) => s.funnel[index]?.saturated),
					note: probe.steps[0].funnel[index]?.historyDependent
						? "(no history)"
						: undefined,
				})),
				{ paint },
			),
		);
	}
	lines.push("");
	lines.push(paint("accent", "Text produced"));
	lines.push(
		...heatText(
			probe.steps.map((s) => ({ text: s.text, value: s.comparison.width })),
			{ paint },
		).map((l) => `  ${l}`),
	);
	if (probe.notes.length > 0) {
		lines.push("");
		for (const note of probe.notes) lines.push(paint("dim", `note: ${note}`));
	}
	return lines;
}

// ---------------------------------------------------------------------------
// Session aggregates
// ---------------------------------------------------------------------------

export interface ChainAggregate {
	chain: string;
	configuration: string;
	generations: number;
	tokens: number;
	medianWidth?: number;
	p90Width?: number;
	forcedRate: number;
	meanEntropy?: number;
	meanChosenProb: number;
	tokPerSec?: number;
	rawRank: RankSummary;
	postRank: RankSummary;
}

export function aggregateByChain(
	records: readonly GenerationRecord[],
): ChainAggregate[] {
	const groups = new Map<string, GenerationRecord[]>();
	for (const record of records) {
		if (record.tokens.length === 0) continue;
		// Knob changes and router generations must not get folded into the same average.
		const key = JSON.stringify([record.kind, record.model, record.chain, Object.entries(record.params).sort(([a], [b]) => a.localeCompare(b)), record.mode, record.nProbs]);
		const list = groups.get(key) ?? [];
		list.push(record);
		groups.set(key, list);
	}
	const out: ChainAggregate[] = [];
	for (const group of groups.values()) {
		const first = group[0];
		const chain = `${first.kind}: ${first.chain.join(" → ") || "(server default)"}`;
		const tokens = group.flatMap((g) => g.tokens);
		const widths = tokens
			.map(tokenWidth)
			.filter((w): w is number => w !== undefined);
		const speeds = group
			.map((g) => summarizeGeneration(g).tokPerSec)
			.filter((v): v is number => v !== undefined && Number.isFinite(v));
		const widthSummary = summarize(widths);
		out.push({
			chain,
			configuration: `${first.model ?? "model unknown"} · ${first.mode}, preview=${first.nProbs} · widths ${widths.length}/${tokens.length} measured · entropy ${measured(tokens.map(tokenEntropy)).length}/${tokens.length} measured · ${Object.entries(first.params).map(([key, value]) => `${key}=${value}`).join(", ")}`,
			generations: group.length,
			tokens: tokens.length,
			medianWidth: widthSummary?.median,
			p90Width: widthSummary?.p90,
			forcedRate: fraction(widths.map((w) => w === 1)),
			meanEntropy: measured(tokens.map(tokenEntropy)).length ? mean(measured(tokens.map(tokenEntropy))) : undefined,
			meanChosenProb: mean(
				tokens.map((t) => t.prob).filter((p): p is number => p !== undefined),
			),
			tokPerSec: speeds.length > 0 ? mean(speeds) : undefined,
			rawRank: summarizeRanks(tokens, "raw"),
			postRank: summarizeRanks(tokens, "post"),
		});
	}
	return out.sort((a, b) => b.tokens - a.tokens);
}

export function renderAggregate(
	records: readonly GenerationRecord[],
	paint: Paint = noPaint,
): string[] {
	const aggregates = aggregateByChain(records);
	if (aggregates.length === 0) {
		return [paint("muted", "No per-token telemetry captured yet.")];
	}
	const rows = aggregates.map((a, index) => [
		String(index + 1),
		clip(a.chain, 44),
		String(a.generations),
		String(a.tokens),
		num(a.medianWidth, 0),
		num(a.p90Width, 0),
		pct(a.forcedRate, 0),
		num(a.meanEntropy, 2),
		num(a.meanChosenProb, 3),
		num(a.rawRank.stats?.mean, 2),
		`${a.rawRank.known}/${a.tokens}`,
		num(a.tokPerSec, 1),
	]);
	return [
		paint("accent", "Sampler chains used this session"),
		...table(rows, {
			header: [
				"config",
				"chain",
				"gens",
				"tok",
				"w50",
				"w90",
				"forced",
				"H",
				"p̄",
				"raw rank avg",
				"measured",
				"tok/s",
			],
			paint,
		}),
		...aggregates.map((a, index) => paint("dim", `Config ${index + 1}: ${a.configuration}`)),
	];
}

/** Distribution of widths across every captured generation. */
export function renderSessionWidthHistogram(
	records: readonly GenerationRecord[],
	paint: Paint = noPaint,
): string[] {
	const widths = records
		.flatMap((r) => r.tokens)
		.map(tokenWidth)
		.filter((w): w is number => w !== undefined);
	if (widths.length === 0) return [];
	return [
		paint("accent", `Session width distribution (${widths.length} steps)`),
		...histogramLines(
			bucketize(widths).filter((b) => b.count > 0),
			{ paint },
		),
	];
}

// ---------------------------------------------------------------------------
// Capabilities
// ---------------------------------------------------------------------------

export function renderCapabilities(
	entries: readonly SamplerSupportEntry[],
	paint: Paint = noPaint,
): string[] {
	const glyph = (support: SamplerSupportEntry["support"]): string =>
		support === "supported"
			? paint("success", "✓")
			: support === "unsupported"
				? paint("error", "✗")
				: paint("warning", "?");
	return [
		paint("accent", "Sampler support on this server"),
		...entries.map(
			(entry) =>
				`  ${glyph(entry.support)} ${padEnd(entry.id, 12)} ${paint("dim", entry.evidence)}`,
		),
	];
}
