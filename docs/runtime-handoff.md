# Runtime model handoff

PreFer's runtime handoff lets a controller launch either a supported catalog
model or a controller-owned Hugging Face selection without adding another
engine-local model entry. The handoff is metadata only. Model files still
stage after container startup onto the engine's external `/models` storage.

The handoff records:

- the selected PreFer engine and base hardware deployment;
- the exact materialized catalog fingerprint from that PreFer release;
- immutable Hugging Face repository revisions;
- exact artifact paths and byte sizes;
- one integrity identity per file: SHA-256 for LFS or caller-hashed content,
  or Git blob SHA-1 for ordinary repository files;
- model, companion, projector, draft, and LoRA roles;
- engine/model settings and the request-facing model ID.

The receiving image rejects an engine mismatch, catalog mismatch, changed
handoff fingerprint, unsafe path, conflicting destination, missing digest, or
unknown model/artifact reference before it launches the inference server.

## Controller flow

For a supported model, resolve the exact engine variant from the
release-matched catalog and create the handoff:

```ts
import {
  createRuntimeHandoff,
  encodeRuntimeHandoffBase64,
  readModelCatalog,
  resolveModelVariant
} from "prefer-inference-core";

const catalog = await readModelCatalog("prefer-model-catalog.json");
const variant = resolveModelVariant(catalog, "qwen-3.8-27b", {
  engine: "vllm",
  quant: "ud-q6-k-xl"
});
const handoff = createRuntimeHandoff(catalog, {
  engine: "vllm",
  baseDeployment: "aws/g7e/2xlarge/performance",
  models: [{ variant, request_model_id: "qwen-3.8-27b" }]
});
const runPodEnvironment = {
  PREFER_RUNTIME_HANDOFF_BASE64: encodeRuntimeHandoffBase64(handoff)
};
```

For a controller extension, first resolve repository metadata, then select the
exact files that make the variant launchable:

```ts
import {
  createCatalogExtension,
  createRuntimeHandoff,
  readModelCatalog,
  resolveExtensionModelVariant
} from "prefer-inference-core";

const catalog = await readModelCatalog("prefer-model-catalog.json");
const extension = await createCatalogExtension([{
  model_id: "neuron-model",
  repository: "org/model",
  revision: "main"
}], { token: process.env.HF_TOKEN });
const variant = resolveExtensionModelVariant(extension, "neuron-model", {
  engine: "sglang",
  quant: "bf16",
  files: ["config.json", "tokenizer.json", "model.safetensors"],
  capabilities: ["text-generation"]
});
const handoff = createRuntimeHandoff(catalog, {
  engine: "sglang",
  baseDeployment: "aws/g7e/2xlarge/balanced",
  models: [{ variant, source: "extension" }]
});
```

Hugging Face LFS metadata supplies the content SHA-256 used for weights.
Ordinary files use their immutable Git blob hash. A controller may supply an
exact SHA-256 for an ordinary file when it already has one. PreFer never
downloads weights merely to build catalog metadata.

Additional exact artifacts can be attached to a selected model through
`additionalArtifacts`. Use `role: "lora"` or `role: "adapter"` for LoRA files;
`settings.adapter_name` supplies the SGLang/vLLM request name when needed.
All files that the adapter directory requires must be present in the handoff.

## CLI flow

The bundled CLI exposes the same steps:

```text
prefer model resolve qwen-3.8-27b --engine vllm --quant ud-q6-k-xl --output variant.json
prefer runtime create --engine vllm --variant variant.json --base-deployment aws/g7e/2xlarge/performance --output handoff.json
prefer runtime validate --engine vllm --handoff handoff.json
```

Controller extensions can be resolved without adding them to PreFer source:

```text
prefer catalog extend --model neuron-model=org/model@main --output extension.json
prefer model resolve-extension neuron-model --extension extension.json --engine sglang --quant bf16 --file config.json --file tokenizer.json --file model.safetensors --output variant.json
prefer runtime create --engine sglang --variant variant.json --extension --output handoff.json
```

Inside a PreFer image, `PREFER_ENGINE` is already set. The entrypoint calls
`prefer runtime materialize`, derives all destination paths beneath
`PREFER_MODELS_DIR` (default `/models`), writes an exact artifact manifest, and
stages it with the shared resumable downloader. Optional S3 read-through uses
the same repository/path layout as existing model staging.

## Container selection

For platforms with file mounts, mount the JSON handoff into the container and
set `PREFER_RUNTIME_HANDOFF` or its engine-scoped alias. For environment-only
provisioning such as a RunPod Pod create request, encode the same validated
object with `encodeRuntimeHandoffBase64` and set
`PREFER_RUNTIME_HANDOFF_BASE64` or its engine-scoped alias.

| Engine | Path variable | Base64 variable |
| --- | --- | --- |
| llama.cpp | `LLAMA_RUNTIME_HANDOFF` | `LLAMA_RUNTIME_HANDOFF_BASE64` |
| audio.cpp | `AUDIO_RUNTIME_HANDOFF` | `AUDIO_RUNTIME_HANDOFF_BASE64` |
| stable-diffusion.cpp | `IMAGE_RUNTIME_HANDOFF` | `IMAGE_RUNTIME_HANDOFF_BASE64` |
| SGLang | `SGLANG_RUNTIME_HANDOFF` | `SGLANG_RUNTIME_HANDOFF_BASE64` |
| vLLM | `VLLM_RUNTIME_HANDOFF` | `VLLM_RUNTIME_HANDOFF_BASE64` |

The base64 transport is strict, single-line RFC 4648 base64 and is limited to
96 KiB so it stays below common process-environment limits. Use the mounted
path transport for a larger handoff. Path and base64 inputs are mutually
exclusive, and both are mutually exclusive with bundle/model selectors. The
decoded object passes the identical schema, fingerprint, release, engine, and
artifact validation before any transfer or server launch.

A handoff replaces bundle/model selection. Hardware deployment defaults and
explicit server/model overrides still apply in the documented composition
order. Existing preset/config startup remains unchanged when no handoff is
selected.

## Engine translation

- llama.cpp maps exact GGUF, projector, draft/MTP, and GGUF LoRA artifacts to
  the generated router preset.
- audio.cpp maps the selected model or repository path and session settings to
  its generated server config.
- stable-diffusion.cpp maps target/checkpoint, VAE, text encoder, and LoRA
  artifacts to the image router's exact staged-file contract.
- SGLang and vLLM launch either a repository directory or an explicitly
  selected GGUF file. Text LoRA artifact groups become engine-native named
  adapter directories.

SGLang and vLLM remain single-model processes. A handoff may expose an
unverified model/engine choice, but it cannot bypass immutable artifact or
release validation; load and behavioral compatibility remain runtime facts.
