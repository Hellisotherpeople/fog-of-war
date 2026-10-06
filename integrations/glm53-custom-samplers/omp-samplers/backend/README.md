# Custom llama.cpp backend

The extension sends sampler settings to llama.cpp; token selection happens in the server. `llama-custom-samplers.patch` contains all existing mink samplers, KL*, the experimental KL-budget sampler, and exact selected-token ranks. It applies to upstream revision `05f2dcfdb` (b11013, 2026-09-16). The patch also uses double precision when accumulating raw probability previews, preserving small tail probabilities for large vocabularies.

```sh
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
git checkout 05f2dcfdb
git apply --check /path/to/omp-samplers/backend/llama-custom-samplers.patch
git apply /path/to/omp-samplers/backend/llama-custom-samplers.patch
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --target llama-server test-sampling -j 8
build/bin/test-sampling
```

Build in a separate checkout if another version is serving a model. Later upstream revisions may require reconciling the patch. Verify sampler names and knob echoes with `LLAMA_URL=http://127.0.0.1:8080 bun run e2e/samplers-live.ts` from the extension directory.

## KL*

API: `samplers: ["kl_opt", "temperature"]`, `kl_opt_lambda: 1`, `kl_opt_global: true`, `temperature: 1000000`. CLI: `--samplers 'kl_opt;temperature' --kl-opt-lambda 1 --temp 1000000`; add `--kl-opt-first-local` for the local variant.

Ported from the local infinite-temperature research implementation in `Downloads/inftemp-repo/code/infinitemp/samplers.py` and `llama.cpp-inftemp/src/llama-sampler.cpp`. The global method minimizes `-lambda log(k) - mean(log p)` over every prefix, retaining the earliest global minimizer. The local variant stops at the first strict increase. The implementation computes the equivalent logit-gap objective; this avoids turning softmax underflow into an artificial probability floor. Masked tokens remain excluded even with `min_keep`.

## KL-budget

API: `samplers: ["min_p", "kl_budget"]`, `min_p: 0.05`, `kl_budget: 0.1`. CLI: `--samplers 'min_p;kl_budget' --min-p 0.05 --kl-budget 0.1`.

For the distribution `p` normalized on the support entering this stage, solve:

```text
maximize H(q)
subject to KL(q || p) <= budget and sum(q) = 1
```

The Lagrangian `H(q) - mu(KL(q||p) - budget)` gives `q_i ∝ p_i^beta`, where `beta = mu/(1+mu)`. Uniform (`beta=0`) is optimal when feasible. Otherwise the constraint is active and the unique solution is between `beta=0` and `beta=1`. With centered logits `z`:

```text
KL(beta) = (beta-1) E_q[z] + log Z(1) - log Z(beta)
d KL / d beta = (beta-1) Var_q(z) <= 0
```

A 32-iteration bisection keeps the feasible endpoint. Double-precision moments avoid underflow in the reference tail; output logits are floats as usual. The unit test checks the KL constraint, entropy monotonicity, the uniform limit, zero budget, cloning, masked tokens, a large logit gap, and the entropy optimum against a dense three-token simplex grid.

This is our constrained-optimization prototype, not a reproduction of [KL-Divergence Guided Temperature Sampling](https://arxiv.org/abs/2306.01286), which uses source relevance to guide temperature. No claim of superior generated-text quality is made. A bound against model probabilities is a coherence proxy, and per-step entropy differs from diversity over complete texts.

## Full-distribution telemetry

When `n_probs > 0`, native and OpenAI-compatible probability entries include:

```json
{"id": 123, "token": "example", "raw_rank": 41, "post_rank": 1, "candidate_count": 40000, "vocab_size": 151936, "entropy_bits": 12.3, "varentropy_bits2": 2.1}
```

`raw_rank` counts strictly greater model logits across the full vocabulary, before any sampler changes. `post_rank` counts strictly greater final logits among the surviving candidates. Both are one-based and assign tied logits the same rank. They are independent of the truncated candidate array. Absent ranks serialize as null.

`candidate_count` counts all finite post-chain logits, including candidates whose softmax probabilities underflow, excluding bans and masks. `vocab_size` is the model's entire vocabulary. Both counts are returned in raw and post capture modes. `entropy_bits` and `varentropy_bits2` are computed with double-precision logit moments across the full distribution for the requested mode, before preview truncation. The raw selected-token probability is also computed over the full vocabulary, even when the sampled token lies outside the preview.

The upstream speculative path does not retain each accepted token's candidate distribution. Probability requests therefore disable speculative and backend sampling for that request; GPU model evaluation remains enabled. Capture-off requests keep normal speculation. Counting raw rank is a linear CPU pass over already available logits, with no extra inference request.

## Local installation and rollback

The active checkout is `/Users/lain/llama.cpp-samplers-20260916`, built into `build`. `/Users/lain/llamacpp-opencode.sh` launches it on port 8080 through the `com.lain.llamacpp-opencode` login service. Commands in `~/.local/bin` select the same custom build.

The model is DavidAU Qwen3.8-27B TURBO Fable Cold Fusion 735-882 NEO CODER MAX, Q6_K with fused MTP. It uses the full 262,144-token native context, Q8 K/V caches for both main and draft models, one slot, four recurrent checkpoints, and no extra RAM prompt cache. All 66 layers are offloaded to Metal. The stable `qwen38-27b-uncensored` alias keeps existing OMP sessions compatible; `qwen38-27b-turbo-fable-q6` is also accepted. The saved sampler profile is unchanged.

The model-specific template `qwen3.8-davidau-omp.jinja` retains the existing merged system/developer messages, tool-call handling, and Qwen reasoning aliases. These fixes are compatible with the new model's embedded template.

The old source, staged/unstaged changes, and `build-width` binary in `/Users/lain/llama.cpp-samplers-20260904` remain unchanged. Its Huihui model is retained for rollback. The unused older `Qwen3.8-27B-Uncensored-Q6_K.gguf` was removed to make space.

Launcher, OMP configuration, source changes, portable patches, model checksums, and validation results are saved under `/Users/lain/llama-backups/upgrade-20260916-230036/`. To restore the previous service and model definition:

```sh
python3 /Users/lain/llama-backups/upgrade-20260916-230036/rollback.py
```

Earlier sampler installation backups remain under `/Users/lain/sampler-backups/20260904/` and `/Users/lain/sampler-backups/width-20260904-224136/`.

## Validation on 2026-09-16

- C++ `test-sampling`, `test-chat`, and `test-chat-template` pass on b11013.
- All 20 live catalog samplers, KL* reference comparisons, KL-budget bounds, exact ranks, full-vocabulary statistics, and native/OpenAI streaming checks pass on the new 248,320-token vocabulary.
- The original sampler changes and saved OMP sampler profile are preserved. The only additional C++ change increases raw probability accumulation precision.
- Direct answers, separate reasoning, tool calls, tool-result history, and the saved sampler profile generate successfully.
- The installed OMP binary passes the extension autoload and KL* integration check, including all per-token rank/width/entropy telemetry.
- The Q6_K download matches SHA-256 `ac011aabe685edbdf542e49351eb6c76c0e5531408f2507f2235ab10931e23a5` at Hugging Face revision `c02caef111a8acf987947f35e1e288aa5450e184`.
- Full-context Metal allocation, including MTP, is about 34.06 GiB against a 37.44 GiB recommended working set. Up to four recurrent checkpoints add about 0.58 GiB of host memory.

## Validation on 2026-09-04

- Extension: 264 tests pass; TypeScript check passes.
- Updated C++ `test-sampling` passes, including KL* reference cases and KL-budget optimization checks.
- All 20 catalog samplers accept their settings and emit candidates on the live Qwen3.8-27B server.
- Live KL* agrees with the reference prefix objective; KL-budget stays within 0, 0.05, 0.1, 0.3, and 1 nat budgets with increasing entropy.
- Raw rank 41 remains exact with `n_probs=2` and a bias forcing that token to final rank 1.
- Full width and entropy remain exact with `n_probs=2`: tested all 151,936 tokens, 64-token uniform support, banned tokens, and probability underflow. Native and OpenAI streams carry the summary fields; probe funnels use full counts.
- Native and OpenAI streaming return rank fields. Real oh-my-pi 18.1.10 runs verify KL*, KL-budget, extension autoloading, and JSONL rank averages.
- Existing live bias, ordinary-token ban, and thinking-budget request checks pass; capture-off requests still use MTP speculation. The bias sweep is a wiring check, not a statistical quality benchmark.

To test the installed omp binary rather than the development dependency, set `OMP_BIN=/path/to/omp` when running `e2e/rank-omp-live.ts` or `e2e/logit-bias-live.ts`. `SAMPLER_METHOD=kl_budget` selects the budget variant in the rank test; `E2E_AUTOLOAD=1` exercises automatic extension discovery.
