# PreFer Container

A llama.cpp router container hosting Gemma 4, Qwen3.5/Qwen3.6/Qwen3.8, Muse Glimmer,
GLM, and DeepSeek V4.

Published hosted-model and preset changes are recorded by immutable container
SHA in the repository [changelog](../../CHANGELOG.md).
On first start it downloads the models from Hugging Face, then serves them
via `llama-server`'s router mode (the repository's narrow tested OpenAI-style
contract on port 8080; see [`benchmark/README.md`](../../benchmark/README.md)).

Base image: pinned to
`ghcr.io/ggml-org/llama.cpp:server-cuda-b10362@sha256:182a26fbd68d1774860bd2a0fb5581ba3047974307eaeee64930d8bf889e0c0c`
(source `4801e3c567d5131dd41b387df5f2d4b1370d92be`). It includes DeepSeek V4
MTP/DSpark PR #25784, dynamic split-graph input allocation from PR #22789,
the Gemma E4B MTP fix, and Muse target/projector/DFlash support from PR #26841.
See AGENTS.md "Base image".

llama.cpp publishes source releases before all container architectures finish.
The corresponding image may take hours to appear, and an intermediate image
tag may be skipped in favor of a higher build. PreFer therefore pins the first
versioned multi-platform CUDA image whose source revision contains the required
changes; it does not require a same-number source/image pair or pin the moving
`server-cuda` tag.

The generated Muse presets are runtime-supported on b10362. Its source is 13
commits after PR #26841's merge
(`62bf73d25c53b8161f8a22894d4f90c4aebbd7d0`). Their first deployment still
needs fit, contract, DFlash, projector, and concurrency verification on each
target GPU shape.

## Presets

On startup, `detect-preset.sh` reads the GPU's total VRAM (`nvidia-smi`) and
picks the largest `presets/<N>gb.ini` whose tier fits, falling back to the
smallest tier if VRAM is below all of them. Override with
`LLAMA_ARG_MODELS_PRESET=/presets/<name>.ini` (and optionally
`LLAMA_ARG_MODELS_MAX`) to force a specific preset.

AWS scenario presets are generated under `presets/aws/` and are always
selected explicitly. Edit `preset-catalog.json` for model/artifact facts and
`preset-scenarios/aws.json` for deployment shape, then run:

```bash
python docker/prefer/generate-presets.py
python docker/prefer/generate-presets.py --check
```

Do not hand-edit generated `.ini`, `.prestage`, or
`model-downloads.generated.sh` files.

| Preset | VRAM tier | Models | `models-max` | Notes |
| ------ | --------- | ------ | ------------- | ----- |
| `96gb.ini` | ~96GB | Gemma 4 26B/E2B/E4B, Qwen3.6 35B/27B, GLM-4.7-Flash | `1` on normal Compose/auto-detect paths | `n-cpu-moe = 0`; models load on demand |
| `12gb.ini` | ~12GB | Same model ids as `96gb.ini`, swap-on-demand | `1` | Per-model `n-cpu-moe` (12-26), `mmap = false`, `sleep-idle-seconds = 1800` |
| `12gb-pascal.ini` | ~12GB Pascal compatibility | Same model ids as `12gb.ini`, swap-on-demand | `1` on normal Compose when explicitly selected | Identical to `12gb.ini` except E4B MTP is disabled; never auto-detected |
| `8gb.ini` | ~8GB | Same model ids as `96gb.ini`, swap-on-demand | `1` | Higher `n-cpu-moe` (18-32), same `mmap`/sleep settings |

### Generated AWS scenarios

`ctx-size` is a total cache divided across `parallel` slots. Every normal AWS
route therefore keeps at least 128K per request, and every AWS scenario uses
f16 K and f16 V. Each `general.ini` is cumulative: it contains the best
host-appropriate lane for models assigned to that instance tier and every
lower tier. A model with multiple catalog quants appears only once; Muse, for
example, uses Q4 on g6 and Q6 on g6e/g7e.

| Preset | Instance | Models | Per-request context / concurrency |
| ------ | -------- | ------ | --------------------------------- |
| `aws/g6/xlarge/general.ini` | `g6.xlarge`, L4 24 GB | Gemma E2B/E4B/12B, Qwen3.5-9B, Muse Q4 | Gemmas 128K ×4; Qwen9 128K ×2; Muse 128K ×1 |
| `aws/g6e/xlarge/general.ini` | `g6e.xlarge`, L40S 48 GB | All g6 routes plus Gemma 26B/31B, Qwen3.6 35B/27B, Muse Q6 | See the instance matrix below; 128K minimum |
| `aws/g6e/xlarge/gemma.ini` | `g6e.xlarge`, L40S 48 GB | Gemma 26B-A4B, 31B | 26B 256K ×2; 31B 256K ×1 |
| `aws/g6e/xlarge/qwen.ini` | `g6e.xlarge`, L40S 48 GB | Qwen3.6 35B-A3B/27B Q6 | 192K ×1 each |
| `aws/g7e/2xlarge/general.ini` | `g7e.2xlarge`, RTX PRO 6000 96 GB | All g6e routes plus GLM-4.7-Flash | 26B/31B/Qwen3.6 at native context; GLM at max; smaller lanes inherited |
| `aws/g7e/2xlarge/gemma.ini` | `g7e.2xlarge`, RTX PRO 6000 96 GB | Gemma 26B-A4B, 31B | 26B 256K ×4; 31B 256K ×2 |
| `aws/g7e/2xlarge/qwen.ini` | `g7e.2xlarge`, RTX PRO 6000 96 GB | Qwen3.6 35B-A3B/27B | 256K ×4 each |
| `aws/g7e/12xlarge/deepseek-v4-flash-0731.ini` | `g7e.12xlarge`, 2× RTX PRO 6000 96 GB | DeepSeek V4 Flash 0731 | 384K ×4, DSpark enabled |
| `aws/g6/xlarge/muse.ini` | `g6.xlarge`, L4 24 GB | Muse Glimmer 30B `UD-Q4_K_XL` | 128K ×1, DFlash enabled |
| `aws/g6e/xlarge/muse.ini` | `g6e.xlarge`, L40S 48 GB | Muse Glimmer 30B `UD-Q6_K_XL` | 128K ×2, DFlash enabled |
| `aws/g7e/2xlarge/muse.ini` | `g7e.2xlarge`, RTX PRO 6000 96 GB | Muse Glimmer 30B `UD-Q6_K_XL` | 128K ×4, DFlash enabled |

The exact cumulative `general.ini` matrix is:

| Model lane | g6 | g6e | g7e |
| ---------- | -- | --- | ---- |
| Gemma E2B QAT Q4 | 4×128K | 4×128K | 4×128K |
| Gemma E4B QAT Q4 | 4×128K | 4×128K | 4×128K |
| Gemma 12B QAT Q4 | 4×128K | 4×128K | 4×128K |
| Gemma 26B-A4B QAT Q4 | — | 2×256K | 4×256K |
| Gemma 31B QAT Q4 | — | 1×256K | 2×256K |
| Qwen3.5-9B Q4 | 2×128K | 2×128K | 2×128K |
| Qwen3.6-35B-A3B Q6 | — | 1×192K | 4×256K |
| Qwen3.8-27B Q6 | — | 1×192K | 4×256K |
| Muse Glimmer 30B | Q4 1×128K | Q6 2×128K | Q6 4×128K |
| GLM-4.7-Flash Q6 | — | — | 4×202,752 |

The original four-host shape uses 4 + 4 + 8 + 48 = 64 vCPUs. Family presets
are alternatives to the corresponding cumulative `general.ini`, not extra
simultaneous hosts. Each
generated preset has a sibling `.prestage` manifest; selecting the preset
stages exactly its model keys unless `PRESTAGE_MODELS` is set to a nonblank
override. A cumulative `general.ini` therefore stages its complete inventory;
use a family or single-model preset when that transfer and startup work is not
wanted.

For controller-owned hosts, each bundled route also has a dedicated preset.
It preserves the bundle's effective model, context, parallelism, cache,
sampling, projector, and speculative-decoding settings, while containing one
model section, staging one catalog key, and loading that model at startup.

| Instance | Dedicated single-model presets |
| -------- | ------------------------------ |
| `g6.xlarge` | `gemma-e2b.ini`, `gemma-e4b.ini`, `gemma-12b.ini`, `qwen-9b.ini`, `muse.ini` |
| `g6e.xlarge` | `gemma-26b-a4b.ini`, `gemma-31b.ini`, `qwen-35b-a3b.ini`, `qwen-27b.ini`, `muse.ini` |
| `g7e.2xlarge` | `gemma-26b-a4b.ini`, `gemma-31b.ini`, `qwen-35b-a3b.ini`, `qwen-27b.ini`, `glm-4.7-flash.ini`, `muse.ini` |

The family bundles remain supported. Prefer a dedicated preset when NeurOn or
another controller already knows the model assigned to the instance; unused
router sections have caused undesirable startup overhead even with bounded
prestaging and `models-max`.

Muse's Q4/Q6 target, DFlash drafter, and quantized projector are all pinned to
`unsloth/Muse-Glimmer-30B-GGUF@faa5b025c584459c13febfa5c59883516710ae39`.
The exact three-file payload is 18.91 GB for Q4 and 29.30 GB for Q6 before
runtime/KV. `spec-draft-n-max = 15` matches the DFlash model's trained
16-token block. Sampling is `temp=1.0`, `top_p=0.95`, `top_k=64`, with
llama.cpp's extra `min_p` filter disabled. All three shapes use f16 K/V. The
All three Muse shapes use the publisher-default 128K per request. The 96 GB
route spends its additional memory on four concurrent slots instead of an
extended 256K position range.

All presets share `dry-multiplier = 0.8`, `dry-base = 1.75`,
`dry-allowed-length = 24` (DRY sampling) as a mitigation against repetition
loops, particularly relevant to Gemma 4's tool-calling.

### Historical 12 GB Pascal compatibility

The old b9843 CUDA image predates llama.cpp PR #25148. Gemma
E4B's main GGUF uses a supported GQA ratio of 4, but its MTP draft uses
512-wide K/V heads at GQA ratio 2. Pascal selects b9843's generic
FlashAttention tile kernel, which aborts for that exact draft shape. E2B's MTP
draft is ratio 4 and remains healthy.

Current b10362 contains the fix. Keep
`LLAMA_ARG_MODELS_PRESET=/presets/12gb-pascal.ini` only as a rollback or old
result reproduction lane until a b10362 Pascal smoke is recorded. The preset
preserves q4_0 K/V cache, FlashAttention, model
identity, aliases, context, and every non-E4B setting; it removes only E4B's
`model-draft` and `spec-*` keys. The cost is lower E4B throughput from losing
speculative decoding. `12gb.ini`, `8gb.ini`, and `96gb.ini` are unchanged, and
the compatibility preset is deliberately outside the `<N>gb.ini` auto-detect
glob. Turning FlashAttention off is not an equivalent workaround because the
12 GB preset's quantized V cache requires it.

### `models-max` precedence

The normal checked-in Compose service passes
`LLAMA_ARG_MODELS_MAX=${LLAMA_ARG_MODELS_MAX:-1}`, so its effective default is
`1` for every selected preset, including `96gb.ini`. The example environment
also sets `1`.

Outside Compose, an explicit `--models-max` argument wins, then an existing
`LLAMA_ARG_MODELS_MAX` value. With neither set, auto-detection assigns `1` to a
tier preset that has no `load-on-startup` entry; all current 8/12/96 GB tier
presets meet that condition. If a preset is selected explicitly outside
Compose, detection leaves the setting alone and llama.cpp's router default of
`4` applies. The named presets each contain one model, so `4` does not make
them multi-model hosts.

The prior claim that 96 GB normally used `4` was inaccurate documentation. No
operational default was changed. Whether 96 GB should intentionally move from
`1` to a larger value remains a benchmarked owner decision; the harness exposes
`--models-max` as a run dimension.

### Large multi-GPU presets (named, not auto-detected)

These host a single multi-hundred-GB model on a dedicated multi-GPU box (one
model per host). They are **not** auto-detected — VRAM detection only reads the
first GPU — so you select one explicitly with
`LLAMA_ARG_MODELS_PRESET=/presets/<name>.ini`. Staging is automatic: when one of
these is the selected preset, `download-models.sh` defaults `PRESTAGE_MODELS` to
just that model, so you don't also need to set it (an explicit `PRESTAGE_MODELS`
value still overrides when it is nonblank). Sizes assume 96 GB/card (RTX PRO
6000 Blackwell).

| Preset | Model | On-disk | GPUs | Alias |
| ------ | ----- | ------- | ---- | ----- |
| `deepseek-v4-flash.ini` | DeepSeek-V4-Flash (antirez Q4 experts) | ~153 GB | 2× 96 GB | `deepseek-v4-flash` |
| `aws/g7e/12xlarge/deepseek-v4-flash-0731.ini` | DeepSeek-V4-Flash-0731 `UD-Q4_K_XL` + Q8_0 DSpark | ~166 GB | 2× 96 GB | `deepseek-v4-flash-0731` |
| `glm-5.2.ini` | GLM-5.2 full `UD-Q4_K_XL` (11 shards) | ~467 GB | 6× 96 GB | `glm-5.2` |
| `glm-5.2-reap.ini` | GLM-5.2 REAP-504B `Q4_K_XL` (8 shards) | ~308 GB | 4× 96 GB | `glm-5.2-reap` |

All run on the `b10362` base image. The generated 0731+DSpark route's 4×384K
allocation has been verified with headroom on 2×96 GB, although its wider
contract/template/DSpark concurrency gates remain. Muse and GLM 5.2 still need
their documented target-hardware gates. See AGENTS.md for the per-preset risk
notes (context sizing, `flash-attn`, DeepSeek sampling, GPU split).

### Tiny preset (named, not auto-detected)

| Preset | Model | On-disk | GPUs | Alias |
| ------ | ----- | ------- | ---- | ----- |
| `smol.ini` | SmolLM2-135M-Instruct `Q8_0` | ~145 MB | any/none | `smol` |

A single 135M dense model whose only job is to come up fast and light so the
companion app has something to smoke-test against — not tool calls, reasoning,
or real work. Like the large presets it is **not** auto-detected (no `<N>gb`
tier), so select it explicitly with
`LLAMA_ARG_MODELS_PRESET=/presets/smol.ini`; staging then defaults to just this
model.

## Models

All models download from Hugging Face on first start (see
`download-models.sh`) and land under `/models/<hf-org>/<hf-repo>/...`. Mount
a persistent volume at `/models` to avoid re-downloading on restart. The
layout means multiple presets/services can safely share one volume.

| Source repo | Quant | Notes |
| ------------ | ----- | ----- |
| [unsloth/gemma-4-26B-A4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF) | `UD-Q4_K_XL` | Includes `mtp-gemma-4-26B-A4B-it.gguf` and `mmproj-F16.gguf` in the same repo |
| [unsloth/gemma-4-E2B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E2B-it-qat-GGUF) | `UD-Q4_K_XL` | Includes `mtp-gemma-4-E2B-it.gguf` and `mmproj-F16.gguf` in the same repo |
| [unsloth/gemma-4-E4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-E4B-it-qat-GGUF) | `UD-Q4_K_XL` | Includes `mtp-gemma-4-E4B-it.gguf` and `mmproj-F16.gguf` in the same repo |
| [unsloth/gemma-4-12B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-12B-it-qat-GGUF) | `UD-Q4_K_XL` | Revision-pinned QAT target + same-repo Q4_0 MTP + F16 projector; AWS g6 |
| [unsloth/gemma-4-31B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-31B-it-qat-GGUF) | `UD-Q4_K_XL` | Revision-pinned QAT target + same-repo Q4_0 MTP + F16 projector; AWS g6e |
| [unsloth/Qwen3.5-9B-GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) | `UD-Q4_K_XL` | Revision-pinned target + F16 projector; no speculative decoding; AWS g6 |
| [unsloth/Qwen3.6-35B-A3B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF) | `UD-Q6_K_XL` | MTP draft is built into the main GGUF, no separate `model-draft` |
| [unsloth/Qwen3.8-27B-GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) | `UD-Q6_K_XL` | Revision-pinned target with MTP built into the main GGUF; no separate `model-draft` or projector is configured |
| [unsloth/Muse-Glimmer-30B-GGUF](https://huggingface.co/unsloth/Muse-Glimmer-30B-GGUF) | `UD-Q4_K_XL` / `UD-Q6_K_XL` | Revision-pinned target + `dflash-kquant.gguf` + `mmproj-kquant.gguf`; AWS 24/48/96 GB; requires b10362 or later |
| [unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF](https://huggingface.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF) | `UD-Q6_K_XL` | No speculative decoding |
| [antirez/deepseek-v4-gguf](https://huggingface.co/antirez/deepseek-v4-gguf) | `Q4KExperts...imatrix` | Preserved Preview-era target-only route |
| [unsloth/DeepSeek-V4-Flash-0731-GGUF](https://huggingface.co/unsloth/DeepSeek-V4-Flash-0731-GGUF) | `UD-Q4_K_XL` | Five pinned target shards + pinned Q8_0 DSpark companion; AWS 2×96 GB |
| [unsloth/GLM-5.2-GGUF](https://huggingface.co/unsloth/GLM-5.2-GGUF) | `UD-Q4_K_XL` | `glm-5.2` preset only; full (non-pruned), 11 shards |
| [0xSero/GLM-5.2-REAP-504B-GGUF](https://huggingface.co/0xSero/GLM-5.2-REAP-504B-GGUF) | `Q4_K_XL` | `glm-5.2-reap` preset only; 34%-pruned, 8 shards |
| [unsloth/SmolLM2-135M-Instruct-GGUF](https://huggingface.co/unsloth/SmolLM2-135M-Instruct-GGUF) | `Q8_0` | `smol` preset only; 135M dense, no draft/mmproj, ~145 MB |

## Router model ids

| Alias | Context | Presets |
| ----- | ------- | ------- |
| `gemma-4`, `gemma-4-26b-a4b` | g6e 256K ×2; g7e 256K ×4 | tier presets; g6e/g7e `general.ini`, `gemma.ini`, and `gemma-26b-a4b.ini` |
| `gemma-4-e2b` | 128K ×4 | tier presets; g6/g6e/g7e `general.ini`; g6 `gemma-e2b.ini` |
| `gemma-4-e4b` | 128K ×4 | tier presets; g6/g6e/g7e `general.ini`; g6 `gemma-e4b.ini` |
| `gemma-4-12b` | 128K ×4 | g6/g6e/g7e `general.ini`; g6 `gemma-12b.ini` |
| `gemma-4-31b` | g6e 256K ×1; g7e 256K ×2 | g6e/g7e `general.ini`, `gemma.ini`, and `gemma-31b.ini` |
| `qwen-3.5`, `qwen-3.5-9b` | 128K ×2 | g6/g6e/g7e `general.ini`; g6 `qwen-9b.ini` |
| `qwen-3.6`, `qwen-3.6-35b-a3b` | g6e 192K ×1; g7e 256K ×4 | tier presets; g6e/g7e `general.ini`, `qwen.ini`, and `qwen-35b-a3b.ini` |
| `qwen-3.8-27b` | g6e 192K ×1; g7e 256K ×4 | tier presets; g6e/g7e `general.ini`, `qwen.ini`, and `qwen-27b.ini` |
| `muse-glimmer`, `muse-glimmer-30b` | Q4 128K ×1; Q6 128K ×2 or ×4 | g6/g6e/g7e `general.ini` and `muse.ini` |
| `glm-4.7-flash` | 202,752 ×4 on g7e | tier presets; g7e `general.ini` and `glm-4.7-flash.ini` |
| `deepseek-v4-flash` | 393216 | `deepseek-v4-flash.ini` |
| `deepseek-v4-flash`, `deepseek-v4-flash-0731` | 393216 ×4 | `aws/g7e/12xlarge/deepseek-v4-flash-0731.ini` |
| `glm-5.2` | 262144 | `glm-5.2.ini` |
| `glm-5.2-reap` | 262144 | `glm-5.2-reap.ini` |
| `smol`, `smollm2-135m` | 8192 | `smol.ini` |

Full per-model sampling params and shared defaults live in the corresponding
`presets/<N>gb.ini` (or the named preset for the large multi-GPU models).

The bracketed preset section is the configured cross-system/model identity. On
measured b9843, `/v1/models` normalized Unsloth quantization tags (for example the E2B
configured ID ends in `:UD-Q4_K_XL`, while discovery reports `:Q4_K_XL`). The
normalized discovery ID and short alias routed PreFer requests; b9843 rejected
the configured UD identity as a request model. b10362 is current, but its exact
identity behavior remains a live verification item. These roles are versioned
separately in the client contract, and aliases are not promised as
`/v1/models` entries.

## Running

From the repo root:

```bash
docker compose up --build prefer
```

Relevant env vars (all read from your shell or a `.env` file in the repo
root; on Windows, prefer a `.env` file for path-shaped values like
`LLAMA_ARG_MODELS_PRESET`, since Git Bash mangles leading-`/` paths passed as
shell env vars):

- `LLM_PORT` - host port mapped to the container's 8080 (default `8080`)
- `PREFER_MODEL_VOLUME` - Docker volume mounted at `/models` (default
  `prefer-model-cache`)
- `HF_TOKEN` - optional, helps with Hugging Face rate limits
- `PRESTAGE_MODELS` - optional comma-separated override. If unset or blank, a
  generated preset uses its sibling `.prestage` manifest; legacy presets
  retain their existing defaults. Use `none` for an intentional no-download
  run
- `S3_BUCKET_NAME` - optional for the AWS launcher or a direct `docker run`.
  When passed, `download-models.sh` stages only catalog-listed artifacts from
  `s3://<bucket>/<hf-repo>/`. A fresh per-model completion marker skips the
  Hugging Face verification pass; a missing, stale, or mismatched marker falls
  back to `hf download` and repairs the cache. The checked-in local Compose
  service deliberately does not pass this variable and remains Hugging
  Face-only. On EC2, supply the bucket through an instance role rather than
  static keys (the container reads IMDS; the instance needs IMDS hop limit 2).
- `MODEL_CACHE_RECHECK_DAYS` - S3 marker lifetime (default `7`). When it
  expires, staging re-runs `hf download` so moving model repos can refresh.
  Set `0` to force a recheck on every launch, or delete
  `s3://<bucket>/.prefer-cache/downloads-v1/<model-key>.complete` to refresh one
  model on its next launch.
- `MODEL_DOWNLOAD_JOBS` - maximum independent model keys staged concurrently
  (default `4` with S3, `1` without S3). All foreground jobs join before
  `llama-server` starts.
- `LLAMA_ARG_MODELS_PRESET` / `LLAMA_ARG_MODELS_MAX` - optional, force a
  specific preset instead of auto-detection

On every tier preset (`96gb.ini`, `12gb.ini`, and `8gb.ini`) and the named
`12gb-pascal.ini` compatibility preset, models load on first request. Only the
named single-model presets use `load-on-startup`.

Once running, `GET /v1/models` lists the available router model ids, and
`POST /v1/chat/completions` with `"model": "<id>"` routes to (and
loads/swaps in, if needed) the matching model.

## Pre-warming model downloads

To populate `/models` without starting the GPU server (e.g. ahead of time on
a slow connection):

```bash
docker compose run --rm prefer /download-models.sh
```

## Extra args

The entrypoint forwards any extra container arguments to `llama-server`
after its fixed flags (`--host`, `--port`), so you can override or add flags
at runtime without rebuilding by setting `command:` on the service in
`docker-compose.yml`, e.g. `command: ["--cache-ram", "0"]`.

## Aliases

The presets already expose short aliases such as `gemma-4`, `qwen-3.6`,
`qwen-3.6-35b-a3b`, and `glm-4.7-flash`; an external routing
layer can usually target those directly.

## Contract and isolated benchmark

The versioned client fixture, synthetic evaluation corpus, reproducible result
schema, isolated local Compose lane, and exact commands live under
[`benchmark/`](../../benchmark/README.md). The benchmark never uses the
operator container name `prefer`, never binds host port 8080, never downloads
models, and never runs as a live GPU job in ordinary CI.
