# llm-containers

Container builds for self-hosted LLM inference, primarily targeting RunPod
(and eventually some lighter-weight home-network boxes).

Each container packages a known-good [llama.cpp](https://github.com/ggml-org/llama.cpp)
server configuration: on first start it downloads the relevant model(s) from
Hugging Face via the `hf` CLI, then launches `llama-server` in
[router mode](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#using-multiple-models),
exposing an OpenAI-compatible API on port `8080`. Each container ships
multiple VRAM-tiered presets (`presets/<N>gb.ini`) and auto-selects one based
on the detected GPU's VRAM at startup, so the same image works across
different hardware without rebuilding.

## Layout

```
docker/
  multiple-moe/    # gemma-4, qwen3.6, glm-4.7-flash; presets for 96gb/12gb/8gb VRAM tiers
.github/workflows/ # GitHub Actions to build + push images to GHCR
```

Additional `docker/<name>/` folders may be added for other model sets or
build variants.

## Images

Images are built via GitHub Actions and pushed to GHCR at
`ghcr.io/<owner>/<repo>/<name>` (e.g. `ghcr.io/<owner>/<repo>/multiple-moe`).
See each subfolder's README for model details, presets, and the model
aliases each container's router exposes.

## Building locally

```bash
docker compose up --build multiple-moe
```

Relevant env vars (read from your shell or a `.env` file in this directory):

- `LLM_MODEL_PATH` — host directory mounted at `/models` for downloaded GGUFs
  (default `./model-cache`)
- `LLM_PORT` — host port mapped to the container's `8080` (default `8080`)
- `HF_TOKEN` — optional, helps with Hugging Face rate limits
- `LLAMA_ARG_MODELS_PRESET` / `LLAMA_ARG_MODELS_MAX` — optional, force a
  specific preset instead of VRAM-based auto-detection. On Windows, prefer
  setting these in a `.env` file rather than as shell env vars — Git Bash
  mangles leading-`/` paths passed as arguments/env to non-MSYS programs.

The `/models/<hf-org>/<hf-repo>/...` layout means multiple services in this
compose file can safely share the same `LLM_MODEL_PATH` without colliding or
re-downloading shared models.