# PreFer changelog

This file is the canonical update reference for consumer-visible PreFer
hosted-model and preset changes. Each entry is written in the same commit as
the changes it describes and uses a concise descriptive heading. It records
the llama.cpp base image, hosted-model inventory, preset additions or removals,
context and concurrency changes, artifact or speculative-decoding changes,
prestaging impact, and compatibility notes.

There is no prospective `Unreleased` section and no independent PreFer
calendar or semantic version. An entry does not try to predict its own commit
SHA; CI assigns the resulting immutable `sha-<short-commit>` image tag after
merge.

The first entry below was recorded immediately after its implementation image
had already published, before the same-commit policy above was adopted.

## AWS hosted-model preset expansion

- Source: `53b2f31d1f5bf2cc03c681343781d6d6555b19a3`
- Image: `ghcr.io/cvalusek/prefer:sha-53b2f31@sha256:3bb7b4bbeddeff0441a91cf0d0074541895423c26503db213b3b1989762254d2`
- llama.cpp base: `server-cuda-b10362@sha256:182a26fbd68d1774860bd2a0fb5581ba3047974307eaeee64930d8bf889e0c0c`

### Hosted-model and preset changes

- Made every AWS `general.ini` cumulative: it now contains one best
  host-appropriate lane for every model assigned to that instance tier and
  lower tiers.
- Expanded `aws/g6/xlarge/general.ini` with Muse Glimmer 30B Q4 plus DFlash.
  Gemma E4B increased from 2×128K to 4×128K. The complete g6 inventory is now
  Gemma E2B/E4B/12B at 4×128K, Qwen3.5-9B at 2×128K, and Muse at 1×128K.
- Added `aws/g6e/xlarge/general.ini`. Its complete inventory is Gemma
  E2B/E4B/12B at 4×128K, Gemma 26B-A4B at 2×256K, Gemma 31B at 1×256K,
  Qwen3.5-9B at 2×128K, Qwen3.6 35B-A3B/27B at 1×192K, and Muse at 2×128K.
- Added g6e Qwen family and single-model presets: `qwen.ini`,
  `qwen-35b-a3b.ini`, and `qwen-27b.ini`. Both Qwen3.6 models use
  `UD-Q6_K_XL`, embedded MTP, f16 K/V, and one 192K slot. Gemma 26B's g6e
  family and single-model lanes changed from 4×128K to 2×256K; Gemma 31B
  remains 1×256K.
- Expanded `aws/g7e/2xlarge/general.ini` with the lower-tier Gemma,
  Qwen3.5-9B, and Muse routes. Gemma 26B-A4B runs 4×256K, Gemma 31B runs
  2×256K, Qwen3.6 35B-A3B/27B increased from 4×128K to 4×256K,
  GLM-4.7-Flash increased from 4×128K to 4×202,752, and Muse uses 4×128K.
- Added g7e Gemma family and single-model presets: `gemma.ini`,
  `gemma-26b-a4b.ini`, and `gemma-31b.ini`. The QAT Gemma lanes use
  `UD-Q4_K_XL`, their matching Q4_0 MTP assistants, F16 projectors, and f16
  K/V.
- Updated the g7e Qwen family and single-model presets to 4×256K. Updated the
  g7e Muse family/single lane from the experimental 4×256K shape to the
  publisher-default 4×128K shape.
- Increased `aws/g7e/12xlarge/deepseek-v4-flash-0731.ini` from 1×256K to the
  owner-verified 4×384K shape. It retains the five-shard `UD-Q4_K_XL` target,
  Q8_0 DSpark companion, `draft-dspark`, draft maximum 5, f16 K/V, and no
  IQ1/IQ2 lane.
- No hosted model was removed. Stable aliases, the v1 client contract,
  `models-max=1`, the b10362 runtime pin, and the removed Qwen 1M YaRN route
  are unchanged.

### Prestaging and operator impact

- Regenerated every affected `.ini` and `.prestage` pair. Blank
  `PRESTAGE_MODELS` now stages the full cumulative inventory selected by each
  `general.ini`; the g6e general sidecar contains nine model keys and the g7e
  general sidecar contains ten.
- Added matching sidecars for every new g6e Qwen and g7e Gemma family/single
  preset. Family and single-model presets remain the recommended choice when
  the controller already knows the assigned model and the full cumulative S3
  transfer/startup inventory is undesirable.
- All AWS lanes continue to use f16 K and V. Existing immutable Hugging Face
  artifact revisions and hashes are unchanged; this release changes where
  those pinned artifacts are exposed and their context/concurrency shapes.
