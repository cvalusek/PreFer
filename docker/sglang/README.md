# PreFer SGLang runtime

This opt-in CUDA 13 image serves Qwen3.8 text and MiniMax H3 diffusion video.
It is an alternative backend, not a llama.cpp replacement.

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

## Modes

Text configurations launch the SGLang text server on the internal public port.
Diffusion configurations launch `sglang serve` behind `video_gateway.py`, which
owns `/v1/videos`, local-file and multipart policy, warmup readiness, and worker
failure reporting. H3 input/output volumes remain `/inputs` and `/outputs`.

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
