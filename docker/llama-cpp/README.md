# PreFer llama.cpp runtime

The CUDA 12 and ROCm (Linux AMD64) images run the same pinned llama.cpp router
and PreFer handoff. The ROCm image is build-only until exact GPU/model/API
verification. Native Linux requires `/dev/kfd` and `/dev/dri`; Windows WSL
`/dev/dxg` needs separate ROCDXG setup and is not an equivalent device mount.
Hardware presets, VRAM-tier INIs, local GPU profiles, and automatic preset
detection have been removed.

## Selection

Choose models explicitly with `LLAMA_MODELS`/`PREFER_MODELS`, or supply an
immutable handoff through `LLAMA_RUNTIME_HANDOFF` or
`LLAMA_RUNTIME_HANDOFF_BASE64`. A blank selection fails instead of guessing.

At startup, `generate-presets.py --compose` writes:

- `/run/prefer/llama.ini`
- `/run/prefer/llama.prestage`
- `/run/prefer/plan.json`

The precedence is catalog lane defaults, server overrides, model overrides,
then raw llama-server arguments. `LLAMA_ARG_MODELS_MAX` remains an independent
router residency limit and defaults to one in Compose.

Direct model selection is an unmanaged convenience path. Context, parallelism,
cache types, offload, and speculation must be chosen explicitly based on live
resources. Controllers should use `prefer-inference-core` planning and a
release-bound handoff.

## Artifact staging

Direct selections resolve exact immutable revisions, paths, sizes, and SHA-256
values from the engine catalog. `/download-models.sh` stages them with the
shared `downloads-v2` helper and verification markers. Runtime handoffs use the
same helper and `/models/<repository>/<path>` layout.

For a cheap pre-GPU stage, use the release-matched CPU downloader image with the
same handoff and model volume. `PRESTAGE_MODELS=none` intentionally skips direct
model-key staging.

## API

The router listens on port 8080 and exposes the repository's versioned narrow
OpenAI-style contract. Model aliases and exact request IDs are listed in
`deployment-inventory.generated.json`; deployment records are intentionally
empty because hardware/model pairings are no longer published.

## Generation

```bash
python generate-presets.py
python generate-presets.py --check
```

The generator emits only the model download map and deployment inventory.
Runtime INIs are ephemeral.
