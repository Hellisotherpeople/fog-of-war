"""A versioned, JSON-string wire format fits vLLM's vllm_xargs schema."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

WIRE_KEY = "omp_sampler_config"
DEFAULT_BREAKERS = ["\n", ":", '"', "*"]
# default, lower bound, upper bound, integer required
RULES = {
    "dry": {
        "dry_multiplier": (0.8, 0, 100, False),
        "dry_base": (1.75, 1, 100, False),
        "dry_allowed_length": (15, 0, 1048576, True),
        "dry_penalty_last_n": (-1, -1, 1048576, True),
    },
    "xtc": {
        "xtc_probability": (0.5, 0, 1, False),
        "xtc_threshold": (0.1, 0, 1, False),
    },
    "top_n_sigma": {"top_n_sigma": (1.0, 0, 1000, False)},
    "p_less": {"p_less_exponent": (2.0, 0.01, 100, False)},
    "min_k": {"min_k_tau": (3.0, -1000, 1000, False)},
    "min_p": {"min_p": (0.05, 0, 1, False)},
    "temperature": {"temperature": (1.0, 0, math.inf, False)},
    "top_p": {"top_p": (1.0, 0, 1, False)},
    "top_k": {"top_k": (-1, -1, 1048576, True)},
    "penalties": {
        "repeat_penalty": (1.0, 0.01, 100, False),
        "repeat_last_n": (64, -1, 1048576, True),
        "presence_penalty": (0.0, -100, 100, False),
        "frequency_penalty": (0.0, -100, 100, False),
    },
}
NATIVE_NEUTRAL = {
    "temperature": 1.0, "min_p": 0.0, "top_p": 1.0, "top_k": -1,
    "repetition_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0,
}


@dataclass(frozen=True)
class ChainConfig:
    chain: tuple[str, ...]
    params: dict[str, Any]


def parse_config(raw: Any) -> ChainConfig:
    if not isinstance(raw, str) or len(raw) > 32768:
        raise ValueError(f"{WIRE_KEY} must be a JSON string of at most 32768 characters")
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid {WIRE_KEY} JSON") from exc
    if not isinstance(value, dict) or set(value) != {"version", "chain", "params"}:
        raise ValueError("Sampler config requires exactly version, chain, params")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Unsupported sampler config version; expected 1")
    chain, supplied = value["chain"], value["params"]
    if not isinstance(chain, list) or len(chain) > 32 or any(
        not isinstance(s, str) or s not in RULES for s in chain
    ):
        raise ValueError("Unknown sampler or chain longer than 32 stages")
    if not isinstance(supplied, dict):
        raise ValueError("Sampler params must be an object")
    rules = {k: r for s in chain for k, r in RULES[s].items()}
    special = set()
    if "dry" in chain:
        special.add("dry_sequence_breakers")
    if "p_less" in chain:
        special.add("p_less_norm")
    unknown = supplied.keys() - rules.keys() - special
    if unknown:
        raise ValueError(f"Inactive or unknown sampler parameters: {sorted(unknown)}")
    params: dict[str, Any] = {}
    for key, (default, lo, hi, integer) in rules.items():
        n = supplied.get(key, default)
        if key == "temperature" and isinstance(n, str) and n.lower() in {"inf", "infinity", "+inf", "+infinity", "∞"}:
            params[key] = math.inf
            continue
        try:
            finite = math.isfinite(n) if isinstance(n, (int, float)) else False
        except OverflowError:
            finite = False
        if (isinstance(n, bool) or not isinstance(n, (int, float))
                or not finite or not lo <= n <= hi
                or (integer and int(n) != n)):
            raise ValueError(f"{key} must be {'an integer' if integer else 'a number'} in [{lo}, {hi}]")
        params[key] = int(n) if integer else float(n)
    if "p_less" in chain:
        norm = supplied.get("p_less_norm", False)
        if not isinstance(norm, bool):
            raise ValueError("p_less_norm must be boolean")
        params["p_less_norm"] = norm
    if "dry" in chain:
        breakers = supplied.get("dry_sequence_breakers", DEFAULT_BREAKERS)
        if (not isinstance(breakers, list) or len(breakers) > 32
                or any(not isinstance(s, str) or not s or len(s.encode()) > 40 for s in breakers)):
            raise ValueError("DRY breakers must be up to 32 nonempty strings, each at most 40 UTF-8 bytes")
        params["dry_sequence_breakers"] = tuple(breakers)
    return ChainConfig(tuple(chain), params)


def config_from_sampling_params(params: Any) -> ChainConfig | None:
    extra = params.extra_args or {}
    if WIRE_KEY not in extra:
        return None
    config = parse_config(extra[WIRE_KEY])
    for field, neutral in NATIVE_NEUTRAL.items():
        if getattr(params, field, neutral) != neutral:
            raise ValueError(f"Custom sampler chains require native {field}={neutral}; put it in the chain")
    return config
