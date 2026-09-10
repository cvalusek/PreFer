import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  createCatalogExtension,
  createRuntimeHandoff,
  createRuntimeModelCatalog,
  decodeRuntimeHandoffBase64,
  encodeRuntimeHandoffBase64,
  loadCatalogSources,
  mergeCatalogExtensions,
  modelRequestsFromDeployment,
  normalizeDeploymentResources,
  parseNvidiaSmi,
  planModelSet,
  quantQuality,
  refreshModelCatalog,
  listModelVariants,
  materializeRuntimeHandoff,
  resolveHuggingFaceSelections,
  resolveExtensionModelVariant,
  resolveModelVariant,
  estimateVariantFit,
  tuneWorkloadToFit
} from "../dist/index.js";
import { globMatch } from "../dist/utils.js";

const REVISION = "a".repeat(40);
const EXTRA_REVISION = "b".repeat(40);
const GIB = 1024 ** 3;

test("model ids come from filenames and settings follow the documented precedence", async () => {
  await withFixture(async (root) => {
    const sources = await loadCatalogSources(root);
    assert.deepEqual(Object.keys(sources.models), ["sample-7b"]);
    assert.equal(sources.models["sample-7b"].family, "sample");
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const resolved = resolveModelVariant(catalog, "sample-7b", {
      engine: "llama.cpp",
      overrides: { precedence: "caller", caller: true }
    });
    assert.equal(resolved.repository, "owner/sample-gguf");
    assert.equal(resolved.repository_path, "/models/owner/sample-gguf");
    assert.equal(resolved.revision, REVISION);
    assert.equal(resolved.quant, "q6");
    assert.deepEqual(resolved.profile, { summary: "A fixture model." });
    assert.deepEqual(resolved.files, ["sample-q6.gguf"]);
    assert.equal(resolved.artifact_bytes, 123);
    assert.equal(resolved.artifacts[0].lfs_sha256, "c".repeat(64));
    assert.equal(resolved.artifacts[0].local_path, "/models/owner/sample-gguf/sample-q6.gguf");
    assert.deepEqual(resolved.capabilities.sort(), ["chat", "tools"]);
    assert.deepEqual(resolved.settings, {
      precedence: "caller",
      global: true,
      marker: "original",
      engine: true,
      model: true,
      model_engine: true,
      repository: true,
      quant: true,
      all_engine: true,
      exact_engine: true,
      caller: true
    });
  });
});

test("model resolution accepts one unique authored alias", async () => {
  await withFixture(async (root) => {
    const path = join(root, "models", "sample", "sample-7b.yaml");
    await writeFile(path, modelYaml().replace("display_name: Sample 7B", "display_name: Sample 7B\naliases: [sample]"));
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const resolved = resolveModelVariant(catalog, "sample", { engine: "llama.cpp" });
    assert.equal(resolved.model_id, "sample-7b");
    assert.equal(listModelVariants(catalog, "sample", "llama.cpp").length, 1);
  });
});

test("a failed refresh reuses repository facts but rematerializes current authored settings", async () => {
  await withFixture(async (root) => {
    const first = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    await writeFile(join(root, "defaults.yaml"), defaultsYaml("changed"));
    const second = await refreshModelCatalog(root, {
      previous: first.catalog,
      fetch: async () => { throw new Error("offline"); },
      now: () => new Date("2026-09-10T00:00:00.000Z")
    });
    assert.equal(second.reused_previous, true);
    assert.notEqual(second.catalog.source_fingerprint, first.catalog.source_fingerprint);
    assert.notEqual(second.catalog.catalog_fingerprint, first.catalog.catalog_fingerprint);
    assert.equal(second.catalog.defaults.global.marker, "changed");
    assert.equal(second.catalog.repositories["owner/sample-gguf@main"].retrieved_at, "2026-09-09T00:00:00.000Z");
  });
});

test("NeurOn can fetch selected repositories and merge named or metadata-only runtime extensions", async () => {
  await withFixture(async (root) => {
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const extension = await createCatalogExtension([
      { repository: "extra/model", revision: "main" },
      { repository: "extra/model", revision: "main", model_id: "neuron-extra" }
    ], { fetch: fakeHuggingFaceFetch(EXTRA_REVISION), now: fixedNow });
    assert.equal(Object.keys(extension.repositories).length, 1);
    assert.deepEqual(extension.models["neuron-extra"], {
      repository: "extra/model",
      resolved_revision: EXTRA_REVISION
    });
    const runtime = createRuntimeModelCatalog(catalog, [extension]);
    assert.equal(runtime.models["sample-7b"].source, "prefer");
    assert.equal(runtime.models["neuron-extra"].source, "extension");
    assert.ok(runtime.repositories[`extra/model@${EXTRA_REVISION}`]);

    const metadataOnly = await createCatalogExtension(
      [{ repository: "extra/model", revision: "main" }],
      { fetch: fakeHuggingFaceFetch(EXTRA_REVISION), now: fixedNow }
    );
    assert.deepEqual(metadataOnly.models, {});
    const merged = mergeCatalogExtensions(metadataOnly, extension);
    assert.ok(merged.models["neuron-extra"]);
    assert.throws(() => createRuntimeModelCatalog(catalog, [{ ...extension, models: { "sample-7b": extension.models["neuron-extra"] } }]), /model id conflict/u);
  });
});

test("immutable runtime handoffs bind exact artifacts to one release catalog and engine", async () => {
  await withFixture(async (root) => {
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const variant = resolveModelVariant(catalog, "sample-7b", { engine: "llama.cpp" });
    const handoff = createRuntimeHandoff(catalog, {
      engine: "llama.cpp",
      baseDeployment: "local/example/1x/general",
      serverSettings: { parallel: 2 },
      models: [{ variant, request_model_id: "sample" }],
      additionalArtifacts: [{
        repository: "owner/sample-companion",
        revision: EXTRA_REVISION,
        path: "adapter.safetensors",
        size: 10,
        sha256: "f".repeat(64),
        model_id: "sample-7b",
        role: "lora",
        settings: { argument: "--lora" }
      }]
    });
    assert.equal(handoff.catalog_fingerprint, catalog.catalog_fingerprint);
    assert.equal(handoff.models[0].request_model_id, "sample");
    assert.equal(handoff.artifacts.length, 2);
    assert.equal(handoff.models[0].artifact_ids.length, 2);
    assert.equal(handoff.artifacts[0].sha256, "c".repeat(64));

    const encoded = encodeRuntimeHandoffBase64(handoff);
    assert.deepEqual(decodeRuntimeHandoffBase64(encoded), handoff);
    assert.throws(() => decodeRuntimeHandoffBase64(` ${encoded}`), /base64 is invalid/u);
    assert.throws(() => decodeRuntimeHandoffBase64("bm90LWpzb24="), /does not contain valid UTF-8 JSON/u);
    const oversized = createRuntimeHandoff(catalog, {
      engine: "llama.cpp",
      serverSettings: { padding: "x".repeat(80 * 1024) },
      models: [{ variant }]
    });
    assert.throws(() => encodeRuntimeHandoffBase64(oversized), /exceeds 98304 characters/u);

    const materialized = materializeRuntimeHandoff(handoff, catalog, {
      engine: "llama.cpp",
      modelRoot: "/persistent/models"
    });
    assert.equal(materialized.models[0].repository_path, "/persistent/models/owner/sample-gguf");
    assert.equal(materialized.artifacts[1].local_path, "/persistent/models/owner/sample-companion/adapter.safetensors");

    const changed = {
      schema_version: "prefer.runtime-model-catalog.v1",
      base_catalog_fingerprint: "9".repeat(64),
      models: {},
      repositories: {}
    };
    assert.throws(
      () => materializeRuntimeHandoff(handoff, changed, { engine: "llama.cpp" }),
      /does not match image catalog/u
    );
    assert.throws(
      () => materializeRuntimeHandoff(handoff, catalog, { engine: "vllm" }),
      /does not match image engine/u
    );
    const tampered = structuredClone(handoff);
    tampered.artifacts[0].size += 1;
    assert.throws(
      () => materializeRuntimeHandoff(tampered, catalog, { engine: "llama.cpp" }),
      /artifact id does not match|fingerprint does not match/u
    );
  });
});

test("controller extensions become launchable only after exact file and hash selection", async () => {
  const extension = await createCatalogExtension(
    [{ repository: "extra/model", revision: "main", model_id: "neuron-extra" }],
    { fetch: fakeHuggingFaceFetch(EXTRA_REVISION), now: fixedNow }
  );
  assert.throws(
    () => resolveExtensionModelVariant(extension, "neuron-extra", {
      engine: "vllm",
      files: ["missing.safetensors"],
      quant: "bf16"
    }),
    /does not contain/u
  );
  const resolved = resolveExtensionModelVariant(extension, "neuron-extra", {
    engine: "vllm",
    files: ["config.json"],
    quant: "bf16",
    capabilities: ["text-generation"]
  });
  assert.equal(resolved.artifacts[0].blob_oid, "f".repeat(40));
  assert.equal(resolved.repository_path, "/models/extra/model");
  const handoff = createRuntimeHandoff({
    schema_version: "prefer.runtime-model-catalog.v1",
    base_catalog_fingerprint: "9".repeat(64),
    models: {},
    repositories: {}
  }, {
    engine: "vllm",
    models: [{ variant: resolved, source: "extension" }]
  });
  assert.equal(handoff.artifacts[0].git_blob_sha1, "f".repeat(40));
});

test("NeurOn repository selections retain whether the returned file tree is complete or filtered", async () => {
  const [repository] = await resolveHuggingFaceSelections([
    { repository: "extra/model", revision: "main", include: ["*.gguf"] },
    { repository: "extra/model", revision: "main", include: ["*.json"] }
  ], { fetch: fakeHuggingFaceFetch(EXTRA_REVISION), now: fixedNow });
  assert.equal(repository.files_complete, false);
  assert.deepEqual(repository.include_patterns, ["*.gguf", "*.json"]);
  assert.deepEqual(repository.files.map((file) => file.path), ["config.json", "mmproj-F16.gguf", "sample-Q4_K_M.gguf", "sample-q6.gguf"]);
});

test("authored model ids may not be repeated inside YAML", async () => {
  await withFixture(async (root) => {
    const path = join(root, "models", "sample", "sample-7b.yaml");
    await writeFile(path, `${modelYaml()}\nid: repeated\n`);
    await assert.rejects(loadCatalogSources(root), /derived from the filename/u);
  });
});

test("catalog globs include files at the selected root and in nested folders", () => {
  assert.equal(globMatch("FL2VA/model_index.json", "FL2VA/**/*.json"), true);
  assert.equal(globMatch("FL2VA/scheduler/config.json", "FL2VA/**/*.json"), true);
  assert.equal(globMatch("Ref2VA/model_index.json", "FL2VA/**/*.json"), false);
});

test("model-level engines and multi-repository artifact bundles avoid repeated quant configuration", async () => {
  await withFixture(async (root) => {
    await writeFile(join(root, "models", "sample", "sample-7b.yaml"), multiRepositoryModelYaml());
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const resolved = resolveModelVariant(catalog, "sample-7b", { engine: "sglang" });
    assert.deepEqual(resolved.artifacts.map(({ repository, path, role }) => ({ repository, path, role })), [
      { repository: "owner/sample-gguf", path: "sample-q6.gguf", role: "model" },
      { repository: "owner/sample-companion", path: "config.json", role: "tokenizer" }
    ]);
  });
});

test("engine artifact-role defaults remove repeated component bindings and permit exceptions", async () => {
  await withFixture(async (root) => {
    await writeFile(join(root, "defaults.yaml"), `${defaultsYaml("original")}engine_artifact_roles:\n  stable-diffusion.cpp:\n    target: { argument: --diffusion-model }\n    vae: { argument: --vae }\n`);
    await writeFile(join(root, "models", "sample", "sample-7b.yaml"), `schema_version: prefer.model-source.v1
display_name: Image fixture
default: { repository: owner/sample-gguf, quant: q6 }
engines:
  stable-diffusion.cpp: {}
repositories:
  owner/sample-gguf:
    quants:
      q6:
        artifacts:
          - { files: [sample-q6.gguf], role: target }
          - { files: [config.json], role: vae, settings: { argument: --custom-vae } }
`);
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const resolved = resolveModelVariant(catalog, "sample-7b", { engine: "stable-diffusion.cpp" });
    assert.equal(resolved.artifacts[0].settings.argument, "--diffusion-model");
    assert.equal(resolved.artifacts[1].settings.argument, "--custom-vae");
  });
});

test("GGUF discovery exposes repository quants without authoring every Hugging Face file", async () => {
  await withFixture(async (root) => {
    await writeFile(join(root, "models", "sample", "sample-7b.yaml"), `schema_version: prefer.model-source.v1
display_name: Sample 7B
profile: { summary: A fixture model. }
default: { repository: owner/sample-gguf, quant: q6 }
engines:
  llama.cpp: {}
  sglang: {}
repositories:
  owner/sample-gguf:
    discover: gguf
    quants:
      q6:
        artifacts:
          - { files: [sample-q6.gguf], role: model }
          - { files: [mmproj-F16.gguf], role: projector }
`);
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const variants = listModelVariants(catalog, "sample-7b", "sglang");
    assert.deepEqual(variants.map(({ quant }) => quant), ["q6", "q4-k-m"]);
    const discovered = resolveModelVariant(catalog, "sample-7b", {
      engine: "sglang",
      quant: "q4-k-m",
      modelRoot: "/custom-models"
    });
    assert.deepEqual(discovered.files, ["sample-Q4_K_M.gguf", "mmproj-F16.gguf"]);
    assert.equal(discovered.repository_path, "/custom-models/owner/sample-gguf");
    assert.equal(discovered.settings.launcher.load_format, "gguf");
  });
});

test("quant source mappings choose engine-specific NVFP4 repositories while Q6 remains the default", async () => {
  await withFixture(async (root) => {
    await writeFile(join(root, "models", "sample", "sample-7b.yaml"), `schema_version: prefer.model-source.v1
display_name: Sample 7B
profile: { summary: A fixture model. }
default: { repository: owner/sample-gguf, quant: q6 }
engines:
  sglang: {}
  vllm: {}
quant_sources:
  nvfp4:
    sglang: owner/sample-sglang
    vllm: owner/sample-vllm
repositories:
  owner/sample-gguf:
    quants:
      q6: { files: [sample-q6.gguf] }
  owner/sample-sglang:
    quants:
      nvfp4:
        include: ["*.json"]
        engines: { sglang: {} }
  owner/sample-vllm:
    quants:
      nvfp4:
        include: ["*.json"]
        engines: { vllm: {} }
`);
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    assert.equal(resolveModelVariant(catalog, "sample-7b", { engine: "sglang" }).repository, "owner/sample-gguf");
    const sglang = resolveModelVariant(catalog, "sample-7b", { engine: "sglang", useNvfp4: true });
    const vllm = resolveModelVariant(catalog, "sample-7b", { engine: "vllm", quant: "nvfp4" });
    assert.equal(sglang.repository, "owner/sample-sglang");
    assert.equal(vllm.repository, "owner/sample-vllm");
    assert.equal(sglang.settings.launcher.quantization, "modelopt_fp4");
  });
});

test("deployment hardware normalizes discrete and unified memory without double counting", () => {
  const discrete = normalizeDeploymentResources({
    provider: "aws",
    hardware: { provider_sku: "g7e.12xlarge", gpu_slug: "rtx-pro-6000", gpu_count: 2, vram_gb_each: 96, architecture: "Blackwell", vcpu: 48 }
  });
  assert.equal(discrete.memory_topology, "discrete");
  assert.equal(discrete.accelerators.length, 2);
  assert.equal(discrete.accelerators[0].total_bytes, 96 * 1024 ** 3);
  assert.equal(discrete.accelerators[0].slug, "rtx-pro-6000");
  assert.ok(discrete.capabilities.includes("nvfp4"));
  assert.equal(discrete.cpu.logical_cores, 48);

  const unified = normalizeDeploymentResources({
    provider: "local",
    hardware: { gpu_count: 1, vram_gb_each: 128, memory_topology: "unified", unified_memory_gb: 128, gpu_name: "NVIDIA GB10", architecture: "Blackwell" }
  }, {
    accelerators: [{ name: "NVIDIA GB10", total_bytes: 128 * 1024 ** 3, available_bytes: 110 * 1024 ** 3, capabilities: ["nvfp4"] }],
    host_memory: { total_bytes: 128 * 1024 ** 3, available_bytes: 100 * 1024 ** 3 },
    unified_memory: { total_bytes: 128 * 1024 ** 3, available_bytes: 105 * 1024 ** 3 }
  });
  assert.equal(unified.memory_topology, "unified");
  const variant = { artifact_bytes: 99 * 1024 ** 3 };
  const fit = estimateVariantFit(variant, unified, { runtime_overhead_bytes: 0, headroom_fraction: 0, minimum_headroom_bytes: 0 });
  assert.equal(fit.capacity_bytes, 100 * 1024 ** 3);
  assert.equal(fit.status, "fits");

  const runtimeMismatch = normalizeDeploymentResources({
    hardware: { gpu_count: 1, vram_gb_each: 96, gpu_name: "NVIDIA RTX PRO 6000", architecture: "Blackwell", compute_capability: "sm_120" }
  }, {
    accelerators: [{ name: "NVIDIA L4", total_bytes: 24 * 1024 ** 3, available_bytes: 20 * 1024 ** 3, compute_capability: "sm_89", capabilities: ["cuda", "fp8"] }]
  });
  assert.equal(runtimeMismatch.accelerators[0].name, "NVIDIA L4");
  assert.equal(runtimeMismatch.accelerators[0].architecture, undefined);
  assert.ok(!runtimeMismatch.capabilities.includes("nvfp4"));
});

test("runtime GPU facts parse into exact available memory and capabilities", () => {
  const [gpu] = parseNvidiaSmi("NVIDIA RTX PRO 6000 Blackwell Server Edition, GPU-1, 97887, 90000, 12.0\n");
  assert.equal(gpu.available_bytes, 90000 * 1024 ** 2);
  assert.equal(gpu.compute_capability, "sm_120");
  assert.ok(gpu.capabilities.includes("nvfp4"));
});

test("resource planning keeps the preferred quant when it fits and drops to a quality-credible smaller quant when constrained", async () => {
  await withFixture(async (root) => {
    await writeFile(join(root, "models", "sample", "sample-7b.yaml"), `schema_version: prefer.model-source.v1
display_name: Sample 7B
profile: { summary: A fixture model. }
default: { repository: owner/sample-gguf, quant: q6 }
engines: { llama.cpp: {} }
repositories:
  owner/sample-gguf:
    discover: gguf
    quants:
      q6: { files: [sample-q6.gguf] }
`);
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const roomy = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
      accelerators: [{ total_bytes: 200, available_bytes: 200, capabilities: [] }]
    });
    const constrained = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
      accelerators: [{ total_bytes: 110, available_bytes: 110, capabilities: [] }]
    });
    const workloadCapacity = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
      accelerators: [{ total_bytes: 500, available_bytes: 500, capabilities: [] }]
    });
    const common = {
      engine: "llama.cpp",
      models: [{ model_id: "sample-7b", required: true }],
      fit: { runtime_overhead_bytes: 0, headroom_fraction: 0, minimum_headroom_bytes: 0 }
    };
    const preferred = planModelSet(catalog, { ...common, resources: roomy });
    const fallback = planModelSet(catalog, { ...common, resources: constrained });
    const capacityBiased = planModelSet(catalog, {
      ...common,
      resources: roomy,
      hints: { quant_bias: "capacity" }
    });
    const workloadAware = planModelSet(catalog, {
      ...common,
      resources: workloadCapacity,
      workload: {
        desired_context_tokens: 390,
        desired_concurrency: 1,
        minimum_context_tokens: 300,
        bytes_per_token: 1,
        source: "architecture"
      }
    });
    assert.equal(preferred.selected[0].selected.quant, "q6");
    assert.equal(preferred.selected[0].quant_changed, false);
    assert.equal(fallback.selected[0].selected.quant, "q4-k-m");
    assert.equal(fallback.selected[0].quant_changed, true);
    assert.equal(fallback.complete, true);
    assert.equal(capacityBiased.selected[0].selected.quant, "q4-k-m");
    assert.equal(workloadAware.selected[0].selected.quant, "q4-k-m");
    assert.equal(workloadAware.selected[0].fit.confidence, "architecture");
    assert.equal(workloadAware.selected[0].workload_request.desired_context_tokens, 390);
  });
});

test("default device reserve scales from 1.5 GiB to a 4 GiB cap", () => {
  const twentyFour = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 24 } });
  const ninetySix = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 96 } });
  const small = estimateVariantFit({ artifact_bytes: 20 * GIB }, twentyFour, { runtime_overhead_bytes: 0 });
  const large = estimateVariantFit({ artifact_bytes: 92 * GIB }, ninetySix, { runtime_overhead_bytes: 0 });
  assert.equal(small.status, "fits");
  assert.equal(small.usable_capacity_bytes, 22.5 * GIB);
  assert.equal(large.status, "fits");
  assert.equal(large.usable_capacity_bytes, 96 * GIB - Math.floor(96 * GIB * 0.04));

  const fixed = estimateVariantFit({ artifact_bytes: 20 * GIB }, twentyFour, {
    runtime_overhead_bytes: 0,
    headroom_fraction: 0,
    minimum_headroom_bytes: 2 * GIB,
    maximum_headroom_bytes: 2 * GIB
  });
  assert.equal(fixed.usable_capacity_bytes, 22 * GIB);
});

test("configured host offload is selected conditionally until host RAM is observed", async () => {
  await withFixture(async (root) => {
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const unknownHost = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
      accelerators: [{ total_bytes: 110, available_bytes: 110, capabilities: [] }]
    });
    const request = {
      model_id: "sample-7b",
      required: true,
      fit: {
        runtime_overhead_bytes: 0,
        headroom_fraction: 0,
        minimum_headroom_bytes: 0,
        maximum_headroom_bytes: 0,
        allow_host_offload: true,
        allow_unknown_host_offload: true
      }
    };
    const conditional = planModelSet(catalog, {
      engine: "llama.cpp",
      resources: unknownHost,
      models: [request]
    });
    assert.equal(conditional.complete, true);
    assert.equal(conditional.selected[0].fit.status, "unknown");
    assert.equal(conditional.selected[0].fit.host_offload_bytes, 13);

    const knownHost = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
      accelerators: [{ total_bytes: 110, available_bytes: 110, capabilities: [] }],
      host_memory: { available_bytes: 20 }
    });
    const measured = planModelSet(catalog, {
      engine: "llama.cpp",
      resources: knownHost,
      models: [request]
    });
    assert.equal(measured.selected[0].fit.status, "host-offload");
  });
});

test("workload hints rank optional bundle members without turning preferences into hard requirements", async () => {
  await withFixture(async (root) => {
    await writeFile(join(root, "models", "sample", "sample-7b.yaml"), `schema_version: prefer.model-source.v1
display_name: Writing model
capabilities: [chat]
profile:
  summary: A writing fixture.
  architecture: { kind: dense, total_parameters_b: 27, active_parameters_b: 27 }
  roles: { preferred: [general-writing] }
default: { repository: owner/sample-gguf, quant: q6 }
engines: { llama.cpp: {} }
repositories:
  owner/sample-gguf:
    quants:
      q6: { files: [sample-q6.gguf] }
`);
    await writeFile(join(root, "models", "sample", "fast-30b-a3b.yaml"), `schema_version: prefer.model-source.v1
display_name: Fast MoE
capabilities: [chat, tools]
profile:
  summary: A fast fixture.
  architecture: { kind: moe, total_parameters_b: 30, active_parameters_b: 3 }
  roles: { capable: [coding] }
default: { repository: owner/sample-gguf, quant: q6 }
engines: { llama.cpp: {} }
repositories:
  owner/sample-gguf:
    quants:
      q6: { files: [sample-q6.gguf] }
`);
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const resources = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
      accelerators: [{ total_bytes: 500, available_bytes: 500, capabilities: [] }]
    });
    const common = {
      engine: "llama.cpp",
      resources,
      models: [
        { model_id: "sample-7b", priority: 2 },
        { model_id: "fast-30b-a3b", priority: 1 }
      ],
      max_models: 1,
      fit: { runtime_overhead_bytes: 0, headroom_fraction: 0, minimum_headroom_bytes: 0 }
    };
    const writing = planModelSet(catalog, { ...common, hints: { preferred_roles: ["general-writing"] } });
    const speed = planModelSet(catalog, { ...common, hints: { speed_importance: 1 } });
    const quality = planModelSet(catalog, {
      ...common,
      models: [
        { model_id: "sample-7b", priority: 2, quality_score: 40 },
        { model_id: "fast-30b-a3b", priority: 1, quality_score: 90 }
      ],
      hints: { quality_importance: 1 }
    });
    const unavailable = planModelSet(catalog, {
      ...common,
      max_models: 2,
      hints: { required_capabilities: ["image-understanding"] }
    });
    assert.equal(writing.selected[0].model_id, "sample-7b");
    assert.equal(speed.selected[0].model_id, "fast-30b-a3b");
    assert.equal(quality.selected[0].model_id, "fast-30b-a3b");
    assert.equal(unavailable.selected.length, 0);
    assert.ok(unavailable.skipped.every((entry) => entry.reason === "missing-capability"));
    assert.equal(unavailable.complete, true);
  });
});

test("bundle planning skips optional models that cannot satisfy memory or staging budgets", async () => {
  await withFixture(async (root) => {
    const { catalog } = await refreshModelCatalog(root, { fetch: fakeHuggingFaceFetch(), now: fixedNow });
    const resources = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
      accelerators: [{ total_bytes: 500, available_bytes: 500, capabilities: [] }],
      storage: { total_bytes: 100, available_bytes: 100 }
    });
    const plan = planModelSet(catalog, {
      engine: "llama.cpp",
      resources,
      models: [{ model_id: "sample-7b" }],
      fit: { runtime_overhead_bytes: 0, headroom_fraction: 0, minimum_headroom_bytes: 0 }
    });
    assert.equal(plan.selected.length, 0);
    assert.equal(plan.skipped[0].reason, "storage-budget");
    assert.equal(plan.complete, true);
  });
});

test("generated general deployments become optional planner requests with host-specific starting quants", () => {
  const requests = modelRequestsFromDeployment({
    id: "aws/g6/xlarge/general",
    kind: "bundle",
    models: [
      { profile_id: "qwen-3.8-27b", quant_slug: "ud-q4-k-xl" },
      { model_slug: "gemma-4-12b", quant_slug: "ud-q4-k-xl" }
    ]
  });
  assert.deepEqual(requests, [
    { model_id: "qwen-3.8-27b", preferred_quant: "ud-q4-k-xl", required: false, priority: 2 },
    { model_id: "gemma-4-12b", preferred_quant: "ud-q4-k-xl", required: false, priority: 1 }
  ]);
  assert.ok(modelRequestsFromDeployment({
    id: "audio/cuda12",
    models: [{ model_slug: "qwen3-tts-0.6b" }, { model_slug: "qwen3-asr-0.6b" }]
  }).every((entry) => entry.required === false));

  assert.deepEqual(modelRequestsFromDeployment({
    id: "local/rtx-4090/1x/h3-fl2va",
    residency: { offload: { components: "dit,text_encoder" } },
    models: [{
      request_model_id: "minimax-h3-fl2va",
      model_slug: "minimax-h3-fl2va",
      profile_id: "minimax-h3",
      quant_slug: "int8-convrot"
    }]
  }), [{
    model_id: "minimax-h3-fl2va",
    preferred_quant: "int8-convrot",
    required: true,
    priority: 1,
    fit: { allow_host_offload: true, allow_unknown_host_offload: true }
  }]);
});

test("workload tuning preserves the selected priority within a measured token budget", () => {
  const resources = normalizeDeploymentResources({ hardware: { gpu_count: 1, vram_gb_each: 1 } }, {
    accelerators: [{ total_bytes: 1000, available_bytes: 1000, capabilities: [] }]
  });
  const variant = { artifact_bytes: 100 };
  const tuned = tuneWorkloadToFit(variant, resources, {
    desired_context_tokens: 200,
    desired_concurrency: 4,
    minimum_context_tokens: 100,
    minimum_concurrency: 1,
    priority: "context",
    bytes_per_token: 1
  }, { runtime_overhead_bytes: 0, headroom_fraction: 0, minimum_headroom_bytes: 0 });
  assert.equal(tuned.fits, true);
  assert.equal(tuned.context_tokens, 200);
  assert.equal(tuned.concurrency, 4);
  assert.equal(tuned.changed, false);
  const constrained = tuneWorkloadToFit(variant, resources, {
    desired_context_tokens: 400,
    desired_concurrency: 4,
    minimum_context_tokens: 100,
    minimum_concurrency: 1,
    priority: "context",
    bytes_per_token: 1
  }, { runtime_overhead_bytes: 0, headroom_fraction: 0, minimum_headroom_bytes: 0 });
  assert.equal(constrained.context_tokens, 400);
  assert.equal(constrained.concurrency, 2);
  assert.equal(quantQuality("UD-Q6_K_XL").tier, "high");
  assert.equal(quantQuality("IQ2_M").tier, "fit-floor");
});

async function withFixture(callback) {
  const root = await mkdtemp(join(tmpdir(), "prefer-catalog-"));
  try {
    await mkdir(join(root, "models", "sample"), { recursive: true });
    await writeFile(join(root, "defaults.yaml"), defaultsYaml("original"));
    await writeFile(join(root, "models", "sample", "sample-7b.yaml"), modelYaml());
    await callback(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

function defaultsYaml(marker) {
  return `schema_version: prefer.model-defaults.v1
global: { precedence: global, global: true, marker: ${marker} }
engines:
  llama.cpp: { precedence: engine, engine: true }
`;
}

function modelYaml() {
  return `schema_version: prefer.model-source.v1
display_name: Sample 7B
profile: { summary: A fixture model. }
capabilities: [chat]
default: { repository: owner/sample-gguf, quant: q6 }
settings: { precedence: model, model: true }
engines:
  llama.cpp:
    settings: { precedence: model-engine, model_engine: true }
repositories:
  owner/sample-gguf:
    settings: { precedence: repository, repository: true }
    quants:
      q6:
        files: [sample-q6.gguf]
        settings: { precedence: quant, quant: true }
        engines:
          all:
            capabilities: [tools]
            settings: { precedence: all-engine, all_engine: true }
          llama.cpp:
            settings: { precedence: exact-engine, exact_engine: true }
`;
}

function multiRepositoryModelYaml() {
  return `schema_version: prefer.model-source.v1
display_name: Sample 7B
profile: { summary: A fixture model. }
default: { repository: owner/sample-gguf, quant: q6 }
engines:
  sglang: {}
repositories:
  owner/sample-gguf:
    quants:
      q6:
        artifacts:
          - { files: [sample-q6.gguf], role: model }
          - { repository: owner/sample-companion, files: [config.json], role: tokenizer }
  owner/sample-companion:
    {}
`;
}

function fakeHuggingFaceFetch(revision = REVISION) {
  return async (url) => {
    if (url.includes("/revision/")) {
      return jsonResponse({
        sha: revision,
        tags: ["transformers", "base_model:Base/Model"],
        cardData: { license: "apache-2.0", base_model: "Base/Model" },
        pipeline_tag: "text-generation",
        library_name: "transformers",
        gated: false,
        private: false
      });
    }
    if (url.includes("/tree/")) {
      return jsonResponse([
        { type: "file", path: "sample-q6.gguf", size: 123, oid: "blob", lfs: { oid: "c".repeat(64) } },
        { type: "file", path: "sample-Q4_K_M.gguf", size: 100, oid: "q4-blob", lfs: { oid: "d".repeat(64) } },
        { type: "file", path: "mmproj-F16.gguf", size: 20, oid: "projector-blob", lfs: { oid: "e".repeat(64) } },
        { type: "file", path: "config.json", size: 45, oid: "f".repeat(40) }
      ]);
    }
    return new Response("not found", { status: 404 });
  };
}

function jsonResponse(value) {
  const body = JSON.stringify(value);
  return new Response(body, { headers: { "content-type": "application/json", "content-length": String(Buffer.byteLength(body)) } });
}

function fixedNow() { return new Date("2026-09-09T00:00:00.000Z"); }
