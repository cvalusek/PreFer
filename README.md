# PreFer

PreFer is a set of practical llama.cpp inference presets for self-hosted LLMs.
It packages known-good model mixes, VRAM-aware router configs, and download
scripts into containers that are easy to run locally or on RunPod.

The current PreFer container serves Gemma 4, Qwen3.6, and GLM-4.7-Flash
through `llama-server` router mode with an
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
  prefer/             PreFer's llama.cpp router image
.github/workflows/    Build workflows
```

## Quick Start

Copy the example environment file and adjust as needed:

```bash
cp .env.example .env
```

Build the inference image:

```bash
docker compose build prefer
```

Run the inference server directly:

```bash
docker compose up prefer
```

Models are stored in the named Docker volume `prefer-model-cache` by
default. Override `LLM_MODEL_VOLUME` in `.env` if you want a different cache.

Once the server is ready:

```bash
curl http://localhost:8080/v1/models
```

## Environment

Most local configuration lives in `.env`; see [.env.example](.env.example).
Useful knobs:

- `PRESTAGE_MODELS` limits which Hugging Face repos are downloaded.
- `HF_TOKEN` improves Hugging Face rate limits.
- `LLAMA_ARG_MODELS_PRESET` forces a specific preset instead of VRAM detection.
- `LLAMA_ARG_MODELS_MAX` controls llama.cpp router concurrency/loading.
- `LLM_MODEL_VOLUME` names the persistent Docker volume for `/models`.
- `LLM_PORT` sets the host port.

## Netskope / Corporate TLS

If Docker builds fail with Python or npm certificate errors, use the Netskope
overlay. Export your corporate root/intermediate certificates as `.crt` files
under `docker/certs/` and run:

```bash
docker compose -f docker-compose.yml -f docker-compose.netskope.yml build prefer
docker compose -f docker-compose.yml -f docker-compose.netskope.yml up prefer
```

Certificate files under `docker/certs/` are ignored by git.

## Images

GitHub Actions build the PreFer image. Additional model sets can be added
under `docker/<name>/` as the preset library grows.

See [docker/prefer/README.md](docker/prefer/README.md) for model
details, preset tiers, aliases, and operational notes.
