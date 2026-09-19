# PreFer vLLM runtime

This opt-in official-upstream CUDA 13 image serves the Inferact Qwen3.8-27B
NVFP4 lane behind a warmup-aware gateway.

Generated hardware deployments, local profiles, and checked-in server configs
have been removed. The inventory retains exact model artifacts, profiles,
runtime/API facts, and composition inputs; it does not select hardware.

## Runtime selection

vLLM is one-model-per-process. Set `VLLM_MODELS`/`PREFER_MODELS` to exactly one
catalog identity, or supply `VLLM_RUNTIME_HANDOFF` /
`VLLM_RUNTIME_HANDOFF_BASE64`. Blank or multiple selections fail.

Catalog model defaults are followed by server overrides, model overrides, and
raw arguments. The caller must explicitly plan context, sequence concurrency,
KV precision, memory utilization, eager/graph behavior, and speculation from
live resources. No named hardware config is inherited.

## Artifact staging

The canonical bundle includes the exact tokenizer/configuration files, six
safetensors shards, and MTP companion. Files use immutable revisions, exact
sizes and SHA-256 values, atomic publication, and shared `downloads-v2`
markers. The CPU-only release downloader can stage the same handoff before a
GPU worker starts.

## Generation

```bash
python generate.py
python generate.py --check
```

The generator emits the artifact map and inventory. Effective runtime config is
written under `/run/prefer`.
