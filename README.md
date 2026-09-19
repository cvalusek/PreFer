# PreFer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PreFer publishes release-matched inference containers for llama.cpp, audio.cpp,
stable-diffusion.cpp, SGLang, and vLLM, plus a CPU-only artifact downloader.
Model weights never ship in an image or release artifact; they are staged onto
external `/models` storage from exact, release-bound runtime handoffs.

The current model set covers Gemma 4, Qwen3.5/Qwen3.6/Qwen3.8, Ornith 1.5,
Nemotron 3.5 Lightning, Muse Glimmer, GLM, DeepSeek V4, speech and music models,
image generation/edit models, and MiniMax H3 video. See [CHANGELOG.md](CHANGELOG.md)
for consumer-visible changes.

## Architecture

PreFer separates three concerns:

1. **Provider hardware facts** live in `catalog/hardware-profiles.json`. These
   AWS and RunPod records contain capacity, provider identity, compatibility,
   and dated evidence only. They are library inputs, not runtime selectors.
2. **Planning** happens in `prefer-inference-core`. A controller combines a
   provider profile or live resource observation with model intent and calls
   `planModelSet`, then creates an immutable runtime handoff.
3. **Execution** consumes the resolved handoff. The CPU downloader and the GPU
   runtime use the same artifact list, `/models` layout, integrity identities,
   and `downloads-v2` verification markers.

There are no local named hardware profiles, VRAM-tier presets, generated
hardware/model pairings, or `PREFER_DEPLOYMENT` runtime selector. Unmanaged
local launchers should detect live resources, choose explicit models/settings,
and generate a handoff rather than guessing from a GPU name.

## Layout

```text
catalog/
  hardware-profiles.json             provider-only AWS/RunPod resource facts
  models/                             cross-engine model selection metadata
packages/prefer/                      planner, catalog, release, and handoff APIs
docker/
  llama-cpp/                          llama.cpp router runtime
  audio-cpp/                          audio.cpp CUDA and CPU runtimes
  stable-diffusion-cpp/               image runtime
  sglang/                             SGLang text/video runtime
  vllm/                               vLLM text runtime
  downloader/                         CPU-only exact-artifact staging image
scripts/runtime-handoff-download.sh   shared handoff staging adapter
release/                              grouped release builder and schema
benchmark/                            deterministic contract and replay tests
aws/                                  AMI and infrastructure tooling
```

Each engine-local catalog owns launch semantics. Generated deployment
inventories publish models, profiles, bundles where meaningful, composition
inputs, and API/runtime facts; their `deployments` arrays are intentionally
empty. Runtime configuration is materialized under `/run/prefer`.

## Build from source

```bash
npm install
npm run prepare:containers
docker compose build prefer audio image
```

`prepare:containers` builds metadata-only tooling. It does not download model
weights. Published images already contain the matching CLI and materialized
catalog.

## Plan and create a handoff

The package exports provider hardware APIs separately from runtime composition:

```js
import {
  readHardwareProfileCatalog,
  resolveHardwareProfile,
  readModelCatalog,
  planModelSet,
  createRuntimeHandoff
} from "prefer-inference-core";

const hardware = await readHardwareProfileCatalog("prefer-hardware-profiles.json");
const catalog = await readModelCatalog("prefer-model-catalog.json");
const resources = resolveHardwareProfile(hardware, "aws/g7e.2xlarge", observation);
const plan = planModelSet(catalog, {
  engine: "llama.cpp",
  resources,
  models: [{ model_id: "qwen-3.8-27b", required: true }]
});
const choice = plan.selected[0];
const handoff = createRuntimeHandoff(catalog, {
  engine: "llama.cpp",
  models: [{ variant: choice.selected }],
  serverSettings: { parallel: 1, "ctx-size": 131072 }
});
```

Provider profiles do not choose models, quants, context, concurrency, cache,
offload, or speculative companions. Those choices belong to the planner and
its explicit caller policy. Live observations may overlay static capacity
immediately before planning.

See [docs/model-catalog.md](docs/model-catalog.md) and
[docs/runtime-handoff.md](docs/runtime-handoff.md) for the full APIs and
validation contract.

## Stage artifacts on CPU

The release-matched downloader requires no CUDA runtime or GPU:

```bash
docker run --rm \
  -e PREFER_ENGINE=llama.cpp \
  -e PREFER_RUNTIME_HANDOFF_BASE64="$HANDOFF_BASE64" \
  -e HF_TOKEN \
  -v prefer-model-cache:/models \
  ghcr.io/cvalusek/prefer:downloader-preview
```

With source Compose:

```bash
PREFER_ENGINE=llama.cpp \
PREFER_RUNTIME_HANDOFF_BASE64="$HANDOFF_BASE64" \
PREFER_DOWNLOADER_MODEL_VOLUME=prefer-model-cache \
  docker compose --profile downloader run --rm downloader
```

Use storage that the later GPU worker can actually mount. A host-local Docker
volume does not transfer artifacts between machines. Network volumes, shared
object-cache workflows, or explicit volume transfer are required across hosts.

The downloader validates the complete handoff before transfer, checks immutable
repository revisions and exact paths/sizes/digests, publishes files atomically,
and writes the same `.prefer-cache/downloads-v2/verified` markers used by the
runtime images. Optional `S3_BUCKET_NAME`/`S3_MODEL_PREFIX` enables exact
read-through with Hugging Face fallback.

## Run a runtime

Pass the same handoff to the selected GPU runtime and mount the staged volume:

```bash
LLAMA_RUNTIME_HANDOFF_BASE64="$HANDOFF_BASE64" \
PREFER_MODEL_VOLUME=prefer-model-cache \
  docker compose up prefer
```

Engine-scoped Compose inputs are:

- llama.cpp: `LLAMA_MODELS`, `LLAMA_SERVER_OVERRIDES`,
  `LLAMA_MODEL_OVERRIDES`, `LLAMA_RUNTIME_HANDOFF[_BASE64]`
- audio.cpp: `AUDIO_BUNDLE`, `AUDIO_MODELS`, overrides, and
  `AUDIO_RUNTIME_HANDOFF[_BASE64]`
- image: `IMAGE_BUNDLE`, `IMAGE_MODELS`, overrides, and
  `IMAGE_RUNTIME_HANDOFF[_BASE64]`
- SGLang: `SGLANG_MODELS`, overrides, and
  `SGLANG_RUNTIME_HANDOFF[_BASE64]`
- vLLM: `VLLM_MODELS`, overrides, and
  `VLLM_RUNTIME_HANDOFF[_BASE64]`

A handoff is mutually exclusive with direct model/bundle selectors. SGLang and
vLLM require exactly one model. llama.cpp requires explicit models; it does not
auto-detect a preset. Audio and image retain semantic bundles, which group
capabilities without encoding hardware choices.

Direct selectors are an unmanaged convenience path. Operators are responsible
for live resource detection and explicit context, concurrency, cache, offload,
and speculative settings. Controllers should prefer immutable handoffs.

Ports:

| Service | Compose service | Default host port |
| --- | --- | --- |
| llama.cpp | `prefer` | 8080 |
| audio.cpp | `audio` | 8081 |
| image | `image` | 8082 |
| SGLang | `sglang` profile | 8083 |
| vLLM | `vllm` profile | 8084 |

## Runtime composition precedence

Base-free composition applies:

1. catalog model/quant defaults;
2. server JSON overrides;
3. per-model JSON overrides;
4. raw engine arguments.

Objects merge recursively; scalars and arrays replace. There is no hardware
preset layer. Generated configs, prestage manifests, and plans are ephemeral
and written under `/run/prefer`.

## Releases

One grouped workflow publishes the five engines, both audio variants, and the
CPU downloader under one seven-character source SHA. `prefer-release.json`
binds every immutable OCI digest, the five runtime inventories, shared model
catalog, provider hardware catalog, schemas, CLI, and npm package. Stable
aliases advance from `main`; preview aliases advance from `develop`.

The downloader aliases are `downloader` and `downloader-preview`; immutable
releases use `downloader-sha-<commit>`. Runtime model bytes remain external.

## Verification

```bash
python -m unittest discover -s benchmark/tests -v
python -m prefer_bench validate
python -m prefer_bench contract --mock
npm test
```

Live model verification remains hardware-dependent. Historical benchmark
artifacts can document old local hardware results, but they are evidence only
and are not selectable planning profiles.

## License

MIT. Model licenses vary and remain recorded in the catalogs and release
inventories.
