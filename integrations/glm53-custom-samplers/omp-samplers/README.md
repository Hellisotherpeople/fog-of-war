# omp-samplers

Per-prompt sampler control, model-selected sampling, per-token logit bias, and per-token sampler telemetry for [oh-my-pi](https://github.com/can1357/oh-my-pi) with a local llama.cpp server.

You can still build a sampler chain by hand, tune every knob, and save presets. Auto mode adds a sampling router: before omp asks the model to answer, the same model makes an internal schema-constrained tool call that chooses, orders, and configures the samplers for that prompt. The validated choice is applied to the answer from its first token onward.

`/logit-bias` works one level down, on individual tokens: any token in the vocabulary can be pushed up, pushed down, or banned outright, at any offset you like. Because the interesting tokens are usually the special ones and their ids differ per model, it reads the model's own vocabulary and finds them for you. `/think-less` is the reason it exists: upweight the model's end-of-thinking token and a reasoning model stops padding its scratchpad.

`/sampler-scope` then shows what that chain actually did: how many candidates survived truncation at each step, how the distribution looked before and after the samplers touched it, and which sampler in the chain did the cutting.

![omp-samplers demo](assets/demo.gif)

## How it works

Manual mode subscribes to omp's `before_provider_request` event and writes the active `samplers` array and knob fields into the outgoing request body. llama.cpp rebuilds its sampler stack for that request.

Auto mode adds a routing prelude to the normal agent loop:

1. `before_agent_start` quickly activates the internal `route_samplers` tool and initializes routing state; it never waits for a model call.
2. The first provider request contains only the static sampler guidance, an extension-authored envelope holding the current task as inert JSON data, and that one forced tool. The raw task is never presented as an instruction to answer during routing; the normal agent context remains intact for the answer.
3. The compact tool schema contains every sampler ID and positional values. Its array order is execution order; a compact catalog maps those values to each sampler's knobs, and the local validator enforces types, bounds, and ownership. An optional one-sentence rationale can be removed from the schema entirely.
4. The tool validates and stores the route, then omp's normal tool follow-up becomes the answer request. Every token of that answer—and every later tool follow-up in the run—uses the selected route.

If the model somehow returns an invalid schema payload, generation continues with the saved manual profile as a fallback.

### Why routing is a separate request

llama.cpp fixes the sampler stack when an HTTP generation request starts. It cannot generate configuration tokens and then replace its own sampler stack halfway through that same request through the OpenAI-compatible API. Doing that literally would require a new stateful protocol and server-side llama.cpp changes.

The two-request design preserves the intended behavior: the structured route is generated first, then every answer token uses it. Both requests now run inside omp's normal agent loop, so routing is controlled by the agent's own cancellation lifecycle and cannot hit omp's 30-second extension-handler deadline.

## Requirements

Use oh-my-pi with a local llama.cpp provider configured as `api: openai-completions`. Auto routing is tested with omp 17.0.5.

The standard names `dry`, `top_k`, `top_p`, `min_p`, `typ_p`, `top_n_sigma`, `xtc`, `penalties`, and `temperature` work on recent stock llama.cpp builds. `hill`, `top_h`, `p_less`, `min_k`, `geo_mean`, `otsu`, `kneedle`, `top_gap`, and `robust_z` require a build that implements them, such as mink.

## Install

Clone the repository into the omp user extensions directory, then restart omp:

```sh
git clone https://github.com/Hellisotherpeople/omp-samplers.git ~/.omp/agent/extensions/omp-samplers
```

You can also load it for one run with `omp --extension /path/to/omp-samplers` or add it to the `extensions` list in `~/.omp/agent/config.yml`.

## Usage

Open `/samplers` for the interactive menu. The footer reports whether the override is off, manual, or auto and displays the latest selected route. `/samplers show` also reports the optional rationale plus routing latency and token/cache counters; every selection is written to omp's debug log.

Useful direct commands:

```text
/samplers auto          enable model-selected routing
/samplers manual        use the saved manual profile
/samplers show          show mode, route rationale, fallback, and storage path
/samplers rationale off omit rationale generation for lower latency
/samplers-auto          toggle auto/manual
/samplers-auto on|off   set auto/manual explicitly
/samplers-rationale     toggle rationale generation
/samplers-rationale on|off
/sampler-preset coding  apply a preset and switch to manual mode
/temp 0.7               set manual temperature and switch to manual mode
/samplers-off           toggle all request overrides
/sampler-scope          live telemetry and visualizations (see below)
/sampler-probe          measure a distribution before and after the chain
/sampler-preset kl-star select KL* followed by near-uniform sampling
/sampler-scope ranks    selected-token ranks and the generation average
/logit-bias             per-token logit bias (see below)
/think-less             upweight the end-of-thinking token
/think-cap              hard-limit reasoning length
```

Editing the chain, tuning a knob, applying a preset, or using `/temp` switches to manual mode. Auto mode itself persists in `sampler-profile.json`, so it survives restarts.

For a non-interactive run, `OMP_SAMPLERS_AUTO=1` forces auto mode without changing the stored profile. The extension imposes no independent routing deadline; routing uses omp's normal agent request lifecycle.

## KL* sampling

`kl_opt` implements the infinite-temperature paper's admission rule. It sorts the incoming logits, evaluates every prefix, and keeps the prefix minimizing

```text
J(k) = -lambda * log(k) - mean(log(p[1:k]))
```

At `kl_opt_lambda=1`, this is exactly `KL(Uniform(top-k) || p)`. `kl_opt_global=true` selects the global minimum, including a later minimum after an initial rise. Set it to `false` for the paper's conservative first-local-minimum variant. Lambda controls the reward for breadth; 1 is the parameter-free rule. Both controls are available in `/samplers` and to the auto router.

`/sampler-preset kl-star` uses `kl_opt → temperature`, lambda 1, global search, and temperature 1,000,000, matching the research's practical approximation to an infinite-temperature draw. It is near-uniform, not mathematically exact uniform sampling. `/sampler-preset kl-star-local` chooses the local variant. A finite temperature can be set afterward with `/temp`.

Order matters: KL* must see the distribution **before** the high final temperature. Earlier penalties and gates change the distribution/candidates it optimizes over. The preset includes only KL* and temperature; separately configured logit bias, grammar, and thinking budgets still apply.

KL* needs the updated custom server. The complete backend patch and build instructions are in [backend/README.md](backend/README.md). Stock llama.cpp can silently drop unknown sampler names, so check `/sampler-scope caps` when connecting to another build.

## Experimental alternative: KL-budget

Try `/sampler-preset kl-budget` alongside KL*. It uses `min_p=0.05` to admit plausible candidates, then chooses the **maximum-entropy distribution on that support** subject to `KL(q || p_support) <= 0.1` nats. Unlike a uniform draw, it retains relative preferences when flattening further would exceed the budget. It becomes uniform when that is feasible.

The solver uses `q_i ∝ p_i^beta` and finds the smallest feasible `beta` in `[0,1]` by bisection. Budget 0 leaves the incoming probabilities unchanged; higher budgets allow more flattening. It neither changes candidate order nor revives banned tokens. It maximizes entropy at each position, which is not a guarantee of semantic coherence or diversity across whole outputs. This is an experimental candidate, not an empirically established improvement over KL*.

| Preset | Chain | Settings |
| --- | --- | --- |
| `kl-budget` | `min_p → kl_budget` | min-p 0.05, budget 0.1 nats |
| `kl-budget-creative` | `dry → min_p → kl_budget` | min-p 0.02, budget 0.3 nats, DRY multiplier 0.8 |

Tune **KL budget (nats)** through `/samplers`. Keep `kl_budget` last: subsequent temperature, penalties, or truncation would invalidate the bound. The auto router enforces this order. The bound is relative to the **renormalized distribution entering this stage**, after earlier penalties, bias, grammar, and admission; it does not include the probability mass removed by min-p or earlier gates. The explicit min-p gate also keeps the solver cheap. Compare output quality and the raw-rank averages on the same tasks before choosing a default.

## Selected-token rank

Enable `/sampler-scope capture on`. The live widget and footer show the average selected-token rank, and these commands inspect it:

```text
/sampler-scope ranks       average and the last 100 per-step ranks
/sampler-scope report      full generation statistics
/sampler-scope inspect     inspect a token and its candidates
/sampler-scope stats       compare captured configurations
/sampler-scope jsonl on    save all per-step ranks and generation summaries
```

**Raw model rank** is `1 + count(logit > selected_token_logit)` across the full vocabulary, before bias, penalties, grammar, truncation, and temperature. Rank 1 means most likely; ranks 4 and 6 average to 5. Equal logits share a rank. This is the primary measure of how far your sampler moves the chosen token from the model's preference. **Post-chain rank** measures the choice within the final sampling distribution instead.

The updated server reports raw rank independently of `n_probs`, in both raw and post capture modes. A token can therefore have raw rank 603 with `n_probs=20`, even when its final rank is 1. There are no extra inference requests. On older servers, only ranks visible in the captured distribution are available. Missing ranks are excluded, coverage is shown, and incomplete means are labeled partial. Post-chain ranks are never presented as raw ranks.

Session averages weight individual tokens and keep different models, knob values, capture modes, and routing/answer requests separate. JSONL contains `tokens[].rawRank`, `tokens[].postRank`, and `summary.rawRank` / `summary.postRank` with `stats.mean`, `known`, and `total`. Files live under `~/.omp/agent/sampler-scope/` (or `$PI_CODING_AGENT_DIR/sampler-scope/`).

Probability capture uses ordinary CPU sampling and disables speculative decoding for that request: upstream's speculative verification does not retain each token's candidate distribution. Inference still uses the GPU. `/sampler-scope capture off` restores normal speculative/backend sampling eligibility. Measuring ranks therefore changes throughput; it does not add a second model pass.

## Router behavior

The router is deliberately conservative about structured output:

- It must choose between one and eight unique samplers.
- Sampler order and configuration are emitted together, preventing knobs from being attached to the wrong sampler.
- Numeric choices are schema-bounded; manual mode remains available for experiments outside those bounds.
- The router request itself uses greedy `top_k=1 → temperature=0` sampling and has thinking disabled. A route cannot apply to the tokens that generate that same route.
- User text is treated as classification input, not as authority to disable the schema or skip routing.

Auto mode adds one model inference and its latency to each top-level prompt. The internal tool turn reports the selected route, while the footer and `/samplers show` retain it afterward. Turning rationale off removes that field from both the provider schema and generated output; it saves decoding time, though the sampler configuration itself still has to be generated.

### Prompt caching and overhead

The routing request keeps a small, invariant instruction prefix and only the current user turn, while the following answer request restores the normal agent context. Both use omp's normal conversation cache key, and routing explicitly sends llama.cpp's `cache_prompt: true`, allowing recent llama.cpp/mink servers to retain both alternating prefixes in slot or host memory.

The routing request exposes only one compact tool, and its schema avoids a separate object grammar for every sampler; one compact catalog documents positional knob order. Thinking is disabled, routing uses a conservative fixed distribution, output is capped at 512 tokens with rationale or 384 without it, and one route is reused for every tool follow-up in the agent run. The unavoidable remaining cost is the second model decode: schema-constrained selection cannot be free while the LLM itself remains the router.

## Logit bias and thinking less

`logit_bias` on a llama.cpp request adds a fixed offset to a token's logit. Any token qualifies — a word, a fragment, a raw id, a special token. It has one very good use: a reasoning model that will not stop reasoning has exactly one token standing between it and an answer, and you can put a thumb on it.

```text
/think-less             pick a strength interactively
/think-less firm        apply a named level
/think-less 4.5         apply a raw logit offset
/think-less off         stop biasing it

/think-cap 128          hard limit: 128 tokens of reasoning, then force the close tag
/think-cap 1            no reasoning at all
/think-cap off          no limit
```

Two different tools, and the difference matters. `/think-less` makes the close tag *more likely*; `/think-cap` makes the block *end*. Reach for the cap when you want a guarantee, and for the bias when you want the model to still decide.

That is the whole feature for most people. `/logit-bias` is the general form underneath it.

### Why a big bias backfires, and what to use instead

A bias is fixed for the whole request. There is no way to say "count this one only the first time", so a bias large enough to guarantee an early close is also large enough to keep winning *after* the block has closed:

```text
/logit-bias set </think> 100
→ content: "</think></think></think></think></think>…"   and no answer, ever
```

Measured on Qwen3.8-27B: at `+100` the close tag was emitted 24 times in one turn and the answer never arrived. Adding a cap does not repair this — the tag wins at the very first step, the block ends immediately, and from then on the reasoning budget is in its passthrough state while the bias still dominates. The fix is to lower the bias; a cap is what you use *instead* of an extreme one.

The extension will not stop you setting `+100` — it is your logit — but it says what will happen when you set it, and if a turn does come back with the tag repeated it says so once rather than leaving you to wonder why the model stopped answering.

`/think-cap` has no such failure mode. llama.cpp's reasoning-budget sampler counts tokens inside the block and, at the budget, forces the close sequence by driving every other logit to negative infinity — exactly once, then it reverts to passthrough. That "once, then stop" is the thing a static bias cannot express. Measured with greedy sampling on a fixed prompt:

| cap | off | 1 | 2 | 4 | 8 | 32 |
| --- | --- | --- | --- | --- | --- | --- |
| completion tokens | 44 | 4 | 5 | 7 | 11 | 35 |
| reasoning chars | 123 | 0 | 3 | 14 | 23 | 103 |

Every one of those still answered `9` correctly. Note the first two columns: **a cap of 0 is a no-op**, byte-identical to no cap, because of how llama.cpp arms the sampler. `1` is the value that means "do not reason". `/think-cap 0` is refused with that explanation rather than accepted and quietly ignored.

Over the OpenAI-compatible endpoint the wire field is `thinking_budget_tokens`, and the server derives the start and end tags from the model's own chat template, so nothing has to be told which tags to look for. A build without the reasoning-budget sampler will accept the field and ignore it; `/think-cap` warns when `/props` gives no sign of support.

### Finding the special tokens

Bias is applied by token id, and ids are model-specific. For an ordinary word you can just type it and the server is asked; for the special tokens there is nothing to type, so the vocabulary is read up front. Two sources are used, best first:

| Tier | Source | Coverage |
| --- | --- | --- |
| `gguf` | `tokenizer.ggml.tokens` and `tokenizer.ggml.token_type` in the model file `/props` names | Exact and complete: every token the converter marked CONTROL, USER_DEFINED or UNKNOWN, with its id. |
| `probe` | Candidates from the chat template, `bos_token`, `eos_token` and a builtin per-family list, each confirmed with `/tokenize` | Works against a server whose model file is not readable, but only finds tokens it thought to ask about. |

The gguf tier reads only the metadata block at the head of the file, never the tensors, and skips the merge list without materializing it. Before it is trusted, a handful of the ids it found are re-tokenized against the live server: a `model_path` can be stale or point at a sibling quantization, and biasing an id from the wrong file would silently hit an unrelated token. On a mismatch it falls back to probing.

Results are cached in `sampler-tokens.json`, keyed by model alias and vocabulary size. That matters for correctness rather than speed: a request is stamped synchronously, so without a warm cache the first turn of a session would go out unbiased. When the cache is cold, the first turn waits up to three seconds for detection and then proceeds either way.

`/logit-bias tokens` prints what was found, grouped by role, end-of-thinking first:

```text
33 special token(s) from gguf · qwen38-27b-uncensored · n_vocab 248320
think_close:
  </think>  id 248069  [+4]  user_defined (merges as text)
think_open:
  <think>  id 248068  user_defined (merges as text)
eot:
  <|im_end|>  id 248046  control
tool_call_start:
  <tool_call>  id 248058  user_defined
…
```

"merges as text" is worth knowing about. `parse_special` is the usual test for whether a string is a special token, and on Qwen3 it fails: `<think>` and `</think>` are USER_DEFINED, so the tokenizer merges them whether special parsing is on or not, and the check reports them as ordinary text. Detection reports the flag rather than filtering on it.

### Any token, not just the special ones

A reference that is not a detected special token and not a `#<id>` is tokenized as literal text. One token, and it is biased and remembered:

```text
/logit-bias set " delve" -5      an ordinary word
/logit-bias ban Certainly        never open with it
/logit-bias set #78926 -5        the same thing by id
```

The quotes matter. On a BPE vocabulary the leading space belongs to the token: on Qwen3.8, `" delve"` is one token (78926) while `delve` is two (`del` + `ve`). Quoting is the only way to say which one you mean, and an unquoted word that turns out to be several tokens gets told so, with the leading-space form suggested if that one is single:

```text
> /logit-bias set delve -5
"delve" is 2 tokens, not one: "del"=9302 "ve"=571. Note that " delve" with a
leading space is a single token (id 78926); quote it to keep the space:
`/logit-bias set " delve" -5`. Bias one of them with `/logit-bias set #<id>
<bias>`, or all of them with `/logit-bias parts delve <bias>`.
```

`/logit-bias tokenize <text>` shows the breakdown for anything, whether or not you intend to bias it. `/logit-bias parts <text> <bias>` biases every token a string is made of — the same thing llama.cpp does with a string in `logit_bias`, and the same shape of suppression `presence_penalty` applies to everything, but as an explicit verb rather than a surprise. Each piece becomes its own entry, so the listing shows exactly what is biased and any one of them can be removed alone.

Words you add are stored by their text and folded into the token set, so they resolve synchronously on later requests and survive a `/logit-bias scan`. They are listed under "added by you", apart from the vocabulary's own inventory.

### Choosing a strength

llama.cpp inserts the bias sampler at the very front of the chain, so the offset lands on raw logits — before `dry`, before every truncation gate, before temperature. Two things follow.

First, a modest bias mostly decides whether a token *survives* truncation. It does not have to beat the model's preferred continuation outright; it only has to stay in the candidate set often enough to be chosen. This is why biasing the end-of-thinking token works at all rather than needing an overwhelming offset.

Second, because temperature is applied last, the same offset is worth less as temperature rises: the odds multiplier is `exp(bias / T)`. A `+4` that is mild on a temp-10 creative chain is overwhelming on a temp-0.3 coding chain. `/logit-bias show` reports the multiplier for the current chain.

Measured on Qwen3.8-27B at temp 10 with `hill` q=10, three prompts per level, median tokens inside the reasoning block:

| bias | 0 | +1 | +2 | +3 | +5 | +8 |
| --- | --- | --- | --- | --- | --- | --- |
| reasoning tokens | 165 | 165 | 160 | 103 | 91 | 71 |

So `+1` is indistinguishable from nothing, the curve bends between `+2` and `+3`, and past `+8` it flattens out as the block starts closing almost immediately. The bundled levels — `nudge` +2, `firm` +4, `hard` +6, `skip` +12 — come from that curve and do not transfer to a different model or a different final temperature.

`/logit-bias measure` re-runs that sweep against the model and chain you are actually using. Each level is one `/completion` that stops at the close tag, so `tokens_predicted` is exactly the length of the reasoning block, and the shared prompt prefix means only the decode is paid for:

```text
Reasoning length vs bias on </think> (id 248069)
chain: dry → hill(order=10) → xtc(probability=0.5,threshold=0.1) → temperature(temperature=10)

      0   165 tok ████████████████████████████
     +2   160 tok ███████████████████████████ (−3%)
     +4   103 tok █████████████████ (−38%)
     +6    91 tok ███████████████ (−45%)
    +12    28 tok █████ (−83%)
```

### The general commands

```text
/logit-bias                    open the menu
/logit-bias tokens [all]       list detected special tokens
/logit-bias tokenize <text>    show what a string is made of
/logit-bias scan               re-detect and refresh the cache
/logit-bias set </think> 4     bias by token text
/logit-bias set think_close 4  bias by role
/logit-bias set #248069 4      bias by raw id
/logit-bias set " delve" -5    bias an ordinary word (quote to keep the space)
/logit-bias parts <text> -2    bias every token the text is made of
/logit-bias ban <|box_start|>  never sample it (-infinity)
/logit-bias clear [token]      remove one bias, or all of them
/logit-bias measure [levels] [prompt]
/logit-bias on | off
/think-cap <tokens|off>        hard limit on reasoning length
```

Bias values are not clamped. Any finite offset is accepted, including `1e6`, because a bias is a raw logit offset and quietly capping it would misrepresent what the model is being told. The only rejected numbers are ones that cannot be sent: `NaN` and `+Infinity` serialize to JSON `null`, which llama.cpp discards without a word, so a "force this token" has to be spelled as a large finite number. Negative infinity does have a wire encoding (`false`), which is what `ban` produces.

Biases are stored by token *text*, not by id, so a profile keeps meaning across models: `</think>` is `</think>` everywhere it exists, and so is `" delve"`. A stored key that the current model has no token for is reported as unresolved and simply not sent, rather than being guessed at. Raw ids are checked against `n_vocab` first, because llama.cpp discards an out-of-range id without an error. A reference carrying whitespace is only ever matched exactly, never trimmed, since trimming it would land on a different token.

Bias is independent of the sampler override, with its own switch: `/samplers-off` plus a `/think-less` is a reasonable thing to want. It does not apply to the routing request in auto mode, which stays greedy and unperturbed. `logit_bias` already on an outgoing request is merged rather than replaced.

An applied bias cannot normally be read back: `/slots` serializes a slot's parameters in a short form that omits `logit_bias` unless the server was started with `LLAMA_SERVER_SLOTS_DEBUG` set. With that set, differences appear as debug hints for slots with a matching sampler chain. Slots can describe previous requests or other clients, so these hints do not prove a bias was ignored. An absent field is not evidence either way and no check is run.

One thing this deliberately does not do is pass strings to `logit_bias`. llama.cpp accepts them, but tokenizes them with `parse_special` off, so `"</think>"` becomes six ordinary text tokens and biases each one — quietly doing something else entirely. Everything here resolves to integer ids first.

### Models without a close token

Not every reasoning model has a single token to bias. gpt-oss leaves its analysis channel with `<|end|>` followed by a new header, so there is nothing to upweight; `/think-less` says so instead of biasing something arbitrary. `/think-cap` is the answer for those models: it works off the tags the server took from the chat template, so it does not need a single-token close tag at all.

## Telemetry and visualization

`/sampler-scope` measures what the chain is actually doing, token by token, and `/sampler-probe` shows one distribution before and after the samplers touch it.

### What gets measured

| Signal | Source | Cost |
| --- | --- | --- |
| Candidates allowed at each step (truncation width) | server `candidate_count`, counted across all surviving logits | no extra inference |
| Post-chain probabilities, sampled token, its rank | same | free |
| Full entropy and varentropy | server `entropy_bits` / `varentropy_bits2`, over the full reported distribution | no extra inference |
| Forced-step rate and preview clipping rate | derived from full counts and preview size | free |
| tok/s, TTFT, inter-token gaps, prompt-cache hit rate | `timings_per_token` + `/slots` | free |
| Current or previous configuration of a server slot | `/slots` (not correlated to our request) | free |
| Samplers missing from a request's applied chain | that response's `generation_settings.samplers`, when available | free |
| Raw pre-sampler distribution at a position | teacher-forced probe | one decode step |
| Survivors after each individual sampler in the chain | teacher-forced probe | one decode step per stage |

Width is the number of tokens still admitted after the chain. The custom server counts every finite surviving logit before limiting the candidate preview, so a preview of 20 can report a width of 40,000 or the entire vocabulary. Banned tokens do not count; finite logits whose probabilities underflow still count. `vocab_size` gives the full model vocabulary as a reference. Width does not measure how evenly probability is spread: entropy describes that separately.

Full counts are available in both raw and post capture modes. Entropy and varentropy describe the selected mode's complete distribution. The widget shows current width, mean, median, p90, maximum, and vocabulary size. JSONL schema version 2 records exact per-token `w`, `vocabSize`, entropy, and a separate `previewCount`. Older capped captures cannot be reconstructed; unknown widths and incomplete entropy measurements are excluded from aggregates and measurement coverage is shown.

### Why there is a proxy

llama.cpp will happily return per-token probabilities, but omp's OpenAI-compatible parser models only the fields it needs and drops `logprobs` before any extension can see it. `after_provider_response` carries status and headers, not the body.

So `capture` starts a loopback reverse proxy in front of llama-server and re-points the provider's `baseUrl` at it. Bytes are forwarded verbatim in both directions; a copy of the response stream is parsed for telemetry. If the redirect cannot be verified the proxy is rolled back and the session keeps talking to llama-server directly. Recording hooks are individually sandboxed, so a telemetry bug cannot fail a request.

Capture is off by default. Turn it on with `/sampler-scope capture on`; the setting persists.

### Before and after

One request can report probabilities in exactly one flavor — raw model logits *or* the post-chain survivors — so measuring both sides of the same position takes two evaluations. The probe teacher-forces a token sequence and re-asks the server one step at a time:

```
Step #4 · sampled ·every (raw rank 3)
width 3 · kept 23.0% of raw mass · H 1.97 → 1.54 bits · KL 2.13 bits · top candidate dropped

dry         ██████████████████████ 151936+ (no history)
hill        ███                          5 −151931
xtc         ██                           3 −2
temperature ██                           3 ·

rank token           p_raw                 p_post
   1 ·the           0.4100 ██████████████  ✂ cut
   2 ·a             0.1900 ██████▌         ✂ cut
▶  3 ·every         0.1100 ███▊            0.4400 ██████████████
   4 ·some          0.0700 ██▍             0.3100 █████████▉
   5 ·that          0.0500 █▊              0.2500 ████████
   6 ·one           0.0300 █               ✂ cut
```

Run with no argument and it replays the answer the model just produced, forcing the real token ids, so the numbers describe that answer rather than a fresh sample. Pass text (`/sampler-probe 24 write a haiku about tide pools`) to probe a prompt of your own; a leading number sets the step count.

Every probe request shares a growing prefix, so with `cache_prompt` each step costs one token of decode rather than a prefill. The command reports the request count and asks before spending it. On a single-slot server a probe replaces the cached prompt, so the next turn reprocesses its prefix; the confirmation says so. With `--parallel 2` or more, probes are pinned to the last slot and leave the agent's cache alone.

### Commands

```text
/sampler-scope              open the telemetry menu
/sampler-scope capture on   start per-token capture (starts the proxy)
/sampler-scope capture off  stop capturing
/sampler-scope mode raw     report raw logprobs instead of post-chain survivors
/sampler-scope nprobs 40    candidate preview depth; full width/entropy stay exact
/sampler-scope report       full statistics for the last generation
/sampler-scope tokens       widest and narrowest steps
/sampler-scope inspect      candidate list for one step
/sampler-scope stats        per-chain aggregates and the session width histogram
/sampler-scope caps         which samplers this build implements
/sampler-scope jsonl        append every generation to a JSONL file
/sampler-scope widget off   hide the live readout above the editor
/sampler-probe [n] [text]   before/after probe
```

The live widget shows the active chain, a log-scaled width sparkline with median and p90, and throughput with the prompt-cache hit rate. The footer carries a condensed version.

### Costs and limits

- `post` mode is close to free: llama.cpp already has the post-chain candidate array. It does sort it, which is cheap when the chain truncates and less cheap when nothing does.
- `raw` mode makes the server run a full-vocabulary softmax for every token. Prefer it for short investigations.
- `n_probs` only limits the candidate preview on the updated custom server. Exact width, rank, and entropy do not require sending the full vocabulary. Older servers produce lower-bound previews (`40+`), excluded from exact width averages.
- Probe mass and KL comparisons still use candidate previews and are labeled accordingly; probe widths, funnel counts, and entropy use the full server measurements.
- `dry` and `penalties` score tokens generated within a request, so a one-token forced probe under-reports them. Those funnel stages are labeled `(no history)`.
- `xtc` is stochastic, so a replayed position may keep a different set than the original generation did.
- `/slots` must be enabled on the server (`--slots`) for the effective-configuration readout. Everything else works without it.
- Dropped-sampler warnings require the same response's applied-chain echo. OpenAI-compatible responses normally omit this, so a missing sampler in `/slots` does not trigger a warning. Use `/sampler-scope caps` for capability checks. Warnings clear at the next captured request or when connecting to a different server.
- Nothing here can recover probabilities for tokens generated before capture was turned on.

## Presets

Bundled manual presets include three high-temperature creative stacks, a balanced everyday stack, a low-entropy coding stack for reliable tool JSON, and greedy generation. Applying one replaces the manual chain and updates its relevant knobs.

Very high temperature makes coding agents and tool calls unreliable unless paired with a restrictive adaptive sampler. Prefer auto mode, `coding`, or `balanced` when omp needs to use tools.

## Development

```sh
bun test          # schema, validation, token detection, command wiring
bun run typecheck
bun run e2e:live  # drives a real omp against a real llama.cpp through a proxy
```

`bun test` includes `commands.test.ts`, which loads the extension and calls the commands it registers against a stub llama.cpp, so the command and request wiring is covered without a generation. `e2e:live` is the other half: it runs a real `omp -p` with a recording proxy in front of the server and asserts on the bytes llama.cpp was actually sent, which is the only way to know that a per-request field such as `logit_bias` survives omp's serializer. It needs a llama.cpp on `LLAMA_URL` (default `http://127.0.0.1:8080`).

## License

MIT. See [LICENSE](LICENSE).
# Local vLLM adapter

Providers with `vllm` in their provider name (for example `glm53-vllm`) use the
ordered sampler plugin in the companion GLM53 integration package. Install and
validate that server plugin before installing this adapter: ordinary vLLM does
not implement these custom arguments.

Supported stages: **XTC, DRY, top-n-sigma, P-less, min_k**, temperature, min_p,
top_p, top_k, and repeat/frequency/presence penalties. Only enabled stages run,
in the selected order. The request uses a versioned JSON string in
`vllm_xargs.omp_sampler_config`; native vLLM sampling settings remain neutral.
The llama.cpp `samplers` array is not sent.

Use `/samplers` to add, remove, reorder or tune stages, and `/samplers show` to
inspect settings. Direct examples:

```text
/samplers chain dry top_n_sigma xtc temperature
/temp 10
/temp inf
```

Temperature supports every nonnegative finite JavaScript number and exact
positive infinity. Infinity makes the currently surviving candidates uniform
without reviving excluded tokens. It is persisted as a boolean marker and sent
as the JSON string `"inf"`; returning to a finite value clears that marker.
`/temp` adds the temperature stage if absent. Put temperature last for a uniform
final distribution. Dynamic temperature is not part of this port.

The sampler proxy also applies the active profile to compaction, which bypasses
OMP's normal request hook. Keep the proxy enabled for this behavior. When the
override is off, OMP's model and launcher defaults apply. Saved user choices are
not replaced during installation.

Telemetry records the actual custom chain and knobs and uses authenticated
OpenAI-compatible streaming logprobs, capped at a 20-candidate preview. This
preview does not enable top-k sampling. The logprobs are raw model probabilities,
not measured post-chain survivor counts. Native llama.cpp endpoints (`/props`,
`/slots`, token detection and `/completion` probes) are not queried.

Automatic routing, token-bias tools, think-cap and other unported llama.cpp
samplers remain unavailable on vLLM. Restart OMP after installing the adapter.
