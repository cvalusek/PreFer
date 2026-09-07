# PreFer vLLM

This sibling image serves the text lane of Qwen3.8-27B through the official
upstream vLLM OpenAI server. It is behind the `vllm` Compose profile so the
default PreFer application does not reserve a second text-serving GPU.

## Pinned runtime and model

- vLLM source: `v0.28.0`, source revision
  `2cf0a6915ce544dc493a0990f2ea38d81601128a`.
- Base image: `vllm/vllm-openai:v0.28.0-ubuntu2404` at OCI index
  `sha256:f8fe15a8039343336945db10494eaad80ef941fe2b2a5fa6649fa38636051a65`.
  The image is official upstream and is not built from a fork.
- Model: `Inferact/Qwen3.8-27B-NVFP4` at immutable revision
  `6128240ebaf4eaa7bad2b3d1c72c37d677c5f462`.
- The selected tokenizer/configuration/weight bundle is exactly
  `26,404,413,873` bytes. The generated catalog records every staged file's
  revision, size, SHA-256, and role.
- The derivative records `Qwen/Qwen3.8-27B` as its base lineage. Model weights
  are staged at runtime and are not copied into the image or release artifact.

## Hardware contract

The canonical lane targets NVIDIA Blackwell GPUs (SM100 or newer) and follows
the official Qwen3.8 vLLM recipe: one-way tensor parallelism, native 262,144
token context, FP8 KV cache, Qwen reasoning/tool-call parsers, and three
in-checkpoint MTP speculative tokens. All concrete shapes are marked
`configuration-only` until they pass target-card load, request, MTP, context,
and concurrency smoke tests.

The checked-in starting shapes are:

- AWS `g7e.2xlarge`: one 96 GB RTX PRO 6000 Blackwell.
- RunPod RTX PRO 6000: one 96 GB Blackwell card.
- RunPod RTX 5090: one 32 GB card, with a conservative 32K target-only lane
  using `--enforce-eager` and a separate bounded MTP experiment.
- Local GB10: one 128 GB unified-memory Blackwell-class device.

The inventory keeps native image/video capability metadata, but this first
runtime lane is configured for text input only. Multimodal requests must pass a
direct target-card smoke before the configured modalities are expanded.

## vLLM versus other Qwen3.8 lanes

This image intentionally uses the official upstream vLLM runtime and the
Inferact NVFP4 checkpoint. It does not silently import the SGLang runtime,
custom vLLM forks, or a Flash-Next checkpoint. Those routes have different
kernel, checkpoint, and speculative-decoding behavior.

Qwen3.8 Flash is tracked as a deferred experimental route. It requires a
dedicated `vllm/vllm-openai:qwen38-flash-next` image and a much larger FP8
checkpoint; it is not part of this portable CUDA 13 image or its canonical
inventory. DFlash2 is also not enabled here because the first lane is pinned to
the official recipe's in-checkpoint MTP path.

## Downloads and gateway

The entrypoint starts model staging in the background, exposes `/v1/models`
immediately, and reports warmup through `GET /readyz`. Once every requested
artifact passes size and SHA-256 verification, it starts vLLM on the private
backend port and proxies OpenAI-compatible `/v1` traffic. The gateway
normalizes the catalog aliases to the canonical request model ID.

The generated downloader uses the shared resumable `downloads-v2` cache and
atomic publication rules. Set `VLLM_S3_BUCKET_NAME` to enable optional S3
read-through; a miss or integrity mismatch falls back to the pinned Hugging
Face revision. `VLLM_S3_MODEL_PREFIX` is a relative object prefix. The common
`S3_BUCKET_NAME` and `S3_MODEL_PREFIX` names remain accepted for operators
reusing the llama.cpp staging environment.

The vLLM-specific variables take precedence when set:

- `VLLM_SERVER_CONFIG` selects a generated JSON configuration.
- `VLLM_PRESTAGE_MODELS` selects catalog keys; blank follows the selected
  config's `.prestage` sidecar and `none` skips downloads.
- `VLLM_DOWNLOAD_JOBS` bounds transfers from one through eight.
- `VLLM_S3_BUCKET_NAME` and `VLLM_S3_MODEL_PREFIX` enable S3 read-through.
- `PRESTAGE_MODELS` and `MODEL_DOWNLOAD_JOBS` remain accepted as compatibility
  aliases.

## Compose

The service listens on container port `8000` and host port `8084` by default.
It is opt-in because it is an alternative text backend:

```bash
docker compose --profile vllm build vllm
docker compose --profile vllm up vllm
curl http://localhost:8084/v1/models
```

The default provider-neutral config is `/app/server.json`. Hardware configs
are copied under `/server-configs`, for example
`/server-configs/aws/g7e/2xlarge/performance.json` or
`/server-configs/runpod/rtx-5090/1x/target-only.json`. The canonical request
model ID is `qwen3.8-27b`; `qwen-3.8-27b` is an accepted alias. Use
`GET /readyz` for warmup-aware readiness and `GET /v1/models` for discovery.

## Verification gates

Before enabling a shape for production, verify full-GPU load, peak memory,
native and configured context, Qwen reasoning controls, strict JSON/tools/SSE,
MTP acceptance versus target-only, and request concurrency. FP8 KV is a
performance default rather than an accuracy claim until it is compared with a
BF16-KV control on the target card. The generated inventory preserves these
unknowns instead of presenting configuration as measured throughput.

Authoritative references: [vLLM Qwen3.8 recipe](https://recipes.vllm.ai/Qwen/Qwen3.8-27B),
[vLLM speculative decoding](https://docs.vllm.ai/en/stable/features/speculative_decoding/),
[Qwen3.8 model card](https://huggingface.co/Qwen/Qwen3.8-27B), and the
[pinned Inferact checkpoint](https://huggingface.co/Inferact/Qwen3.8-27B-NVFP4).
