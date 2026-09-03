# Grouped PreFer release

PreFer publishes llama.cpp, audio.cpp, and stable-diffusion.cpp as one atomic
release. A runtime change rebuilds all engine images with the same
`sha-<commit>` version instead of asking downstream consumers to combine
component releases.

`main` is the stable release line. `develop` is the opt-in preview line, and
its immutable GitHub releases are marked as prereleases. A successful grouped
build advances only its own branch's moving image aliases: stable aliases for
`main`, preview aliases for `develop`. Promotion is a merge from `develop` to
`main`, followed by the normal stable grouped build. Existing releases created
before this split are stable.

Each immutable GitHub release and matching Actions artifact contains:

- `prefer-release.json`: exact engine/backend image tags and OCI index digests
- `prefer-release.schema.json`: the public `prefer.release.v1` schema
- `prefer-llama-deployment-inventory.json`
- `prefer-audio-deployment-inventory.json`
- `prefer-image-deployment-inventory.json`
- `SHA256SUMS`

A controller starts with `prefer-release.json`, selects the required
engine/backend, and then reads that engine's referenced inventory for hardware,
configuration, model, and prestaging choices. All references are immutable.
NeurOn and similar controllers can select `main` or `develop` as their release
source, but must ignore a branch head until its complete grouped release exists.

The bundle contains metadata only. Model weights are neither copied into the
release nor embedded in its container images; each runtime stages them onto its
external `/models` storage after deployment.

`build-release.py` runs only after every engine build returns its published OCI
digest. It validates the source revision and all four digests, copies the exact
generated inventories without rewriting them, records their catalog
fingerprints and SHA-256 values, and emits the grouped manifest.
