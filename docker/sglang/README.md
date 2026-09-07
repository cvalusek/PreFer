# PreFer SGLang

This sibling image serves Qwen3.8-27B through SGLang's OpenAI-compatible API
and MiniMax H3 through SGLang's multimodal-generation video API. It is kept
behind the `sglang` Compose profile so starting the default PreFer application
does not reserve a second text- or video-serving GPU.

## Pinned runtime and model

- SGLang source and image build revision: `30705c004ca4bbfc92216dfaf845da14d84c4c4d`.
- Base image: `lmsysorg/sglang:nightly-dev-cu13-20260907-30705c00` at OCI index
  `sha256:19b8fa1223cc339c1eae7a5b703f1a8c2543b5b119155bf3d7efaef18f77f007`.
  The image is official upstream and is not built from the
  `jpezzulli/sglang-rtxpro6000` fork.
- Model: `RadixArk/Qwen3.8-27B-NVFP4` at revision
  `319f741cce68d7914884900c138a1fbb70a42f30`.
- The three safetensors shards total `21,921,697,280` bytes. The catalog also
  pins the tokenizer, template, configs, license, and audit metadata with
  exact sizes and SHA-256 values.
- The derivative is Apache-2.0 and records its Qwen base lineage at
  `Qwen/Qwen3.8-27B` revision
  `e13a4f0e35203116364e3b3f3f0c82f6ef1afd3c`.

The same image carries two explicit MiniMax H3 diffusion lanes:

- `minimax-h3-fl2va-int8-convrot`: text-to-video plus first/last-frame video
  conditioning, with aliases `minimax-h3-fl2va`, `t2va`, `t2v`, and `i2v`.
- `minimax-h3-ref2va-int8-convrot`: reference/video-to-video conditioning,
  with aliases `minimax-h3-ref2va`, `ref2va`, and `v2v`.

Both use the official H3 base revision
`5d9b308a59ab12e67147f191e184baf704185bd1`, Comfy-Org's immutable INT8
ConvRot transformer and NVFP4 text encoder artifacts, and synchronized MP4
H.264/AAC output at 24 fps. The exact staged component bundle is external to
the image and recorded in the generated inventory. The H3 Community License
applies. The generated H3 commands disable pinned CPU memory because the
diffusion loader can stage substantial DiT state through host memory; exact
host-RAM headroom remains a configuration-only gate.
This runtime parses the dynamic `--component-weights-paths.<component>` options
used for all four exact component files. The former `c4271c3f` image did not and
exited before model loading. Canonical configs also disable `torch.compile`,
including on the 96 GB full-GPU shapes, because upstream keeps H3 speed mode
eager and documents compile-on as numerically different experimental behavior.

The checkpoint accepts text, image, and video inputs, has a native 262,144-token
context, and carries one trained MTP layer. The packaged profiles use FP8 E4M3
KV cache, the FlashInfer attention backend, chunked prefill, CUDA graphs, Qwen
reasoning and tool-call parsers, BF16 recurrent state, and the native Qwen chat
template. Roomy Blackwell scenarios expose a 524,288-token per-request maximum
from a dynamically shared runtime pool with four configured request slots; the
effective admitted concurrency and total KV token pool remain smoke-test
measurements. The larger performance profiles add the in-checkpoint NEXTN
settings (`3` steps, top-k `1`, `4` draft tokens); target-only controls are
retained to isolate the target checkpoint from MTP.

## Hardware contract

The Qwen3.8 text lane is for NVIDIA Blackwell GPUs with compute capability
SM100 or newer. The MiniMax H3 diffusion lane has a separate CUDA 13
compatibility gate starting at SM86 for its INT8/NVFP4 component route. The
checked-in shapes are:

- AWS `g7e.2xlarge`: one 96 GB RTX PRO 6000 Blackwell.
- RunPod `NVIDIA RTX PRO 6000 Blackwell Server Edition`: one 96 GB card.
- RunPod or local RTX 5090: one 32 GB card with a 262K target-only starting
  route and a separate bounded 128K NEXTN throughput experiment.
- Generic local GB10: one 128 GB unified-memory device, with the documented
  0.80 static-memory fraction and a BF16-KV single-user fidelity alternate.
- AWS g6e.xlarge / local RTX 4090: one 48/24 GB-class card using the H3
  memory/offload route.
- AWS g7e.2xlarge / RunPod RTX PRO 6000: one 96 GB card using the H3 full-GPU
  speed route.

The provider-neutral `sglang/cuda13` entry is a runtime default, not a concrete
hardware scenario. Every concrete shape is marked `configuration-only` until it
passes a target-card load, multimodal request, context, API-contract, MTP, and
concurrency smoke. H200 and older architectures are intentionally absent from
this NVFP4 catalog, and the generic local entries do not describe the operator's
private GPU inventory.

## Source provenance and lineage review

The checked-in image is the portable upstream lane. The high-performance
RTX PRO 6000 work that motivated this sibling runtime is a separate patched
SGLang source tree, so its backend resolution and measured results must not be
silently attributed to this image.

| Feature or campaign | Official pinned image/source | `jpezzulli/sglang-rtxpro6000` custom fork | PreFer decision |
| --- | --- | --- | --- |
| Native NEXTN/MTP on this model | The pinned RadixArk checkpoint has one embedded MTP layer; the stock 96/128 GB configs expose NEXTN `3/1/4` as a configuration-only performance lane. | The fork's Flash-Next route uses a different `RadixArk/Qwen3.8-Flash-Next-NVFP4` checkpoint. | Keep native NEXTN visible in the stock lane and smoke it on each exact card. |
| DFlash2 on RadixArk NVFP4 | The official image contains upstream DFlash2 and quantized target-head support from [#35371](https://github.com/sgl-project/sglang/pull/35371) and [#35496](https://github.com/sgl-project/sglang/pull/35496), but [#35437](https://github.com/sgl-project/sglang/issues/35437) reports prefill CUDA-graph failures for the RadixArk + incoai pair. | The published 27B campaign uses an `orcarouter` block-FP8 target plus `incoai/Qwen3.8-27B-DFlash2`, with additional fork patches. | Keep DFlash2 as an exact-target verification experiment; do not enable it canonically or import its throughput. |
| FP8 E4M3 KV | Configured for performance. The RadixArk checkpoint declares FP8 KV but has no separate scale file, so the runtime default scale `1.0` is not a fidelity result. | Also uses FP8 KV, with custom capacity and persistence behavior. | Keep FP8 as the performance default, with target-only and BF16-KV controls. |
| BF16 recurrent/Mamba state | Stock configs use documented `bfloat16`, `extra_buffer_lazy`, and bounded Mamba-cache settings. | The fork uses BF16 on Flash-Next but reports FP32 SSM state on its DFlash2 route. | Use BF16 in the stock configs; verify stability and admitted concurrency on hardware. |
| Attention/MoE backends | Stock configs declare generic FlashInfer, chunked prefill, and ModelOpt FP4; they do not claim the fork's resolved SM120 backends. | Adds target-specific TRTLLM-MHA/XQA, QSA, Triton FP8 MoE, and CUTLASS MoE resolution. | Keep only portable stock flags in this image. |
| CUDA graphs and recovery | Stock configs set ordinary graph batch bounds; DFlash2 prefill graphs remain gated by the upstream issue above. | Adds target, draft, verify, prefill, and accepted-state recovery graphs. | Do not describe stock graph bounds as custom recovery-graph support. |
| 524K context and KV capacity | Roomy stock shapes set a 524,288-token request maximum and four configured slots with a dynamically shared pool; effective capacity is still unknown until smoke. | Claims factor-2 YaRN and measured pools for separate campaigns. | Preserve the explicit ceiling and unknown capacity fields; do not borrow the fork's pool measurements. |
| Vision, tools, and reasoning | Stock catalog retains native text/image/video inputs and Qwen parsers, pending target-card smoke. | Reports exact-card qualification for its own model/runtime combinations. | Keep the capability declarations but keep verification `configuration-only`. |
| HiCache/NIXL | Optional and disabled. | Adds complete hybrid-state persistence and restart recovery. | Do not enable until a separate storage and recovery contract is pinned. |

The headline campaign identities are deliberately kept separate: the published
`~108.75 tok/s` 27B DFlash2 result is the custom fork's block-FP8 target
campaign, not this RadixArk NVFP4 artifact; the `~171 tok/s` Flash-Next result
uses a separate Flash-Next NVFP4 checkpoint and native NEXTN; and the earlier
`~146 tok/s` C1 NVFP4/native-MTP result is a separate runtime/state. None is a
stock-image result for the current 21.945 GB snapshot.

The official mainline image does not include
[#36806](https://github.com/sgl-project/sglang/pull/36806) for exact SM120 QSA
routing or [#35821](https://github.com/sgl-project/sglang/pull/35821) for Mamba
radix-cache/speculative tracking; those changes were merged only to SGLang's
`qwen4-main-squashed` and `qwen_optimize` branches.
[#35744](https://github.com/sgl-project/sglang/pull/35744) is also outside the
pinned image. The current recommendation is an immutable
custom-fork image alongside this upstream portable lane if high-performance
parity is required. Choosing that lineage is an owner decision; this image does
not silently switch to it.

## Downloads and shared cache

SGLang uses the same `/models/<Hugging Face owner>/<repository>/<file>` layout,
`hf download` client, persistent `/models` volume, and `PRESTAGE_MODELS`/
`MODEL_DOWNLOAD_JOBS` compatibility aliases as the llama.cpp launcher. Its
stricter per-file `downloads-v2` markers remain separate from llama.cpp's
model-level `downloads-v1` markers, so either launcher can reuse matching files
without treating the other's marker as authoritative. The Compose
profile defaults `PREFER_SGLANG_MODEL_VOLUME` to `prefer-model-cache`, the same
named volume used by llama.cpp; set it to another volume when isolation is
preferred.

On AWS, set `S3_BUCKET_NAME` (or the SGLang-specific
`SGLANG_S3_BUCKET_NAME`) to enable optional read-through staging. The optional
`S3_MODEL_PREFIX` / `SGLANG_S3_MODEL_PREFIX` is normalized as a relative object
prefix; with it blank, objects use the same
`s3://<bucket>/<repository>/<path>` layout as the llama.cpp downloader. SGLang
copies only exact catalog objects with pinned `s5cmd` 2.2.2, verifies their size
and SHA-256 before atomic publication, and falls back cleanly to the pinned HF
revision on a miss or mismatch. It never uploads to S3, so AWS needs only
`s3:GetObject` and `s3:ListBucket`; local and RunPod generated scenarios remain
HF-only by default. No model-level marker is trusted as a substitute for the
per-file checks, while successful runs still write the llama-compatible local
completion marker.

The SGLang-specific variables take precedence when set:

- `SGLANG_SERVER_CONFIG` selects a generated JSON config.
- `SGLANG_PRESTAGE_MODELS` selects catalog keys; blank follows the selected
  config's `.prestage` sidecar and `none` skips downloads.
- `SGLANG_DOWNLOAD_JOBS` bounds transfers from one through eight.
- `SGLANG_S3_BUCKET_NAME` and `SGLANG_S3_MODEL_PREFIX` explicitly opt in to
  SGLang's S3 read-through; the AWS launcher also accepts the common
  `S3_BUCKET_NAME` and `S3_MODEL_PREFIX` names.
- `PRESTAGE_MODELS` and `MODEL_DOWNLOAD_JOBS` remain accepted for operators
  reusing the llama.cpp staging environment.

## Compose

The service listens on container port `30000` and host port `8083` by default.
It is opt-in because it is an alternative text backend:

```bash
docker compose --profile sglang build sglang
docker compose --profile sglang up sglang
curl http://localhost:8083/v1/models
```

For a 96 GB Blackwell performance shape, set `SGLANG_SERVER_CONFIG` to
`/server-configs/aws/g7e/2xlarge/balanced.json` or the matching RunPod config.
Use `target-only.json` to isolate MTP, or `fidelity.json` for the BF16-KV
single-user alternate. The 5090 `performance.json` is deliberately bounded to
128K until exact-card smoke supports a larger speculative envelope.
The request model ID is `qwen3.8-27b`. The health endpoint is `GET /health`;
chat, completion, and Anthropic messages use the `/v1` API.

For H3, select a generated configuration such as
`/server-configs/aws/g7e/2xlarge/h3-fl2va.json` or
`/server-configs/aws/g7e/2xlarge/h3-ref2va.json`. The gateway keeps the stable
PreFer port while the diffusion server runs internally on port `30001`. Use
`GET /readyz` for warmup-aware readiness, `GET /v1/models` for capability
discovery, `POST /v1/videos` to submit a job, and the returned video ID for
`GET /v1/videos/{id}` and `GET /v1/videos/{id}/content`. Inputs must be local
`file://` paths under `/inputs` or multipart uploads; remote URLs are rejected.
While a live worker is loading, discovery returns `upstream_not_ready`; if the
worker exits, discovery and generation return `upstream_failed` with its exit
status instead of continuing to report warmup.
Generated output is written under `/outputs` and the Compose profile provides
separate persistent input/output volumes. The gateway normalizes `t2v`, `i2v`,
and `v2v` aliases to SGLang's `t2va`, `fl2va`, and `ref2va` tasks.

Qwen's template enables thinking by default. Requests may use
`reasoning_effort` values `low`, `medium`, or `xhigh`, and may use the Qwen
`enable_thinking` and `preserve_thinking` controls. Tools should use the
`qwen3_coder` parser shape.

## Fidelity and experimental routes

The pinned checkpoint declares FP8 KV quantization but contains no separate KV
scale parameter file. FP8 configurations therefore expose performance-oriented
cache behavior but remain a fidelity gate until calibrated scaling is supplied
and verified; the runtime's implicit scale of `1.0` is not an accuracy claim.
The AWS/RunPod 96 GB and generic GB10 inventories include a BF16-KV,
single-user, target-only alternate for fidelity checks. BF16-KV is intentionally
not offered on the 32 GB RTX 5090.

Native NEXTN is the stock canonical speculative path. DFlash2 is tracked as an
upstream exact-target experiment but remains blocked on the prefill-graph issue;
the custom FP8 campaign's throughput is not borrowed for this current 21.945 GB
RadixArk NVFP4 snapshot. The custom RTX PRO 6000 Flash-Next route is retained in
the generated inventory as the next experimental lane, but it is not copied into
the canonical image. HiCache/NIXL is optional and not enabled by default until
its storage and recovery behavior are explicitly configured and smoked.

Authoritative references: [SGLang Qwen3.8-27B cookbook](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-27B),
[Qwen3.8 model card](https://huggingface.co/Qwen/Qwen3.8-27B),
[the pinned NVFP4 checkpoint](https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4),
and [SGLang quantization documentation](https://github.com/sgl-project/sglang/blob/main/docs/advanced_features/quantization.md).
