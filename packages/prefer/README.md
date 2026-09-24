# `prefer-inference-core`

Shared model-catalog, Hugging Face metadata, configuration-resolution, and
immutable-release tooling for PreFer controllers.

The package is data-driven. PreFer's authored YAML and the materialized catalog
shipped with a grouped release define supported models; the library does not
hard-code a second model list. Model weights are never packaged here.

## Supported catalog

```ts
import { readModelCatalog, resolveModelVariant } from "prefer-inference-core";

const catalog = await readModelCatalog("prefer-model-catalog.json");
const qwen = resolveModelVariant(catalog, "qwen-3.8-27b", {
  engine: "sglang",
  useNvfp4: true,
  modelRoot: "/models"
});
```

Settings merge from broadest to narrowest: global, engine, inferred
artifact/quant behavior, model, model+engine, repository, quant, exact
repository/quant+engine, then caller overrides. Arrays and scalar values
replace earlier values; objects merge recursively.

Resolved variants include a repository storage root and an exact local path for
each artifact. Engine artifact-role defaults supply repeated component bindings
such as image target, VAE, and text-encoder arguments; authored artifact
settings are only needed for a real exception.

The release catalog currently covers every logical model in PreFer's five
engine catalogs. Each model exposes a consistent prompt-ready profile and each
resolved variant returns the exact selected artifact bundle, including
cross-repository companions such as projectors, draft models, encoders, VAEs,
and runtime metadata. Hugging Face supplies the resolved file facts; authored
YAML carries only PreFer's choices and overrides.

Dedicated GGUF repositories opt into metadata-only quant discovery, so their
full published quant selection is available without copying Hugging Face's file
catalog into YAML. All llama.cpp text artifacts are selectable for SGLang and
vLLM as well as llama.cpp. Discoverability is not a claim that an
engine/model/quant/hardware tuple has been validated; runtime evidence remains
separate from model discoverability.

## Resource-aware planning

The package ships a provider-only hardware catalog and normalizes those records
or live observations into the same `prefer.resources.v1` shape. The catalog
contains AWS and RunPod capacity/identity facts only; it never selects models,
quants, context, concurrency, cache, offload, or speculation. GPU identity,
count, usable memory, architecture,
compute capability, and format capabilities are primary. Host RAM, CPU, and
storage remain independent resources and only participate when a route uses
them. Unified-memory systems use one shared pool; the planner never adds the
same bytes once as VRAM and again as host RAM.

```ts
import {
  readHardwareProfileCatalog,
  resolveHardwareProfile,
  resolvePreferRelease,
  resolveRuntimeImage,
  readModelCatalog,
  planModelSet
} from "prefer-inference-core";

const hardware = await readHardwareProfileCatalog("prefer-hardware-profiles.json");
const release = await resolvePreferRelease({ repository: "cvalusek/PreFer", channel: "preview" });
const catalog = await readModelCatalog("prefer-model-catalog.json");
const resources = resolveHardwareProfile(hardware, "aws/g7e.2xlarge", runtimeObservation);
// runtimeObservation must include the observed host driver API, e.g.
// runtime_compatibility: { cuda_max_major: 13 }, not a guessed GPU-SKU value.
const image = resolveRuntimeImage(release.manifest, "llama.cpp", resources);
const plan = planModelSet(catalog, {
  engine: "llama.cpp",
  resources,
  models: [
    { model_id: "qwen-3.8-27b", required: true },
    { model_id: "gemma-4-12b", priority: 10, speed_score: 74, quality_score: 88 }
  ],
  hints: {
    required_capabilities: ["tool-calling"],
    preferred_roles: ["repository-coding"],
    speed_importance: 0.8,
    quality_importance: 1,
    quant_bias: "balanced"
  }
});
```

Image selection precedes fitting. On releases that publish accelerator metadata,
`resolveRuntimeImage` returns an immutable release image candidate using vendor, platform, observed CUDA driver API, and
ROCm architecture restrictions; it cannot validate a model's kernels or
output. One resource profile/process represents one GPU vendor. A provider
profile may include dated CUDA-major evidence but the live driver observation
controls deployment; a host CUDA toolkit version does not select the image.
RunPod/AWS and local observed profiles use the same contract, without authored
`local/*` entries.

Planning starts with each model's normal quant and walks downward through
quality-credible published variants only when the preferred artifact does not
fit. NVFP4 and FP8 selections require matching hardware capabilities. Optional
bundle members may be omitted for memory, model-count, or staged-storage
limits; required omissions make the plan incomplete and remain explicit.
Required capabilities are hard gates. Preferred capabilities and roles only
rank optional bundle members. `speed_importance` weights a caller-supplied
route speed score when available; otherwise active parameter count is used as
a low-confidence ordering hint. Quality importance uses only a caller-supplied
workload score; PreFer does not invent or embed a cross-model leaderboard. The
default curated order is preserved when no hints are supplied. `quant_bias`
can explicitly favor quality or capacity, while `balanced` retains the normal
quant and falls back only when needed.

The default estimate uses exact selected artifact bytes, a small runtime
allowance, and a device reserve equal to 4% of capacity with a 1.5 GiB floor
and 4 GiB cap. `--headroom-gib` fixes that reserve directly and
`--headroom-percent` changes the scaling factor. Its result is labelled
`artifact-only`, not presented as a measured peak. A caller can add
architecture-derived or measured fixed memory and bytes-per-token, exact free
device memory, and host-memory availability. `tuneWorkloadToFit` can then trade
context and concurrency while respecting the caller's minimums and stated
priority. Explicit planner choices that use CPU expert/component offload remain
conditional rather than being rejected when provider metadata omits host RAM;
runtime discovery must supply that capacity before launch. This lets NeurOn
replace static provider capacity with runtime measurements without forking
PreFer's selection rules. Unmanaged local execution should use live detection;
there are no bundled `local/*` hardware profiles.

The standalone CLI exposes the same boundary:

```text
prefer hardware normalize --input observed-or-provider-resource.json
prefer hardware detect --base observed-or-provider-resource.json
prefer model plan --resources resources.json --engine llama.cpp --models qwen-3.8-27b,gemma-4-12b --preferred-role repository-coding --speed-importance 0.8 --headroom-gib 2
```

Qwen3.8 27B keeps Unsloth UD-Q6_K_XL as its cross-engine default; Qwen3.5-9B
uses first-party BF16 for SGLang and vLLM while retaining GGUF for llama.cpp.
The former NVFP4 direct text lanes are explicit-only rather than friendly-name
defaults. Setting
`USE_NVFP4=true` in the CLI environment (or passing `useNvfp4` to the library)
selects the engine-specific NVFP4 source. Explicit repository and quant choices
still win. The CLI resolves storage from `--model-root`, then
`PREFER_MODELS_DIR`, then `/models`.

## NeurOn-owned runtime extensions

NeurOn can request any additional Hugging Face repositories without editing or
rebuilding PreFer:

```ts
import {
  createCatalogExtension,
  createRuntimeModelCatalog
} from "prefer-inference-core";

const extension = await createCatalogExtension([
  { repository: "org/another-model", revision: "main" },
  {
    model_id: "neuron-private-choice",
    repository: "org/private-model",
    revision: "0123456789abcdef0123456789abcdef01234567"
  }
], { token: process.env.HF_TOKEN, cacheDir: ".cache/huggingface" });

const runtime = createRuntimeModelCatalog(supportedCatalog, [extension]);
```

A repository-only selection adds metadata without inventing a canonical model
ID. A named selection adds a NeurOn-owned ID. PreFer IDs win by default:
collisions throw unless the caller explicitly chooses `keep` or `replace`.
Resolved revisions, file paths, byte sizes, LFS hashes, base-model declarations,
license, library/pipeline identity, and tags reported by Hugging Face are retained in the
extension. Repository results also say whether the returned file tree is
complete or was narrowed by the caller's `include` patterns. Controllers decide when to refresh and can supply their own `fetch`
implementation, token, cache, timeout, and bounded concurrency.

The standalone bundled CLI exposes the same operations:

```text
prefer catalog extend \
  --repo org/another-model@main \
  --model neuron-private-choice=org/private-model@0123456789abcdef0123456789abcdef01234567 \
  --output neuron-extension.json
```

## Immutable runtime handoff

`resolveExtensionModelVariant` turns a controller-owned extension into an
engine-ready exact-file selection. `createRuntimeHandoff` then binds supported
or extension variants, companions, and LoRAs to the selected engine and the
release catalog fingerprint. `validateRuntimeHandoff` and
`materializeRuntimeHandoff` enforce that binding and derive paths beneath the
receiving runtime's model root.

`encodeRuntimeHandoffBase64` and `decodeRuntimeHandoffBase64` provide the
strict, validated environment transport used by RunPod-style provisioning.
The encoded value is capped at 96 KiB; larger handoffs use the JSON-file path
transport.

LFS artifacts use their content SHA-256. Ordinary Hugging Face files use their
immutable Git blob SHA-1 unless the controller supplies a content SHA-256.
Every handoff artifact has exactly one digest, an immutable repository
revision, an exact path, and an exact byte size.

The standalone CLI exposes `model resolve-extension`, `runtime create`,
`runtime validate`, and `runtime materialize`. See
[the full controller and container flow](../../docs/runtime-handoff.md).

## Immutable PreFer releases

`listPreferReleases`, `resolvePreferRelease`, and `downloadPreferTooling` cover
stable/preview release selection, full-SHA identity checks, asset checksum
verification, and local caching. NeurOn may keep its existing scheduling and
rate-limit policy while replacing duplicate parsing and integrity logic with
these functions.
