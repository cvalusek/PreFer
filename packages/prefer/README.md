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
engine/model/quant/hardware tuple has been validated; deployment inventories
carry that state.

## Resource-aware planning

The package normalizes every engine's deployment inventory into the same
`prefer.resources.v1` shape. GPU identity, count, usable memory, architecture,
compute capability, and format capabilities are primary. Host RAM, CPU, and
storage remain independent resources and only participate when a route uses
them. Unified-memory systems use one shared pool; the planner never adds the
same bytes once as VRAM and again as host RAM.

```ts
import { normalizeDeploymentResources, planModelSet } from "prefer-inference-core";

const resources = normalizeDeploymentResources(deployment, runtimeObservation);
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
priority. Existing deployments that explicitly configure CPU expert/component
offload remain conditional rather than being rejected when static local
inventory omits private host RAM; runtime discovery must supply that capacity
before launch. This lets NeurOn replace a static launch estimate with runtime
measurements without forking PreFer's selection rules.

The standalone CLI exposes the same boundary:

```text
prefer hardware normalize --input prefer-llama-deployment-inventory.json --deployment aws/g6/xlarge/general
prefer hardware detect --base prefer-vllm-deployment-inventory.json --deployment local/gb10/1x/performance
prefer model plan --resources resources.json --engine llama.cpp --models qwen-3.8-27b,gemma-4-12b --preferred-role repository-coding --speed-importance 0.8 --headroom-gib 2
```

Qwen3.8 27B defaults to Unsloth UD-Q6_K_XL on every engine. Setting
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

## Immutable PreFer releases

`listPreferReleases`, `resolvePreferRelease`, and `downloadPreferTooling` cover
stable/preview release selection, full-SHA identity checks, asset checksum
verification, and local caching. NeurOn may keep its existing scheduling and
rate-limit policy while replacing duplicate parsing and integrity logic with
these functions.
