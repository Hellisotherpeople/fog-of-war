/**
 * Token discovery for a llama.cpp server.
 *
 * Logit bias is applied by token id, and ids are model-specific. An ordinary
 * word can just be tokenized on demand (`resolveLiteralToken`), but the special
 * tokens are the ones nobody can be expected to type from memory, so those are
 * enumerated up front. Two independent sources are used, best first:
 *
 *   gguf   The model file's own tokenizer metadata. `tokenizer.ggml.tokens` and
 *          `tokenizer.ggml.token_type` are the authoritative list: every token
 *          the converter marked CONTROL, USER_DEFINED or UNKNOWN, with its id
 *          being its index. Exact and complete, but needs the file to be
 *          readable from this process.
 *   probe  Candidate strings harvested from `/props` (chat template, bos, eos)
 *          plus a builtin per-family list, each confirmed with `/tokenize`.
 *          Works against a remote server; only finds what it thought to ask for.
 *
 * The probe tier cannot simply use `parse_special` as the "is it special?" test.
 * Qwen3 carries `<think>` and `</think>` as USER_DEFINED tokens, which the
 * tokenizer merges whether or not special parsing is on, so that check reports
 * them as ordinary text. A single-token round trip plus a markup shape test is
 * what actually separates them.
 */

import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Model
// ---------------------------------------------------------------------------

/**
 * What a special token is for. Only `think_close` carries real weight — it is
 * the token a "think less" bias has to find — but the rest make the token list
 * readable and let a user bias a class of tokens by name.
 */
export type TokenRole =
	| "think_open"
	| "think_close"
	| "bos"
	| "eos"
	| "eot"
	| "turn_start"
	| "turn_end"
	| "channel"
	| "tool_call_start"
	| "tool_call_end"
	| "tool_response_start"
	| "tool_response_end"
	| "vision"
	| "audio"
	| "fim"
	| "pad"
	| "unk"
	| "mask"
	| "sep"
	| "unused"
	| "other";

/** How the converter classified a token, when that is known. */
export type TokenKind =
	| "control"
	| "user_defined"
	| "unknown"
	| "byte"
	| "normal"
	| "unused"
	| "undefined";

export interface SpecialToken {
	id: number;
	text: string;
	role: TokenRole;
	kind: TokenKind;
	/** True when the tokenizer only produces this token with special parsing on. */
	needsParseSpecial?: boolean;
	/**
	 * True for a token the user named rather than one detection found: an
	 * ordinary word, a fragment, a raw id. Kept in the same list so lookup and
	 * bias resolution do not need a second code path, and flagged so the token
	 * listing can keep it out of the vocabulary's own inventory.
	 */
	added?: boolean;
}

export type TokenSource = "gguf" | "probe";

export interface SpecialTokenSet {
	source: TokenSource;
	/** Cache identity: alias plus vocabulary size, so a model swap invalidates. */
	key: string;
	modelAlias?: string;
	modelPath?: string;
	architecture?: string;
	nVocab?: number;
	bosToken?: string;
	eosToken?: string;
	tokens: SpecialToken[];
	/** Human-readable note about how the list was obtained or why it is partial. */
	note?: string;
}

// ---------------------------------------------------------------------------
// Role classification
// ---------------------------------------------------------------------------

/**
 * Ordered role patterns. The end-of-thinking forms are listed exhaustively
 * because that is the token this whole feature exists to find; families differ
 * more than you would hope (`</think>`, `<|end_thinking|>`, `◁/think▷`,
 * `</seed:think>`).
 */
const ROLE_PATTERNS: [TokenRole, RegExp][] = [
	[
		"think_close",
		/^(?:<\|?\/|<\|)(?:\/?)(?:end[_-]?)?(?:think|thinking|thought|reason|reasoning|seed:think|scratchpad)(?:[_-]?end)?(?:\|?>|\|>)$/i,
	],
	[
		"think_close",
		/^(?:◁|<)\s*\/\s*(?:think|thinking|thought|reasoning)\s*(?:▷|>)$/i,
	],
	["think_close", /^\[\/(?:think|thinking|thought|reasoning)\]$/i],
	[
		"think_open",
		/^<\|?(?:start[_-]?)?(?:think|thinking|thought|reason|reasoning|seed:think|scratchpad)(?:[_-]?start)?\|?>$/i,
	],
	["think_open", /^(?:◁|\[)(?:think|thinking|thought|reasoning)(?:▷|\])$/i],
	["channel", /channel|analysis|commentary|<\|start\|>|<\|message\|>/i],
	// The closing form has to be tested first: an optional slash in the opening
	// pattern would swallow `</tool_call>` as an opening tag.
	["tool_call_end", /^<\/(?:\|)?tool[_-]?call[s]?(?:\|)?>$/i],
	["tool_call_start", /^<\|?tool[_-]?call[s]?\|?>$/i],
	["tool_response_start", /^<\|?tool[_-]?(?:response|result|output)\|?>$/i],
	[
		"tool_response_end",
		/^<\/(?:\|)?tool[_-]?(?:response|result|output)(?:\|)?>$/i,
	],
	["vision", /vision|image|video|patch/i],
	["audio", /audio|tts|speech/i],
	["fim", /fim|repo[_-]?name|file[_-]?sep|middle|suffix|prefix/i],
	["eot", /^<\|(?:im_end|eot_id|eom_id|end|endofturn|turn_end)\|>$/i],
	["eot", /^(?:<end_of_turn>|<\/s>|\[\/INST\]|<\|end▁of▁sentence\|>)$/i],
	["turn_start", /^(?:<\|im_start\|>|<start_of_turn>|<\|start_header_id\|>)$/i],
	["turn_end", /^<\|end_header_id\|>$/i],
	["eos", /^(?:<\|endoftext\|>|<\|end_of_text\|>|<eos>)$/i],
	["bos", /^(?:<s>|<bos>|<\|begin_of_text\|>|\[gMASK\])$/i],
	["pad", /^(?:<\|?pad\|?>|<pad>|<\|finetune_right_pad_id\|>)$/i],
	["unk", /^<unk>$/i],
	["mask", /mask/i],
	["sep", /^(?:<sep>|\[SEP\])$/i],
];

/**
 * Placeholder slots a converter emits to pad the vocabulary to a round size:
 * `[PAD248260]`, `<|reserved_special_token_3|>`, `<|unused_12|>`.
 */
const UNUSED_PATTERN =
	/^(?:<\|)?\[?(?:PAD|UNUSED|unused|reserved_special_token)[_\d]*\]?(?:\|>)?$/;

export interface RoleContext {
	bosToken?: string;
	eosToken?: string;
}

/** Best-effort role for one token's text. */
export function classifyTokenRole(
	text: string,
	context: RoleContext = {},
): TokenRole {
	if (UNUSED_PATTERN.test(text)) return "unused";
	for (const [role, pattern] of ROLE_PATTERNS) {
		if (pattern.test(text)) return role;
	}
	// The server names these two explicitly, so they win over "other" but lose to
	// a structural match: Qwen's bos is <|endoftext|>, which is really an eos.
	if (context.eosToken && text === context.eosToken) return "eos";
	if (context.bosToken && text === context.bosToken) return "bos";
	return "other";
}

/**
 * Does this text look like tokenizer markup rather than ordinary language?
 *
 * Used only by the probe tier, where nothing authoritative is available. The
 * gguf tier knows the real answer and never calls this.
 */
export function looksLikeSpecialToken(text: string): boolean {
	if (text.length < 3 || text.length > 64) return false;
	if (/\s/.test(text)) return false;
	return (
		/^<[^<>]+>$/.test(text) ||
		/^<\|[^|]*\|>$/.test(text) ||
		/^<｜.*｜>$/.test(text) ||
		/^\[[A-Za-z0-9_/|:.-]+\]$/.test(text) ||
		/^◁.*▷$/.test(text) ||
		/^\[\/?INST\]$/.test(text)
	);
}

// ---------------------------------------------------------------------------
// gguf tier
// ---------------------------------------------------------------------------

const GGUF_MAGIC = "GGUF";
/** Stop reading rather than pull a whole quantized model through memory. */
const GGUF_METADATA_LIMIT = 256 * 1024 * 1024;
const GGUF_CHUNK = 4 * 1024 * 1024;
const GGUF_MAX_VOCAB = 4_000_000;

enum GgufType {
	UINT8 = 0,
	INT8 = 1,
	UINT16 = 2,
	INT16 = 3,
	UINT32 = 4,
	INT32 = 5,
	FLOAT32 = 6,
	BOOL = 7,
	STRING = 8,
	ARRAY = 9,
	UINT64 = 10,
	INT64 = 11,
	FLOAT64 = 12,
}

const SCALAR_WIDTH: Record<number, number> = {
	[GgufType.UINT8]: 1,
	[GgufType.INT8]: 1,
	[GgufType.UINT16]: 2,
	[GgufType.INT16]: 2,
	[GgufType.UINT32]: 4,
	[GgufType.INT32]: 4,
	[GgufType.FLOAT32]: 4,
	[GgufType.BOOL]: 1,
	[GgufType.UINT64]: 8,
	[GgufType.INT64]: 8,
	[GgufType.FLOAT64]: 8,
};

/**
 * Forward-only reader over the head of a file.
 *
 * A gguf's metadata block sits at the front, so only a prefix is ever read; the
 * tensor payload behind it is never touched.
 */
class PrefixReader {
	#buf = Buffer.alloc(0);
	#filled = 0;
	#pos = 0;

	constructor(private readonly fd: number) {}

	get offset(): number {
		return this.#pos;
	}

	#ensure(need: number): void {
		const want = this.#pos + need;
		if (want <= this.#filled) return;
		if (want > GGUF_METADATA_LIMIT) {
			throw new Error("gguf metadata exceeds the read limit");
		}
		while (this.#filled < want) {
			if (this.#filled === this.#buf.length) {
				const grown = Buffer.alloc(
					Math.min(
						GGUF_METADATA_LIMIT,
						Math.max(GGUF_CHUNK, this.#buf.length * 2),
					),
				);
				this.#buf.copy(grown, 0, 0, this.#filled);
				this.#buf = grown;
			}
			const read = fs.readSync(
				this.fd,
				this.#buf,
				this.#filled,
				this.#buf.length - this.#filled,
				this.#filled,
			);
			if (read === 0) throw new Error("unexpected end of gguf file");
			this.#filled += read;
		}
	}

	skip(bytes: number): void {
		if (bytes < 0) throw new Error("negative skip in gguf");
		this.#ensure(bytes);
		this.#pos += bytes;
	}

	bytes(length: number): Buffer {
		this.#ensure(length);
		const out = this.#buf.subarray(this.#pos, this.#pos + length);
		this.#pos += length;
		return out;
	}

	u32(): number {
		this.#ensure(4);
		const value = this.#buf.readUInt32LE(this.#pos);
		this.#pos += 4;
		return value;
	}

	i32(): number {
		this.#ensure(4);
		const value = this.#buf.readInt32LE(this.#pos);
		this.#pos += 4;
		return value;
	}

	u64(): number {
		this.#ensure(8);
		const value = this.#buf.readBigUInt64LE(this.#pos);
		this.#pos += 8;
		if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
			throw new Error("gguf length does not fit in a safe integer");
		}
		return Number(value);
	}

	string(): string {
		const length = this.u64();
		return this.bytes(length).toString("utf8");
	}
}

export interface GgufTokenizer {
	architecture?: string;
	tokens: string[];
	tokenTypes: number[];
	chatTemplate?: string;
	specialIds: Record<string, number>;
}

/**
 * Read the tokenizer block out of a gguf file.
 *
 * Values for keys nobody asked for are skipped without being materialized,
 * which matters: `tokenizer.ggml.merges` is a quarter of a million strings and
 * sits between the token list and the special-token ids.
 */
export function readGgufTokenizer(filePath: string): GgufTokenizer {
	const fd = fs.openSync(filePath, "r");
	try {
		const reader = new PrefixReader(fd);
		if (reader.bytes(4).toString("latin1") !== GGUF_MAGIC) {
			throw new Error("not a gguf file");
		}
		const version = reader.u32();
		if (version < 2 || version > 3) {
			throw new Error(`unsupported gguf version ${version}`);
		}
		reader.u64(); // tensor count
		const kvCount = reader.u64();

		const out: GgufTokenizer = { tokens: [], tokenTypes: [], specialIds: {} };
		for (let index = 0; index < kvCount; index += 1) {
			const key = reader.string();
			const type = reader.u32();
			switch (key) {
				case "general.architecture":
					out.architecture = readString(reader, type);
					break;
				case "tokenizer.chat_template":
					out.chatTemplate = readString(reader, type);
					break;
				case "tokenizer.ggml.tokens":
					out.tokens = readStringArray(reader, type);
					break;
				case "tokenizer.ggml.token_type":
					out.tokenTypes = readIntArray(reader, type);
					break;
				default:
					if (
						key.startsWith("tokenizer.ggml.") &&
						key.endsWith("_token_id") &&
						SCALAR_WIDTH[type] !== undefined
					) {
						const name = key.slice("tokenizer.ggml.".length, -"_token_id".length);
						const value = readScalar(reader, type);
						if (typeof value === "number") out.specialIds[name] = value;
					} else {
						skipValue(reader, type);
					}
					break;
			}
		}
		return out;
	} finally {
		fs.closeSync(fd);
	}
}

function readString(reader: PrefixReader, type: number): string | undefined {
	if (type !== GgufType.STRING) {
		skipValue(reader, type);
		return undefined;
	}
	return reader.string();
}

function readStringArray(reader: PrefixReader, type: number): string[] {
	if (type !== GgufType.ARRAY) {
		skipValue(reader, type);
		return [];
	}
	const elementType = reader.u32();
	const count = reader.u64();
	if (elementType !== GgufType.STRING) {
		skipArrayElements(reader, elementType, count);
		return [];
	}
	if (count > GGUF_MAX_VOCAB) throw new Error(`vocabulary too large: ${count}`);
	const out = new Array<string>(count);
	for (let index = 0; index < count; index += 1) out[index] = reader.string();
	return out;
}

function readIntArray(reader: PrefixReader, type: number): number[] {
	if (type !== GgufType.ARRAY) {
		skipValue(reader, type);
		return [];
	}
	const elementType = reader.u32();
	const count = reader.u64();
	if (elementType !== GgufType.INT32 && elementType !== GgufType.UINT32) {
		skipArrayElements(reader, elementType, count);
		return [];
	}
	if (count > GGUF_MAX_VOCAB) throw new Error(`vocabulary too large: ${count}`);
	const out = new Array<number>(count);
	for (let index = 0; index < count; index += 1) {
		out[index] =
			elementType === GgufType.INT32 ? reader.i32() : reader.u32();
	}
	return out;
}

function readScalar(reader: PrefixReader, type: number): number | undefined {
	const width = SCALAR_WIDTH[type];
	if (width === undefined) {
		skipValue(reader, type);
		return undefined;
	}
	switch (type) {
		case GgufType.UINT32:
			return reader.u32();
		case GgufType.INT32:
			return reader.i32();
		case GgufType.UINT64:
		case GgufType.INT64:
			return reader.u64();
		default: {
			const buf = reader.bytes(width);
			return type === GgufType.INT8 ? buf.readInt8(0) : buf.readUInt8(0);
		}
	}
}

function skipValue(reader: PrefixReader, type: number): void {
	if (type === GgufType.STRING) {
		reader.skip(reader.u64());
		return;
	}
	if (type === GgufType.ARRAY) {
		const elementType = reader.u32();
		const count = reader.u64();
		skipArrayElements(reader, elementType, count);
		return;
	}
	const width = SCALAR_WIDTH[type];
	if (width === undefined) throw new Error(`unknown gguf value type ${type}`);
	reader.skip(width);
}

function skipArrayElements(
	reader: PrefixReader,
	elementType: number,
	count: number,
): void {
	if (elementType === GgufType.STRING) {
		for (let index = 0; index < count; index += 1) reader.skip(reader.u64());
		return;
	}
	if (elementType === GgufType.ARRAY) {
		for (let index = 0; index < count; index += 1) {
			skipValue(reader, GgufType.ARRAY);
		}
		return;
	}
	const width = SCALAR_WIDTH[elementType];
	if (width === undefined) {
		throw new Error(`unknown gguf array element type ${elementType}`);
	}
	reader.skip(width * count);
}

/** gguf token_type values; see `llama_token_type` in llama.h. */
const GGUF_TOKEN_KIND: Record<number, TokenKind> = {
	0: "undefined",
	1: "normal",
	2: "unknown",
	3: "control",
	4: "user_defined",
	5: "unused",
	6: "byte",
};

/** Kinds worth listing: everything the model treats as markup, not language. */
const SPECIAL_KINDS = new Set<TokenKind>(["control", "user_defined", "unknown"]);

/**
 * Turn a parsed gguf tokenizer into the special-token list.
 *
 * `includeUnused` exists because a converter can emit hundreds of `[PAD…]`
 * placeholder slots; they are real vocabulary entries and biasing them is
 * legitimate, but they would bury the twenty tokens anyone cares about.
 */
export function specialTokensFromGguf(
	tokenizer: GgufTokenizer,
	context: RoleContext = {},
	includeUnused = false,
): SpecialToken[] {
	const out: SpecialToken[] = [];
	const namedIds = new Set(Object.values(tokenizer.specialIds));
	const count = Math.min(tokenizer.tokens.length, tokenizer.tokenTypes.length);
	for (let id = 0; id < count; id += 1) {
		const kind = GGUF_TOKEN_KIND[tokenizer.tokenTypes[id]] ?? "undefined";
		const isSpecial = SPECIAL_KINDS.has(kind) || namedIds.has(id);
		const isUnused = kind === "unused";
		if (!isSpecial && !(includeUnused && isUnused)) continue;
		const text = tokenizer.tokens[id];
		out.push({
			id,
			text,
			role: isUnused ? "unused" : classifyTokenRole(text, context),
			kind,
		});
	}
	// A converter can leave a special token typed NORMAL while still naming it in
	// tokenizer.ggml.*_token_id; those come in through namedIds above. Sort by id
	// so the list reads in vocabulary order.
	return out.sort((a, b) => a.id - b.id);
}

// ---------------------------------------------------------------------------
// probe tier
// ---------------------------------------------------------------------------

/**
 * Special tokens worth asking about when the model file cannot be read.
 *
 * One entry per known form across the families a local llama.cpp is likely to
 * be serving. A wrong guess costs nothing: `/tokenize` simply reports that the
 * string is not a single token and it is dropped.
 */
export const SPECIAL_TOKEN_CANDIDATES: readonly string[] = [
	// Reasoning open/close, the reason this list exists.
	"<think>",
	"</think>",
	"<thinking>",
	"</thinking>",
	"<thought>",
	"</thought>",
	"<reasoning>",
	"</reasoning>",
	"<seed:think>",
	"</seed:think>",
	"<|think|>",
	"<|/think|>",
	"<|thinking|>",
	"<|/thinking|>",
	"<|start_thinking|>",
	"<|end_thinking|>",
	"<|START_THINKING|>",
	"<|END_THINKING|>",
	"<|thought_start|>",
	"<|thought_end|>",
	"<|reasoning_start|>",
	"<|reasoning_end|>",
	"◁think▷",
	"◁/think▷",
	"[think]",
	"[/think]",
	// ChatML and friends.
	"<|im_start|>",
	"<|im_end|>",
	"<|endoftext|>",
	"<|end_of_text|>",
	"<|begin_of_text|>",
	"<|start_header_id|>",
	"<|end_header_id|>",
	"<|eot_id|>",
	"<|eom_id|>",
	"<|python_tag|>",
	"<|finetune_right_pad_id|>",
	"<s>",
	"</s>",
	"<bos>",
	"<eos>",
	"<pad>",
	"<unk>",
	"<mask>",
	"<sep>",
	"[INST]",
	"[/INST]",
	"[gMASK]",
	"<sop>",
	"<|user|>",
	"<|assistant|>",
	"<|system|>",
	"<|observation|>",
	"<start_of_turn>",
	"<end_of_turn>",
	"<|start|>",
	"<|end|>",
	"<|message|>",
	"<|channel|>",
	"<|constrain|>",
	"<|return|>",
	"<|call|>",
	"<|begin▁of▁sentence|>",
	"<|end▁of▁sentence|>",
	"<|User|>",
	"<|Assistant|>",
	// Tools.
	"<tool_call>",
	"</tool_call>",
	"<tool_response>",
	"</tool_response>",
	"<|tool_call|>",
	"<|tool_response|>",
	"<|tool_calls_section_begin|>",
	"<|tool_calls_section_end|>",
	"[TOOL_CALLS]",
	// Multimodal and infill, so the list is a complete picture of the vocabulary.
	"<|vision_start|>",
	"<|vision_end|>",
	"<|vision_pad|>",
	"<|image_pad|>",
	"<|video_pad|>",
	"<|audio_start|>",
	"<|audio_end|>",
	"<|audio_pad|>",
	"<image>",
	"<|fim_prefix|>",
	"<|fim_middle|>",
	"<|fim_suffix|>",
	"<|fim_pad|>",
	"<|repo_name|>",
	"<|file_sep|>",
];

/**
 * Pull token-shaped literals out of a chat template.
 *
 * A template is the one place a server always reveals the markup its model
 * expects, and it costs nothing to read. It is not complete: Qwen's template
 * never mentions `<|endoftext|>` or `<tool_call>`.
 */
export function harvestTemplateCandidates(template: string): string[] {
	const patterns = [
		/<\|[^|<>\s]{1,48}\|>/g,
		/<｜[^｜<>\s]{1,48}｜>/g,
		/<\/?[A-Za-z][A-Za-z0-9_:.-]{0,46}>/g,
		/◁[^◁▷\s]{1,32}▷/g,
		/\[(?:\/?[A-Z][A-Z_]{1,30}|gMASK|sop)\]/g,
	];
	const found = new Set<string>();
	for (const pattern of patterns) {
		for (const match of template.matchAll(pattern)) found.add(match[0]);
	}
	return [...found];
}

/** The `/tokenize` and `/props` surface the probe tier needs. */
export interface TokenProbeClient {
	tokenize(
		content: string,
		options?: { addSpecial?: boolean; parseSpecial?: boolean },
		signal?: AbortSignal,
	): Promise<{ tokens: number[] }>;
	/** Optional: only needed to bias tokens by arbitrary text. */
	tokenizePieces?(
		content: string,
		options?: { addSpecial?: boolean; parseSpecial?: boolean },
		signal?: AbortSignal,
	): Promise<{ tokens: { id: number; piece: string }[] }>;
}

export type LiteralTokenResult =
	| { kind: "single"; token: SpecialToken }
	| { kind: "multi"; pieces: { id: number; piece: string }[] };

/**
 * Resolve arbitrary text to a token, so anything in the vocabulary can be
 * biased and not just the markup.
 *
 * Most words are one token and resolve cleanly. Text that is several tokens is
 * reported as such rather than being silently collapsed: llama.cpp's own string
 * form of `logit_bias` biases every constituent token, which is a different
 * thing from what someone typing a word usually means, and the caller should
 * say so before doing it.
 */
export async function resolveLiteralToken(
	client: TokenProbeClient,
	text: string,
	signal?: AbortSignal,
): Promise<LiteralTokenResult> {
	const pieces = await tokenizeWithPieces(client, text, signal);
	if (pieces.length === 1) {
		return {
			kind: "single",
			token: {
				id: pieces[0].id,
				// The typed text is the key users will recognize; the rendered piece
				// is the same string for any text that is a single token.
				text,
				role: classifyTokenRole(text),
				kind: looksLikeSpecialToken(text) ? "control" : "normal",
				added: true,
			},
		};
	}
	return { kind: "multi", pieces };
}

/** Pieces for a string, falling back to ids alone when the server is older. */
export async function tokenizeWithPieces(
	client: TokenProbeClient,
	text: string,
	signal?: AbortSignal,
): Promise<{ id: number; piece: string }[]> {
	if (client.tokenizePieces) {
		const result = await client.tokenizePieces(
			text,
			{ addSpecial: false, parseSpecial: true },
			signal,
		);
		if (result.tokens.length > 0) return result.tokens;
	}
	const result = await client.tokenize(
		text,
		{ addSpecial: false, parseSpecial: true },
		signal,
	);
	return result.tokens.map((id) => ({ id, piece: "" }));
}

/**
 * Add or replace tokens in a set, keeping it sorted by id.
 *
 * A detected token always wins over an added one with the same id: if the user
 * biased `</think>` as free text before detection reached the model file, the
 * richer entry should replace theirs rather than sit alongside it.
 */
export function withAddedTokens(
	set: SpecialTokenSet,
	added: readonly SpecialToken[],
): SpecialTokenSet {
	const byId = new Map<number, SpecialToken>();
	for (const token of added) byId.set(token.id, token);
	for (const token of set.tokens) byId.set(token.id, token);
	return {
		...set,
		tokens: [...byId.values()].sort((a, b) => a.id - b.id),
	};
}

/**
 * Confirm which candidate strings are single tokens, and get their ids.
 *
 * Each candidate needs two `/tokenize` calls. With special parsing off a
 * genuine control token shatters into text, which is recorded as
 * `needsParseSpecial`; a USER_DEFINED token such as Qwen's `</think>` merges
 * either way, so that flag is reported rather than used as a filter.
 */
export async function probeSpecialTokens(
	client: TokenProbeClient,
	candidates: readonly string[],
	context: RoleContext = {},
	signal?: AbortSignal,
): Promise<SpecialToken[]> {
	const seen = new Set<string>();
	const out: SpecialToken[] = [];
	for (const candidate of candidates) {
		if (seen.has(candidate)) continue;
		seen.add(candidate);
		if (!looksLikeSpecialToken(candidate)) continue;
		try {
			const special = await client.tokenize(
				candidate,
				{ addSpecial: false, parseSpecial: true },
				signal,
			);
			if (special.tokens.length !== 1) continue;
			const id = special.tokens[0];
			let needsParseSpecial = true;
			try {
				const plain = await client.tokenize(
					candidate,
					{ addSpecial: false, parseSpecial: false },
					signal,
				);
				needsParseSpecial =
					plain.tokens.length !== 1 || plain.tokens[0] !== id;
			} catch {
				/* the flag is informational; a failure here must not drop the token */
			}
			out.push({
				id,
				text: candidate,
				role: classifyTokenRole(candidate, context),
				kind: needsParseSpecial ? "control" : "user_defined",
				needsParseSpecial,
			});
		} catch {
			/* an unreachable server is reported by the caller, not per candidate */
		}
	}
	return out.sort((a, b) => a.id - b.id);
}

// ---------------------------------------------------------------------------
// Orchestration
// ---------------------------------------------------------------------------

export interface DetectOptions {
	client?: TokenProbeClient;
	modelPath?: string;
	modelAlias?: string;
	nVocab?: number;
	bosToken?: string;
	eosToken?: string;
	chatTemplate?: string;
	includeUnused?: boolean;
	/** Extra strings to try in the probe tier, e.g. ones the user named. */
	extraCandidates?: readonly string[];
	signal?: AbortSignal;
	log?: (message: string, data?: Record<string, unknown>) => void;
}

/** Cache identity for a detection result. */
export function tokenSetKey(
	modelAlias: string | undefined,
	nVocab: number | undefined,
): string {
	return `${modelAlias ?? "unknown"}:${nVocab ?? 0}`;
}

/**
 * Find the vocabulary's special tokens, preferring the model file.
 *
 * The gguf result is spot-checked against the server before it is trusted: a
 * `model_path` can be stale, or point at a sibling quantization with a
 * different vocabulary, and biasing by an id from the wrong file would silently
 * hit an unrelated token.
 */
export async function detectSpecialTokens(
	options: DetectOptions,
): Promise<SpecialTokenSet> {
	const context: RoleContext = {
		...(options.bosToken !== undefined ? { bosToken: options.bosToken } : {}),
		...(options.eosToken !== undefined ? { eosToken: options.eosToken } : {}),
	};
	const base = {
		key: tokenSetKey(options.modelAlias, options.nVocab),
		...(options.modelAlias !== undefined
			? { modelAlias: options.modelAlias }
			: {}),
		...(options.nVocab !== undefined ? { nVocab: options.nVocab } : {}),
		...context,
	};

	if (options.modelPath) {
		try {
			const tokenizer = readGgufTokenizer(options.modelPath);
			const tokens = specialTokensFromGguf(
				tokenizer,
				context,
				options.includeUnused ?? false,
			);
			if (tokens.length === 0) throw new Error("no special tokens in metadata");
			const mismatch = options.client
				? await verifyAgainstServer(options.client, tokens, options.signal)
				: undefined;
			if (mismatch) {
				options.log?.("gguf token ids disagree with the server", { mismatch });
			} else {
				return {
					...base,
					source: "gguf",
					modelPath: options.modelPath,
					...(tokenizer.architecture !== undefined
						? { architecture: tokenizer.architecture }
						: {}),
					tokens,
					note: options.client
						? "read from the model file and spot-checked against /tokenize"
						: "read from the model file",
				};
			}
		} catch (error) {
			options.log?.("could not read tokenizer metadata from the model file", {
				modelPath: options.modelPath,
				error: error instanceof Error ? error.message : String(error),
			});
		}
	}

	if (!options.client) {
		throw new Error(
			"no model file to read and no server to probe, so no tokens could be detected",
		);
	}

	const candidates = [
		...(options.bosToken ? [options.bosToken] : []),
		...(options.eosToken ? [options.eosToken] : []),
		...(options.chatTemplate
			? harvestTemplateCandidates(options.chatTemplate)
			: []),
		...SPECIAL_TOKEN_CANDIDATES,
		...(options.extraCandidates ?? []),
	];
	const tokens = await probeSpecialTokens(
		options.client,
		candidates,
		context,
		options.signal,
	);
	return {
		...base,
		source: "probe",
		...(options.modelPath !== undefined ? { modelPath: options.modelPath } : {}),
		tokens,
		note: `confirmed ${tokens.length} of ${new Set(candidates).size} candidate strings with /tokenize; only tokens this list knows to ask for can be found`,
	};
}

/**
 * Re-tokenize a few discovered tokens and check the ids match.
 *
 * Tokens whose text the tokenizer will not reproduce as a single id (byte
 * fallbacks, unused placeholders) are skipped rather than counted as failures.
 */
async function verifyAgainstServer(
	client: TokenProbeClient,
	tokens: readonly SpecialToken[],
	signal?: AbortSignal,
): Promise<string | undefined> {
	const sample = tokens
		.filter((token) => token.role !== "unused" && looksLikeSpecialToken(token.text))
		.slice(0, 6);
	if (sample.length === 0) return undefined;
	for (const token of sample) {
		let result: { tokens: number[] };
		try {
			result = await client.tokenize(
				token.text,
				{ addSpecial: false, parseSpecial: true },
				signal,
			);
		} catch {
			// An unreachable server proves nothing about the file; trust the file.
			return undefined;
		}
		if (result.tokens.length !== 1) continue;
		if (result.tokens[0] !== token.id) {
			return `${token.text} is ${token.id} in the file but ${result.tokens[0]} on the server`;
		}
	}
	return undefined;
}

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

/**
 * Detection results, persisted per model.
 *
 * Bias has to be stamped onto a request synchronously, but detection is a file
 * read or a round of HTTP calls. Without a cache the first turn of a session
 * would go out unbiased. Keyed by alias plus vocabulary size so re-quantizing or
 * swapping models invalidates the entry instead of silently reusing stale ids.
 */
export class TokenSetCache {
	#sets = new Map<string, SpecialTokenSet>();

	constructor(private readonly filePath: string) {
		try {
			const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
			if (typeof raw === "object" && raw !== null) {
				for (const [key, value] of Object.entries(
					raw as Record<string, unknown>,
				)) {
					const set = reviveTokenSet(value);
					if (set) this.#sets.set(key, set);
				}
			}
		} catch {
			/* no cache yet, or an unreadable one; detection will refill it */
		}
	}

	get(key: string): SpecialTokenSet | undefined {
		return this.#sets.get(key);
	}

	put(set: SpecialTokenSet): void {
		this.#sets.set(set.key, set);
		try {
			fs.mkdirSync(path.dirname(this.filePath), { recursive: true });
			fs.writeFileSync(
				this.filePath,
				JSON.stringify(Object.fromEntries(this.#sets), null, 2),
			);
		} catch {
			/* best effort; an unwritable cache only costs a re-detect */
		}
	}
}

function reviveTokenSet(value: unknown): SpecialTokenSet | undefined {
	if (typeof value !== "object" || value === null) return undefined;
	const raw = value as Record<string, unknown>;
	if (typeof raw.key !== "string" || !Array.isArray(raw.tokens)) return undefined;
	const tokens: SpecialToken[] = [];
	for (const entry of raw.tokens) {
		if (typeof entry !== "object" || entry === null) continue;
		const token = entry as Record<string, unknown>;
		if (!Number.isInteger(token.id) || typeof token.text !== "string") continue;
		tokens.push({
			id: token.id as number,
			text: token.text,
			role: (typeof token.role === "string"
				? token.role
				: "other") as TokenRole,
			kind: (typeof token.kind === "string"
				? token.kind
				: "control") as TokenKind,
			...(typeof token.needsParseSpecial === "boolean"
				? { needsParseSpecial: token.needsParseSpecial }
				: {}),
			...(token.added === true ? { added: true } : {}),
		});
	}
	return {
		source: raw.source === "gguf" ? "gguf" : "probe",
		key: raw.key,
		tokens,
		...(typeof raw.modelAlias === "string"
			? { modelAlias: raw.modelAlias }
			: {}),
		...(typeof raw.modelPath === "string" ? { modelPath: raw.modelPath } : {}),
		...(typeof raw.architecture === "string"
			? { architecture: raw.architecture }
			: {}),
		...(Number.isInteger(raw.nVocab) ? { nVocab: raw.nVocab as number } : {}),
		...(typeof raw.bosToken === "string" ? { bosToken: raw.bosToken } : {}),
		...(typeof raw.eosToken === "string" ? { eosToken: raw.eosToken } : {}),
		...(typeof raw.note === "string" ? { note: raw.note } : {}),
	};
}

// ---------------------------------------------------------------------------
// Lookup
// ---------------------------------------------------------------------------

/** Roles that end a reasoning block, most specific first. */
const THINK_CLOSE_ROLES: TokenRole[] = ["think_close"];

/**
 * The token that ends a reasoning block, if this model has one.
 *
 * Some models do not: gpt-oss leaves the analysis channel with `<|end|>`
 * followed by a new header, so there is no single token to bias. Those return
 * undefined and the caller has to say so rather than bias something arbitrary.
 */
export function findThinkCloseToken(
	set: SpecialTokenSet | undefined,
): SpecialToken | undefined {
	if (!set) return undefined;
	for (const role of THINK_CLOSE_ROLES) {
		const found = set.tokens.find((token) => token.role === role);
		if (found) return found;
	}
	return undefined;
}

/**
 * Resolve a user-typed token reference against a detected set.
 *
 * Accepts an exact token text, a `#<id>` literal, a bare integer, or a role
 * name (`think_close`). Matching is case-insensitive on text so `</THINK>`
 * still finds `</think>`.
 */
export function resolveTokenReference(
	set: SpecialTokenSet | undefined,
	reference: string,
): SpecialToken | { id: number } | undefined {
	// Whitespace is significant in a token: on a BPE vocabulary " delve" is one
	// token and "delve" is two different ones. So an exact match on the raw string
	// comes first, and when the reference carries whitespace the trimming
	// conveniences below are skipped entirely — trimming it would resolve to a
	// neighbouring token that the caller did not ask for.
	if (reference === "") return undefined;
	const raw = set?.tokens.find((token) => token.text === reference);
	if (raw) return raw;
	const trimmed = reference.trim();
	if (trimmed === "") return undefined;
	const idMatch = /^#?(\d+)$/.exec(trimmed);
	if (idMatch) {
		const id = Number(idMatch[1]);
		return set?.tokens.find((token) => token.id === id) ?? { id };
	}
	if (!set || trimmed !== reference) return undefined;
	const exact = set.tokens.find((token) => token.text === trimmed);
	if (exact) return exact;
	const folded = trimmed.toLowerCase();
	const insensitive = set.tokens.find(
		(token) => token.text.toLowerCase() === folded,
	);
	if (insensitive) return insensitive;
	return set.tokens.find((token) => token.role === folded);
}
