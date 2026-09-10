# Shared model catalog and tooling

PreFer releases one small ESM package, one standalone CLI, and one materialized
model catalog alongside its engine inventories. These are configuration and
metadata artifacts. Model weights remain runtime downloads on external model
storage.

## Source layout

- `catalog/defaults.yaml` owns only genuine cross-model runtime behavior, such
  as Audio's offline mode and stable-diffusion.cpp component-role arguments.
- `catalog/models/<family>/<prefer-id>.yaml` owns PreFer's selection, profile,
  artifact bundle, engine applicability, and genuinely model-specific tuning
  for one logical model. The filename is the PreFer model ID; an `id` field is
  rejected and the same ID is not repeated as an alias or routing setting.
- Hugging Face remains the source for repository identity, resolved commits,
  base-model declarations, file trees, byte sizes, LFS hashes, library,
  pipeline, license, tags, and gating metadata. Do not transcribe those facts
  into YAML unless PreFer is choosing a specific file or setting.

The shared source covers all 32 logical models currently configured across
llama.cpp, audio.cpp, stable-diffusion.cpp, SGLang, and vLLM. A coverage test
compares it with every engine-local model and quant so either side cannot drift
silently. Existing engine-local catalogs and generated deployment inventories
remain the authoritative launch/deployment inputs; the shared layer gives
controllers one release-matched cross-engine view without changing those
routes.

Every model has a consistent prompt-ready profile: summary, architecture,
modalities, context, reasoning controls, preferred/capable/avoid roles,
strengths, limitations, prompting guidance, and evidence confidence. These are
model metadata, not launcher settings. Profiles contain qualitative product
guidance and do not copy third-party rankings or throughput measurements.

A quant may select one file, a compact include/exclude pattern, or a bundle of
role-labelled artifacts from several declared repositories. This represents
projectors, draft models, VAEs, encoders, tokenizers, and runtime metadata
without repeating their byte sizes or hashes in YAML. A dedicated GGUF
repository can set `discover: gguf`; the release build then exposes every
recognizable primary quant in its Hugging Face file tree while reusing the
authored bundle as the companion/settings template. Mixed repositories do not
opt in, so unrelated artifacts are not mistaken for model choices. Discovery
reads metadata only and never downloads weights.

Repository revisions normally stay out of authored YAML. The build resolves
the requested repository head and records the exact commit, files, sizes, and
hashes in the immutable materialized catalog. An authored `revision` remains an
escape hatch for a deliberate historical pin.

## Setting resolution

`resolveModelVariant` merges settings from broadest to narrowest:

1. global defaults
2. engine defaults
3. settings inferred from the chosen artifact format and quant
4. model and model-engine settings
5. repository settings
6. model-quant settings
7. the exact repository/quant/engine choice
8. caller overrides

Nested objects merge recursively. Arrays and scalar values replace earlier
values. A model's ordinary default applies to every engine unless an explicit
engine selection changes the repository or quant. Engine entries express
applicability and tuning, not a duplicated readiness verdict; deployment
inventories remain the owner of hardware/runtime verification state.

Every llama.cpp text model is also visible as a selectable GGUF option for
SGLang and vLLM. Visibility does not claim that every cross-engine tuple has
been smoked. Qwen3.8 27B keeps Unsloth UD-Q6_K_XL as the shared default across
all engines. `USE_NVFP4=true` (or `--use-nvfp4`) deliberately selects the
engine-specific RadixArk or Inferact NVFP4 repository; an explicit repository
or quant remains available for expert control. The official BF16 and FP8
repositories are choices as well.

Artifact format is inferred from the selected files, and SGLang/vLLM's NVFP4
launcher mode is inferred from that explicit choice. Model YAML must not repeat
an inherited setting. Shared model-engine settings apply to every quant unless
an individual quant actually needs to restrict or override an engine. Engine
artifact-role defaults map common component roles to launcher arguments, so
image quants only describe their target, VAE, and text-encoder selections.

The library accepts `modelRoot`; the CLI accepts `--model-root`, then
`PREFER_MODELS_DIR`, and finally defaults to `/models`. Storage layout is not a
model-catalog setting.

## Resources, fit, and bundle selection

Host scenarios remain engine-owned because they contain real launcher choices.
The shared package translates their differing hardware records into one
resource profile rather than copying those choices into model YAML. The GPU is
the primary identity: device count, memory, architecture, compute capability,
and precision support. Provider SKU, host RAM, logical CPU count, and storage
are additional facts.

Discrete VRAM, host memory, and unified memory are distinct accounting models.
On a unified-memory system, host and accelerator observations constrain one
pool and are never summed. Runtime observations may overlay a release's static
capacity with actual free memory, CPU, and storage immediately before a plan is
resolved.

`planModelSet` starts with the model's configured default and may choose a
smaller published quant when capacity is constrained. Its normal floor is the
quality-credible Q4/native-four-bit tier; IQ1/IQ2-style fit-floor variants do
not become automatic defaults. Explicit model/quant choices remain exact.
Optional bundle members can be removed for memory, model-count, or staging
limits, while a missing required model makes the plan incomplete.

Workload hints keep that pruning useful instead of positional. Required
capabilities are hard gates; preferred capabilities and profile roles adjust
the optional-model order. Speed importance consumes a controller's normalized
route score when one is supplied and otherwise uses active parameters only as
a low-confidence proxy. Quality importance consumes only a controller-supplied
workload score, keeping attributed external evaluations and NeurOn results out
of the release catalog. A quality, balanced, or capacity quant bias is
independent of the quant quality floor. Without hints, the authored deployment
order and normal quant remain the defaults.

Exact artifact bytes are only the static starting point. Fit output states
whether its confidence is measured, architecture-derived, artifact-only, or
unknown. The default device reserve is 4% of capacity, bounded to 1.5–4 GiB;
callers may replace it with a fixed byte allowance or another percentage.
Configured CPU expert/component-offload routes remain visible as conditional
choices when static inventory lacks host RAM instead of being misclassified as
GPU-only failures. The controller must observe enough host memory before
launch. Callers can also supply observed fixed allocation and per-token
cache/state cost; the workload tuner then adjusts context and concurrency to
caller-defined minimums. Engine adapters remain responsible for translating
that result into llama.cpp, SGLang, vLLM, Audio, or Image arguments.

## Build and fallback

`npm run tooling` builds the package and CLI, resolves the authored repositories
through the Hugging Face API, and writes `build/prefer-tooling/`. It also stages
the metadata-only files needed by local Docker build contexts. It does not
download model contents.

The grouped workflow performs this step once before any engine image builds.
It first locates the most recent completed catalog for the same stable or
preview channel. A live Hugging Face refresh is preferred. If that refresh
fails, old repository metadata may be reused only when it contains every
currently authored repository for the same requested ref (`main` normally, or
an explicit historical revision). The current YAML is then rematerialized over
those repository facts. Adding a repository or changing an explicit pin cannot
pass on a stale catalog that lacks it.

Every engine image contains:

- `/usr/local/bin/prefer`
- `/prefer-model-catalog.json`
- the catalog schemas under `/prefer-catalog/schemas/`
- `PREFER_ENGINE` set to its own engine

Only the Node 24 executable needed to run the bundled CLI is added; npm,
TypeScript, build tools, package sources, and model weights are not copied into
the runtime image.

## Release artifacts

After all six images build, `prefer-release.json` binds the following tooling to
the same full source SHA and checksums as the images:

- `prefer-inference-core.tgz`
- `prefer.mjs`
- `prefer-model-catalog.json`
- `prefer-model-catalog.schema.json`
- `prefer-model-catalog-extension.schema.json`
- `prefer-resource-profile.schema.json`
- `prefer-model-plan.schema.json`

The package version is `0.0.0-g<seven-character-sha>` and is published as
`prefer-inference-core` on npm only after the grouped runtime jobs succeed. Controllers may
also download the tarball directly from the immutable GitHub release. Release
selection helpers require the full 40-character commit and verify asset hashes
before caching them.

Stable builds advance the package's `latest` distribution tag. Preview builds
advance only `preview`, so opting into the package follows the same channel
boundary as the runtime images and GitHub releases.

## NeurOn extensions

The package does not hard-code a second model list. NeurOn can add its own
Hugging Face selections at runtime with `createCatalogExtension`:

```ts
const extension = await createCatalogExtension([
  { repository: "org/repository", revision: "main" },
  {
    model_id: "neuron-owned-id",
    repository: "org/another-repository",
    revision: "0123456789abcdef0123456789abcdef01234567"
  }
], {
  token: process.env.HF_TOKEN,
  cacheDir: ".cache/prefer/huggingface",
  concurrency: 4
});
```

A repository-only selection adds discoverable metadata without inventing a
canonical ID. `model_id` is optional and belongs to NeurOn when supplied.
`createRuntimeModelCatalog` joins one or more extensions to the selected PreFer
catalog. ID and repository conflicts fail by default; callers must explicitly
choose `keep` or `replace` when they want another policy.

The same operation is available without package integration:

```bash
prefer catalog extend \
  --repo org/repository@main \
  --model neuron-owned-id=org/another-repository@0123456789abcdef0123456789abcdef01234567 \
  --output neuron-extension.json
```

Callers own refresh scheduling and may supply their own `fetch`, authentication,
cache directory, timeout, include patterns, and bounded concurrency. Filtered
repository results are explicitly marked as incomplete and retain their include
patterns. HTTP rate-limit errors retain
retry/reset guidance rather than being converted into an empty catalog.
