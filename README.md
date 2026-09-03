# PreFer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PreFer packages practical self-hosted inference runtimes. Its llama.cpp image
provides known-good LLM mixes, VRAM-aware router configs, and model staging for
local, RunPod, and AWS hardware. Its audio.cpp images provide pinned speech,
music-generation, and speech-to-speech routes behind a separate audio API. Its
stable-diffusion.cpp image provides curated image generation and editing behind
OpenAI-style image endpoints without requiring ComfyUI workflows.
Its opt-in SGLang image serves Qwen3.8-27B NVFP4 on modern NVIDIA Blackwell
GPUs through a separate OpenAI-compatible text API.

Published runtime, hosted-model, and preset changes are recorded by immutable
grouped release SHA in the [PreFer changelog](CHANGELOG.md).

The current llama.cpp catalog covers Gemma 4, Qwen3.5/Qwen3.6/Qwen3.8, Ornith 1.5,
Nemotron 3.5 Lightning, Muse Glimmer, GLM, and DeepSeek V4
through `llama-server` router mode with an
OpenAI-style API on port `8080`. PreFer deliberately promises only its
[versioned narrow client contract](benchmark/README.md#stable-client-contract),
not broad drop-in OpenAI compatibility.

Muse's generated AWS presets are supported by the pinned b10362 image, whose
source includes llama.cpp PR #26841. The prepared 24/48/96 GB shapes still need
their first-boot fit, contract, DFlash, projector, and concurrency gates on
target GPUs before production use.

## Why PreFer

Running local inference is mostly plumbing: model filenames, context limits,
KV cache choices, GPU memory tradeoffs, startup downloads, and the occasional
upstream sharp edge. PreFer keeps those choices explicit and versioned so the
container can do the boring parts reliably:

- auto-select a preset from detected GPU VRAM
- download the right GGUF files into a persistent `/models` volume
- expose stable model aliases through llama.cpp router mode
- keep tuning rationale in repo docs instead of tribal memory
- support tiny local boxes and larger long-context hosts from one image

## Layout

```text
docker/
  llama-cpp/          PreFer's llama.cpp router image
    preset-catalog.json       runtime and legacy-prestage metadata
    models/<family>/<model>/  model.json files with deployable quant lanes
    preset-scenarios/         AWS, RunPod, and generic local deployment shapes
    deployment-inventory.generated.json  controller-readable release inventory
    generate-presets.py       deterministic preset/downloader/inventory generator
  audio-cpp/          PreFer's audio.cpp CUDA 12 and CPU images
    runtime.json              pinned upstream runtime images and manifests
    models/<family>/<model>/  immutable audio model artifacts and lineage
    deployment-inventory.generated.json  controller-readable audio inventory
    generate.py               deterministic server/downloader/inventory generator
  stable-diffusion-cpp/  PreFer's image generation and editing image
    runtime.json              pinned upstream CUDA runtime and Linux platform
    models/<family>/<model>/  immutable image pipelines and quant lanes
    deployment-inventory.generated.json  controller-readable image inventory
    generate.py               deterministic config/downloader/inventory generator
  sglang/             PreFer's opt-in SGLang CUDA 13 text image
    runtime.json              pinned SGLang image, source, and GPU requirements
    models/<family>/<model>/  immutable NVFP4 model artifacts and lineage
    deployment-inventory.generated.json  controller-readable SGLang inventory
    generate.py               deterministic config/downloader/inventory generator
aws/                  EC2 deployment (AMI + boot scripts + CDK); see aws/DESIGN.md
release/              grouped-release manifest builder and public JSON schema
.github/workflows/    grouped runtime release plus independent AMI/IaC workflows
```

## Quick Start

Copy the example environment file and adjust as needed:

```bash
cp .env.example .env
```

Build the inference image:

```bash
docker compose build prefer
```

Run the inference server directly:

```bash
docker compose up prefer
```

Models are stored in the named Docker volume `prefer-model-cache` by
default. Override `PREFER_MODEL_VOLUME` in `.env` if you want a different cache.

Once the server is ready:

```bash
curl http://localhost:8080/v1/models
```

The audio and image services are part of the default Compose application. Build
and start all three runtimes with:

```bash
docker compose up --build
curl http://localhost:8081/v1/models
curl http://localhost:8082/v1/models
```

To run only one runtime, target its Compose service explicitly with
`docker compose up prefer`, `docker compose up audio`, or
`docker compose up image`.

It exposes Qwen3 TTS Base, CustomVoice, VoiceDesign, and ASR; ACE-Step 1.5;
MiniMax Music 3; and PersonaPlex. It keeps at most one resident model and swaps
lazily. The TTS Base model is a voice-cloning route and needs `voice_ref` plus
`reference_text`, or a matching server-side voice library. See
[the audio runtime guide](docker/audio-cpp/README.md) for request examples.

The image service exposes FLUX.2 Klein, Z-Image-Turbo, Qwen Image, Qwen Image
Edit 2511, and SDXL through `/v1/images/generations` and `/v1/images/edits`.
Discovery and background prestaging do not load a model; the first request
starts the selected worker and the router retains only one model. See
[the image runtime guide](docker/stable-diffusion-cpp/README.md) for request
examples and hardware lanes.

The SGLang service is an opt-in alternative text backend for Qwen3.8-27B. It
uses a shared-compatible `/models` layout and defaults to the same named model
volume as llama.cpp, but has its own generated server configs and stricter
per-file verification. Matching repository/path/revision files can be reused by
either launcher; model keys and server configs remain runtime-specific. AWS can
optionally use the same S3 bucket convention as llama.cpp for exact read-through
staging with HF fallback; local and RunPod scenarios remain HF-only by default.
See
[the SGLang runtime guide](docker/sglang/README.md)
for Blackwell shapes, model controls, and its deliberately deferred Flash lane.

## Environment

Most local configuration lives in `.env`; see [.env.example](.env.example).
Useful knobs:

- A nonblank `PRESTAGE_MODELS` optionally overrides which catalog models are
  downloaded; when unset or blank, generated presets use their sibling
  `.prestage` manifests. Use `none` for an intentional no-download run.
- `S3_BUCKET_NAME` enables an optional S3 model cache when it is passed by the
  AWS launcher or a direct `docker run`. The checked-in local Compose service
  intentionally does not pass it and remains Hugging Face-only.
- `HF_TOKEN` improves Hugging Face rate limits.
- `HF_HUB_DISABLE_XET` and `HF_XET_*` transfer controls can disable or bound
  Xet downloads on constrained Docker Desktop installations. The example
  values are blank; Audio and Image use their image default of high-performance
  Xet unless that setting is overridden.
- `LLAMA_ARG_MODELS_PRESET` forces a specific preset instead of VRAM detection.
- `LLAMA_ARG_MODELS_MAX` controls how many routed models may be loaded at once.
  The normal Compose path defaults to `1`; see the exact
  [override precedence](benchmark/README.md#models-max-facts-and-open-policy).
- On the AWS AMI, first-boot user-data writes deployment values to
  `/opt/prefer/deployment.env`; see the race-free
  [manual launch contract](aws/DESIGN.md#iac-layer-cdk-distributed-as-cloudformation).
- `PREFER_MODEL_VOLUME` names the persistent Docker volume for `/models`.
- `LLM_PORT` sets the host port.
- `AUDIO_PORT` sets the audio service host port (default `8081`).
- `AUDIO_SERVER_CONFIG` selects a generated audio deployment config. Blank
  uses the all-capabilities default; a selected config also selects its
  prestage sidecar when `AUDIO_PRESTAGE_MODELS` is blank.
- `AUDIO_PRESTAGE_MODELS` selects pinned audio packages to stage. Blank or
  unset follows the selected server config; use `none` to skip downloads.
- `AUDIO_DOWNLOAD_JOBS` bounds independent audio artifact transfers from 1 to
  8 (default `4`). Shared component paths are deduplicated before work starts.
- `PREFER_AUDIO_MODEL_VOLUME` and `PREFER_AUDIO_VOICE_VOLUME` name the audio
  model and server-side voice-library volumes.
- `IMAGE_PORT` sets the image service host port (default `8082`).
- `IMAGE_SERVER_CONFIG` selects a generated image deployment config. Blank
  uses the all-capabilities default.
- `IMAGE_PRESTAGE_MODELS` selects pinned image lanes to stage. Blank follows
  the selected config; use `none` to skip downloads.
- `IMAGE_DOWNLOAD_JOBS` bounds independent image artifact transfers from 1 to
  8 (default `4`). Image discovery remains available while those jobs run.
- `PREFER_IMAGE_MODEL_VOLUME` names the persistent image `/models` volume.
- `SGLANG_PORT` sets the opt-in SGLang host port (default `8083`).
- `SGLANG_SERVER_CONFIG` selects a generated SGLang deployment config. Blank
  uses the safe target-only default; the selected config also selects its
  `.prestage` sidecar when `SGLANG_PRESTAGE_MODELS` is blank.
- `SGLANG_PRESTAGE_MODELS` selects the pinned SGLang package to stage. Blank
  follows the selected config; use `none` to skip downloads.
- `SGLANG_DOWNLOAD_JOBS` bounds independent SGLang artifact transfers from 1
  through 8 (default `4`). `PREFER_SGLANG_MODEL_VOLUME` defaults to the same
  named `prefer-model-cache` volume used by llama.cpp, so the two downloaders
  share the `/models` layout.
- `SGLANG_S3_BUCKET_NAME` and `SGLANG_S3_MODEL_PREFIX` opt SGLang into AWS
  read-through staging; the common `S3_BUCKET_NAME` and `S3_MODEL_PREFIX` names
  are also accepted. Exact S3 objects are verified before publication, and an
  S3 miss falls back to the pinned Hugging Face revision.

Audio and image staging use Hugging Face's `hf` CLI and Xet on their separate
model volumes. Interrupted transfers resume from hidden, stable staging paths;
size and SHA-256 are verified before atomic publication. A verified completion
marker avoids rehashing unchanged multi-gigabyte files on every restart. SGLang
uses the same exact artifact layout and writes the llama-compatible local model
marker after its stricter per-file checks.

## Contract and benchmark harness

Run the complete deterministic contract replay without Docker, a GPU, or a
live model:

```bash
python -m prefer_bench contract --mock
```

Run the current b10362 lane against only the already-cached Gemma E2B/E4B
files. The Pascal preset remains available to reproduce the old b9843
workaround, but current b10362 includes its upstream fix:

```bash
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b,gemma-4-e4b --preset 12gb.ini --models-max 1 --contexts 8k,32k
```

The local command uses a generated Compose project, free loopback port (never
8080), temporary network, and temporary model volume. It clones only selected
files from the source cache mounted read-only, disables model downloads, and
removes every temporary container/network/volume afterward. It never manages
provider capacity or touches the operator `prefer` container.

See [benchmark/README.md](benchmark/README.md) for the result format, optional
128K and idle cells, the `models-max=4` comparison, and historical b9843/b9982
evidence. No live GPU benchmark runs in ordinary CI.

## Netskope / Corporate TLS

If Docker builds fail with Python or npm certificate errors, use the Netskope
overlay. Export your corporate root/intermediate certificates as `.crt` files
under `docker/certs/` and run:

```bash
docker compose -f docker-compose.yml -f docker-compose.netskope.yml build prefer
docker compose -f docker-compose.yml -f docker-compose.netskope.yml up prefer
```

Certificate files under `docker/certs/` are ignored by git.

## Grouped releases and images

GitHub Actions build all four runtimes as one PreFer release whenever any
runtime changes. The `main` branch is the stable line and `develop` is the
opt-in preview line. One `sha-<commit>` release therefore identifies the exact
llama CUDA, Audio CUDA/CPU, Image CUDA, and SGLang CUDA images produced from the
same source revision. Releases built from `develop` are GitHub prereleases;
releases built from `main` are stable releases. Existing releases from before
the channel split remain stable.

Stable moving tags remain `latest`, `llama-cuda`, `audio-cuda12`, `audio-cpu`,
`image-cuda12`, and `sglang-cuda`. Preview users opt in through `preview`,
`llama-cuda-preview`, `audio-cuda12-preview`, `audio-cpu-preview`,
`image-cuda12-preview`, or `sglang-cuda-preview`. The generic `latest` and
`preview` tags are llama.cpp compatibility aliases. Immutable tags remain
`sha-<commit>`, `llama-cuda[-sha-<commit>]`, `audio-cuda12[-sha-<commit>]`,
`audio-cpu[-sha-<commit>]`, `image-cuda12[-sha-<commit>]`, and
`sglang-cuda13[-sha-<commit>]`. Image generation remains Linux AMD64 only;
Audio and SGLang publish Linux AMD64 and ARM64 variants.

The immutable GitHub release and the commit-named
`prefer-release-<full-commit>` workflow artifact contain one
`prefer-release.json`, its public schema, all four deployment inventories, and
checksums. Controllers select the needed engine/backend from that manifest and
then use the referenced inventory for its model, hardware, and configuration
choices. The manifest binds exact image digests; it does not contain model
weights. Models continue to stage at runtime on external persistent storage.

Controllers may expose `stable` and `preview` as a branch selector: resolve
stable releases from `main` and preview releases from `develop`, then accept
only a SHA whose grouped `prefer-release.json` was published successfully.
They should deploy the immutable image references from that manifest rather
than compose moving engine tags. Promote tested preview work by merging it to
`main`; the resulting stable branch build publishes the stable grouped release.

Additional llama models and deployment shapes
belong in `models/` and `preset-scenarios/`; regenerate and commit their
deterministic outputs. Every image contains its resolved inventory at
`/deployment-inventory.json` and carries an OCI label naming that path and
schema. The grouped release publishes all four inventories together. NeurOn
can use them to select the exact preset, prestage keys, runtime, provider GPU ID, GPU
count, context, concurrency, cache types, and API-safe `request_model_id`
without parsing the documentation. The inventory's `section` field is the INI
configuration identity and must not be used as the warmup model ID.

The audio release follows the same controller contract. Its inventory adds
AWS, local, and exact RunPod card choices; all-capabilities, related-capability,
and single-model configs; exact staging bytes; and the selected
`AUDIO_SERVER_CONFIG`. It is embedded at the same image path and included as
`prefer-audio-deployment-inventory.json` in the grouped release.

The image release uses the same inventory path and controller pattern. It adds
exact pipeline components and hashes, generation/edit capabilities, background
prestaging, one-model residency, AWS/local/RunPod hardware choices, and the
selected `IMAGE_SERVER_CONFIG`. The grouped release includes it as
`prefer-image-deployment-inventory.json`.

The SGLang release follows the same inventory contract. Its inventory adds the
Qwen3.8-27B NVFP4 lineage, exact safetensor and multimodal asset hashes,
Blackwell hardware gates, generated context/concurrency/cache settings, Qwen
reasoning and tool-parser controls, and the separate `prefer-sglang` Compose
profile. The grouped release includes it as
`prefer-sglang-deployment-inventory.json`.

RunPod presets are organized as `presets/runpod/<gpu>/1x/`; the initial
multi-GPU exception is
`presets/runpod/rtx-pro-6000/2x/deepseek-v4-flash.ini`. Generic household GPU
profiles live under `presets/local/<gpu>/1x/`. They record no hostname, CPU,
RAM, storage, credentials, or other private machine inventory.

See [the llama.cpp runtime guide](docker/llama-cpp/README.md) for LLM model
details, preset tiers, aliases, and operational notes, and
[the audio.cpp runtime guide](docker/audio-cpp/README.md) for speech and music
details, and [the image runtime guide](docker/stable-diffusion-cpp/README.md)
for image generation and editing, and [the SGLang runtime guide](docker/sglang/README.md)
for the Qwen3.8-27B Blackwell route.
