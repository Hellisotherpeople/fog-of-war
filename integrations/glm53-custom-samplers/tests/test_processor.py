"""CPU tests of the vLLM 0.30 batch contract, not a substitute for GPU serving tests."""
import importlib
import json
import sys
import types
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace as NS

import pytest
import torch

from glm53_samplers.config import NATIVE_NEUTRAL, WIRE_KEY


@pytest.fixture
def processor(monkeypatch):
    class Direction(Enum):
        UNIDIRECTIONAL = 1
        SWAP = 2

    @dataclass
    class BatchUpdate:
        batch_size: int
        removed: list
        added: list
        moved: list

    class Tokenizer:
        def __len__(self): return 10
        def batch_decode(self, ids, **kwargs): return [str(i[0]) for i in ids]

    # Only the interfaces we consume. No fake inference engine or sampler math.
    modules = {
        "vllm": {}, "vllm.v1": {}, "vllm.v1.sample": {},
        "vllm.v1.sample.logits_processor": {"LogitsProcessor": object, "MoveDirectionality": Direction},
        "vllm.version": {"__version__": "0.30.0"},
        "vllm.tokenizers": {"cached_tokenizer_from_config": lambda _: Tokenizer()},
    }
    for name, members in modules.items():
        mod = types.ModuleType(name)
        mod.__dict__.update(members)
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.delitem(sys.modules, "glm53_samplers.processor", raising=False)
    mod = importlib.import_module("glm53_samplers.processor")
    cfg = NS(speculative_config=None, model_config=NS(max_model_len=1048576, get_vocab_size=lambda: 10))
    obj = mod.OrderedSamplers(cfg, "cpu", False)
    return obj, BatchUpdate, Direction


def params(chain, seed=123, **knobs):
    return NS(**NATIVE_NEUTRAL, seed=seed, extra_args={WIRE_KEY: json.dumps({"version": 1, "chain": chain, "params": knobs})})


def test_disabled_requests_and_batch_moves(processor):
    obj, Update, Direction = processor
    active = params(["temperature"], temperature="inf")
    disabled = NS(extra_args=None)
    obj.update_state(Update(3, [], [(0, active, [], []), (1, disabled, [], []), (2, active, [], [])], []))
    logits = torch.tensor([[3., 2.], [3., 2.], [3., 2.]])
    obj.apply(logits)
    assert logits.tolist() == [[0., 0.], [3., 2.], [0., 0.]]
    obj.update_state(Update(2, [2], [], [(0, 1, Direction.SWAP)]))
    assert set(obj.states) == {1}
    obj.update_state(Update(1, [], [], [(1, 0, Direction.UNIDIRECTIONAL)]))
    assert set(obj.states) == {0}
    obj.update_state(Update(1, [], [(0, disabled, [], [])], []))
    assert obj.states == {}


def test_dry_tracks_generated_history_and_never_leaks(processor):
    obj, Update, _ = processor
    output = []
    p = params(["dry"], dry_allowed_length=2, dry_sequence_breakers=[])
    obj.update_state(Update(2, [], [(0, p, [1, 2, 3, 1], output), (1, p, [4, 5], [])], []))
    output.append(2)
    obj.update_state(None)
    logits = torch.zeros((2, 10))
    obj.apply(logits)
    assert logits[0, 3].item() == pytest.approx(-0.8)
    assert logits[1].tolist() == [0] * 10


def test_seeded_xtc_is_independent_of_other_batch_requests(processor):
    obj, Update, Direction = processor
    p = params(["xtc"], xtc_probability=0.5)
    obj.update_state(Update(2, [], [(0, p, [], []), (1, p, [], [])], []))
    masks = []
    for _ in range(30):
        logits = torch.tensor([[4., 3.9, 3.8, 0], [4., 3.9, 3.8, 0]])
        obj.apply(logits)
        assert torch.equal(logits[0], logits[1])
        masks.append(torch.isfinite(logits[0]).sum().item())
    assert set(masks) == {2, 4}


@pytest.mark.parametrize("field,bad", [("min_p", 0.05), ("temperature", 10), ("top_k", 20), ("repetition_penalty", 2)])
def test_double_sampling_rejected_at_api_boundary(processor, field, bad):
    obj, _, _ = processor
    p = params(["p_less"])
    setattr(p, field, bad)
    with pytest.raises(ValueError, match=field):
        obj.validate_params(p)
