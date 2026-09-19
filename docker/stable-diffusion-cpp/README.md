# PreFer stable-diffusion.cpp runtime

This image wraps the pinned stable-diffusion.cpp server with PreFer's lazy
one-worker router for image generation and editing.

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
