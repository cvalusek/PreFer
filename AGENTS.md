# AGENTS.md

Context for AI agents (and future humans) working on this repo. This
captures decisions and rationale that aren't visible from the files alone —
read this before changing presets, the Dockerfile, or the detection scripts.

## Project overview

PreFer: sibling llama.cpp, audio.cpp, and stable-diffusion.cpp containers for
self-hosted inference.
`docker/llama-cpp/` serves LLMs on local, RunPod, and AWS hardware and hosts
Gemma 4, Qwen3.5/Qwen3.6/Qwen3.8,
Ornith 1.5, Nemotron 3.5 Lightning, Muse Glimmer, GLM, and DeepSeek V4 routes via
`llama-server` router mode, with models
downloaded from Hugging Face on first start. `docker/audio-cpp/` is a separate
speech/music runtime with its own API, inventory, model volume, and release
tags. `docker/stable-diffusion-cpp/` provides image generation/editing with a
separate API, inventory, model volume, and release tags.

## Published change reference

The root `CHANGELOG.md` is the consumer-facing history for hosted models and
presets. It has no `Unreleased` section and no independent PreFer calendar or
semantic version. Update it in the same commit as every consumer-visible
hosted-model or preset change by adding a populated `Current` section at the
top. `Current` describes the changes already merged while their image is still
building; never leave an empty `Current` section in the file.

After CI publishes the immutable image, make a root-only follow-up commit that
changes the `Current` heading to the resulting `sha-<short-commit>` tag and
adds the exact image identity. Do not rewrite the approved change bullets
during finalization. Image workflows watch their runtime folders, so this root
changelog-only commit does not create another image. Include additions,
removals, and exact context/concurrency deltas, plus quant, speculative,
prestaging, or compatibility changes only when they actually changed. Keep
entries concise, user-facing, nested by platform and instance, and limited to
one model per line. Maintenance instructions and implementation rationale
belong in this file, not in `CHANGELOG.md`.

## Conventions

- **Preset naming**: `presets/<N>gb.ini`, where `N` is a VRAM tier in GB.
  `detect-preset.sh` picks the largest tier that fits the detected GPU's
  total VRAM (falling back to the smallest tier if VRAM is below all of
  them). Adding a new tier (e.g. `16gb.ini`) requires no changes to the
  detection script. `12gb-pascal.ini` is an intentional named compatibility
  preset and is never auto-detected; it is retained as a rollback for the
  historical b9843 Gemma E4B MTP issue described below. Nested generated provider
  presets are also named presets and must be selected explicitly.
- **Router model id naming**: use llama.cpp's HF-style section ids for the
  primary sections (e.g. `unsloth/Qwen3.6-35B-A3B-MTP-GGUF:UD-Q6_K_XL`) and
  expose short aliases for clients (e.g. `gemma-4`, `qwen-3.6`,
  `glm-4.7-flash`). Include context in an alias only when a separately usable
  section intentionally exposes a non-native context. The former Qwen 35B
  single-slot 1M YaRN section failed operationally and has been removed; do not
  restore its `qwen-3.6-35b-a3b-1m` identity from historical baselines.
  The v1 client contract distinguishes these configured section identities
  from normalized `/v1/models`/request IDs. On measured b9843, for example,
  E2B was configured as `:UD-Q4_K_XL` but advertised and accepted as
  `:Q4_K_XL` (plus `gemma-4-e2b`). b10362 is now the production pin; keep the
  distinction until its exact discovery behavior is measured. Do not infer
  request compatibility from the preset header alone.
- **Shared defaults use `[*]`**, not per-section duplication. A per-section
  "common defaults" convention (duplicating `[*]`'s values into every model
  section, with `[*]` commented out as documentation) was tried and
  reverted — it didn't avoid the phantom "default" model entry (see below)
  and added maintenance burden for no benefit. **Exception: single-model named
  presets** (`smol.ini`, `deepseek-v4-flash.ini`, `glm-5.2*.ini`, and all
  generated provider single-model presets) skip `[*]`
  entirely and put every key in their one model section — with nothing to
  share, `[*]` would just be indirection.
- **No comments inside `.ini` files** (deliberate preference). Rationale for
  any non-obvious value lives in this file instead.
- `mmap = false` is set (a) on any preset where `n-cpu-moe > 0` — combining
  mmap with CPU-offloaded MoE tensors triggers a llama.cpp performance
  warning; and (b) on the large multi-GPU presets (both DeepSeek routes,
  glm-5.2, glm-5.2-reap) regardless of `n-cpu-moe`, because mmap loads these
  multi-hundred-GB models pathologically slowly on RunPod's model-volume
  storage (see the large-presets section).
- `sleep-idle-seconds = 1800` is set on `12gb.ini`/`8gb.ini` only.
  `96gb.ini` deliberately omits it (not needed with that much headroom).

## `models-max` precedence and policy

The effective normal Compose default is **1**, including for `96gb.ini`:
`docker-compose.yml` passes
`LLAMA_ARG_MODELS_MAX=${LLAMA_ARG_MODELS_MAX:-1}`, and `.env.example` also
sets 1. An explicit `--models-max` command-line argument wins, followed by an
existing `LLAMA_ARG_MODELS_MAX` value. If neither exists and the preset is
auto-detected, `detect-preset.sh` assigns 1 when that preset contains no
`load-on-startup` entry. None of the current 8/12/96 GB tier presets contains
one, so direct auto-detection also resolves to 1.

The subtle fallback case is an explicitly selected preset outside the normal
Compose path: preset detection is skipped, so with no CLI/environment value
llama.cpp uses its router default of 4. Legacy named presets contain one model,
but generated provider presets can contain several. The AWS AMI therefore also
bakes `LLAMA_ARG_MODELS_MAX=1`, and its deployment environment repeats that
value explicitly. Any other direct launcher selecting a generated provider preset
must set the limit rather than relying on llama.cpp's fallback.

An older operator README row said 96 GB used the upstream default 4. That was
documentation drift, now corrected; the operational default was deliberately
left at 1. Whether 96 GB should later retain more models is an owner policy
decision gated on the checked-in `models-max=1` versus `4` benchmark dimension,
not something to infer from upstream defaults.

## Base image

Pinned to
`ghcr.io/ggml-org/llama.cpp:server-cuda-b10362@sha256:182a26fbd68d1774860bd2a0fb5581ba3047974307eaeee64930d8bf889e0c0c`
(source `4801e3c567d5131dd41b387df5f2d4b1370d92be`). The digest is the official
multi-platform manifest containing linux/amd64 and linux/arm64. Keep
`Dockerfile.netskope` in lockstep. Policy remains "track latest," but a bump
must resolve and pin the published manifest rather than use the moving
`server-cuda` tag.

Upstream source releases and CUDA container publication are asynchronous.
Building every architecture normally takes several hours and can approach a
day; occasionally a release-numbered container is skipped and the next higher
build is the first image published. When waiting for a required merge, do not
require the Docker tag matching the first signed source release and do not pin
the moving tag. Inspect the moving OCI index only to discover its annotated
build and source revision, then select the first available versioned
`server-cuda-bNNNN` tag whose recorded source revision is a descendant of the
required merge. Pin its immutable multi-platform digest only after both
linux/amd64 and linux/arm64 manifests are present. A higher build number is a
valid first consumable artifact when an intermediate image was never
published.

b10362 includes GLM MoE DSA, DeepSeek V4 base support, the Gemma E4B MTP
FlashAttention fix from PR #25148, and DeepSeek V4 MTP/DSpark support from
PR #25784. It also includes PR #22789's dynamic split-graph input allocation,
which removes the fixed scheduler-input cap hit by DeepSeek V4 across two GPUs.
Muse target, multimodal-projector, and DFlash support from PR #26841 is also
included; source `4801e3c567d5131dd41b387df5f2d4b1370d92be` is 13 commits after
the required merge `62bf73d25c53b8161f8a22894d4f90c4aebbd7d0`.
The historical b9843 and b9982 lanes remain in benchmark data for reproducing
old Pascal results; `current` now means b10362. The Muse presets are no longer
runtime-gated, but their 24/48/96 GB shapes still require normal first-boot
fit, contract, DFlash, projector, and concurrency verification on target GPUs.

## Generated deployment presets and inventory

AWS, RunPod, and generic local hardware presets are generated, not hand-edited:

- `preset-catalog.json` owns only the pinned llama.cpp runtime and legacy
  prestage default.
- `models/<family>/<model>/model.json` owns model sections, aliases, exact
  download revisions, files, sizes, hashes, companions, and model-specific
  settings. Its root `profile` owns the logical model's prompt-ready selection
  guidance: concise summary, architecture, native and configured modalities,
  context/reasoning controls, role fit, strengths, limitations, prompting notes,
  and evidence confidence. One logical model file contains a `quants` dictionary; each quant
  lane has a globally unique catalog key used by scenarios and staging.
  Model-wide aliases/license/lineage/runtime facts belong in `shared`; settings
  shared by multiple quant lanes may also live there, with lane settings merged
  over them.
- `preset-scenarios/<provider>/<hardware>/` owns provider/card/count,
  model/context/concurrency, compatibility, and verification status. Files may
  use `extends` to inherit an existing scenario by generated preset path. The
  child always owns provider/hardware identity; inherited AWS instance metadata
  must never leak into a RunPod/local inventory entry.
- `generate-presets.py` recursively discovers both trees and emits the nested
  `.ini` presets, sibling `.prestage` manifests,
  `model-downloads.generated.sh`, and
  `deployment-inventory.generated.json`. Run it after any source change; CI
  runs `generate-presets.py --check`.
- The deployment inventory is copied into the image as
  `/deployment-inventory.json`, published as a commit-named workflow artifact,
  and identified by OCI labels. It is the machine-readable NeurOn contract for
  runtime, model/quant, provider GPU ID/count, effective settings, preset path,
  prestaging, and model-selection guidance. `model_profiles` is deduplicated by
  logical `model_slug`; quant and deployment entries reference it through
  `profile_id`.
- Treat profiles as product routing judgment, not benchmark leaderboards. Keep
  native capability separate from what the checked-in artifacts configure, and
  keep both separate from scenario verification. Record meaningful behavioral
  differences such as prose quality, visual interpretation, tool persistence,
  orchestration fit, and prompt-family needs. Mark mixed or inferential evidence
  honestly, but do not erase useful operator knowledge merely because a broad
  matched benchmark is unavailable. Do not copy third-party evaluation scores,
  rankings, or provider throughput into the release inventory. A profile may
  state a rough qualitative conclusion, but consumers must inject current
  external data through a separately attributed source. NeurOn's route-level
  measurements are authoritative for deployed speed; catalog speed language is
  deliberately qualitative.
- Every catalog lane owns an explicit `request_model_id` that must be one of
  its configured aliases. Controllers use it for warmup and API requests.
  `section` remains the exact generated INI header and is not request-safe:
  llama.cpp can normalize quant names between configuration and discovery
  (for example E2B `:UD-Q4_K_XL` becomes `:Q4_K_XL`).
- A generated preset and its sibling `.prestage` file are a pair. With
  `PRESTAGE_MODELS` unset or blank, `download-models.sh` stages exactly the
  catalog keys referenced by the sidecar. A nonblank environment value still
  wins; use `none` for an intentional no-download run.

AWS authored scenarios are split by instance shape under
`preset-scenarios/aws/`. RunPod paths are
`presets/runpod/<gpu-slug>/<count>x/`; all initial card shapes use one GPU
except `runpod/rtx-pro-6000/2x/deepseek-v4-flash.ini`. RunPod prices and bundled
host resources are dated observations, never stable provisioning constraints.
Generic household profiles live under `presets/local/<gpu-slug>/1x/` and may
record only GPU-class facts and compatibility gates. Never check in a private
hostname, CPU, system RAM, disk, network, credential, or owner-specific mapping;
NeurOn owns that private association.

### AWS deployment matrix

| Preset | Host | Routes | Cache allocation |
| ------ | ---- | ------ | ---------------- |
| `aws/g6/xlarge/general.ini` | 1× L4 24 GB, 4 vCPU | Gemma E2B/E4B/12B, Qwen3.5-9B, Ornith 9B Q8, Nemotron Q4, Muse Q4 | See exact cumulative matrix below |
| `aws/g6e/xlarge/general.ini` | 1× L40S 48 GB, 4 vCPU | All g6 routes plus Gemma 26B/31B, Qwen3.6 35B/27B, Ornith 35B Q8, Nemotron Q8, Muse Q6 | See exact cumulative matrix below |
| `aws/g6e/xlarge/gemma.ini` | 1× L40S 48 GB, 4 vCPU | Gemma 26B-A4B/31B | 26B: 2×256K; 31B: 1×256K |
| `aws/g6e/xlarge/qwen.ini` | 1× L40S 48 GB, 4 vCPU | Qwen3.6 35B-A3B/27B Q6 | 1×192K each |
| `aws/g7e/2xlarge/general.ini` | 1× RTX PRO 6000 96 GB, 8 vCPU | All g6e routes plus GLM-4.7-Flash | See exact cumulative matrix below |
| `aws/g7e/2xlarge/gemma.ini` | 1× RTX PRO 6000 96 GB, 8 vCPU | Gemma 26B-A4B/31B | 26B: 4×256K; 31B: 2×256K |
| `aws/g7e/2xlarge/qwen.ini` | 1× RTX PRO 6000 96 GB, 8 vCPU | Qwen3.6 35B-A3B/27B | 4×256K each |
| `aws/g7e/12xlarge/deepseek-v4-flash-0731.ini` | 2× RTX PRO 6000 96 GB, 48 vCPU | DeepSeek V4 Flash 0731 Q4 + Q8 DSpark | 4×384K |
| `aws/g6/xlarge/muse.ini` | 1× L4 24 GB, 4 vCPU | Muse Glimmer 30B Q4 + DFlash | 1×128K |
| `aws/g6e/xlarge/muse.ini` | 1× L40S 48 GB, 4 vCPU | Muse Glimmer 30B Q6 + DFlash | 2×128K |
| `aws/g7e/2xlarge/muse.ini` | 1× RTX PRO 6000 96 GB, 8 vCPU | Muse Glimmer 30B Q6 + DFlash | 4×128K |

`ctx-size` is the total cache divided among `parallel` slots; the table shows
the per-request allocation. All AWS scenarios deliberately use f16 K and V.
Each `general.ini` is cumulative and contains the best host-appropriate lane
for models assigned to that tier and every lower tier. A model with multiple
catalog quants appears only once: Muse uses Q4 on g6 and Q6 on g6e/g7e.
Cumulative general presets stage every referenced model by default; use a
family or single-model preset when the full transfer and startup inventory is
not wanted.

| Model lane | g6 general | g6e general | g7e general |
| ---------- | ---------- | ----------- | ----------- |
| Gemma E2B QAT Q4 | 4×128K | 4×128K | 4×128K |
| Gemma E4B QAT Q4 | 4×128K | 4×128K | 4×128K |
| Gemma 12B QAT Q4 | 4×128K | 4×128K | 4×128K |
| Gemma 26B-A4B QAT Q4 | — | 2×256K | 4×256K |
| Gemma 31B QAT Q4 | — | 1×256K | 2×256K |
| Qwen3.5-9B Q4 | 2×128K | 2×128K | 2×128K |
| Qwen3.6-35B-A3B Q6 | — | 1×192K | 4×256K |
| Qwen3.8-27B Q6 | — | 1×192K | 4×256K |
| Ornith 1.5 9B Q8 | 2×128K | 2×256K | 4×256K |
| Ornith 1.5 35B-A3B Q8 | — | 1×256K | 4×256K |
| Nemotron 3.5 Lightning 30B-A3B | Q4 + MTP 1×128K | Q8 + MTP 1×256K | Q8 + MTP 2×1M |
| Muse Glimmer 30B | Q4 1×128K | Q6 2×128K | Q6 4×128K |
| GLM-4.7-Flash Q6 | — | — | 4×202,752 |
The original four-host deployment shape consumes exactly 64 vCPUs when running
together. Family presets are alternatives to the corresponding cumulative
`general.ini`, not additional simultaneous hosts. G6/G6e xlarge have 250 GB
local NVMe; G7e 2xlarge has 1.9 TB and G7e 12xlarge has 3.8 TB.

Every bundled AWS route also has a generated single-model alternative on the
same instance type. These presets copy the bundle's effective context,
parallelism, cache, sampling, model, projector, and speculative-decoding
settings, but contain one section, stage one catalog key, and set
`load-on-startup = true`:

| Host | Single-model presets |
| ---- | -------------------- |
| `g6.xlarge` | `gemma-e2b.ini`, `gemma-e4b.ini`, `gemma-12b.ini`, `qwen-9b.ini`, `ornith-9b.ini`, `nemotron-lightning.ini`, `muse.ini` |
| `g6e.xlarge` | `gemma-26b-a4b.ini`, `gemma-31b.ini`, `qwen-35b-a3b.ini`, `qwen-27b.ini`, `ornith-9b.ini`, `ornith-35b-a3b.ini`, `nemotron-lightning.ini`, `muse.ini` |
| `g7e.2xlarge` | `gemma-26b-a4b.ini`, `gemma-31b.ini`, `qwen-35b-a3b.ini`, `qwen-27b.ini`, `ornith-9b.ini`, `ornith-35b-a3b.ini`, `nemotron-lightning.ini`, `glm-4.7-flash.ini`, `muse.ini` |

The family bundles remain supported for flexible hosts. Prefer a single-model
preset when NeurOn or another controller already knows which model owns the
instance: unused router sections have shown undesirable startup overhead even
when prestaging and `models-max` are bounded.

### RunPod and local generated shapes

RunPod's one-card folders cover the current advertised 24 GB through 288 GB
Pod inventory using exact API `gpuTypeIds`. The 24 GB shape is reused by the
24 GB cards and, conservatively, RTX 5090; the 48 GB shape is reused by 48 GB
cards; the g7e high-context shape is reused by 80 GB and larger cards. Every
inherited RunPod scenario remains `configuration-only` until the exact card is
smoked. Do not interpret a larger VRAM number as proof that architecture,
runtime buffers, speculative companions, or context allocation pass. The only
initial multi-GPU RunPod route is 2× RTX PRO 6000 for the quality-credible
DeepSeek 0731 Q4+DSpark preset.

Generic local folders currently cover RTX 4060 8 GB, RTX A2000 8 GB, GTX 1070
Ti, and TITAN X Pascal. Modern 8 GB profiles expose Gemma E2B/E4B, Qwen3.5 9B,
Ornith 1.5 9B Q4, and a deliberately slow Nemotron Lightning Q4 CPU-expert lane;
the 12 GB Pascal profile additionally exposes Gemma 12B, Ornith 9B Q6, Ornith
35B-A3B Q4 with CPU expert offload, and Nemotron. Small routes use q4_0 K/V as
a capacity necessity; the large CPU-expert lanes retain f16 K/V. The Pascal
profiles require a CUDA 12 `sm_61` build, and omit E4B's MTP companion pending
a direct MTP-on Pascal smoke. On b10362,
the TITAN X Pascal generated profile has passed isolated load/generation for
E2B, target-only E4B, Qwen3.5-9B, and Gemma 12B, followed by all four swaps
through `general.ini` with `models-max=1`. Do not silently copy those q4 cache
or target-only decisions into hosted profiles, which retain f16 K/V and normal
speculative lanes.

The b10362 TITAN X Pascal smoke used the generated contexts/concurrency exactly
as shipped and a short text completion. Post-load VRAM was 5,933 MiB for E2B,
7,769 MiB for target-only E4B, 9,906 MiB for Qwen3.5-9B, and 10,284 MiB for
Gemma 12B. The subsequent `general.ini` swap cycle measured 5,932, 7,775,
9,901, and 10,301 MiB respectively, with every request returning HTTP 200.
Treat these as fit/routing smoke results, not throughput or long-context quality
benchmarks.

The TITAN X Pascal cumulative `general.ini` also exposes deliberately slow,
high-intelligence CPU-expert-offload lanes for Gemma 4 26B-A4B QAT Q4 and
Qwen3.6 35B-A3B Q4. Both allocate one 128K slot and preserve f16 K/V instead
of inheriting the smaller models' q4_0 cache. Their speculative paths are
disabled on Pascal. They are router choices in the existing general preset,
not separate named presets.

Both large lanes passed isolated b10362 load/generation and an LRU swap through
the generated `general.ini` with `models-max=1`. Gemma 26B used
`n-cpu-moe=15`, loaded its F16 projector and one 128K f16-K/V slot in about
2.5 minutes, peaked near 12,043/12,288 MiB GPU and 7.6/15.5 GiB container
memory, and decoded the short smoke at 0.36 tok/s. Qwen 35B used
`n-cpu-moe=28`, ignored its embedded MTP tensors as intended, loaded one 128K
f16-K/V slot in about 1 minute 40 seconds after Gemma eviction, peaked near
12,025/12,288 MiB GPU and 13.7/15.5 GiB container memory, and decoded the short
smoke at 0.90 tok/s. These are operational fit/routing measurements, not
quality or sustained-throughput benchmarks; both lanes have very little memory
headroom and are intentionally low-speed intelligence options.

The apparently aggressive Gemma 12B `4×128K` f16 cache is intentional. Its
[published architecture](https://huggingface.co/google/gemma-4-12B/blob/main/config.json)
has 48 layers: eight full-attention layers with one global KV head and forty
layers using a 1,024-token sliding window. That
makes its long-context cache materially smaller than a conventional 48-layer
dense-attention estimate. The 24 GB route is still a first-boot peak-VRAM gate,
including the MTP assistant, projector, compute buffers, and allocator slack.

Gemma 12B/31B use Unsloth's QAT-derived UD-Q4_K_XL targets, same-repository
Q4_0 MTP assistants, and F16 projectors. Qwen3.5-9B uses the non-MTP
UD-Q4_K_XL target plus its F16 projector, preserving the g6 route's two-way
parallelism and vision support. Do not set `draft-mtp` on that GGUF: b10257
rejects it because it contains no MTP layers. Qwen3.8-27B replaces the former
Qwen3.6-27B route with the immutable Unsloth UD-Q6_K_XL artifact at
`4604b899a826000505a834e623272db5b7fd62f6`; it retains embedded MTP with
`spec-draft-n-max=2`, but intentionally does not configure the optional
projector. The model's native 262K context, thinking sampler, and existing
192K/256K deployment shapes did not require a preset-setting change. Its
embedded template exposes `reasoning_effort` (`low`, `medium`, and `xhigh`,
defaulting to `xhigh`) and defaults to preserving prior thinking; those remain
request/template behavior rather than duplicated INI settings. DeepSeek 0731
uses the five-shard
UD-Q4_K_XL target plus the
co-located Q8_0 DSpark companion; `spec-type` is `draft-dspark` and
`spec-draft-n-max=5`. IQ1/IQ2 are intentionally absent.

Ornith 1.5 uses first-party immutable GGUFs. The 9B catalog lanes are Q4_K_M,
Q6_K, and Q8_0; the 35B-A3B lanes are Q4_K_M and Q8_0. Both include the
matching BF16 projector and preserve the publisher's native 262,144-token
range. The 9B route uses Q4 on 8 GB local cards, Q6 on TITAN X Pascal, and Q8
on hosted cards. The 35B route uses Q4 plus CPU expert offload only on TITAN X
and Q8 on hosted 48 GB or larger cards. Although the architectures expose a
trained next-token layer, the first-party llama.cpp card does not document the
embedded-MTP serving path, so Ornith remains target-only until a direct smoke.

Nemotron 3.5 Lightning uses the repaired immutable ggml-org Q4_0/Q8_0 target
and matching MTP artifacts at revision
`9169f1a8ac58a29383ec27a447b4af3532da8864`, linked to NVIDIA's BF16 revision
`63a200063804e06fdb41d6717e43bc92f67859d2`. It uses `draft-mtp` with
`spec-draft-n-max=3`. Hosted 24 GB uses Q4 at 1×128K; hosted 48 GB uses Q8 at
1×256K; 80/96 GB inherited shapes use Q8 at 2×1M. Local profiles keep MTP but
offload experts with `n-cpu-moe=28`, `mmap=false`, f16 K/V, and one 128K slot.
b10362 has a reproducible draft-loader failure for lower partial `n-cpu-moe`
values on this model, while 28 and above load; do not reduce that setting
without a matched smoke. All new Nemotron shapes remain configuration-only
until exact-card load, context, contract, and MTP-acceptance verification.

Muse uses two immutable Unsloth lanes from
`unsloth/Muse-Glimmer-30B-GGUF@faa5b025c584459c13febfa5c59883516710ae39`,
both linked to the official
`meta-models/Muse-Glimmer-30B@90625aaf7c8d5338df3779e3f2ef1b8c9e669252`
snapshot. The derivative card declares that base repository but does not
publish its exact conversion-input SHA; the serving artifacts themselves are
fully pinned. The 24 GB preset uses `UD-Q4_K_XL`; the 48/96 GB presets use
`UD-Q6_K_XL`. Both add the pinned `dflash-kquant.gguf` and
`mmproj-kquant.gguf`, use `draft-dflash`, and draft 15 tokens from the
model's trained 16-token block. Exact target + draft + projector bytes are
18.91 GB for Q4 and 29.30 GB for Q6 before runtime/KV. The quantized projector
is deliberate: BF16 would consume another 2.45 GB and make the 24 GB lane
needlessly tight. Sampling follows the publisher's `temp=1.0`, `top_p=0.95`,
`top_k=64`; `min_p=0` disables llama.cpp's additional unrequested filter.

Muse's 52 layers repeat three 2K sliding-window layers then one global layer,
with two KV heads, so its f16 cache grows much more slowly than a conventional
52-layer dense-attention model. The 24/48/96 GB shapes allocate 1×128K,
2×128K, and 4×128K respectively. The 96 GB route spends its extra memory on
concurrency while staying at the publisher's default 131,072-token position
range. For all three,
verify full-GPU load, peak VRAM, image input, strict JSON/tools/SSE, per-slot
context, DFlash acceptance and throughput before production use. If DFlash
hurts concurrency or stability, record a target-only comparison; do not silently
remove the companion from the canonical preset.

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
meant to own the whole host (one model at a time — that was the design goal), so
each sets `load-on-startup = true`: the one model loads at boot rather than
lazily on first request. The normal Compose path passes
`LLAMA_ARG_MODELS_MAX=1`; an explicit non-Compose launch can fall through to
llama.cpp's default 4, but either way there is only one configured model.
`download-models.sh`'s default `PRESTAGE_MODELS` is **preset-aware**. Generated
presets use a sibling `.prestage` manifest; legacy named single-model presets
fall back to a basename that matches the catalog key. Selecting either form is
enough. A nonblank `PRESTAGE_MODELS` still overrides, including when
pre-warming directly without a preset environment value.

Sizes/hardware assume **RTX PRO 6000 Blackwell, 96 GB/card** (the only card that
makes the GPU counts work). `ctx-size = 0` (native) would blow up the KV
allocation (both models are natively 1M), so context is capped explicitly:
`deepseek-v4-flash` runs **393216** (384K), the GLM presets **262144** (256K).
Both archs compress KV (CSA/HCA, DSA) so context is affordable; raise toward
native 1M as VRAM headroom allows — for the GLM presets, unsloth's KV-cache-quant
trick (`cache-type-k/v = q8_0`, which `flash-attn = on` already permits) buys
roughly 2× more if f16 KV runs tight. Dial back if a preset OOMs.

`deepseek-v4-flash` uses `batch-size = 2048`, `ubatch-size = 256` — smaller than
usual, on purpose. With flash-attention inactive for V4 (see risk notes), the
prefill compute buffer scales with `ubatch × ctx-size` and is a single
per-device allocation (it can NOT be split across GPUs — see the multi-GPU note
below). **Measured on 2× RTX PRO 6000 (96 GB)**: the `ubatch × ctx` budget is
~1.0–1.1e8 before device 0 OOMs. Working points: `256 × 262144` ✓, `512 × 131072`
✓, `256 × 393216` ✓ (~1.0e8, both cards ~94 GB used); OOM: `512 × 262144`
(~1.34e8, the buffer was ~71 GB). We ship `256 × 393216` because 384K hits
DeepSeek's Think-Max threshold. Trade prefill speed (ubatch) against context
(ctx) within that budget. If a build ever wires up V4 flash-attention, this
buffer collapses and both can go far higher.

All three set **`mmap = false`** despite `n-cpu-moe = 0`. On RunPod's
model-volume storage, loading a multi-hundred-GB model via mmap page-faults it
in on demand over a network/overlay filesystem (no readahead), so it crawls and
looks like a boot hang — GLM-5.2's 467 GB never appeared to finish loading.
`--no-mmap` does bulk sequential reads straight into VRAM and loads fine.
**Confirmed** on 8× 96 GB with 1.5 TB RAM free and the model fully on disk, so
it is NOT memory pressure (the earlier RAM-thrash guess was wrong) — it's the
mmap-over-network-FS penalty, and it scales with model size (DeepSeek's 153 GB
was slow-but-tolerable under mmap; GLM's 467 GB crossed into "looks dead").
Trade-off: no page-cache reuse across restarts, fine here since these are
one-model-per-host boxes.

| Preset | GGUF | On-disk | Fits | Notes |
| ------ | ---- | ------- | ---- | ----- |
| `deepseek-v4-flash` | [antirez/deepseek-v4-gguf](https://huggingface.co/antirez/deepseek-v4-gguf) `Q4KExperts...imatrix` | ~153 GB | 2× 96 GB | Preserved Preview-era target-only route. Q4 experts / F16 attn+indexer / Q8 shared+out; no draft is configured. |
| `aws/g7e/12xlarge/deepseek-v4-flash-0731` | [unsloth/DeepSeek-V4-Flash-0731-GGUF](https://huggingface.co/unsloth/DeepSeek-V4-Flash-0731-GGUF) `UD-Q4_K_XL` + Q8_0 DSpark | ~166 GB | 2× 96 GB | Quality-credible 0731 successor; b10362 `draft-dspark`, max 5, f16 K/V, verified 4×384K with headroom. |
| `glm-5.2` | [unsloth/GLM-5.2-GGUF](https://huggingface.co/unsloth/GLM-5.2-GGUF) `UD-Q4_K_XL` | ~467 GB (11 shards) | 6× 96 GB (5× very tight) | Full, non-pruned GLM-5.2. Best quality, no REAP loop tax. |
| `glm-5.2-reap` | [0xSero/GLM-5.2-REAP-504B-GGUF](https://huggingface.co/0xSero/GLM-5.2-REAP-504B-GGUF) `Q4_K_XL` | ~308 GB (8 shards) | 4× 96 GB | REAP 34%-expert-pruned. Fits in 4 cards, but per the card the loop rate roughly doubles (3.6%→7.2%) and the DSA indexer tensors are faked (duplicated from the nearest full layer) to load — no DSA speedup. Prefer `glm-5.2` if you have the 6th card. |

The Preview-era DeepSeek route has the measured load/context points above. The
generated 0731+DSpark route has also been owner-verified at 4×384K with
headroom on 2×96 GB. Its wider client-contract, template, DSpark-acceptance,
and sustained-concurrency gates still apply. The GLM 5.2 presets remain
untested on target hardware and require their first-boot gates below:
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
  `ctx-size` ≥ ~384K per request. The Preview route ships one 384K slot; the
  0731+DSpark route ships four 384K slots and therefore covers the Think-Max
  threshold for every concurrent request. The
  official chat encoding is a Python encoder, not jinja —
  antirez's "chat-v2" GGUF embeds a template (`jinja = true` uses it), worth
  eyeballing that turns render correctly.
- `glm-5.2` / `glm-5.2-reap` use `temp = 1.0`, `top-p = 0.95`, `min-p = 0.01`,
  `top-k = 0` — unsloth's and Z.ai's published GLM-5.2 settings (Z.ai advises
  tuning only one of temp/top_p). This repo's GLM-4.x presets use `temp = 0.7`,
  but that was a 4.x-specific choice; GLM-5.2's own recommendation is 1.0. If
  generation doesn't stop cleanly (the GLM EOG-token issue in "Known upstream
  issues"), dropping temp toward 0.6 is the known lever.
- The preserved Preview-era DeepSeek preset remains target-only. The generated
  0731 route is separate and uses the checkpoint's DSpark head with
  `spec-type = draft-dspark`; do not relabel it as MTP. b10362 contains the
  required PR #25784 support. Its Q8_0 companion adds about 10.9 GB; the
  measured 2×96 GB deployment still retained headroom at four 384K slots.
- Multi-GPU: weights split across both GPUs by default (layer split) — confirm
  with `nvidia-smi` that both cards show the target and, for 0731, the DSpark
  companion after load (~76 GB/card for the old target alone; roughly
  ~83 GB/card aggregate for the new target+draft before buffers). But the
  prefill **compute buffer** is a single per-device
  allocation that can't be split or pooled across GPUs (NVLink is bandwidth, not
  shared memory), so "add/link GPUs" does not help it. If it OOMs, shrink it via
  `ubatch-size` / `ctx-size` (see the batch note above). `tensor-split` can't
  rescue it either: 153 GB of weights already forces both 96 GB cards near-full,
  so you can't bias enough weight off device 0 to make room for a big buffer.

## Image runtime

`docker/stable-diffusion-cpp/` wraps upstream stable-diffusion.cpp rather than
ComfyUI. Its supported public surface is deliberately small:
`GET /health`, `GET /v1/models`, `POST /v1/images/generations`, and
`POST /v1/images/edits`. Do not claim the native asynchronous `/sdcpp/v1` or
WebUI `/sdapi/v1` surfaces until the router has a durable job-to-worker
lifetime contract.

The upstream server loads exactly one pipeline at process start and reports a
generic model id. PreFer's Python router owns the real catalog and starts a
private worker lazily for the request's `model`. Discovery must remain
side-effect free: `/v1/models` must never download, warm, or load a model.
Prestaging runs in the background and publishes state through `/health` and
the catalog. A request waits only for its selected artifacts. The router
serializes generation/editing, retains at most one worker, swaps on model
change, and unloads after 30 idle minutes.

Image catalog ownership mirrors the other generated runtimes:

- `runtime.json` pins the upstream CUDA image index, platform manifest, and
  source revision.
- `models/<family>/<model>/model.json` owns request ids, capabilities,
  licenses, lineage, runtime flags, and a quant dictionary. Every pipeline
  component has an immutable repository revision, exact path, size, SHA-256,
  role, and server argument.
- `deployment-bundles.json` owns `general`, `fast`, `generation`, `edit`, and
  `quality` groupings.
- `deployment-scenarios/` owns AWS, RunPod, and generic local hardware lane
  selection. Its compact source files may describe multiple hardware variants;
  generated configs still live under
  `server-configs/<provider>/<gpu>/<count>/` with sibling `.prestage` files.
- `generate.py` emits every server config, prestage sidecar, the integrity-
  checking downloader, and `deployment-inventory.generated.json`. CI runs it
  with `--check`.

The release inventory is embedded at `/deployment-inventory.json`, labeled
with schema `prefer.image-deployment-inventory.v1`, and uploaded as
`prefer-image-deployment-inventory-<commit-sha>`. NeurOn should select
`IMAGE_SERVER_CONFIG` and leave `IMAGE_PRESTAGE_MODELS` blank to follow its
sidecar. A nonblank override wins; `none` intentionally skips downloads. The
local Compose route is Hugging Face-only and does not pass S3 settings.

Current request ids are `flux-2-klein-4b`, `z-image-turbo`, `qwen-image`,
`qwen-image-edit-2511`, and `sdxl-1.0`. Qwen Image Edit 2511 must keep
`--model-args qwen_image_zero_cond_t=true`. Its supported stable-diffusion.cpp
recipe uses the BF16 Qwen 2.5 VL encoder and no separate projector; do not
substitute a GGUF encoder/projector pair without a matched smoke. SDXL
advertises generation plus maskless img2img through the edit endpoint; it does
not advertise masks, inpainting, or ControlNet because stable-diffusion.cpp's
current documentation limits the known ControlNet path to SD 1.5. Adding those
capabilities requires an exact pinned model/runtime smoke rather than inference
from SDXL support.

The pinned upstream CUDA base is
`ghcr.io/leejet/stable-diffusion.cpp:master-cuda@sha256:dcd82f38252a32822dcd0c80672d5948df8e63bb4a3064988e0f7c2bec10c100`
at source `be0e34480dada95f8ce9a021bbb95c5de85d67c7`. It currently provides
Linux AMD64 only. The release workflow must not advertise ARM64 or pin the
moving tag without its immutable digest. The image tags are `image-cuda12`
and `image-cuda12-sha-<commit>`; they do not alter llama.cpp's `latest` tags.

All initial image hardware routes are `configuration-only`. Before promotion,
smoke the exact card/runtime/artifact tuple for load, output integrity,
generation/edit behavior, peak VRAM/RAM, and swap/unload. Preserve the open
FLUX.2 Klein metadata-validation contradiction as VERIFY until the pinned CUDA
tuple produces a non-corrupt image. Pascal configs also require confirmation
that the upstream image contains working `sm_61` kernels.

## Known upstream llama.cpp issues (not fixable via our config)

- **#22789 (fixed in current b10362)** — DeepSeek V4 0731 plus DSpark could
  exceed llama.cpp's fixed 30 split-graph input slots during multi-GPU graph
  reservation and abort at `GGML_SCHED_MAX_SPLIT_INPUTS`. PR #22789 replaces
  the fixed arrays with dynamic allocation. This is an upstream scheduler
  defect: context, batching, tensor split, and GPU count are not reliable
  configuration workarounds.
- **#25148 (fixed in current b10362)** — Gemma E4B's MTP draft has 512-wide K/V
  heads and GQA ratio 2. On Pascal, b9843 selects the generic CUDA
  FlashAttention tile kernel, whose 512-wide specialization only compiled GQA
  ratios 4 and above; it aborts at `fattn-tile.cuh:1321`. E2B's draft is ratio
  4 and works. `flash-attn = off` is not a drop-in workaround on the 8/12 GB
  presets because their quantized V cache requires FlashAttention. The explicit
  `12gb-pascal.ini` compatibility preset keeps q4_0 K/V, FlashAttention, model
  identity, and all other 12 GB settings but omits only E4B's `model-draft` /
  `spec-*` keys. Cost: E4B loses MTP speculative throughput on that preset.
  `12gb.ini`, `8gb.ini`, and `96gb.ini` retain E4B MTP unchanged. Current
  b10362 contains the upstream fix, so the compatibility preset is now only a
  rollback/reproduction lane. Its target-only path is measured on b10362, but
  E4B's MTP-on path still needs a direct Pascal smoke before removing the
  compatibility distinction.
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

96gb has no VRAM pressure for the normal one-loaded-model path (unlike
12gb/8gb), so there's no real downside to trade off there. The caveat is that
f16 KV cache is ~4x q4_0's size if an operator raises `models-max` and retains
several models. None of the tier entries uses `load-on-startup`; the normal
Compose/auto-detected default is 1, so the current path does not hold every
configured model at once. A 96 GB `models-max=4` run remains unmeasured. If it
doesn't fit, q8_0 would be the fallback for gemma at minimum (still better than
q4_0's KL 1.088, though q8_0's 0.377 isn't great either) while keeping f16 for
Qwen/GLM if their headroom allows.

## Qwen sampling: `presence-penalty`

Qwen3.8-27B's default thinking profile recommends `presence_penalty = 0.0`
alongside `temp=1.0, top_p=0.95, top_k=20`, exactly matching its PreFer route.
Older Qwen guidance also proposed `presence_penalty = 1.5` to avoid loops in
some non-thinking or long-reasoning configurations, but
presence penalty applies to *every* token seen so far in the context,
regardless of whether repeating it is a loop or legitimate verbatim reuse
(e.g. an agent re-typing the same file path). This is a documented tension
in the Qwen community itself, not unique to our setup. Since the
`dry-allowed-length = 24` change above covers the same "long reasoning loop"
failure mode more precisely (only penalizing actual repeated *sequences*,
not all repeated tokens), Qwen's `presence-penalty` remains `0.0` across
all presets, relying on DRY as the targeted loop mitigation. If long-reasoning
loops reappear on Qwen without presence_penalty, that'd be the first thing to revisit —
either raise `presence-penalty` back up (accepting the agentic-output risk)
or tune DRY further before doing so.

## `n-cpu-moe` tuning status

- **`96gb.ini`**: `n-cpu-moe = 0` for all three models — confirmed working
  (all three load and generate correctly).
- **`12gb.ini`**: the preset now mirrors the `96gb.ini`/`8gb.ini` router id
  shape and uses `ctx-size = 0` for native context. The failed Qwen 35B YaRN
  1M section has been removed. Legacy 64k smoke tests on Titan X Pascal confirmed
  gemma-4-26B-A4B and GLM could load/generate, but the current native-context
  entries are still heuristic: gemma-4-26B-A4B uses `n-cpu-moe=20`, Qwen3.6
  35B uses `n-cpu-moe=26`, and GLM uses `n-cpu-moe=18`. Qwen3.8 27B is dense,
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
- Unsloth publishes separate `Qwen3.5-9B-GGUF` and `Qwen3.5-9B-MTP-GGUF`
  repositories. The MTP repository's documented llama.cpp path does not yet
  support `--parallel > 1` or `--mmproj`, so the AWS g6 route deliberately uses
  the non-MTP repository without speculative settings to retain two-way
  concurrency and vision. The prior combination of non-MTP GGUF plus
  `draft-mtp` was measured on b10257 to abort with
  `context type MTP requested but model doesn't contain MTP layers`.
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
  drafter files themselves are confirmed present. The only exception is the
  explicit `12gb-pascal.ini` compatibility preset, which disables E4B's draft
  to avoid b9843's upstream ratio-2 tile crash; E2B still uses MTP there.

  **Measured 2026-07-14 on b9843 / Titan X Pascal:** E2B loaded and passed the
  contract, strict structured cases, tools, and calibrated 8K retrieval. E4B
  failed on both `models-max=1` and `4` at llama.cpp's CUDA flash-attention tile
  assertion (`fattn-tile.cuh:1321`). Exact GGUF metadata and a b9843 source
  trace identified the E4B draft's 512-wide GQA-ratio-2 specialization as the
  cause; upstream PR #25148 confirms and fixes that exact case. Disabling flash
  attention on the 12 GB preset still conflicts with its q4_0 V cache, so the
  explicit no-E4B-draft compatibility preset is the b9843/Pascal fallback.
  Scrubbed evidence is under `benchmark/baselines/`.

## Audio and image artifact downloads

Audio and image deliberately share transfer behavior without sharing a Docker
build context. `docker/audio-cpp/download-artifacts.sh` and
`docker/stable-diffusion-cpp/download-artifacts.sh` are checked-in,
byte-for-byte copies; the downloader integration test enforces that parity.
Keep both copies in the same change. Moving the helper to a root-level common
path would require changing both Docker build contexts and both workflow path
filters, otherwise a helper-only change could publish neither runtime. The
generated `model-downloads.generated.sh` files remain runtime-owned maps from
model keys to immutable artifact IDs and exact transfer metadata.

Both runtime images install the same `hf` CLI used by llama.cpp, keep
`HF_HOME` on their own `/models` volume, and enable Xet high-performance mode
by default. Audio and image do not inherit llama's optional S3 cache. Compose
passes `HF_TOKEN`, `HF_HUB_DISABLE_XET`, and the existing `HF_XET_*` tuning
variables to each service. `AUDIO_DOWNLOAD_JOBS` and `IMAGE_DOWNLOAD_JOBS`
default to four and accept only 1 through 8. Generators reject two immutable
identities that target the same final repository/path; selected model keys are
resolved and deduplicated to artifact IDs before batches launch. Batches join
in catalog order, report the first failure in that stable order, and do not
launch a later batch after a failed one.

Each artifact uses a stable hidden staging directory under
`/models/.prefer-cache/downloads-v2/`. `hf download --local-dir` owns its
resumable `.incomplete` state there; never add PID-scoped cleanup or delete the
staging tree on transfer failure. A completed staging file must pass the
catalog byte size and SHA-256 before `mv` atomically replaces the final path on
the same volume. An invalid staged *completed* file may be removed so the next
`hf` call repairs it, but any separate `.incomplete` state is retained. An
invalid existing final remains in place until its verified replacement is
ready, so a failed repair cannot destroy the prior path.

Successful publication writes an atomic `downloads-v2/verified` marker bound
to the artifact fingerprint and current device/inode/size. A file newer than
its marker is rehashed. Existing installations without markers pay one exact
SHA-256 pass, then unchanged restarts use the marker instead of rescanning
multi-gigabyte files. A crash after file publication but before marker
publication is safe: the next run hashes the final and repairs the marker.

Image prestaging remains a background child and must never delay router
discovery. The router reports a requested artifact staged only when its exact
size and marker match while prestaging is active; this prevents a same-sized
corrupt file from being loaded during repair. After a successful empty
`IMAGE_PRESTAGE_MODELS=none` pass, an exact-size legacy file without a marker
remains usable, preserving the explicit no-download contract. A stale marker
never gets that fallback. Requests can proceed as soon as all artifacts for
their selected model are published even when unrelated background jobs remain.

## S3 model cache (`S3_BUCKET_NAME`)

`download-models.sh` has an optional S3 layer gated on `S3_BUCKET_NAME`.
Independent catalog model keys stage concurrently (`MODEL_DOWNLOAD_JOBS`, four
by default with S3) and all foreground jobs join before `llama-server` starts.
Per-model completion markers under
`s3://$BUCKET/.prefer-cache/downloads-v1/` carry the generated catalog
fingerprint, bucket, last-check epoch, and observed exact-artifact sizes. A
fresh marker skips Hugging Face's large-file verification after the filtered S3
copy validates those sizes; missing, stale, mismatched, or incomplete markers
fall back to `hf download` and self-repair. The default seven-day TTL is
`MODEL_CACHE_RECHECK_DAYS=7`; zero forces every-launch revalidation, and deleting
one marker forces just that model key. Catalog changes invalidate markers
immediately through their fingerprint.

S3 download copies each exact catalog artifact key directly rather than using
include/exclude filters; background upload sends those same exact artifacts and
publishes the marker last. Stale locks are removed before HF, then `/models/xet`
and S3-mode per-repo `.cache`
directories are removed after the foreground join. Old remote `.cache` objects
are intentionally not deleted automatically, but exact copies make them inert.
Unset `S3_BUCKET_NAME` (local / RunPod) remains HF-only and sequential by
default. Needs `s5cmd` (installed in the Dockerfile); credentials come from the
AWS chain (env / instance role). S3 was chosen over a persistent EBS volume
because a single EBS volume caps at 1 GB/s while S3 via s5cmd is NIC-bound at
multiple GB/s.

## EC2 deployment (`aws/`)

Self-serve EC2 launch lives under `aws/` (design + rationale in `aws/DESIGN.md`):
a Packer-built public AMI (DLAMI Base GPU Ubuntu 24.04 base, resolved via SSM) +
systemd boot unit (stage instance-store NVMe at `/opt/dlami/nvme`, `docker run`
with `/models` on NVMe) + a CDK stack distributed as synthesized CloudFormation.
The container is pulled at boot (not baked), and CI is path-filtered so AWS
changes never rebuild the container (`build-prefer.yml` is `docker/llama-cpp/**`
only; `build-aws.yml` covers `aws/`). `build-aws.yml` is one workflow with
ordered jobs — a paths-filtered `ami` job (Packer; public AMI built into
us-east-1 + us-east-2) hands its `ami-map` artifact to a `cdk` job that bakes it
into the template's RegionMap and publishes the `template-latest` release. A
CDK-only change skips the AMI build and reuses the last release's map; nothing is
committed back. Don't reopen the settled calls there (S3-over-EBS, AMI base,
dlami-nvme, `--restart no`) without reading `aws/DESIGN.md` first.

The AMI boot contract deliberately separates immutable defaults from
deployment values. `/opt/prefer/prefer-boot.env` is baked and must not be
mutated by user-data; cloud-init writes `/opt/prefer/deployment.env` instead.
`prefer-boot.service` is ordered after `cloud-final.service`, reads the
deployment file second, and is enabled under `cloud-init.target` rather than
`multi-user.target`: the DLAMI orders `cloud-final` after `multi-user`, so the
latter would form a dependency cycle and systemd would drop the PreFer start
job. The unit launches the container once. User-data must never
start or restart `prefer-boot.service`: doing so reintroduces the first-boot
default-preset race. Normal shell user-data may write the deployment file and
exit; the service owns startup afterward.

## Testing

The measurement-first harness under `benchmark/` and `prefer_bench/` has a
dependency-free automated suite for schemas, fixtures, parsers, aliases,
reports, semantic anomaly classification, negative contract cases, and Compose
isolation. Ordinary CI never launches a GPU server or downloads a model.

Run the deterministic suite and mock replay:

- `python -m unittest discover -s benchmark/tests -v`
- `python -m prefer_bench validate`
- `python -m prefer_bench contract --mock`

Live verification remains hardware-dependent. The isolated command creates a
generated Compose project, loopback port other than 8080, network, and cloned
model volume, then removes all of them while leaving the operator llama service and
NeurOn state alone. See `benchmark/README.md` for current b10362, the historical
Pascal compatibility preset, `models-max`, long-context, idle, and historical
b9843/b9982 evidence.

Other useful manual checks:

- `docker compose config` — verify env var resolution (especially
  `LLAMA_ARG_MODELS_PRESET`/`LLAMA_ARG_MODELS_MAX`) before `up`.
- `docker compose run --rm prefer /download-models.sh` — pre-warm the
  model cache without starting the GPU server.
- `GET /v1/models` and a minimal `POST /v1/chat/completions` per model id —
  confirm a preset's models load and respond.

Any future live smoke job still needs a GPU host; no CPU-only fallback is
practical for the normal model tiers.

## audio.cpp sibling runtime

`docker/audio-cpp/` is deliberately separate from the llama router. The GHCR
product remains `ghcr.io/cvalusek/prefer`, but runtime tags do not overlap:
`audio-cuda12`, `audio-cuda12-sha-<commit>`, `audio-cpu`, and
`audio-cpu-sha-<commit>`. The llama workflow retains `latest` and
`sha-<commit>` for compatibility and also publishes `llama-cuda` and
`llama-cuda-sha-<commit>`. Never point `latest` at audio.cpp.

The local Compose service key remains `prefer` for command compatibility, but
its container is `prefer-llama`. The default Compose application also runs
`prefer-audio` on host port 8081. Target `docker compose up prefer` or
`docker compose up audio` when only one runtime should run. Audio models and
server-side voice references use separate named volumes. Both services request
the available NVIDIA GPUs, so operators must account for aggregate residency
when they intentionally load llama and audio models at the same time.

`docker/audio-cpp/runtime.json` owns the immutable upstream audio.cpp source
and dual-platform CPU/CUDA image identities. Per-model files under
`models/<family>/<model>/model.json` own official lineage plus either one exact
artifact or a same-repository multi-file package, byte sizes, SHA-256 values,
optional package-level server path, task, mode, and request id. `generate.py`
also reads `deployment-bundles.json` and
`deployment-scenarios/<provider>/<hardware>.json`, then emits both backend
defaults, nested `server-configs/` plus paired `.prestage` manifests, the exact
resumable downloader, and `deployment-inventory.generated.json`; CI requires
`generate.py --check`.
No model bytes or Git LFS pointers belong in this repository.

The audio inventory owns backend-level CUDA 12 and CPU deployments plus CUDA
scenario trees for AWS G6/G6e, generic local cards, and exact one-card RunPod
24-48 GB offers. `general` exposes every capability for exploration. `speech`,
`assistant`, `voice-lab`, `conversation`, and `music` group related routes,
and every supported route has a single-model alternative. All configs retain
one-model lazy residency: inclusion controls discoverability and prestaging,
not simultaneous GPU load. With `AUDIO_PRESTAGE_MODELS` blank, the entrypoint
uses the `.prestage` sidecar paired with `AUDIO_SERVER_CONFIG`; an explicit
model list or `none` still wins. Only the CUDA image contains provider scenario
configs, and inventory scenario entries point to `audio-cuda12`.

AWS audio scenarios cover `g6.xlarge` (L4 24 GB) and `g6e.xlarge` (L40S 48
GB). RunPod scenarios cover the exact current 24/32/48 GB card IDs already used
by the llama inventory: L4, RTX 3090/4090/5090, RTX A5000/A6000, A40,
L40/L40S, RTX 6000 Ada, and RTX PRO 6000 MIG 24/48 GB. Generic local profiles
cover RTX 4060 8 GB, RTX A2000 8 GB, GTX 1070 Ti, and TITAN X Pascal without
private host metadata. The 8 GB and GTX 1070 Ti profiles expose only the four
Qwen speech/voice models; TITAN X exposes the full catalog based on the owner
smokes below. A route appearing in a configuration-only scenario is not proof
of fit, useful latency, or quality on that exact card.

Every audio release embeds the resolved catalog at
`/deployment-inventory.json`, identifies it with OCI path/schema labels, and
uploads `prefer-audio-deployment-inventory-<commit-sha>`. NeurOn should use the
inventory's provider hardware ID, image tag, `AUDIO_SERVER_CONFIG`, model IDs,
staged artifact bytes, compatibility, and verification status rather than
parsing these docs or guessing from VRAM.

The audio catalog selects Qwen3 TTS 12Hz 0.6B Base BF16, Qwen3 TTS 12Hz 1.7B
CustomVoice BF16, Qwen3 TTS 12Hz 1.7B VoiceDesign BF16, Qwen3 ASR 0.6B Q8_0,
ACE-Step 1.5 Turbo Q8_0, MiniMax Music 3's mixed Q4_0/Q8_0 package, and
PersonaPlex 7B Q4_K. TTS stays BF16 because the modest savings from Q8 do not
justify assuming audible parity. The Base checkpoint is a voice-cloning route,
so callers must supply `voice_ref` and `reference_text` or use a server-side
voice library; do not document it as a generic built-in voice. CustomVoice uses
packaged speaker ids and optional style instructions. VoiceDesign uses the
framework `vdes` task plus an instruction and requires no reference audio. ASR
is configured in streaming mode so the same id can serve normal
uploads and the live PCM endpoint. ACE-Step and MiniMax run through
`/v1/tasks/run`; MiniMax remains experimental upstream. PersonaPlex runs
full-duplex conversation through `/v1/audio/speech/live`, is English-only, and
uses its own 7B conversational intelligence rather than the llama service.
The ACE-Step and MiniMax server/catalog `task` value is `gen`; `music` is the
model-spec capability label, not an accepted framework task kind.
ACE-Step enables its memory-saver session option for local 12 GB headroom.
MiniMax explicitly selects the packaged Q4 language model, Q8 depth decoder,
and Q4 flow transformer; its generic session default names a BF16 depth decoder
that is not present in the selected balanced package.
PersonaPlex Q4 sets `personaplex.graph_arena_mb=512`. On the local TITAN X
Pascal, that setting completed both a direct one-second speech-to-speech path
and the server's chunked-PCM/SSE live route at 24 kHz mono. The live smoke
emitted 12 audio deltas, `speech.audio.done`, and `[DONE]`; its reconstructed
output was a valid 0.96-second, 24 kHz mono WAV. This is an API/load/fit smoke,
not a conversation-quality result. The default 1 GiB arena is unnecessary for
this bounded route.
The CUDA server's generic pre-load memory guard is disabled because its fixed
`1.5x` single-file estimate reports 11.11 GiB for the 7.86 GB artifact and
rejects it before applying the smaller arena, despite the measured fit. Keep
`max_loaded_models=1`; do not re-enable the generic guard until upstream can
account for effective per-model memory settings or provide a safe override.

Both Qwen 1.7B BF16 routes passed local TITAN X Pascal load/generation and LRU
swap smokes on the pinned runtime. CustomVoice accepted packaged speakers
`Vivian` and `Ryan` plus style instructions through `/v1/audio/speech` and
produced a valid 4.32-second 24 kHz mono WAV. VoiceDesign accepted the native
`vdes` request through `/v1/tasks/run` without reference audio and produced a
valid 4.72-second 24 kHz mono WAV. Observed whole-device usage was 4,758 MiB
with CustomVoice resident and 5,028 MiB with VoiceDesign resident on the 12,288
MiB card. These are fit/API smokes, not voice-quality or latency benchmarks.

With both audio selection variables unset or blank, the entrypoint uses the
all-capabilities default and stages every generated primary package. A selected
`AUDIO_SERVER_CONFIG` changes that blank default to its paired prestage
manifest. A comma-separated `AUDIO_PRESTAGE_MODELS` value overrides either
default; `none` intentionally skips downloads. Multi-file packages must stay within one
immutable repository revision and are only considered staged after every file
passes its catalog byte-size and SHA-256 check.
The full generated default is about 34.5 GB, so both audio images use a four-hour
health-check start period. A successful check still marks the server healthy
immediately; the long grace only prevents slow first-boot staging from becoming
a false failure.

Both configs register models lazily, set `max_loaded_models=1`, and unload an
idle resident model after 30 minutes. This allows audio-route swapping on small
devices; it is not a concurrency claim. audio.cpp serializes calls per model,
and new audio routes remain configuration-only until exact-card load, quality,
API, and latency smoke tests pass. The upstream management UI is not enabled:
PreFer stages only its pinned catalog artifacts and verifies size plus SHA-256.
