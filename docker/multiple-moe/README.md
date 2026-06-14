# multiple-moe

A llama.cpp router container hosting four model slots side-by-side on a
single GPU, tuned for an **RTX 6000** (with room to spare for possibly one
more small model alongside these).

Base image: [`ghcr.io/ggml-org/llama.cpp:server-cuda`](https://github.com/ggml-org/llama.cpp/pkgs/container/llama.cpp)

## Models

All models download from Hugging Face on first start (see `entrypoint.sh`)
and land under `/models/<hf-org>/<hf-repo>/...`. Mount a persistent volume at
`/models` to avoid re-downloading on restart.

| Router model id                    | Source repo                                                                                              | Context | Notes |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------- | ------- | ----- |
| `gemma-4-26b-a4b-256k`              | [unsloth/gemma-4-26B-A4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF)            | 256k    | 1 slot, MTP speculative decoding, reasoning on |
| `gemma-4-26b-a4b-64k`               | [unsloth/gemma-4-26B-A4B-it-qat-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-qat-GGUF)            | 256k / 4 slots (64k each) | parallel=4, MTP speculative decoding, reasoning off |
| `qwen3.6-35b-a3b-64k`                | [unsloth/Qwen3.6-35B-A3B-MTP-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-MTP-GGUF)                  | 64k     | 1 slot, MTP speculative decoding, reasoning on |
| `glm-4.7-flash-reap-23b-a3b-64k`     | [unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF](https://huggingface.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF)    | 64k     | 1 slot, reasoning on, no speculative decoding |

All four use the `UD-Q4_K_XL` quant. Full per-model sampling params and
shared defaults (GPU offload, batch sizes, KV cache types, etc.) are in
[`models.ini`](./models.ini).

## Aliases (for litellm or similar)

These are example client-side aliases — they're not configured in this
container, just documented here so the mapping to router model ids is
obvious when wiring up a routing layer:

```
gemma-4         -> gemma-4-26b-a4b-64k
gemma-4-64k     -> gemma-4-26b-a4b-64k
gemma-4-256k    -> gemma-4-26b-a4b-256k
qwen-3.6        -> qwen3.6-35b-a3b-64k
glm-4.7-flash   -> glm-4.7-flash-reap-23b-a3b-64k
```

## Running

```bash
docker run --gpus all -p 8080:8080 -v ./model-cache:/models \
  ghcr.io/<owner>/<repo>/multiple-moe:latest
```

All four models have `load-on-startup = true`, so the first start will take
a while (downloading ~tens of GB, then loading all four into VRAM). Once
running, `GET /v1/models` should list all four router model ids, and
`POST /v1/chat/completions` with `"model": "<id>"` routes to the matching
slot.

## Extra args

The entrypoint forwards any extra container arguments to `llama-server`
after its fixed flags (`--host`, `--port`, `--models-preset`), so you can
override or add flags at runtime without rebuilding, e.g.:

```bash
docker run --gpus all -p 8080:8080 -v ./model-cache:/models \
  ghcr.io/<owner>/<repo>/multiple-moe:latest --models-max 2
```