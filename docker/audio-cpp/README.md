# PreFer audio.cpp runtime

PreFer publishes CUDA 12 and CPU audio.cpp images with pinned speech, music,
ASR, and full-duplex conversation artifacts.

Generated hardware deployments and server-config trees have been removed.
`deployment-inventory.generated.json` publishes model/profile/bundle metadata
and a base-free runtime composition contract; its `deployments` array is empty.

## Runtime selection

Use one or both semantic selectors:

- `AUDIO_BUNDLE` / `PREFER_BUNDLE`
- `AUDIO_MODELS` / `PREFER_MODELS`

Or supply an immutable handoff through `AUDIO_RUNTIME_HANDOFF` or
`AUDIO_RUNTIME_HANDOFF_BASE64`. Handoffs are mutually exclusive with direct
selectors. Server and per-model JSON overrides are applied after catalog
settings. The generated effective config and plan live under `/run/prefer`.

Semantic bundles group capabilities only; they do not encode GPU choices,
context, concurrency, or hardware fit.

## Staging

Artifacts use immutable revisions, exact paths, byte sizes, SHA-256 checks,
atomic publication, and `downloads-v2` markers on `/models`. The release-matched
CPU downloader can stage the same handoff before a GPU worker starts.

## API and residency

The server listens on port 8080 in the container. Models remain lazy and the
runtime retains at most one resident model unless explicitly overridden.
Consult `deployment-inventory.generated.json` for request IDs, tasks, model
profiles, and exact artifact totals.

## Generation

```bash
python generate.py
python generate.py --check
```

Checked-in CUDA/CPU server JSON files are empty base templates. Effective model
configs are generated only at runtime.
