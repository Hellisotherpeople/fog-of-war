#!/usr/bin/env python3
"""Verify the native context boundary with all custom stages, including full-history DRY."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def main(output):
    env = dict(line.split("=", 1) for line in
               (Path.home() / "glm53-vllm-client/api.env").read_text().splitlines() if "=" in line)
    headers = {"Authorization": "Bearer " + env["VLLM_API_KEY"], "Content-Type": "application/json"}
    base = "http://127.0.0.1:8800"

    def post(path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=7200) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode()}") from None

    sample = post("/tokenize", {"model": "glm53", "prompt": " x", "add_special_tokens": False})
    config = {"version": 1,
              "chain": ["dry", "top_n_sigma", "p_less", "min_k", "xtc", "min_p", "temperature"],
              "params": {"dry_multiplier": 0.2, "dry_allowed_length": 2, "dry_penalty_last_n": -1,
                         "dry_sequence_breakers": [], "top_n_sigma": 2, "p_less_exponent": 6,
                         "min_k_tau": 0.1, "xtc_probability": 0.1, "xtc_threshold": 0.1,
                         "min_p": 0.1, "temperature": "inf"}}
    body = {"model": "glm53", "prompt": [sample["tokens"][0]] * 1048568,
            "max_tokens": 8, "ignore_eos": True, "add_special_tokens": False,
            "temperature": 1, "min_p": 0, "top_p": 1, "top_k": -1,
            "repetition_penalty": 1, "presence_penalty": 0, "frequency_penalty": 0,
            "vllm_xargs": {"omp_sampler_config": json.dumps(config)}}
    print("Testing 1,048,568 input + 8 output tokens with all custom samplers and full-history DRY.", flush=True)
    started = time.monotonic()
    result = post("/v1/completions", body)
    usage = result["usage"]
    assert usage["prompt_tokens"] == 1048568, usage
    assert usage["completion_tokens"] == 8, usage
    assert usage["total_tokens"] == 1048576, usage
    report = {"passed": True, "usage": usage, "samplers": config,
              "elapsed_seconds": round(time.monotonic() - started, 2),
              "finish_reason": result["choices"][0]["finish_reason"]}
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output)
