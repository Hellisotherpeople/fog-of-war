"""DRY history matching, including llama.cpp's breaker-token exemption.

CPU token histories stay on CPU. Only sparse penalties are transferred to GPU.
There is no hidden history/occurrence cap: -1 uses the full model context.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np


class TokenHistory:
    def __init__(self, prompt: list[int], output: list[int], max_length: int):
        self.prompt = prompt
        self.output = output  # vLLM updates this list in place.
        self.max_length = max_length
        self.seen = -1
        self.data = np.empty(0, dtype=np.int32)
        self.size = 0

    def refresh(self) -> np.ndarray:
        n = len(self.output)
        if self.seen == n:
            return self.data[:self.size]
        if self.seen < 0 or n < self.seen:
            total = len(self.prompt) + n
            self.data = np.empty(min(self.max_length, max(total + 1024, 1024)), dtype=np.int32)
            self.data[:len(self.prompt)] = self.prompt
            self.size = len(self.prompt)
            self.seen = 0
        needed = self.size + n - self.seen
        if needed > self.max_length:
            raise ValueError("Token history exceeded model context")
        if needed > self.data.size:
            grown = np.empty(min(self.max_length, max(needed, self.data.size * 2)), dtype=np.int32)
            grown[:self.size] = self.data[:self.size]
            self.data = grown
        self.data[self.size:needed] = self.output[self.seen:n]
        self.size, self.seen = needed, n
        return self.data[:self.size]


class BreakerResolver:
    def __init__(self, tokenizer: Any, vocab_size: int):
        self.tokenizer = tokenizer
        self.vocab_size = vocab_size
        self.texts: list[str] | None = None
        self.cache: dict[tuple[str, ...], dict[int, tuple[tuple[int, ...], ...]]] = {}

    def resolve(self, breakers: tuple[str, ...]) -> dict[int, tuple[tuple[int, ...], ...]]:
        if breakers in self.cache:
            return self.cache[breakers]
        if not breakers:
            return {}
        if self.tokenizer is None:
            raise ValueError("DRY sequence breakers require a tokenizer")
        if self.texts is None:
            self.texts = []
            # Model vocabulary can include unused padded entries beyond the tokenizer.
            size = min(self.vocab_size, len(self.tokenizer))
            for start in range(0, size, 8192):
                self.texts.extend(self.tokenizer.batch_decode(
                    [[i] for i in range(start, min(start + 8192, size))],
                    skip_special_tokens=False, clean_up_tokenization_spaces=False,
                ))
        sequences: dict[int, set[tuple[int, ...]]] = {}
        for i, word in enumerate(self.texts):
            if not word:
                continue
            for breaker in breakers:
                if breaker in word:
                    sequences.setdefault(i, set()).add(())
                    continue
                # Match a breaker starting inside this token and ending in later tokens.
                pos = word.find(breaker[0])
                while pos >= 0:
                    suffix = word[pos:]
                    if breaker.startswith(suffix):
                        tail = tuple(self.tokenizer.encode(breaker[len(suffix):], add_special_tokens=False)[:20])
                        sequences.setdefault(i, set()).add(tail)
                    pos = word.find(breaker[0], pos + 1)
        result = {i: tuple(sorted(tails)) for i, tails in sequences.items()}
        self.cache[breakers] = result
        return result


def dry_penalties(history: np.ndarray, params: dict, breakers: dict[int, tuple[tuple[int, ...], ...]]) -> tuple[np.ndarray, np.ndarray]:
    multiplier, base = params["dry_multiplier"], params["dry_base"]
    allowed, last_n = params["dry_allowed_length"], params["dry_penalty_last_n"]
    empty = np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float32)
    if multiplier == 0 or last_n == 0:
        return empty
    window = history[-last_n:] if last_n > 0 else history
    size = len(window)
    if size <= allowed or size < 2:
        return empty
    rep_limit = size
    if breakers:
        heads = np.fromiter(breakers, dtype=np.int32)
        positions = np.flatnonzero(np.isin(window, heads))
        for pos in positions[::-1]:
            lengths = [len(tail) for tail in breakers[int(window[pos])]
                       if pos + len(tail) < size
                       and np.array_equal(window[pos + 1:pos + 1 + len(tail)], tail)]
            if lengths:
                rep_limit = size - 1 - int(pos) - max(lengths)
                break
    if rep_limit < allowed:
        return empty
    # llama.cpp includes zero-length matches when allowed_length is zero.
    occurrences = (np.arange(size - 1) if allowed == 0
                   else np.flatnonzero(window[:-1] == window[-1]))
    if not occurrences.size:
        return empty
    lengths = np.zeros(len(occurrences), dtype=np.int32)
    alive, slots = occurrences, np.arange(len(occurrences))
    # Beyond this length all penalties saturate. Match length no longer matters.
    limit_log = math.log(np.finfo(np.float32).max / 4)
    cap = (allowed if base == 1 else allowed + max(0, math.ceil((limit_log - math.log(multiplier)) / math.log(base))))
    cap = min(rep_limit, size - 1, max(cap, allowed))
    for offset in range(cap):
        prior = alive - offset
        keep = prior >= 0
        keep &= window[np.maximum(prior, 0)] == window[size - 1 - offset]
        alive, slots = alive[keep], slots[keep]
        if not alive.size:
            break
        lengths[slots] += 1
    qualifies = lengths >= allowed
    tokens, inverse = np.unique(window[occurrences[qualifies] + 1], return_inverse=True)
    best = np.zeros(len(tokens), dtype=np.int32)
    np.maximum.at(best, inverse, lengths[qualifies])
    keep = np.array([() not in breakers.get(int(t), ()) for t in tokens], dtype=bool)
    tokens, best = tokens[keep], best[keep]
    log_penalty = math.log(multiplier) + (best - allowed) * math.log(base)
    penalties = np.exp(np.minimum(log_penalty, limit_log)).astype(np.float32)
    return tokens.astype(np.int64), penalties
