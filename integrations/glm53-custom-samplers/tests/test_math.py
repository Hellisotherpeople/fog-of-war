import ctypes as C
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest
import torch

from glm53_samplers.config import parse_config
from glm53_samplers.dry import TokenHistory, dry_penalties
from glm53_samplers.math import apply_chain


def config(chain, **params):
    return parse_config(json.dumps({"version": 1, "chain": chain, "params": params}))


def run(values, chain, history=(), breakers=None, draws=None, **params):
    return apply_chain(torch.tensor(values, dtype=torch.float32), config(chain, **params),
        np.array(history, dtype=np.int32), breakers or {}, draws or [0.0] * chain.count("xtc")).numpy()


class Token(C.Structure):
    _fields_ = [("id", C.c_int32), ("logit", C.c_float), ("p", C.c_float)]


class Candidates(C.Structure):
    _fields_ = [("data", C.POINTER(Token)), ("size", C.c_size_t), ("selected", C.c_int64), ("sorted", C.c_bool)]


@pytest.fixture(scope="module")
def llama():
    path = os.environ.get("LLAMA_SAMPLER_LIBRARY")
    if not path:
        pytest.skip("Set LLAMA_SAMPLER_LIBRARY for compiled llama.cpp parity tests")
    lib = C.CDLL(path)
    signatures = {
        "top_n_sigma": [C.c_float], "p_less": [C.c_float, C.c_bool, C.c_size_t],
        "min_k": [C.c_float, C.c_size_t], "xtc": [C.c_float, C.c_float, C.c_size_t, C.c_uint32],
        "temp": [C.c_float], "min_p": [C.c_float, C.c_size_t],
    }
    for name, args in signatures.items():
        fn = getattr(lib, "llama_sampler_init_" + name)
        fn.argtypes, fn.restype = args, C.c_void_p
    lib.llama_sampler_apply.argtypes = [C.c_void_p, C.POINTER(Candidates)]
    lib.llama_sampler_free.argtypes = [C.c_void_p]
    lib.llama_sampler_accept.argtypes = [C.c_void_p, C.c_int32]
    bridge = os.environ.get("LLAMA_DRY_BRIDGE")
    if bridge:
        lib.bridge = C.CDLL(bridge)
        lib.bridge.test_dry_init.argtypes = [C.c_float, C.c_float, C.c_int, C.c_int, C.POINTER(C.c_int), C.POINTER(C.c_int), C.c_int]
        lib.bridge.test_dry_init.restype = C.c_void_p
    return lib


def reference(lib, values, stages, history=()):
    arr = (Token * len(values))(*(Token(i, float(v), 0) for i, v in enumerate(values)))
    candidates = Candidates(arr, len(values), -1, False)
    for name, args in stages:
        if name == "dry":
            sampler = lib.bridge.test_dry_init(*args)
        else:
            sampler = getattr(lib, "llama_sampler_init_" + name)(*args)
        try:
            for token in history:
                lib.llama_sampler_accept(sampler, int(token))
            lib.llama_sampler_apply(sampler, C.byref(candidates))
        finally:
            lib.llama_sampler_free(sampler)
    result = np.full(len(values), -np.inf, dtype=np.float32)
    for i in range(candidates.size):
        item = candidates.data[i]
        result[item.id] = item.logit
    return result


@pytest.mark.parametrize("name,args,params", [
    ("top_n_sigma", [1.3], {"top_n_sigma": 1.3}),
    ("min_k", [3, 1], {"min_k_tau": 3}),
    ("min_k", [0, 1], {"min_k_tau": 0}),
    ("p_less", [2, False, 1], {"p_less_exponent": 2}),
    ("p_less", [3, True, 1], {"p_less_exponent": 3, "p_less_norm": True}),
    ("p_less", [0.5, False, 1], {"p_less_exponent": 0.5}),
    ("xtc", [1, 0.05, 1, 1], {"xtc_probability": 1, "xtc_threshold": 0.05}),
    ("xtc", [0, 0.1, 1, 1], {"xtc_probability": 0, "xtc_threshold": 0.1}),
    ("min_p", [0.1, 1], {"min_p": 0.1}),
    ("temp", [10], {"temperature": 10}),
])
def test_matches_compiled_llama(llama, name, args, params):
    rng = np.random.default_rng(4321)
    for size in [2, 3, 19, 257]:
        for _ in range(20):
            values = rng.normal(0, 2, size).astype(np.float32)
            values[rng.random(size) < 0.15] = -np.inf
            values[0] = 1.2345
            expected = reference(llama, values, [(name, args)])
            actual = run(values, ["temperature" if name == "temp" else name], **params)
            np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=2e-6)


def test_order_and_mask_count_match_llama(llama):
    rng = np.random.default_rng(2)
    for _ in range(80):
        values = rng.normal(0, 2, 103).astype(np.float32)
        chain = ["top_n_sigma", "p_less", "xtc", "temperature"]
        params = dict(top_n_sigma=2, p_less_exponent=3, p_less_norm=True,
                      xtc_probability=1, xtc_threshold=0.1, temperature=10)
        expected = reference(llama, values, [("top_n_sigma", [2]), ("p_less", [3, True, 1]),
                                             ("xtc", [1, 0.1, 1, 1]), ("temp", [10])])
        np.testing.assert_allclose(run(values, chain, **params), expected, rtol=2e-5, atol=2e-6)


@pytest.mark.parametrize("allowed", [0, 1, 2, 5])
@pytest.mark.parametrize("base", [1, 1.75])
def test_dry_matches_compiled_llama(llama, allowed, base):
    if not hasattr(llama, "bridge"):
        pytest.skip("Set LLAMA_DRY_BRIDGE")
    rng = np.random.default_rng(5)
    sequences = [[7], [3, 4]]
    flattened = (C.c_int * 3)(7, 3, 4)
    sizes = (C.c_int * 2)(1, 2)
    breakers = {7: ((),), 3: ((4,),)}
    for _ in range(60):
        history = rng.integers(0, 8, 70).tolist()
        values = rng.normal(0, 1, 8).astype(np.float32)
        params = dict(dry_multiplier=0.8, dry_base=base, dry_allowed_length=allowed, dry_penalty_last_n=64,
                      dry_sequence_breakers=[])
        expected = reference(llama, values, [("dry", [0.8, base, allowed, 64, flattened, sizes, 2])], history)
        np.testing.assert_allclose(run(values, ["dry"], history=history, breakers=breakers, **params),
                                   expected, rtol=2e-5, atol=2e-6)


@pytest.mark.parametrize("temperature", [0, 0.7, 2, 10, 1e6, 1e300, "inf"])
def test_temperature_preserves_exclusions(temperature):
    result = run([4, 3, 0, -np.inf], ["top_n_sigma", "temperature"],
                 top_n_sigma=1, temperature=temperature)
    assert not np.isnan(result).any()
    assert np.isneginf(result[2:]).all()
    if temperature == "inf":
        np.testing.assert_equal(result[:2], [0, 0])
        np.testing.assert_allclose(torch.tensor(result).softmax(0).numpy(), [0.5, 0.5, 0, 0])


def test_temperature_order_changes_distribution():
    # P-less is probability-dependent: ordering must be observable.
    a = run([3, 2, 1, 0], ["p_less", "temperature"], temperature=10)
    b = run([3, 2, 1, 0], ["temperature", "p_less"], temperature=10)
    assert not np.array_equal(np.isfinite(a), np.isfinite(b))


def test_uniform_min_k_fallback_and_masked_distribution():
    np.testing.assert_equal(run([1, 1, 1], ["min_k"]), [1, 1, 1])
    result = run([1, 1, -np.inf], ["min_k", "temperature"], temperature="inf")
    np.testing.assert_equal(result, [0, 0, -np.inf])


def test_xtc_zero_threshold_keeps_a_finite_candidate():
    result = run([3, 2, -np.inf], ["xtc"], xtc_probability=1, xtc_threshold=0)
    np.testing.assert_equal(result, [-np.inf, 2, -np.inf])


def test_full_context_dry_uses_early_history():
    history = np.full(1048570, 9, dtype=np.int32)
    history[:4] = [1, 2, 3, 4]
    history[-3:] = [1, 2, 3]
    cfg = config(["dry"], dry_allowed_length=3, dry_penalty_last_n=-1)
    ids, values = dry_penalties(history, cfg.params, {})
    assert dict(zip(ids, values))[4] == pytest.approx(0.8)
    cfg.params["dry_penalty_last_n"] = 64
    ids, _ = dry_penalties(history, cfg.params, {})
    assert 4 not in ids


def test_token_history_observes_append_and_rewind():
    output = [3]
    history = TokenHistory([1, 2], output, 1048576)
    np.testing.assert_equal(history.refresh(), [1, 2, 3])
    output.append(4)
    np.testing.assert_equal(history.refresh(), [1, 2, 3, 4])
    output.clear()
    np.testing.assert_equal(history.refresh(), [1, 2])


@pytest.mark.parametrize("raw", ["null", "{}", '{"version":1,"chain":["unknown"],"params":{}}',
    '{"version":1,"chain":["temperature"],"params":{"temperature":-1}}',
    '{"version":1,"chain":["temperature"],"params":{"temperature":NaN}}',
    '{"version":1,"chain":["min_k"],"params":{"top_k":3}}'])
def test_invalid_params_rejected(raw):
    with pytest.raises(ValueError):
        parse_config(raw)
