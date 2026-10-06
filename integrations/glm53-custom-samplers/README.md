# GLM-5.3 custom samplers for vLLM and oh-my-pi

**Status: deployed and verified on the H200 and in the installed OMP extension.**
Live CUDA, API, OMP coding, temperature, compaction, and the exact native context
boundary all pass. See `artifacts/result.json` for the deployment receipt.

This package targets vLLM **0.30.0** on `alpha-h200`, reached through
`ubuntu@47.47.180.93` and then `ubuntu@192.168.200.207`.
It uses the copied model weights, a 1,048,576-token context setting and an
unlimited-remaining-context output policy. Speculative decoding is disabled.

The H200 configuration uses tensor parallelism 2 and pipeline parallelism 4,
with BF16 KV cache. `VLLM_PP_LAYER_PARTITION=18,20,20,20` keeps each GLM sparse
attention indexer and its dependent layers on the same pipeline stage. Default
even partitioning would split these groups. Prefill batches contain 4,096 tokens;
this bounds temporary memory without truncating the context.

## Implemented

| Stage | Parameters | Behavior |
| --- | --- | --- |
| XTC | `xtc_probability`, `xtc_threshold` | Probabilistically removes high-probability choices except the weakest eligible choice. |
| DRY | `dry_multiplier`, `dry_base`, `dry_allowed_length`, `dry_penalty_last_n` | Penalizes repeated continuations; includes prompt and output history, respects sequence breakers, exempts single-token breakers. `-1` scans the full context. |
| top-n-sigma | `top_n_sigma` | Keeps logits within N population standard deviations of the maximum; masked values are excluded from variance. |
| P-less | `p_less_exponent`, `p_less_norm` | Collision-probability gate with the local generalized exponent and normalized variant. |
| min_k | `min_k_tau` | Weighted raw-logit cliff detection, with the local near-uniform fallback. |
| temperature | Any finite value ≥ 0, or `inf` | Supports values above 2 and exact positive infinity. Infinity makes surviving finite logits equal, preserving excluded tokens. Zero selects the maximum. |

The processor also implements min_p, top_p, top_k and repeat/frequency/presence
penalties so mixed chains execute in exactly the selected order. No inactive
filter is enabled. Ordinary API requests without `omp_sampler_config` continue
using the existing vLLM defaults.

The oh-my-pi adapter uses `vllm_xargs.omp_sampler_config`, a versioned JSON string.
Native vLLM temperature is 1; its other filters and penalties are neutral.
This avoids both double sampling and the OpenAI temperature field's limit.
Infinity is serialized as `"inf"`, never non-standard JSON `Infinity` or `null`.
The saved OMP profile stores it with a `temperature_infinite` boolean.

## Local verification

- Python sampler tests include **1,360 comparisons** with the user's compiled
  `/Users/lain/llama.cpp-samplers-20260916/build/bin/libllama.dylib`.
- Covered: all five requested samplers, chain order, DRY single/multi-token
  breakers, normalized P-less, min_k fallback, masked distributions, temperature
  10/1e6/1e300/infinity, and DRY history extending to the full million-token context.
- Batch-contract tests cover removed/replaced/swapped requests, live output
  history, seeded XTC isolation and rejection of double-applied sampling.
- OMP tests cover wire serialization, inactive knobs, command handlers, persistence
  of infinity, existing router/bias/telemetry code and TypeScript checking.
- All **286 OMP tests** and TypeScript checking pass, including authenticated
  proxy integration and the compaction request path.
- All **eight CUDA/API cases pass**, including every requested sampler,
  temperature 10, infinity, and a mixed chain. Invalid configs receive HTTP 400.
- An actual OMP session used all five custom samplers to read/edit/test a code
  fix (four passing tests), then exercised `/temp 10`, `/temp inf`, and compaction.
  All nine captured generations had neutral native filters and no fixed output
  cap. No llama.cpp `/props` requests occurred. The real saved profile is unchanged.
- The full boundary test passed with **1,048,568 input + 8 output tokens**, all
  five custom samplers, full-history DRY, and infinite temperature. It took
  **260.31 seconds**. See `artifacts/h200-context-boundary.json`.

Logs and receipts are in `artifacts/`. The isolated OMP project and full event
log are in `~/glm53-vllm-client/h200-custom-sampler-check/`. The CPU batch tests
use minimal vLLM interface stubs; GPU/API evidence is recorded separately.

Active server release:
`/home/ubuntu/glm53-vllm/custom-samplers-releases/20261002-041738`.
Local extension backup:
`~/glm53-vllm-client/sampler-backup-20261002-041738`.
The local tunnel on port 8800 now forwards to `192.168.200.207:8000`.

## Deployment

Run in a session allowed to connect by SSH and edit the installed OMP extension:

```sh
python3 /Users/lain/fogofwar/integrations/glm53-custom-samplers/deploy.py
```

The installer checks the extension has not changed since staging, runs its full
test suite, transfers an immutable source release, backs up the server launcher
and configuration, loads one custom logits processor, and restarts vLLM. **The
restart disconnects active generations.** It verifies CUDA/CPU results, successful
HTTP requests for every requested sampler, full context metadata and rejection
of an invalid sampler config. Rejection is necessary: unmodified vLLM would
silently ignore these custom arguments. Failed server verification restores the
original launcher/configuration and restarts the original service.

Only after server validation succeeds does it install the changed OMP files.
Other preexisting extension edits and the user's saved sampler choices are
preserved. No passwords or API keys are embedded in this package.

After successful installation, restart your session:

```sh
omp-glm53 --continue
```

Use `/samplers` to add, remove, reorder and tune the new stages. Direct examples:

```text
/samplers chain dry top_n_sigma xtc temperature
/temp 10
/temp inf
/samplers show
```

This example chooses a chain; it is not applied automatically. All five custom
samplers are available independently. `/temp` enables the temperature stage if
absent. Turning it back to a finite value clears the saved infinity flag.

Compaction bypasses OMP's ordinary request hook, so the existing sampler proxy
also applies the active profile. Keep the proxy enabled (the current profile has
it enabled) for consistent compaction sampling. Telemetry records the custom
chain and knobs; vLLM's logprobs remain raw model probabilities and do not report
full survivor counts. Automatic routing, dynamic temperature, token-bias tools,
and the other unported llama.cpp samplers remain unavailable on this backend.

## Implementation notes and limits

- No vLLM monkeypatches or dependency upgrades. Explicit
  `logits-processors: [glm53_samplers.processor:OrderedSamplers]` activation and a
  release-specific `PYTHONPATH` in the existing launcher.
- Uses the vLLM 0.30 V1 batch processor interface (vLLM selects its V1 runner
  for custom logits processors). Each request owns its history and
  XTC RNG; moving requests in a batch moves that state. XTC is seed-reproducible
  within this implementation, not bit-for-bit RNG-identical to C++ `mt19937`.
- Logit operations run on the existing tensor device. DRY matches CPU token
  histories and transfers sparse penalties. Full-history DRY adds work that
  grows with the history length and repeated sequence length.
- DRY has no hidden history or occurrence cutoff. Extreme exponential penalties
  saturate below float32 overflow to keep at least a usable finite distribution.
  XTC at threshold zero excludes masked tokens from eligibility, preventing an
  all-masked result possible in the local C++ implementation.
- At exact ties, stable token-ID order may differ from llama.cpp's unstable sort.
  Floating-point boundary decisions can differ between CPU and CUDA reductions.
- Infinity means uniform sampling over survivors **at that stage**. Put
  temperature last if you want the final distribution to remain uniform.

References: the user's local `src/llama-sampler.cpp` is the behavioral reference;
the [vLLM 0.30 processor interface](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/v1/sample/logits_processor/interface.py),
[sampler execution order](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/v1/sample/sampler.py),
and [chat request schema](https://github.com/vllm-project/vllm/blob/v0.30.0/vllm/entrypoints/openai/chat_completion/protocol.py)
define the integration.
