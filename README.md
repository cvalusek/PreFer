# PreFer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PreFer packages practical self-hosted inference runtimes. Its llama.cpp image
provides known-good LLM mixes, VRAM-aware router configs, and model staging for
local, RunPod, and AWS hardware. Its audio.cpp images provide pinned speech,
music-generation, and speech-to-speech routes behind a separate audio API.

Published hosted-model and preset changes are recorded by immutable container
SHA in the [PreFer changelog](CHANGELOG.md).

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
aws/                  EC2 deployment (AMI + boot scripts + CDK); see aws/DESIGN.md
.github/workflows/    Build workflows (container, AMI, and IaC build independently)
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

The audio service is part of the default Compose application. Build and start
both llama.cpp and audio.cpp with:

```bash
docker compose up --build
curl http://localhost:8081/v1/models
```

To run only one runtime, target its Compose service explicitly with
`docker compose up prefer` or `docker compose up audio`.

It exposes Qwen3 TTS Base, CustomVoice, VoiceDesign, and ASR; ACE-Step 1.5;
MiniMax Music 3; and PersonaPlex. It keeps at most one resident model and swaps
lazily. The TTS Base model is a voice-cloning route and needs `voice_ref` plus
`reference_text`, or a matching server-side voice library. See
[the audio runtime guide](docker/audio-cpp/README.md) for request examples.

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
  Xet downloads on constrained Docker Desktop installations; they are blank by
  default in `.env.example`.
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
- `PREFER_AUDIO_MODEL_VOLUME` and `PREFER_AUDIO_VOICE_VOLUME` name the audio
  model and server-side voice-library volumes.

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

## Images

GitHub Actions publish all runtimes to `ghcr.io/cvalusek/prefer`. The existing
`latest` and `sha-<commit>` tags remain llama.cpp compatibility tags; explicit
llama tags are `llama-cuda` and `llama-cuda-sha-<commit>`. Audio publishes
`audio-cuda12`, `audio-cuda12-sha-<commit>`, `audio-cpu`, and
`audio-cpu-sha-<commit>` without changing `latest`.

Additional llama models and deployment shapes
belong in `models/` and `preset-scenarios/`; regenerate and commit their
deterministic outputs. Every image contains the resolved inventory at
`/deployment-inventory.json`, carries an OCI label naming that path and schema,
and publishes the same JSON as a commit-named workflow artifact. NeurOn can use
it to select the exact preset, prestage keys, runtime, provider GPU ID, GPU
count, context, concurrency, cache types, and API-safe `request_model_id`
without parsing the documentation. The inventory's `section` field is the INI
configuration identity and must not be used as the warmup model ID.

The audio release follows the same controller contract. Its inventory adds
AWS, local, and exact RunPod card choices; all-capabilities, related-capability,
and single-model configs; exact staging bytes; and the selected
`AUDIO_SERVER_CONFIG`. It is embedded at the same image path and also published
as `prefer-audio-deployment-inventory-<commit-sha>` for provisioning screens.

RunPod presets are organized as `presets/runpod/<gpu>/1x/`; the initial
multi-GPU exception is
`presets/runpod/rtx-pro-6000/2x/deepseek-v4-flash.ini`. Generic household GPU
profiles live under `presets/local/<gpu>/1x/`. They record no hostname, CPU,
RAM, storage, credentials, or other private machine inventory.

See [the llama.cpp runtime guide](docker/llama-cpp/README.md) for LLM model
details, preset tiers, aliases, and operational notes, and
[the audio.cpp runtime guide](docker/audio-cpp/README.md) for speech and music
details.
