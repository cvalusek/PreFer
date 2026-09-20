# PreFer vLLM runtime

This opt-in official-upstream vLLM v0.29.0 runtime serves the Inferact
Qwen3.8-27B NVFP4 lane. PreFer publishes matched CUDA 12.9 and CUDA 13.0 images
from the same upstream source revision.

Generated hardware deployments, local profiles, and checked-in server configs
have been removed. The inventory retains exact model artifacts, profiles,
runtime/API facts, and composition inputs; it does not select hardware.

## Runtime selection

vLLM is one-model-per-process. Set `VLLM_MODELS`/`PREFER_MODELS` to exactly one
catalog identity, or supply `VLLM_RUNTIME_HANDOFF` /
`VLLM_RUNTIME_HANDOFF_BASE64`. Blank or multiple selections fail.

Catalog model defaults are followed by server overrides, model overrides, and
raw arguments. The caller must explicitly plan context, sequence concurrency,
KV precision, memory utilization, eager/graph behavior, and speculation from
live resources. No named hardware config is inherited.

## Native API

The entrypoint validates the handoff, stages all required artifacts, and then
executes `vllm serve` directly on port 8000. Native vLLM owns health, model
discovery, OpenAI-compatible requests, streaming, cancellation, headers, and
errors. PreFer does not place an HTTP gateway in the inference data path.
The generated `--served-model-name` is the catalog `request_model_id`; friendly
catalog aliases remain planner inputs and are not rewritten at HTTP ingress.

Published tags are explicit: `vllm-cuda12[-preview]` and
`vllm-cuda13[-preview]`. There is no generic alias that silently changes CUDA
major. For a local CUDA 12 build:

```bash
VLLM_CUDA_VARIANT=cuda12 \
VLLM_BASE_IMAGE='vllm/vllm-openai:v0.29.0-cu129-ubuntu2404@sha256:b478e866ccff56876a0e159edae1620055c858c739fb20f23194fc636f1a4108' \
VLLM_SOURCE_REVISION=98dff2a81d747d1dba01a47f939f48c3526d4206 \
VLLM_IMAGE_VERSION=v0.29.0 \
  docker compose build vllm
```

## Artifact staging

The canonical bundle includes the exact tokenizer/configuration files, six
safetensors shards, and MTP companion. Files use immutable revisions, exact
sizes and SHA-256 values, atomic publication, and shared `downloads-v2`
markers. The CPU-only release downloader can stage the same handoff before a
GPU worker starts.

## Generation

```bash
python generate.py
python generate.py --check
```

The generator emits the artifact map and inventory. Effective runtime config is
written under `/run/prefer`.
