# Grouped PreFer release

PreFer publishes llama.cpp, audio.cpp, stable-diffusion.cpp, SGLang, and vLLM as one
atomic release. A runtime change rebuilds all engine images with the same
`sha-<commit>` version instead of asking downstream consumers to combine
component releases. The current matrix has fourteen image indexes: llama CUDA 12/ROCm,
Audio CUDA 12/Vulkan/CPU, Image CUDA 12/Vulkan, SGLang CUDA 12/13 and ROCm MI30x,
vLLM CUDA 12/13 and ROCm, and the CPU downloader. The new AMD-oriented builds
are build-only until exact-card model/API verification; Vulkan is not ROCm.
SGLang's MI30x image is not an R9700 image. SGLang and vLLM tags always name the CUDA major explicitly.

`main` is the stable release line. `develop` is the opt-in preview line, and
its immutable GitHub releases are marked as prereleases. A successful grouped
build advances only its own branch's moving image aliases: stable aliases for
`main`, preview aliases for `develop`. Promotion is a merge from `develop` to
`main`, followed by the normal stable grouped build. Existing releases created
before this split are stable.

Each immutable GitHub release and matching Actions artifact contains:

- `prefer-release.json`: exact engine/backend image tags, OCI index digests, and image accelerator requirements (vendor, CUDA major, and restricted ROCm architecture)
- `prefer-release.schema.json`: the public `prefer.release.v1` schema
- `prefer-llama-deployment-inventory.json`
- `prefer-audio-deployment-inventory.json`
- `prefer-image-deployment-inventory.json`
- `prefer-sglang-deployment-inventory.json`
- `prefer-vllm-deployment-inventory.json`
- `prefer-inference-core.tgz`: the ESM `prefer-inference-core` package for the release SHA
- `prefer.mjs`: a standalone Node 24 CLI used inside every engine image
- `prefer-model-catalog.json`: the last successful materialized supported-model metadata
- `prefer-model-catalog.schema.json`
- `prefer-model-catalog-extension.schema.json`
- `prefer-resource-profile.schema.json`
- `prefer-model-plan.schema.json`
- `prefer-runtime-handoff.schema.json`
- `SHA256SUMS`

A controller starts with `prefer-release.json`, selects the required
engine/backend, and then reads that engine's referenced inventory for hardware,
configuration, model, and prestaging choices. All references are immutable.
NeurOn and similar controllers can select `main` or `develop` as their release
source, but must ignore a branch head until its complete grouped release exists.
Use `resolveRuntimeImage` with observed host driver compatibility to select
an image before model fit planning. Hardware profiles never pin an image or
quant; an image match is not a model-load or API smoke. Older releases without
image accelerator metadata require explicit controller image selection.

The bundle contains metadata only. Model weights are neither copied into the
release nor embedded in its container images; each runtime stages them onto its
external `/models` storage after deployment.

The runtime-handoff schema is release-matched. A controller can bind supported
or controller-extension artifacts to that release's catalog fingerprint and
pass the resulting JSON to any engine image from the same grouped release by
mounted path or by the bounded base64 environment transport.
See [the runtime handoff contract](../docs/runtime-handoff.md).

The model catalog is refreshed from Hugging Face before the fourteen image indexes build.
If that refresh is unavailable, the build can reuse repository metadata from
the previous successful release only when it covers every currently authored
repository and immutable revision. Current YAML settings are still
rematerialized over that last successful metadata. The release manifest records
whether the dataset came from a live refresh or that bounded fallback.

`build-release.py` runs only after every engine build returns its published OCI
digest. It validates the source revision and all fourteen image digests, copies the exact
generated inventories without rewriting them, records their catalog
fingerprints and SHA-256 values, and emits the grouped manifest.
