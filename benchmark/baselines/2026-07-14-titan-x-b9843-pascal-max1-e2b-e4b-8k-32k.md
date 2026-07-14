# PreFer benchmark report

Run `current-3fbbdf6a43` used source `1565b9260d5deb3c4e9e8e7012f6f1c75a536cba` with `ghcr.io/ggml-org/llama.cpp:server-cuda-b9843` (version: 9843 (86b94708f)) on preset `12gb-pascal.ini` and `models-max=1`.

Started: `2026-07-14T03:44:42.911Z`; duration: `269.442s`; contract: `1.0.0`; evaluation corpus: `1.0.0`; hardware tier: `12gb`.

## Outcome

- Schema-contract pass rate: **100.0%** across `4` attempted structured responses
- Semantic anomaly rate: **0.0%** across `4` evaluated response documents
- Cell status counts: `{"passed": 16, "skipped": 2}`

Schema validity and semantic correctness are intentionally separate; a schema-valid response can still contain an impossible date or omit required plan content.

## Cells

| Cell | State | Model | Total ms | TTFT ms | Prefill ms | Decode ms | Prompt / output tokens | Peak GPU MiB | Contract | Schema | Semantic anomalies |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- |
| `cold-readiness` | passed | `—` | 2687.3 | — | — | — | — / — | — | pass | — | — |
| `models-discovery` | passed | `—` | — | — | — | — | — / — | — | pass | — | — |
| `configured-identity-route-a` | passed | `unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL` | 21.1 | — | — | — | — / — | — | pass | — | — |
| `first-load-a-router-id` | passed | `unsloth/gemma-4-E2B-it-qat-GGUF:Q4_K_XL` | 54553.6 | — | 10963.0 | 75.0 | 17 / 5 | 5189 | pass | — | — |
| `warm-a` | passed | `gemma-4-e2b` | 228.0 | — | 51.5 | 39.0 | 15 / 4 | 5189 | pass | — | — |
| `stream-a` | passed | `gemma-4-e2b` | 350.8 | 165.1 | — | — | — / — | 5189 | pass | — | — |
| `stream-cancel-a` | passed | `gemma-4-e2b` | 182.1 | — | — | — | — / — | — | pass | — | — |
| `concurrency-2-a` | passed | `gemma-4-e2b` | 529.3 | — | — | — | — / — | 5189 | pass | — | — |
| `structured-aurora-facts-v1` | passed | `gemma-4-e2b` | 1024.4 | — | 102.1 | 786.8 | 96 / 88 | 5197 | pass | pass | none |
| `structured-cedar-plan-v1` | passed | `gemma-4-e2b` | 4473.5 | — | 125.5 | 4211.1 | 158 / 248 | 5201 | pass | pass | none |
| `tools-a` | passed | `gemma-4-e2b` | 567.7 | — | 80.2 | 142.7 | 80 / 20 | — | pass | — | — |
| `swap-a-to-b` | passed | `unsloth/gemma-4-E4B-it-qat-GGUF:Q4_K_XL` | 12203.8 | — | 119.4 | 98.1 | 17 / 5 | 6663 | pass | — | — |
| `swap-b-to-a` | passed | `gemma-4-e2b` | 7950.8 | — | 111.6 | 61.8 | 18 / 6 | 6663 | pass | — | — |
| `models-max-1` | passed | `—` | — | — | — | — | — / — | — | pass | — | — |
| `idle-unload` | skipped (wait_not_selected) | `gemma-4-e2b` | — | — | — | — | — / — | — | — | — | — |
| `long-context-8k` | passed | `gemma-4-e2b` | 5564.2 | — | 4601.8 | 797.1 | 8000 / 51 | 5217 | pass | pass | none |
| `long-context-32k` | passed | `gemma-4-e2b` | 41761.0 | — | 40683.5 | 742.0 | 32576 / 51 | 5217 | pass | pass | none |
| `long-context-128k` | skipped (not_selected) | `gemma-4-e2b` | — | — | — | — | — / — | — | — | — | — |

## Skipped or unsupported

- `structured_skip` / `wait_not_selected`: Preset idle sleep is 1800s; use --idle-wait-seconds 1805 to measure it. Cells: `idle-unload`.
- `structured_skip` / `not_selected`: Use --contexts to opt into the 131072-token cell. Cells: `long-context-128k`.

## Backend provenance

- Published tag: `ghcr.io/ggml-org/llama.cpp:server-cuda-b9843`
- Immutable linux/amd64 manifest: `sha256:3af9b6f556151848ce221c63a63f87c04832d6666361babca20ee6295255f1c6`
- Source commit: `86b94708f22478f900b76ca02e316f4f3418faff`
- Manifest check: `verified`
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
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b,gemma-4-e4b --preset 12gb-pascal.ini --models-max 1 --contexts 8k,32k --timeout-seconds 300 --readiness-timeout-seconds 120 --output benchmark/artifacts/2026-07-14-b9843-pascal-max1-e2b-e4b-8k-32k.json
```

## Gates for any later backend spike

A future isolated backend comparison should answer these questions before any migration decision:

- Does it pass every promised v1 contract replay cell for configured identities, router discovery IDs, aliases, strict JSON, streaming termination, bounded client cancellation, tools envelopes, and errors?
- Does it avoid regressing schema-contract pass rate or semantic anomaly rate on the same synthetic corpus and prompt version?
- At equal model, quantization, context, and hardware, what measured cold-load, warm, A→B→A, p50/p95 concurrent, TTFT, decode, and memory improvement clears an owner-selected threshold?
- Does it preserve the single-router light-tier swap design and fit the tested hardware without adding provider or reservation lifecycle ownership?
- Does it support the required 8K/32K/128K cells without silently truncating or reporting nominal context as task success?

No architecture choice follows from this report alone.
