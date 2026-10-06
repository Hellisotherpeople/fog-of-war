"""Torch implementations of the user's llama.cpp sampler chain.

All logit math stays on the input device. Membership is separate from -inf masks:
llama.cpp's top-n-sigma masks values but does not shrink its candidate array.
That distinction affects normalized P-less and XTC after other samplers.
"""
from __future__ import annotations

import math

import numpy as np
import torch

from .config import ChainConfig
from .dry import dry_penalties


def apply_chain(logits: torch.Tensor, config: ChainConfig, history: np.ndarray,
                breakers: dict, xtc_draws: list[float]) -> torch.Tensor:
    members = torch.ones_like(logits, dtype=torch.bool)
    p = config.params
    draws = iter(xtc_draws)
    ranks = torch.arange(logits.numel(), device=logits.device)

    def keep_sorted(order: torch.Tensor, count: torch.Tensor | int) -> None:
        nonlocal members
        keep = torch.zeros_like(members).scatter_(0, order, ranks < count)
        members &= keep
        logits.masked_fill_(~members, -torch.inf)

    for stage in config.chain:
        if stage == "temperature":
            temp = p["temperature"]
            if temp == 0 or (0 < temp < torch.finfo(torch.float32).tiny):
                best = logits.argmax()
                logits.masked_fill_(ranks != best, -torch.inf)
            elif math.isinf(temp):
                # -inf / inf is NaN. Preserve masks and flatten surviving logits.
                logits.masked_fill_(torch.isfinite(logits), 0.0)
            elif temp > torch.finfo(torch.float32).max:
                logits.copy_(torch.where(torch.isfinite(logits), logits * (1.0 / temp), logits))
            elif temp != 1:
                logits.div_(temp)
        elif stage == "top_n_sigma":
            n = p["top_n_sigma"]
            if n <= 0:
                continue
            finite = torch.isfinite(logits)
            count = finite.sum().clamp_min(1)
            values = logits.masked_fill(~finite, 0.0)
            mean = values.sum() / count
            variance = ((values - mean).square().masked_fill(~finite, 0.0)).sum() / count
            logits.masked_fill_(logits < logits.max() - n * variance.sqrt(), -torch.inf)
        elif stage == "min_k":
            ordered, order = torch.sort(logits, descending=True, stable=True)
            finite = torch.isfinite(ordered)
            low = ordered.masked_fill(~finite, torch.inf).min()
            span = ordered[0] - low + 1e-8
            if logits.numel() == 1:
                continue
            nxt = torch.where(finite[1:], ordered[1:], low)
            weight = (ordered[:-1] - nxt) / span / (ranks[:-1] + 1)
            weight = weight.masked_fill(~finite[:-1], -torch.inf)
            cliff = weight.argmax() + 1
            fallback = torch.floor(max(0.0, p["min_k_tau"]) / span).clamp(0, logits.numel())
            keep_sorted(order, torch.maximum(cliff, fallback).clamp_min(1))
        elif stage == "p_less":
            probs = torch.softmax(logits, dim=0)
            # C++ accumulates probability powers in double precision.
            q = p["p_less_exponent"]
            threshold = probs.double().pow(q).sum()
            if p["p_less_norm"]:
                n = members.sum().double()
                baseline = n.pow(1 - q)
                threshold = torch.where((n > 1) & (baseline < 1),
                    (threshold - baseline) / (1 - baseline).clamp_min(1e-300), threshold)
            ordered, order = torch.sort(probs, descending=True, stable=True)
            count = ((ordered.double() >= threshold) & members[order]).sum().clamp_min(1)
            keep_sorted(order, count)
        elif stage == "xtc":
            chance = next(draws)
            if p["xtc_probability"] <= 0 or p["xtc_threshold"] > 0.5 or chance > p["xtc_probability"]:
                continue
            probs, order = torch.sort(torch.softmax(logits, dim=0), descending=True, stable=True)
            # A zero threshold must not make previously masked tokens eligible.
            eligible = ((probs >= p["xtc_threshold"]) & members[order] & torch.isfinite(logits[order])).sum()
            # Retain the weakest eligible token and all candidates below it.
            remove = torch.zeros_like(members).scatter_(0, order, ranks < (eligible - 1))
            members &= ~remove
            logits.masked_fill_(~members, -torch.inf)
        elif stage == "min_p":
            if p["min_p"] > 0:
                cutoff = logits.max() + math.log(p["min_p"])
                members &= logits >= cutoff
                logits.masked_fill_(~members, -torch.inf)
        elif stage == "top_k":
            if p["top_k"] > 0:
                keep_sorted(torch.argsort(logits, descending=True, stable=True), p["top_k"])
        elif stage == "top_p":
            if p["top_p"] < 1:
                probs, order = torch.sort(torch.softmax(logits, dim=0), descending=True, stable=True)
                count = (probs.cumsum(0) < p["top_p"]).sum() + 1
                keep_sorted(order, count.clamp_min(1))
        elif stage == "dry":
            ids, penalties = dry_penalties(history, p, breakers)
            if len(ids):
                indices = torch.as_tensor(ids, device=logits.device)
                logits[indices] -= torch.as_tensor(penalties, device=logits.device)
        elif stage == "penalties":
            last = p["repeat_last_n"]
            if not last or not history.size:
                continue
            tokens, counts = np.unique(history[-last:] if last > 0 else history, return_counts=True)
            indices = torch.as_tensor(tokens.astype(np.int64), device=logits.device)
            old = logits[indices]
            repeat = p["repeat_penalty"]
            adjusted = torch.where(old <= 0, old * repeat, old / repeat)
            adjusted -= p["presence_penalty"] + torch.as_tensor(counts, device=logits.device) * p["frequency_penalty"]
            logits[indices] = adjusted
    return logits
