# PreFer stable-diffusion.cpp runtime

CUDA 12 and Vulkan images wrap stable-diffusion.cpp with PreFer's lazy
one-worker router for image generation and editing. The pinned Vulkan base is
at upstream `c92d73c`, newer than the CUDA base `137f740`; its router API,
GPU/model behavior, and worker startup need an exact smoke before use. Vulkan
requires a native Vulkan device/ICD; it is not ROCm.

Hardware-specific deployment scenarios and generated server-config trees have
been removed. The release inventory publishes models, profiles, semantic
bundles, API facts, and composition inputs without model/hardware pairings.

## Runtime selection

Use `IMAGE_BUNDLE` and/or `IMAGE_MODELS`, or provide an immutable
`IMAGE_RUNTIME_HANDOFF` / `IMAGE_RUNTIME_HANDOFF_BASE64`. A handoff is mutually
exclusive with direct selectors. Catalog defaults are followed by server and
model overrides; the effective config and plan are written under `/run/prefer`.

Bundles such as `fast`, `generation`, `edit`, and `quality` express product
intent only. They do not claim fit on a named GPU.

## API

The public surface includes:

- `GET /health`
- `GET /v1/models`
- `POST /v1/images/generations`
- `POST /v1/images/edits`
- the synchronous `/sdapi/v1` compatibility surface

Discovery does not load a model. The router serializes worker access and swaps
the private one-model worker when selection changes.

## Artifact staging

Artifacts are staged beneath `/models` at immutable revisions with exact size
and digest verification, atomic publication, and `downloads-v2` markers. Use
the release-matched CPU downloader to populate shared storage from the same
handoff before starting GPU execution.

## Generation

```bash
python generate.py
python generate.py --check
```

`server.generated.json` is a discovery-only empty base template. Runtime model
configuration is ephemeral.
