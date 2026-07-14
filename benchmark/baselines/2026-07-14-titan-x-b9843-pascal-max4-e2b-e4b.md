# PreFer benchmark report

Run `current-2808dc9f80` used source `caa927332af42b611aaf2444bab2d47129d29934` with `ghcr.io/ggml-org/llama.cpp:server-cuda-b9843` (version: 9843 (86b94708f)) on preset `12gb-pascal.ini` and `models-max=4`.

Started: `2026-07-14T03:51:54.038Z`; duration: `190.687s`; contract: `1.0.0`; evaluation corpus: `1.0.0`; hardware tier: `12gb`.

## Outcome

- Schema-contract pass rate: **100.0%** across `2` attempted structured responses
- Semantic anomaly rate: **0.0%** across `2` evaluated response documents
- Cell status counts: `{"passed": 14, "skipped": 4}`

Schema validity and semantic correctness are intentionally separate; a schema-valid response can still contain an impossible date or omit required plan content.

## Cells

| Cell | State | Model | Total ms | TTFT ms | Prefill ms | Decode ms | Prompt / output tokens | Peak GPU MiB | Contract | Schema | Semantic anomalies |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- |
| `cold-readiness` | passed | `—` | 1726.4 | — | — | — | — / — | — | pass | — | — |
| `models-discovery` | passed | `—` | — | — | — | — | — / — | — | pass | — | — |
| `configured-identity-route-a` | passed | `unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL` | 21.4 | — | — | — | — / — | — | pass | — | — |
| `first-load-a-router-id` | passed | `unsloth/gemma-4-E2B-it-qat-GGUF:Q4_K_XL` | 49434.7 | — | 11255.0 | 71.2 | 17 / 5 | 5189 | pass | — | — |
| `warm-a` | passed | `gemma-4-e2b` | 228.8 | — | 50.0 | 44.7 | 15 / 4 | 5189 | pass | — | — |
| `stream-a` | passed | `gemma-4-e2b` | 368.5 | 182.7 | — | — | — / — | 5189 | pass | — | — |
| `stream-cancel-a` | passed | `gemma-4-e2b` | 181.4 | — | — | — | — / — | — | pass | — | — |
| `concurrency-2-a` | passed | `gemma-4-e2b` | 548.7 | — | — | — | — / — | 5189 | pass | — | — |
| `structured-aurora-facts-v1` | passed | `gemma-4-e2b` | 1049.7 | — | 108.5 | 804.2 | 96 / 88 | 5197 | pass | pass | none |
| `structured-cedar-plan-v1` | passed | `gemma-4-e2b` | 4358.3 | — | 123.5 | 4095.0 | 158 / 248 | 5201 | pass | pass | none |
| `tools-a` | passed | `gemma-4-e2b` | 573.8 | — | 80.0 | 134.2 | 80 / 20 | — | pass | — | — |
| `swap-a-to-b` | passed | `unsloth/gemma-4-E4B-it-qat-GGUF:Q4_K_XL` | 11810.8 | — | 120.7 | 101.8 | 17 / 5 | 10348 | pass | — | — |
| `swap-b-to-a` | passed | `gemma-4-e2b` | 231.7 | — | 55.9 | 36.6 | 17 / 6 | 10348 | pass | — | — |
| `models-max-4` | passed | `—` | — | — | — | — | — / — | — | pass | — | — |
| `idle-unload` | skipped (wait_not_selected) | `gemma-4-e2b` | — | — | — | — | — / — | — | — | — | — |
| `long-context-8k` | skipped (not_selected) | `gemma-4-e2b` | — | — | — | — | — / — | — | — | — | — |
| `long-context-32k` | skipped (not_selected) | `gemma-4-e2b` | — | — | — | — | — / — | — | — | — | — |
| `long-context-128k` | skipped (not_selected) | `gemma-4-e2b` | — | — | — | — | — / — | — | — | — | — |

## Skipped or unsupported

- `structured_skip` / `wait_not_selected`: Preset idle sleep is 1800s; use --idle-wait-seconds 1805 to measure it. Cells: `idle-unload`.
- `structured_skip` / `not_selected`: Use --contexts to opt into the 8192-token cell. Cells: `long-context-8k`.
- `structured_skip` / `not_selected`: Use --contexts to opt into the 32768-token cell. Cells: `long-context-32k`.
- `structured_skip` / `not_selected`: Use --contexts to opt into the 131072-token cell. Cells: `long-context-128k`.

## Backend provenance

- Published tag: `ghcr.io/ggml-org/llama.cpp:server-cuda-b9843`
- Immutable linux/amd64 manifest: `sha256:3af9b6f556151848ce221c63a63f87c04832d6666361babca20ee6295255f1c6`
- Source commit: `86b94708f22478f900b76ca02e316f4f3418faff`
- Manifest check: `pinned_not_checked_cached_image`
- Release: https://github.com/ggml-org/llama.cpp/releases/tag/b9843

## Isolation cleanup

- Temporary containers absent: `True`
- Temporary networks absent: `True`
- Temporary model volume absent: `True`
- Source model cache mount: `read_only`
- Operator `prefer` unchanged: `True` (`exited` → `exited`)
- NeurOn container unchanged: `True` (`running` → `running`)
- Host port 8080 used: `False`

## Reproduce

```text
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b,gemma-4-e4b --preset 12gb-pascal.ini --models-max 4 --contexts none --timeout-seconds 300 --readiness-timeout-seconds 120 --no-build --output benchmark/artifacts/2026-07-14-b9843-pascal-max4-e2b-e4b.json
```

## Gates for any later backend spike

A future isolated backend comparison should answer these questions before any migration decision:

- Does it pass every promised v1 contract replay cell for configured identities, router discovery IDs, aliases, strict JSON, streaming termination, bounded client cancellation, tools envelopes, and errors?
- Does it avoid regressing schema-contract pass rate or semantic anomaly rate on the same synthetic corpus and prompt version?
- At equal model, quantization, context, and hardware, what measured cold-load, warm, A→B→A, p50/p95 concurrent, TTFT, decode, and memory improvement clears an owner-selected threshold?
- Does it preserve the single-router light-tier swap design and fit the tested hardware without adding provider or reservation lifecycle ownership?
- Does it support the required 8K/32K/128K cells without silently truncating or reporting nominal context as task success?

No architecture choice follows from this report alone.
