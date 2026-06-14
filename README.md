# llm-containers

Container builds for self-hosted LLM inference, primarily targeting RunPod
(and eventually some lighter-weight home-network boxes).

Each container packages a known-good [llama.cpp](https://github.com/ggml-org/llama.cpp)
server configuration: on first start it downloads the relevant model(s) from
Hugging Face via the `hf` CLI, then launches `llama-server` in
[router mode](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#using-multiple-models)
using a `models.ini` preset file, exposing an OpenAI-compatible API on port `8080`.

## Layout

```
docker/
  multiple-moe/    # RTX 6000 build: gemma-4 (256k + 64k), qwen3.6, glm-4.7-flash
.github/workflows/ # GitHub Actions to build + push images to GHCR
```

Additional `docker/<name>/` folders may be added for other hardware targets
(e.g. lower-VRAM home GPUs running a subset of these models).

## Images

Images are built via GitHub Actions and pushed to GHCR at
`ghcr.io/<owner>/<repo>/<name>` (e.g. `ghcr.io/<owner>/<repo>/multiple-moe`).
See each subfolder's README for model details, hardware requirements, and
the model aliases each container's router exposes.

## Building locally

```bash
docker build -t multiple-moe ./docker/multiple-moe
docker run --gpus all -p 8080:8080 -v ./model-cache:/models multiple-moe
```

Mounting `/models` to a persistent volume avoids re-downloading the GGUFs
(tens of GB) on every container restart.