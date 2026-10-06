/**
 * Terminal chart primitives.
 *
 * Every function returns plain strings and takes an optional `paint` callback,
 * so the same code renders uncolored in tests and theme-colored in the TUI.
 * Padding is always computed on unpainted text and colored afterwards, which
 * keeps column alignment correct once ANSI escapes are added.
 */

/** Theme color names used by this module (a subset of omp's ThemeColor). */
export type ChartColor =
	| "accent"
	| "success"
	| "warning"
	| "error"
	| "muted"
	| "dim"
	| "text"
	| "border";

export type Paint = (color: ChartColor, text: string) => string;

export const noPaint: Paint = (_color, text) => text;

const SPARK = "▁▂▃▄▅▆▇█";
const EIGHTHS = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉"];

/**
 * Unicode sparkline. `min`/`max` default to the data range; pass them
 * explicitly to keep several sparklines on a shared scale.
 */
export function sparkline(
	values: readonly number[],
	options: { min?: number; max?: number } = {},
): string {
	if (values.length === 0) return "";
	const finite = values.filter((v) => Number.isFinite(v));
	if (finite.length === 0) return " ".repeat(values.length);
	const min = options.min ?? Math.min(...finite);
	const max = options.max ?? Math.max(...finite);
	const span = max - min;
	return values
		.map((value) => {
			if (!Number.isFinite(value)) return " ";
			if (span <= 0) return SPARK[0];
			const scaled = (value - min) / span;
			const index = Math.min(
				SPARK.length - 1,
				Math.max(0, Math.round(scaled * (SPARK.length - 1))),
			);
			return SPARK[index];
		})
		.join("");
}

/** Horizontal bar with eighth-cell resolution. `fraction` is clamped to [0,1]. */
export function bar(fraction: number, width: number): string {
	if (!Number.isFinite(fraction) || width <= 0) return "";
	const clamped = Math.min(1, Math.max(0, fraction));
	const eighths = Math.round(clamped * width * 8);
	const full = Math.floor(eighths / 8);
	const remainder = eighths % 8;
	const head = "█".repeat(Math.min(width, full));
	const tail = full < width ? EIGHTHS[remainder] : "";
	return (head + tail).padEnd(width, " ");
}

/** Vertical column chart drawn in a single row of block characters. */
export function columns(values: readonly number[], max?: number): string {
	const ceiling = max ?? Math.max(...values, 0);
	if (ceiling <= 0) return "▁".repeat(values.length);
	return sparkline(values, { min: 0, max: ceiling });
}

export function padEnd(text: string, width: number): string {
	return text.length >= width ? text : text + " ".repeat(width - text.length);
}

export function padStart(text: string, width: number): string {
	return text.length >= width ? text : " ".repeat(width - text.length) + text;
}

/** Trim to `width` with an ellipsis, never returning something longer. */
export function clip(text: string, width: number): string {
	if (width <= 0) return "";
	return text.length <= width
		? text
		: `${text.slice(0, Math.max(0, width - 1))}…`;
}

/** Fixed-decimal formatter that renders non-finite input as a dash. */
export function num(value: number | undefined, digits = 2): string {
	if (value === undefined || !Number.isFinite(value)) return "—";
	return value.toFixed(digits);
}

export function pct(value: number | undefined, digits = 1): string {
	if (value === undefined || !Number.isFinite(value)) return "—";
	return `${(value * 100).toFixed(digits)}%`;
}

/**
 * Make a detokenized piece safe and legible on one line: whitespace becomes
 * visible glyphs so " the" and "the" are distinguishable while tuning.
 */
export function showToken(text: string, width = 12): string {
	if (text === "") return "∅";
	const visible = text
		.replaceAll("\n", "⏎")
		.replaceAll("\r", "␍")
		.replaceAll("\t", "⇥")
		.replaceAll(" ", "·");
	return clip(visible, width);
}

export interface BarRowOptions {
	labelWidth?: number;
	barWidth?: number;
	color?: ChartColor;
	suffix?: string;
	paint?: Paint;
}

/** `label  0.412 ████████░░   suffix` */
export function barRow(
	label: string,
	value: number,
	max: number,
	options: BarRowOptions = {},
): string {
	const paint = options.paint ?? noPaint;
	const labelWidth = options.labelWidth ?? 14;
	const barWidth = options.barWidth ?? 18;
	const fraction = max > 0 ? value / max : 0;
	const cells = paint(options.color ?? "accent", bar(fraction, barWidth));
	const head = padEnd(clip(label, labelWidth), labelWidth);
	const suffix = options.suffix ? ` ${paint("dim", options.suffix)}` : "";
	return `${head} ${padStart(num(value, 3), 6)} ${cells}${suffix}`;
}

/** Horizontal histogram: one row per bucket, scaled to the largest count. */
export function histogramLines(
	buckets: readonly { label: string; count: number }[],
	options: { barWidth?: number; paint?: Paint; total?: number } = {},
): string[] {
	const paint = options.paint ?? noPaint;
	const barWidth = options.barWidth ?? 24;
	const max = Math.max(...buckets.map((b) => b.count), 0);
	const total = options.total ?? buckets.reduce((acc, b) => acc + b.count, 0);
	const labelWidth = Math.max(...buckets.map((b) => b.label.length), 1);
	return buckets.map((bucket) => {
		const share = total > 0 ? bucket.count / total : 0;
		const cells = bar(max > 0 ? bucket.count / max : 0, barWidth);
		return `${padStart(bucket.label, labelWidth)} ${paint(
			bucket.count > 0 ? "accent" : "dim",
			cells,
		)} ${padStart(String(bucket.count), 5)} ${paint("dim", padStart(pct(share, 0), 5))}`;
	});
}

export interface FunnelStage {
	label: string;
	/** Candidates still alive after this stage. */
	width: number;
	/** True when the measurement hit the probe's n_probs ceiling. */
	saturated?: boolean;
	/** Free-form caveat, e.g. history-dependent samplers measured without history. */
	note?: string;
}

/**
 * Draw the per-stage survivor funnel for one decode step. Widths are drawn on
 * a log scale because a chain routinely goes 151936 → 40 → 8 → 8.
 */
export function funnelLines(
	stages: readonly FunnelStage[],
	options: { vocab?: number; barWidth?: number; paint?: Paint } = {},
): string[] {
	const paint = options.paint ?? noPaint;
	const barWidth = options.barWidth ?? 22;
	const vocab = options.vocab ?? Math.max(...stages.map((s) => s.width), 2);
	const logMax = Math.log(Math.max(2, vocab));
	const labelWidth = Math.max(...stages.map((s) => s.label.length), 6);
	const lines: string[] = [];
	let previous: number | undefined;
	for (const stage of stages) {
		const fraction = Math.log(Math.max(1, stage.width)) / logMax;
		const cut =
			previous !== undefined && previous > stage.width
				? ` ${paint("warning", `−${previous - stage.width}`)}`
				: previous !== undefined
					? ` ${paint("dim", "·")}`
					: "";
		const width = `${stage.width}${stage.saturated ? "+" : ""}`;
		const note = stage.note ? ` ${paint("dim", stage.note)}` : "";
		lines.push(
			`${padEnd(stage.label, labelWidth)} ${paint("accent", bar(fraction, barWidth))} ${padStart(
				width,
				7,
			)}${cut}${note}`,
		);
		previous = stage.width;
	}
	return lines;
}

export interface HeatBucket {
	/** Inclusive lower bound of the bucket. */
	from: number;
	color: ChartColor;
	label: string;
}

/** Default width→color ramp: dim when the chain forced the token, hot when it had room. */
export const WIDTH_HEAT: readonly HeatBucket[] = [
	{ from: 0, color: "dim", label: "1" },
	{ from: 2, color: "muted", label: "2-3" },
	{ from: 4, color: "text", label: "4-7" },
	{ from: 8, color: "success", label: "8-15" },
	{ from: 16, color: "warning", label: "16-31" },
	{ from: 32, color: "error", label: "32+" },
];

export function heatColor(
	value: number,
	buckets: readonly HeatBucket[] = WIDTH_HEAT,
): ChartColor {
	let color: ChartColor = buckets[0]?.color ?? "text";
	for (const bucket of buckets) {
		if (value >= bucket.from) color = bucket.color;
	}
	return color;
}

/** One-line legend for a heat ramp. */
export function heatLegend(
	buckets: readonly HeatBucket[] = WIDTH_HEAT,
	paint: Paint = noPaint,
): string {
	return buckets.map((b) => paint(b.color, `█ ${b.label}`)).join("  ");
}

/**
 * Render generated text with every token tinted by a per-token value — the
 * fastest way to see *where* in an answer the sampler had freedom.
 */
export function heatText(
	tokens: readonly { text: string; value: number }[],
	options: {
		width?: number;
		buckets?: readonly HeatBucket[];
		paint?: Paint;
	} = {},
): string[] {
	const paint = options.paint ?? noPaint;
	const buckets = options.buckets ?? WIDTH_HEAT;
	const width = options.width ?? 76;
	const lines: string[] = [];
	let current = "";
	let currentLength = 0;
	const flush = (): void => {
		if (currentLength > 0) lines.push(current);
		current = "";
		currentLength = 0;
	};
	for (const token of tokens) {
		const pieces = token.text.split("\n");
		for (let i = 0; i < pieces.length; i += 1) {
			if (i > 0) flush();
			const piece = pieces[i];
			if (piece === "") continue;
			if (currentLength + piece.length > width) flush();
			current += paint(heatColor(token.value, buckets), piece);
			currentLength += piece.length;
		}
	}
	flush();
	return lines;
}

/**
 * Side-by-side "before / after intervention" table for one decode step.
 * Rows are ordered by raw rank; survivors show their post-chain probability
 * and everything else is marked as cut.
 */
export function beforeAfterLines(
	raw: readonly { id?: number; token: string; p: number }[],
	post: readonly { id?: number; token: string; p: number }[],
	options: {
		rows?: number;
		paint?: Paint;
		chosenKey?: string | number;
		barWidth?: number;
	} = {},
): string[] {
	const paint = options.paint ?? noPaint;
	const rows = options.rows ?? 12;
	const barWidth = options.barWidth ?? 14;
	const key = (c: { id?: number; token: string }): string | number =>
		c.id ?? c.token;
	const postIndex = new Map(post.map((c) => [key(c), c]));
	const rawMax = Math.max(...raw.map((c) => c.p), 0.000001);
	const postMax = Math.max(...post.map((c) => c.p), 0.000001);

	const lines: string[] = [
		paint(
			"dim",
			`${padEnd("rank token", 20)} ${padEnd("p_raw", barWidth + 7)} ${"p_post"}`,
		),
	];
	const shown = raw.slice(0, rows);
	for (let i = 0; i < shown.length; i += 1) {
		const candidate = shown[i];
		const survivor = postIndex.get(key(candidate));
		const chosen =
			options.chosenKey !== undefined && key(candidate) === options.chosenKey;
		const marker = chosen ? paint("accent", "▶") : " ";
		const label = `${padStart(String(i + 1), 3)} ${padEnd(showToken(candidate.token), 14)}`;
		const rawCell = `${num(candidate.p, 4)} ${paint("muted", bar(candidate.p / rawMax, barWidth))}`;
		const postCell = survivor
			? `${num(survivor.p, 4)} ${paint("success", bar(survivor.p / postMax, barWidth))}`
			: paint("error", "✂ cut");
		lines.push(`${marker}${label} ${rawCell}  ${postCell}`);
	}

	// Survivors the raw top-K never listed still deserve a line; without them a
	// wide chain looks like it dropped everything.
	const rawKeys = new Set(raw.map(key));
	const extras = post.filter((c) => !rawKeys.has(key(c)));
	if (extras.length > 0) {
		lines.push(
			paint(
				"dim",
				`    …${extras.length} survivor(s) below the raw top-${raw.length}`,
			),
		);
	}
	return lines;
}

/** Simple aligned table. Column widths are derived from the content. */
export function table(
	rows: readonly (readonly string[])[],
	options: { header?: readonly string[]; paint?: Paint; gap?: number } = {},
): string[] {
	const paint = options.paint ?? noPaint;
	const gap = " ".repeat(options.gap ?? 2);
	const all = options.header ? [options.header, ...rows] : rows;
	const columnCount = Math.max(...all.map((r) => r.length), 0);
	const widths: number[] = [];
	for (let c = 0; c < columnCount; c += 1) {
		widths[c] = Math.max(...all.map((r) => (r[c] ?? "").length));
	}
	const render = (row: readonly string[]): string =>
		row
			.map((cell, index) =>
				index === 0
					? padEnd(cell, widths[index])
					: padStart(cell, widths[index]),
			)
			.join(gap)
			.trimEnd();
	const lines = rows.map(render);
	return options.header
		? [paint("dim", render(options.header)), ...lines]
		: lines;
}
