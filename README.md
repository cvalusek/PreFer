# PreFer

PreFer is a set of practical llama.cpp inference presets for self-hosted LLMs.
It packages known-good model mixes, VRAM-aware router configs, and download
scripts into containers that are easy to run locally, on RunPod, or behind a
small internal control plane.

The current flagship preset is `multiple-moe`: Gemma 4, Qwen3.6, and
GLM-4.7-Flash served through `llama-server` router mode with an
OpenAI-compatible API on port `8080`.

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
  multiple-moe/       PreFer's current llama.cpp router image
control-plane/        NeurOn, a lightweight capacity switch for local/AWS targets
.github/workflows/    Build workflows
```

`control-plane/` contains NeurOn for now, but it is intentionally separable
and may move to its own repository later.

## Quick Start

Copy the example environment file and adjust as needed:

```bash
cp .env.example .env
```

Build the inference image:

```bash
docker compose --profile llm-capacity build multiple-moe
```

Run the inference server directly:

```bash
docker compose --profile llm-capacity up multiple-moe
```

Models are stored in the named Docker volume `llm-hosting-model-cache` by
default. Override `LLM_MODEL_VOLUME` in `.env` if you want a different cache.

Once the server is ready:

```bash
curl http://localhost:8080/v1/models
```

## NeurOn Local Control

NeurOn is included as a lightweight local control plane. It lets you reserve
models for a short duration and keeps shared capacity on only while someone
needs it.

```bash
docker compose up --build control-plane
```

Open `http://localhost:8090`, pick models, choose a duration, and reserve.
`multiple-moe` stays behind the `llm-capacity` profile until NeurOn starts it.

## Environment

Most local configuration lives in `.env`; see [.env.example](.env.example).
Useful knobs:

- `PRESTAGE_MODELS` limits which Hugging Face repos are downloaded.
- `HF_TOKEN` improves Hugging Face rate limits.
- `LLAMA_ARG_MODELS_PRESET` forces a specific preset instead of VRAM detection.
- `LLAMA_ARG_MODELS_MAX` controls llama.cpp router concurrency/loading.
- `LLM_MODEL_VOLUME` names the persistent Docker volume for `/models`.
- `CONTROL_PLANE_PORT` and `LLM_PORT` set host ports.

## Netskope / Corporate TLS

If Docker builds fail with Python or npm certificate errors, use the Netskope
overlay. Export your corporate root/intermediate certificates as `.crt` files
under `docker/certs/` and run:

```bash
docker compose -f docker-compose.yml -f docker-compose.netskope.yml --profile llm-capacity build multiple-moe
docker compose -f docker-compose.yml -f docker-compose.netskope.yml up --build control-plane
```

Certificate files under `docker/certs/` are ignored by git.

## Images

GitHub Actions build container images for the repo. The PreFer image is the
`multiple-moe` service today; additional model sets can be added under
`docker/<name>/` as the preset library grows.

See [docker/multiple-moe/README.md](docker/multiple-moe/README.md) for model
details, preset tiers, aliases, and operational notes.
