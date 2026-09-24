# PreFer SGLang runtime

PreFer publishes official SGLang CUDA 12.9 (`v0.5.19-cu129`) and CUDA 13
(`v0.5.20`) variants, plus a build-only ROCm MI30x image. The normal named text lane is now first-party Qwen3.5-9B BF16 at a bounded
8K starting context, alongside MiniMax H3 diffusion video. Qwen3.8 NVFP4
remains an explicit-only experimental lane (`qwen-3.8-27b-nvfp4`); its friendly
model name no longer selects it. The MI30x ROCm image is not an R9700
`gfx1201` build and cannot become one by changing the model quant.
Capability and fit remain exact variant/card/model smoke gates.

Generated hardware deployments, local profiles, and checked-in server configs
have been removed. The inventory retains model profiles, runtime modes, API
contracts, artifact metadata, and compatibility facts only.

## Runtime selection

SGLang is one-model-per-process. Set `SGLANG_MODELS`/`PREFER_MODELS` to one
catalog key or identity, or provide `SGLANG_RUNTIME_HANDOFF` /
`SGLANG_RUNTIME_HANDOFF_BASE64`. Blank or multiple model selection fails.

Catalog model defaults are followed by server overrides, model overrides, and
raw arguments. No hardware defaults are inherited. The controller is
responsible for planning context, concurrency, KV precision, memory fraction,
speculation, offload, and diffusion settings from live resources.

## Native API

After validating and staging artifacts, the entrypoint directly executes the
upstream SGLang server on port 30000. PreFer does not proxy text or diffusion
requests. The generated native model name is the catalog `request_model_id`;
friendly aliases remain planner inputs rather than an HTTP rewrite contract.

MiniMax H3 uses SGLang's native `/v1/videos` API. Canonical `conditions[].uri`
inputs may use local paths, `file://`, HTTP(S), `data:`, or `base64://`; SGLang
localizes and validates request-owned material. Native multipart fields remain
available where the upstream API maps them. Outputs remain under `/outputs`,
and native uploads use `/inputs`.

## CUDA variants

Published tags are explicit: `sglang-cuda12[-preview]` and
`sglang-cuda13[-preview]`. There is no generic alias that silently changes CUDA
major. For a local CUDA 12 build, use the values recorded in `runtime.json`:

```bash
SGLANG_CUDA_VARIANT=cuda12 \
SGLANG_BASE_IMAGE='lmsysorg/sglang:v0.5.19-cu129@sha256:59e11312666e1c5c155210ea335589b91daa0d70848521b390b93b1b1e8fb0ef' \
SGLANG_SOURCE_REVISION=0bcd822377da7b5718e674eaf9c870d349424dd1 \
SGLANG_IMAGE_VERSION=v0.5.19 \
  docker compose build sglang
```

## Staging

Pinned artifacts use the common `/models/<repository>/<path>` layout and shared
`downloads-v2` verification markers. S3 read-through is optional. A
release-matched CPU downloader can stage the same immutable handoff before GPU
execution.

## Generation

```bash
python generate.py
python generate.py --check
```

The generator emits the downloader map and inventory. Runtime JSON configs are
materialized under `/run/prefer`.
