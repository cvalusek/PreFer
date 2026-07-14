# PreFer contract and benchmark harness

This repository owns a small, versioned client contract and a measurement
harness for the existing llama.cpp router. It does not select a new serving
backend, translate another vendor API, or manage operational capacity.

All evaluation prompts in `eval/v1/corpus.json` are synthetic and non-private.
Generated local artifacts go under the ignored `benchmark/artifacts/` folder;
only deliberately scrubbed, reviewed baselines belong in
`benchmark/baselines/`.

## Research provenance and decision boundary

This slice was prompted by observatory topic
`research/topics/prefer-next-revision-2026-07/` at commit
`dc5cecc7af4faa8b064bb684bbfd5769b897c7d9`. That corpus is machine-reviewed,
not human-approved, and marked `production_eligible=false`; its claims are
inputs to verification rather than architecture decisions. Its inspected
PreFer revision, `2fc6c8159535757f10f5d193e7ccbd4045ef0dd0`, was the repository
HEAD when implementation began.

The harness resolves repository-local contract, identity, and `models-max`
facts. It deliberately leaves these measurements as VERIFY items: 96 GB
retention at `models-max=4`, the full 1800-second idle/unload cycle, 32K and
128K quality on each supported light model, models other than already-cached
Gemma E2B/E4B, the opt-in b9990 comparison, and whether E4B's observed loader
failure reproduces on another GPU/build. None of those gaps licenses a backend
migration or a production-default change.

## Stable client contract

`contract/v1/contract.json` is the authoritative v1 promise. Tests keep its
model IDs and aliases synchronized with every checked-in preset.

The promised surface is intentionally narrow:

- `GET /v1/models`: HTTP 200 JSON object with a `data` array whose entries have
  non-empty `id` strings. Router-specific metadata and exact status fields are
  evidence, not required response fields.
- `POST /v1/chat/completions`, non-streaming: the minimal chat-completion,
  choice, and assistant-message envelope exercised by current clients.
- The same endpoint with `stream=true`: SSE `data:` JSON chunks with
  `object=chat.completion.chunk`, terminated by `data: [DONE]`.
- Configured cross-system identities, normalized router IDs, and aliases in the
  versioned fixture. Ground Control's NeurOn/control-plane identity is
  `unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL`; its PreFer alias is
  `gemma-4-e2b`. b9843 returns and accepts the normalized router ID ending
  `:Q4_K_XL`. It rejects the configured UD identity as a PreFer route, so the
  fixture intentionally does not conflate these roles or promise that every
  preset section name is a request target.
- Ground Control's strict structured-output request form:
  `response_format.type=json_schema` with nested
  `json_schema={name, strict: true, schema}`. The assistant content must parse
  and validate against the supplied schema.
- OpenAI function-tool request, conditional `tool_calls` envelope, and
  `role=tool` result message. Tool selection, execution, parallel calls, and
  semantic correctness are not promised.
- Rejected contract requests have an `error` object with non-empty `message`
  and `type`. Exact HTTP status, code, and wording are not stable.

PreFer does not promise the rest of the OpenAI API, Anthropic messages,
llama.cpp's built-in `/tools`, or full compatibility with any upstream
specification.

Timeout and cancellation are client-owned in v1: every harness call has a
deadline, and cancellation means the client closes an SSE connection and
returns in bounded time. Whether the backend immediately stops generation is
not observed or promised. PreFer configures no stable request-byte limit; the
harness has a local safety cap and records any backend rejection. Context is a
model/preset dimension, not a generic API guarantee.

Run the deterministic replay (16 positive and negative checks):

```bash
python -m prefer_bench contract --mock
```

Run every unit, parser, schema, fixture, report, anomaly, and isolation test:

```bash
python -m unittest discover -s benchmark/tests -v
```

## `models-max` facts and open policy

The checked-in behavior is now documented without changing it:

1. A `--models-max N` argument passed to `llama-server` has highest precedence.
2. `LLAMA_ARG_MODELS_MAX` is next. The normal `docker-compose.yml` always
   passes it and defaults it to `1`; `.env.example` also says `1`.
3. When no preset was explicitly selected, `detect-preset.sh` chooses a tier
   and assigns `1` if that preset has no `load-on-startup` entries. None of the
   current `8gb.ini`, `12gb.ini`, or `96gb.ini` entries load on startup, so a
   direct auto-detected tier also resolves to `1`.
4. If a preset is selected explicitly outside the normal Compose path and no
   CLI/environment value is supplied, detection does not assign a fallback and
   llama.cpp uses its router default of `4`. The named single-model presets
   contain `load-on-startup`, but their effective loaded-model count is still
   one because each contains one model.

The effective normal Compose default is therefore **1 for every preset unless
the operator overrides it**. The old README statement that 96 GB normally used
4 was documentation drift, not evidence that production should change.

`models-max` is an explicit benchmark flag:

```bash
python -m prefer_bench models-max
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b,gemma-4-e4b --preset 12gb.ini --models-max 4 --contexts 8k
```

The remaining policy choice is whether the normal 96 GB path should continue
with swap-on-demand at 1 or deliberately load/retain more models. That choice
needs cold/warm/swap/concurrency/memory measurements on the 96 GB hardware; the
harness does not guess it.

## Isolated current-backend baseline

The default baseline builds the production-pinned b9843 Dockerfile, never
downloads models, and copies only selected files from an existing Docker cache
into a generated run volume:

```bash
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b,gemma-4-e4b --preset 12gb.ini --models-max 1 --contexts 8k
```

The command records cold router startup/readiness (Compose service start through
the first successful `/v1/models`, excluding image build and cache clone), first model load, warm request,
streaming and termination, client stream close, concurrency, strict JSON,
semantic anomalies, conditional tools, A→B→A swapping, loaded-model count,
idle behavior, and the 8K/32K/128K matrix. Unselected or unsupported cells are
explicitly skipped; there is no synthesized success or benchmark number.

Each JSON result records the source revision and dirty-tree flag,
image/backend revision, model ID, quantization, contract/eval versions, hardware tier, UTC timestamp,
`models-max`, exact command, per-cell state, reliable llama.cpp `timings`, and
sampled aggregate `nvidia-smi` device memory where available (evidence, not a
process-attributed allocation). The generated Markdown report is
a concise view of the same JSON. Schema-contract pass rate and semantic anomaly
rate are separate fields. The command still writes both artifacts when a cell
fails, then exits nonzero; environmental skips alone are not treated as fake
failures.

Optional extensions:

```bash
# Run all bounded context cells. This can take substantial time and memory.
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b --preset 12gb.ini --models-max 1 --contexts all

# Wait past the 12 GB preset's actual 1800-second idle threshold.
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b --preset 12gb.ini --models-max 1 --contexts none --idle-wait-seconds 1805

# Reuse an already-built benchmark image without pulling or building.
python -m prefer_bench local --lane current --cache-source-volume prefer-model-cache --models gemma-4-e2b,gemma-4-e4b --preset 12gb.ini --models-max 1 --contexts 8k --no-build
```

## Pinned local evidence (2026-07-14)

The scrubbed [b9843 max-1 report](baselines/2026-07-14-titan-x-b9843-max1-e2b-e4b-8k.md)
and [machine result](baselines/2026-07-14-titan-x-b9843-max1-e2b-e4b-8k.json),
[b9843 max-4 report](baselines/2026-07-14-titan-x-b9843-max4-e2b-e4b.md)
and [machine result](baselines/2026-07-14-titan-x-b9843-max4-e2b-e4b.json),
and [b9990 availability report](baselines/2026-07-14-b9990-build-skip.md)
and [machine result](baselines/2026-07-14-b9990-build-skip.json) were all
captured from clean source `cc90b09ff81664b47463cc0b91c84369ec7f1f99` on
one NVIDIA TITAN X (Pascal), 12,288 MiB, with driver 582.53. These are single
runs, not distributions.

Measured b9843 (`version: 9843 (86b94708f)`) facts:

- At `models-max=1`, cold service start through readiness was 2,007.9 ms. E2B
  first load was 48,603.5 ms (11,271.4 ms prefill, 70.6 ms decode, 5,116 MiB
  observed peak); its next warm request was 198.4 ms. Streaming TTFT was
  186.4 ms. Two-request concurrency took 531.4 ms wall time, with 339.0 ms p50
  and 425.2 ms p95 individual latency.
- Both strict synthetic structured cases and the 8K retrieval case passed
  schema validation. All three evaluated documents had zero semantic anomalies:
  the dates were possible and exact, all required Cedar planning content was
  present, and all three long-context codes were recovered in order. The 8K
  generator produced 8,000 observed prompt tokens, 4,617.5 ms prefill, and
  589.8 ms decode. Tool call plus tool-result replay passed in 536.6 ms total.
- E4B failed to load at the same CUDA flash-attention tile assertion in both
  runs. With `models-max=1`, the attempt peaked at 7,292 MiB, evicted E2B, and
  the A return required a 10,373.4 ms reload. With `models-max=4`, the failed
  attempt peaked at 10,977 MiB, E2B remained loaded, and the A return took
  207.0 ms. `/v1/models` still showed only one loaded model, so this does not
  establish successful multi-model retention or settle the production policy.
- Every run removed its generated container, network, and volume; retained the
  operator `prefer` container in its prior exited state; retained NeurOn in its
  prior running state; mounted the source cache read-only; and did not use host
  port 8080.

The opt-in b9990 comparison was attempted but not run: the referenced
`server-cuda-b9990` tag returned `manifest unknown` during the isolated image
build. Every benchmark cell is therefore a structured skip, not a comparison
number. The default/production b9843 pin was not changed.

## Opt-in revision comparison

`b9990` is the one bounded, source-backed candidate lane referenced by the July
2026 observatory audit. It is opt-in and does not change either Dockerfile's
default b9843 pin:

```bash
python -m prefer_bench local --lane b9990 --cache-source-volume prefer-model-cache --models gemma-4-e2b,gemma-4-e4b --preset 12gb.ini --models-max 1 --contexts 8k
```

If the image is unpublished, unavailable, incompatible, or cannot build, the
result records a structured skip. Preparing this lane is not an upgrade claim.

## Isolation and CI

`docker-compose.yml` in this directory requires a generated `prefer-bench-*`
project and volume, binds a dynamically selected loopback port rather than
8080, defines no `container_name`, passes no credentials, sets
`PRESTAGE_MODELS=none`, and mounts the cloned run volume read-only in the
router. The orchestrator removes its own containers, network, and volume in a
`finally` path and compares the pre-existing `prefer` and `neuron` container
identity/state before and after without inspecting their environments.

Ordinary CI runs schemas, fixtures, parsers, report generation, negative tests,
mock replay, and `docker compose config --quiet`. It never launches a GPU
benchmark or downloads a model.

## Questions that gate any later backend spike

A later isolated backend experiment should be considered only after owners set
thresholds for these questions:

- Must every v1 contract replay cell pass with no configured identity, router
  discovery ID, or alias change?
- What maximum schema failure and semantic anomaly rates are acceptable per
  extraction and synthesis role?
- At equal model, quantization, context, and hardware, what cold-load, warm,
  A→B→A, TTFT, decode, concurrency, and memory improvement is material?
- Must 8K, 32K, and 128K all pass the retrieval task, or which explicit skips
  are acceptable by tier?
- Can a candidate preserve one-router light-tier swapping without adding
  provisioning, reservation, keepalive, or recovery ownership to PreFer?

The result format is intentionally backend-neutral enough to compare a future
spike, but this slice implements no alternate engine abstraction.
