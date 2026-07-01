# AGENTS.md

Context for AI agents (and future humans) working on this repo. This
captures decisions and rationale that aren't visible from the files alone —
read this before changing presets, the Dockerfile, or the detection scripts.

## Project overview

PreFer: llama.cpp router containers for self-hosted LLM inference, primarily for
RunPod. `docker/prefer/` hosts three model families — gemma-4-26B-A4B,
Qwen3.6-35B-A3B, and GLM-4.7-Flash-REAP-23B-A3B — via `llama-server`'s router
mode, with models downloaded from Hugging Face on first start.

## Conventions

- **Preset naming**: `presets/<N>gb.ini`, where `N` is a VRAM tier in GB.
  `detect-preset.sh` picks the largest tier that fits the detected GPU's
  total VRAM (falling back to the smallest tier if VRAM is below all of
  them). Adding a new tier (e.g. `16gb.ini`) requires no changes to the
  detection script.
- **Router model id naming**: use llama.cpp's HF-style section ids for the
  primary sections (e.g. `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q6_K_XL`) and
  expose short aliases for clients (e.g. `gemma-4`, `qwen-3.6`,
  `glm-4.7-flash`). Include context in an alias only when the section uses a
  non-native explicit context, such as `qwen-3.6-35b-a3b-1m`.
- **Shared defaults use `[*]`**, not per-section duplication. A per-section
  "common defaults" convention (duplicating `[*]`'s values into every model
  section, with `[*]` commented out as documentation) was tried and
  reverted — it didn't avoid the phantom "default" model entry (see below)
  and added maintenance burden for no benefit. **Exception: single-model named
  presets** (`smol.ini`, `deepseek-v4-flash.ini`, `glm-5.2*.ini`) skip `[*]`
  entirely and put every key in their one model section — with nothing to
  share, `[*]` would just be indirection.
- **No comments inside `.ini` files** (deliberate preference). Rationale for
  any non-obvious value lives in this file instead.
- `mmap = false` is set on any preset where `n-cpu-moe > 0` — combining
  mmap with CPU-offloaded MoE tensors triggers a llama.cpp performance
  warning.
- `sleep-idle-seconds = 1800` is set on `12gb.ini`/`8gb.ini` only.
  `96gb.ini` deliberately omits it (not needed with that much headroom).

## Base image

Pinned to `ghcr.io/ggml-org/llama.cpp:server-cuda-b9843`.
(`Dockerfile.netskope` is kept on the same pin.) Policy here is "track latest" —
bump freely. Prior pin was b9592, held back when builds around the
gemma4-assistant MTP merge (#23398, ~b9549) were unstable; that's long settled.

b9843 covers both large-preset architectures:

- **GLM MoE DSA** (`GlmMoeDsaForCausalLM`, PR #19460, merged 2026-02-13) — also
  in any recent build; the GGUFs carry an indexer-tensor workaround (see the
  large-presets section).
- **DeepSeek V4** (CSA/HCA, PR #24162, merged 2026-06-29) — landed in build
  b9840, so b9843 has it.

Note the `server-cuda-b9843` image is published a bit behind the git tag (the
ggml image matrix lags the source tag); if a `--pull` 404s, the build is still
in flight — wait for it rather than pinning lower.

## Tiny preset (smol)

`smol.ini` is a single 135M dense model (SmolLM2-135M-Instruct `Q8_0`, ~145 MB)
whose only purpose is to come up fast and light so the companion app has
something to smoke-test against — explicitly **not** tool calls, reasoning, or
real-quality output. Q8_0 (not Q4) because at 135M the size delta is trivial and
Q8 is noticeably more coherent to eyeball. Like the large presets it is a
**named** preset, not a `<N>gb.ini` tier, so `detect-preset.sh` never
auto-selects it; choose it via `LLAMA_ARG_MODELS_PRESET=/presets/smol.ini`. It's
wired into the same preset-aware `PRESTAGE_MODELS` default in
`download-models.sh` (preset basename `smol` == download key `smol`), so
selecting the preset stages only this model. Being dense it carries no
`n-cpu-moe`/`mmproj`/MTP-draft settings. Future idea (not yet built): a
CPU-only `tiny.ini` variant for GPU-less local machines.

## Large multi-GPU presets (deepseek-v4-flash, glm-5.2, glm-5.2-reap)

These are **named** presets (not `<N>gb.ini` VRAM tiers) and must be selected
explicitly via `LLAMA_ARG_MODELS_PRESET=/presets/<name>.ini`. They are not
auto-detectable: `detect-preset.sh` reads only the *first* GPU's VRAM
(`nvidia-smi ... | head -n1`), so on a multi-GPU box it can't see the combined
pool and would wrongly pick `96gb.ini`. Each preset holds a single model and is
meant to own the whole host (one model at a time — that was the design goal).
`download-models.sh`'s default `PRESTAGE_MODELS` is **preset-aware**: when one
of these named presets is selected, the default stages only that one model
(the preset basename equals the download key), instead of the small-model
lineup the `<N>gb.ini` tiers get. So selecting the preset is enough; an
explicit `PRESTAGE_MODELS` still overrides (needed only when pre-warming
directly without the preset env var set).

Sizes/hardware assume **RTX PRO 6000 Blackwell, 96 GB/card** (the only card that
makes the GPU counts work). `ctx-size = 0` (native) would blow up the KV
allocation (both models are natively 1M), so context is capped explicitly at
**262144** (256K) across all three: DeepSeek V4's compressed CSA/HCA and GLM's
DSA both keep KV small, and these run on big multi-GPU boxes, so 256K is a
sane "not a joke" default. Raise toward native 1M as VRAM headroom allows — for
the GLM presets, unsloth's KV-cache-quant trick (`cache-type-k/v = q8_0`, which
`flash-attn = on` already permits) buys roughly 2× more context if f16 KV runs
tight. Dial back if a preset OOMs.

`deepseek-v4-flash` also uses `batch-size = 4096`, `ubatch-size = 2048` (vs the
`96gb.ini` default of 2048/512) — the better starting point for big-GPU prefill
throughput, matching a real dual-96GB reference run. It costs more compute-buffer
VRAM; drop back toward 2048/512 first if the 256K context + these batches OOM.

| Preset | GGUF | On-disk | Fits | Notes |
| ------ | ---- | ------- | ---- | ----- |
| `deepseek-v4-flash` | [antirez/deepseek-v4-gguf](https://huggingface.co/antirez/deepseek-v4-gguf) `Q4KExperts...imatrix` | ~153 GB | 2× 96 GB | Q4 experts / F16 attn+indexer / Q8 shared+out — the Q4_K_XL-equivalent. unsloth never shipped a V4-Flash GGUF (only FP4/FP8 base); antirez's are what mainline PR #24162 was patched to load. The repo's 3.5 GB MTP draft is **not** wired (b9843 rejects its `deepseek4_mtp_support` arch — see risk notes). |
| `glm-5.2` | [unsloth/GLM-5.2-GGUF](https://huggingface.co/unsloth/GLM-5.2-GGUF) `UD-Q4_K_XL` | ~467 GB (11 shards) | 6× 96 GB (5× very tight) | Full, non-pruned GLM-5.2. Best quality, no REAP loop tax. |
| `glm-5.2-reap` | [0xSero/GLM-5.2-REAP-504B-GGUF](https://huggingface.co/0xSero/GLM-5.2-REAP-504B-GGUF) `Q4_K_XL` | ~308 GB (8 shards) | 4× 96 GB | REAP 34%-expert-pruned. Fits in 4 cards, but per the card the loop rate roughly doubles (3.6%→7.2%) and the DSA indexer tensors are faked (duplicated from the nearest full layer) to load — no DSA speedup. Prefer `glm-5.2` if you have the 6th card. |

**Untested.** None of these have been run on hardware — settings are heuristic
(mirroring the `96gb.ini` `[*]` shape with conservative ctx). Known risks to
check on first boot:
- `deepseek-v4-flash` uses `flash-attn = auto` (not `on`): DeepSeek V4's
  compressed attention (CSA/HCA) isn't fully FA-wired, and real dual-96GB runs
  showed FA auto-disabling with "Flash Attention tensor is assigned to device
  CPU… missing support". `auto` engages it if a build supports it and falls
  back cleanly otherwise; our `f16` KV cache doesn't require FA either way. The
  GLM presets keep `flash-attn = on`; flip to `auto`/`off` if a build rejects
  it.
- `deepseek-v4-flash` sets `top-k = 0` and `min-p = 0.0` on purpose. The model
  card recommends `temp = 1.0, top_p = 1.0` (full distribution), but llama.cpp's
  defaults (`top_k = 40`, nonzero `min_p`) would silently narrow it — zeroing
  both honors the recommendation.
- DeepSeek-V4-Flash is a reasoning model (Non-think / Think-High / Think-Max).
  `reasoning = off` here only controls how thinking is *parsed* in the
  response, not whether the model thinks; Think-Max additionally wants
  `ctx-size` ≥ ~384K (we ship 262144 / 256K, enough for non-think and
  Think-High; raise toward native 1M for Think-Max). The official chat encoding is a Python encoder, not jinja —
  antirez's "chat-v2" GGUF embeds a template (`jinja = true` uses it), worth
  eyeballing that turns render correctly.
- `glm-5.2` / `glm-5.2-reap` use `temp = 1.0`, `top-p = 0.95`, `min-p = 0.01`,
  `top-k = 0` — unsloth's and Z.ai's published GLM-5.2 settings (Z.ai advises
  tuning only one of temp/top_p). This repo's GLM-4.x presets use `temp = 0.7`,
  but that was a 4.x-specific choice; GLM-5.2's own recommendation is 1.0. If
  generation doesn't stop cleanly (the GLM EOG-token issue in "Known upstream
  issues"), dropping temp toward 0.6 is the known lever.
- The DeepSeek MTP `model-draft` was **removed** — on b9843 it fails with
  `unknown model architecture: 'deepseek4_mtp_support'` (mainline has no MTP
  draft support for DeepSeek V4 yet). To re-enable when a build supports it:
  add back `model-draft = .../DeepSeek-V4-Flash-MTP-Q4K-Q8_0-F32.gguf`,
  `spec-type = draft-mtp`, `spec-draft-n-max = 2`, and the `*MTP-Q4K*` download
  include in `download-models.sh`.
- Multi-GPU split is left at llama.cpp's default (layer split across all visible
  GPUs); add `tensor-split` only if the cards are uneven or the layer split
  OOMs one GPU.

## Known upstream llama.cpp issues (not fixable via our config)

- **#22364** — router synthesizes a phantom `"default"` model entry in
  `/v1/models` regardless of whether `[*]`/`default-model` are used.
  Apparently cosmetic (`status: unloaded`), but if real models stop loading
  under `models-max=1`, check whether this entry is consuming a slot.
- **#21375 / #21338 / #22786** — cluster of Gemma 4 thinking+tool-calling
  bugs in llama-server's `peg-gemma4` chat format: infinite repetition loops
  where the model never exits a `<|tool_call>` block. #21418 (merged
  2026-04-04) fixed the original #21375 case and should be included in
  b9592 — but looping has still been observed on b9592, possibly a new
  regression from the June 7 MTP merge interacting with
  tool-calling+reasoning. Mitigated (not fixed) via DRY sampling (see
  below). If still problematic: try `reasoning = off` for gemma (known
  workaround, loses thinking output), or test with `spec-type`/`model-draft`
  removed from gemma to isolate whether MTP is the trigger.
- **GLM tokenizer warnings** (`special_eot_id`/`special_eom_id` not in
  `special_eog_ids`) — known issue across GLM-4.x GGUFs. Generation usually
  still stops correctly via other EOG tokens (e.g. `<|user|>`), but "breaks
  sometimes". If this persists: try `temp = 0.6` (down from `0.7`) on GLM,
  or as a deeper fix, patch the GGUF's tokenizer metadata with
  `gguf-set-metadata.py`.
- **#19379** — `sleep-idle-seconds` leaves ~600MiB resident on the idle
  subprocess (doesn't fully terminate it). With `models-max=1` on
  `12gb.ini`/`8gb.ini`, this is bounded to at most one subprocess and gets
  cleaned up on the next model switch via LRU eviction — not considered a
  real problem here.
- **#20137 / #21678** — `models-max` LRU eviction has TOCTOU races and
  doesn't check for in-flight requests before evicting. Acceptable for
  single-developer use ("these are dev tools, not 5 nines").

## DRY sampling

`dry-multiplier = 0.8`, `dry-base = 1.75`, `dry-allowed-length = 24` are set
globally (in every preset's `[*]`) as a mitigation for repetition loops,
particularly Gemma 4's tool-calling loop issue (see above). `allowed_length`
was deliberately raised from DRY's "chat" default of `2` to `24` — at `2`,
DRY penalizes *any* 3+ token verbatim repeat, which corrupted agentic output
(an agent re-typing the same file path or identifier across tool calls would
get penalized into producing a near-neighbor token instead — e.g. `repos`
becoming `Repositories`). At `24`, short identifiers/paths repeat freely,
while a genuinely looping sequence still gets exponentially penalized after
~24 tokens (`0.8 × 1.75^(n-24)`), which is a tight enough bound in practice.
Caveats: DRY prevents loops from *forming*, it can't break one already in
progress (so a max-tokens cap is still the real backstop for worst-case
cost). Default sequence breakers (`\n`, `:`, `"`, `*`) are common in JSON
tool-call syntax and may reduce DRY's effectiveness for that specific case —
if loops persist on gemma tool calls despite DRY, consider
`dry-sequence-breaker = none` (or dropping `:`/`"` from the breaker set) for
gemma specifically.

## KV cache type: f16 on 96gb, q4_0 on 12gb/8gb

`12gb.ini`/`8gb.ini` use `cache-type-k/v = q4_0` out of necessity — without
it, the long-context variants wouldn't fit in 12GB/8GB at all. `96gb.ini`
uses `cache-type-k/v = f16`, deliberately diverging, for two reasons found
via research:

1. **Speed**: q4_0 KV cache gets significantly *slower* than f16 as context
   grows — a TurboQuant-related benchmark found q4_0 roughly 12% slower than
   f16 at ~24K context and ~37% slower at ~110K, with dequantization
   overhead during decode becoming the bottleneck at long context. Since
   96gb's whole point is long context (up to 262144), q4_0 there would
   likely cost speed, not save it.
2. **Quality, specifically for gemma-4-26B-A4B**: a KL-divergence benchmark
   of Gemma 4 and Qwen3.6 with quantized KV cache found gemma-4-26B-A4B is
   unusually sensitive — q8_0 cache gives KL 0.377 (vs Qwen's <0.04), and
   q4_0 reaches KL 1.088 with only 68% top-1 token match. Cache quantization
   and weight quantization are independent error sources that stack — our
   gemma weights are already `UD-Q4_K_XL` (4-bit), so adding q4_0 KV cache on
   top compounds onto the most quantization-sensitive model in that
   benchmark. Qwen and GLM weren't shown to have this sensitivity, but f16
   is applied uniformly via `[*]` for simplicity, and the speed argument
   applies to all three regardless.

96gb has no VRAM pressure (unlike 12gb/8gb), so there's no real downside to
trade off here — **except** that f16 KV cache is ~4x q4_0's size, and 96gb
now has 5 `load-on-startup` models (the original 3 plus E2B/E4B). This
change has not yet been tested for OOM with all 5 loaded — if it doesn't
fit, q8_0 would be the fallback for gemma at minimum (still better than
q4_0's KL 1.088, though q8_0's 0.377 isn't great either) while keeping f16
for Qwen/GLM if their headroom allows.

## Qwen sampling: `presence-penalty`

Qwen3.6's official recommendation is `presence_penalty = 1.5` (alongside
`temp=1.0, top_p=0.95, top_k=20`) to avoid loops in long reasoning — but
presence penalty applies to *every* token seen so far in the context,
regardless of whether repeating it is a loop or legitimate verbatim reuse
(e.g. an agent re-typing the same file path). This is a documented tension
in the Qwen community itself, not unique to our setup. Since the
`dry-allowed-length = 24` change above covers the same "long reasoning loop"
failure mode more precisely (only penalizing actual repeated *sequences*,
not all repeated tokens), Qwen's `presence-penalty` was set to `0.0` across
all presets, relying on DRY instead. If long-reasoning loops reappear on
Qwen without presence_penalty, that'd be the first thing to revisit —
either raise `presence-penalty` back up (accepting the agentic-output risk)
or tune DRY further before doing so.

## `n-cpu-moe` tuning status

- **`96gb.ini`**: `n-cpu-moe = 0` for all three models — confirmed working
  (all three load and generate correctly).
- **`12gb.ini`**: the preset now mirrors the `96gb.ini`/`8gb.ini` router id
  shape and uses `ctx-size = 0` for native context except the explicit Qwen
  1M entry. Legacy 64k smoke tests on Titan X Pascal confirmed
  gemma-4-26B-A4B and GLM could load/generate, but the current native-context
  entries are still heuristic: gemma-4-26B-A4B uses `n-cpu-moe=20`, Qwen3.6
  35B uses `n-cpu-moe=26`, and GLM uses `n-cpu-moe=18`. Qwen3.6 27B is dense,
  so `n-cpu-moe` is not expected to matter.
- **`8gb.ini`**: **entirely heuristic**. It mirrors the same router id shape
  as `12gb.ini`, with higher MoE offload values (`n-cpu-moe` 26/32/24 for
  gemma-4-26B-A4B, Qwen3.6 35B, and GLM respectively). Nothing here has been
  tested on real 8GB hardware (GTX 1070) yet.

## Download / Hugging Face specifics

- Uses the `hf` CLI (not the deprecated `huggingface-cli`).
- **Download progress** is just hf's default tqdm bars. Considered a custom
  per-repo progress heartbeat for the big multi-shard pulls (tqdm bars are hard
  to read in `docker logs`), but the hf CLI has no log-friendly progress mode
  (only bars, or silence via `--quiet` / `HF_HUB_DISABLE_PROGRESS_BARS`; the
  verbosity vars set logger level, not progress), and rolling our own wasn't
  worth it — left as-is.
- `HF_HOME=/models` so the HF cache/staging directory shares the model
  volume (avoids filling the container's ephemeral filesystem, and survives
  restarts).
- Qwen's actual GGUF filename omits `-MTP-` despite the repo being named
  `Qwen3.6-35B-A3B-MTP-GGUF`; the current presets/downloads use
  `Qwen3.6-35B-A3B-UD-Q6_K_XL.gguf`. The MTP layer is embedded in this file
  (no separate `model-draft`).
- Gemma's MTP draft (`mtp-gemma-4-26B-A4B-it.gguf`) downloads flat into the
  repo's root directory, not under an `MTP/` subfolder.
- Gemma vision is enabled through `mmproj-F16.gguf` for all hosted Gemma
  variants. F16 was chosen over BF16 as the safer default for Pascal-era
  cards (Titan X Pascal / GTX 1070), and over F32 because F32 roughly doubles
  projector size with no known practical quality benefit for this setup.
  Qwen repos also publish mmproj files, but only Gemma is wired up today.
- **gemma-4-E2B/E4B** (added for speed — same family, 2B/4B "effective
  params", 128K max context). **Confirmed on disk** (2026-06-15):
  `gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` (2.62 GB) +
  `mtp-gemma-4-E2B-it.gguf` (59.2 MB), and
  `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` (4.22 GB) +
  `mtp-gemma-4-E4B-it.gguf` (59.7 MB), both at the repo root — same
  root-level-drafter pattern as 26B-A4B's `mtp-gemma-4-26B-A4B-it.gguf`
  (252 MB next to its 14.2 GB main file). All four filenames/paths in
  `download-models.sh` and the presets are correct.

  Without MTP, E2B/E4B were observed to be significantly out-throughput by
  the 26B-A4B (which has MTP) despite being much larger — so MTP isn't
  optional polish here, it's the point of including these models at all.
  Config: `model-draft = mtp-gemma-4-E{2,4}B-it.gguf`,
  `spec-type = draft-mtp`, `spec-draft-n-max = 4`. unsloth's documented E4B
  MTP command also uses `flash-attn = off`, which originally conflicted with
  `[*]`'s `cache-type-k/v = q4_0` ("V cache quantization requires
  flash_attn") — on `96gb.ini`, `[*]` is now `f16` (see KV cache section
  above), which doesn't have that requirement, so `flash-attn = off` was
  restored for E2B/E4B there, matching unsloth's documented command.
  `12gb.ini`/`8gb.ini` still use `q4_0` cache, so `flash-attn = off` would
  still conflict there — E2B/E4B on those two presets keep `flash-attn = on`
  (from `[*]`), same as 26B-A4B's confirmed-working MTP + flash-attn=on
  combination. `spec-draft-n-max = 4` is carried over from unsloth's
  documented command and not independently verified for E2B/E4B, but the
  drafter files themselves are confirmed present.

## S3 model cache (`S3_BUCKET_NAME`)

`download-models.sh` has an optional S3 layer gated on `S3_BUCKET_NAME`: per-repo
sync **down** from `s3://$BUCKET/<hf-repo>/` before `hf download`, then a
background sync **up** of new files. Unset (local / RunPod) = HF-only, unchanged.
Sync is per-repo (not a blanket `/models` sync) on purpose: `HF_HOME=/models`
holds cache cruft (xet, `.cache`) that shouldn't reach the bucket. Needs `s5cmd`
(installed in the Dockerfile); creds come from the AWS chain (env / instance
role). S3 was chosen over a persistent EBS volume because a single EBS volume
caps at 1 GB/s while S3 via s5cmd is NIC-bound at multiple GB/s.

## EC2 deployment (`aws/`)

Self-serve EC2 launch lives under `aws/` (design + rationale in `aws/DESIGN.md`):
a Packer-built public AMI (DLAMI Base GPU Ubuntu 24.04 base, resolved via SSM) +
systemd boot unit (stage instance-store NVMe at `/opt/dlami/nvme`, `docker run`
with `/models` on NVMe) + a CDK stack distributed as synthesized CloudFormation.
The container is pulled at boot (not baked), and CI is path-filtered so AWS
changes never rebuild the container (`build-prefer.yml` is `docker/prefer/**`
only; `build-aws.yml` covers `aws/`). `build-aws.yml` is one workflow with
ordered jobs — a paths-filtered `ami` job (Packer; public AMI built into
us-east-1 + us-east-2) hands its `ami-map` artifact to a `cdk` job that bakes it
into the template's RegionMap and publishes the `template-latest` release. A
CDK-only change skips the AMI build and reuses the last release's map; nothing is
committed back. Don't reopen the settled calls there (S3-over-EBS, AMI base,
dlami-nvme, `--restart no`) without reading `aws/DESIGN.md` first.

## Testing

There's no automated test suite — all verification so far has been manual,
on actual GPU hardware (a Blackwell-class ~96GB card and a Titan X Pascal
12GB card). Useful manual checks:

- `docker compose config` — verify env var resolution (especially
  `LLAMA_ARG_MODELS_PRESET`/`LLAMA_ARG_MODELS_MAX`) before `up`.
- `docker compose run --rm prefer /download-models.sh` — pre-warm the
  model cache without starting the GPU server.
- `GET /v1/models` and a minimal `POST /v1/chat/completions` per model id —
  confirm a preset's models load and respond.

If adding an automated smoke test, it would need to run on a GPU host (no
CPU-only fallback is practical given model sizes) — not currently set up in
CI.
