#!/usr/bin/env python3
"""Run with the server venv after deployment. Never logs API keys or prompts."""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


def api_request(base, key, payload=None, endpoint="/chat/completions"):
    req = urllib.request.Request(base.rstrip("/") + endpoint,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=1800) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def verify(base, key_file):
    from glm53_samplers.config import NATIVE_NEUTRAL, WIRE_KEY, parse_config
    from glm53_samplers.math import apply_chain
    import numpy as np
    import torch
    from vllm.version import __version__

    if __version__.split("+")[0] != "0.30.0":
        raise RuntimeError("vLLM version changed; revalidate the processor integration first")
    if not torch.cuda.is_available():
        raise RuntimeError("GPU verification requires CUDA")
    key = next(line.split("=", 1)[1].strip().strip("\"'") for line in Path(key_file).read_text().splitlines()
               if line.startswith("VLLM_API_KEY="))
    status, models = api_request(base, key, endpoint="/models")
    if status != 200 or not any(m["id"] == "glm53" and m.get("max_model_len") == 1048576 for m in models["data"]):
        raise RuntimeError("GLM53 model or full context metadata is missing")
    cases = [
        (["xtc"], {"xtc_probability": 1, "xtc_threshold": 0.1}),
        (["dry"], {"dry_multiplier": 0.8, "dry_allowed_length": 2, "dry_sequence_breakers": []}),
        (["top_n_sigma"], {"top_n_sigma": 1}),
        (["p_less"], {"p_less_exponent": 3, "p_less_norm": True}),
        (["min_k"], {"min_k_tau": 3}),
        (["top_n_sigma", "temperature"], {"top_n_sigma": 1, "temperature": 10}),
        (["top_n_sigma", "temperature"], {"top_n_sigma": 1, "temperature": "inf"}),
        (["dry", "top_n_sigma", "xtc", "p_less", "min_k", "temperature"],
         {"dry_allowed_length": 2, "top_n_sigma": 2, "xtc_probability": 0.5, "temperature": "inf"}),
    ]
    results = []
    history = np.array([1, 2, 3, 1, 2], dtype=np.int32)
    for chain, knobs in cases:
        raw = json.dumps({"version": 1, "chain": chain, "params": knobs})
        config = parse_config(raw)
        values = torch.tensor([3.5, 3, 2, 0, -1, -torch.inf])
        reference = apply_chain(values.clone(), config, history, {}, [0] * chain.count("xtc"))
        actual = apply_chain(values.cuda(), config, history, {}, [0] * chain.count("xtc")).cpu()
        torch.testing.assert_close(actual, reference, rtol=2e-5, atol=2e-6)
        payload = {"model": "glm53", "messages": [{"role": "user", "content": "Write a short Python addition function."}],
                   **NATIVE_NEUTRAL, "vllm_xargs": {WIRE_KEY: raw}, "reasoning_effort": "low", "max_tokens": 64}
        started = time.monotonic()
        status, response = api_request(base, key, payload)
        if status != 200 or not response.get("choices") or response.get("usage", {}).get("completion_tokens", 0) == 0:
            raise RuntimeError(f"Custom sampler request failed: {chain}, HTTP {status}: {response}")
        results.append({"chain": chain, "params": knobs, "cuda_matches_cpu": True,
                        "completion_tokens": response["usage"]["completion_tokens"], "seconds": round(time.monotonic() - started, 3)})
    # Unknown xargs are silently ignored by stock vLLM. This must be rejected,
    # proving that this processor is active at the API validation boundary.
    payload["vllm_xargs"][WIRE_KEY] = json.dumps({"version": 999, "chain": [], "params": {}})
    status, response = api_request(base, key, payload)
    if status != 400 or "sampler config version" not in json.dumps(response).lower():
        raise RuntimeError("Server did not reject an invalid config: custom processor may not be loaded")
    return {"passed": True, "vllm": __version__, "context_window": 1048576,
            "invalid_config_rejected": True, "cases": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://192.168.200.207:8000/v1")
    parser.add_argument("--key-file", default="/home/ubuntu/glm53-vllm/api.env")
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.base_url, args.key_file)
    args.result.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(result["cases"]), "result": str(args.result)}))
