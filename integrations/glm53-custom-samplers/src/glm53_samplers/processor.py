"""vLLM 0.30's public batch logits-processor interface; no engine monkeypatches."""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass

import numpy as np
import torch
from vllm.v1.sample.logits_processor import LogitsProcessor, MoveDirectionality

from .config import ChainConfig, DEFAULT_BREAKERS, config_from_sampling_params
from .dry import BreakerResolver, TokenHistory
from .math import apply_chain

logger = logging.getLogger(__name__)


@dataclass
class RequestState:
    config: ChainConfig
    history: TokenHistory | None
    breakers: dict
    rng: random.Random


class OrderedSamplers(LogitsProcessor):
    @classmethod
    def validate_params(cls, params):
        config_from_sampling_params(params)

    def __init__(self, vllm_config, device, is_pin_memory):
        from vllm.version import __version__
        from vllm.tokenizers import cached_tokenizer_from_config

        if __version__.split("+")[0] != "0.30.0":
            raise RuntimeError(f"This sampler build targets vLLM 0.30.0, found {__version__}")
        if vllm_config.speculative_config is not None:
            raise ValueError("Ordered samplers require speculative decoding disabled")
        self.device = torch.device(device)
        self.max_length = vllm_config.model_config.max_model_len
        self.states: dict[int, RequestState] = {}
        self.resolver = BreakerResolver(cached_tokenizer_from_config(vllm_config.model_config),
                                       vllm_config.model_config.get_vocab_size())
        # Decode vocabulary once at startup, not during the first active generation.
        self.resolver.resolve(tuple(DEFAULT_BREAKERS))
        logger.info("GLM53 ordered samplers loaded: XTC, DRY, top_n_sigma, p_less, min_k, temperature (including infinity)")

    def is_argmax_invariant(self):
        # Always run the whole chain BEFORE vLLM's native temperature/top-k/top-p.
        return False

    def update_state(self, update):
        if update is None:
            return
        for index in update.removed:
            self.states.pop(index, None)
        for index, params, prompt, output in update.added:
            self.states.pop(index, None)
            config = config_from_sampling_params(params)
            if config is None:
                continue
            history = (TokenHistory(prompt or [], output, self.max_length)
                       if {"dry", "penalties"}.intersection(config.chain) else None)
            breakers = (self.resolver.resolve(config.params["dry_sequence_breakers"])
                        if "dry" in config.chain else {})
            self.states[index] = RequestState(config, history, breakers, random.Random(params.seed))
        for source, target, direction in update.moved:
            src, dst = self.states.pop(source, None), self.states.pop(target, None)
            if src is not None:
                self.states[target] = src
            if direction == MoveDirectionality.SWAP and dst is not None:
                self.states[source] = dst

    def apply(self, logits):
        for index, state in self.states.items():
            if index >= logits.shape[0]:
                continue
            history = state.history.refresh() if state.history is not None else np.empty(0, dtype=np.int32)
            draws = [state.rng.random() for s in state.config.chain if s == "xtc"]
            apply_chain(logits[index], state.config, history, state.breakers, draws)
        return logits
