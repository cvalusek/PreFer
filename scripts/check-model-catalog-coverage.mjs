#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { basename, resolve } from "node:path";
import { loadCatalogSources } from "../packages/prefer/dist/index.js";

const engineRoots = [
  ["llama.cpp", "docker/llama-cpp/models"],
  ["audio.cpp", "docker/audio-cpp/models"],
  ["stable-diffusion.cpp", "docker/stable-diffusion-cpp/models"],
  ["sglang", "docker/sglang/models"],
  ["vllm", "docker/vllm/models"]
];

const sources = await loadCatalogSources(resolve("catalog"));
assert.equal(sources.defaults.global, undefined, "catalog defaults must not own storage, API, or Hugging Face metadata policy");
assert.equal(sources.defaults.quants, undefined, "quant taxonomy belongs to resolved repository metadata, not defaults.yaml");
assert.equal(sources.defaults.engine_quants, undefined, "engine/quant behavior must be inferred or be a genuine model override");
const engineModels = [];
for (const [engine, root] of engineRoots) {
  for (const file of await modelFiles(resolve(root))) {
    engineModels.push({ engine, file, value: JSON.parse(await readFile(file, "utf8")) });
  }
}

const expectedIds = [...new Set(engineModels.map(({ value }) => value.model_slug))].sort();
const catalogIds = Object.keys(sources.models).sort();
assert.deepEqual(catalogIds, expectedIds, "the shared catalog must cover exactly every engine-local logical model");

for (const { engine, file, value } of engineModels) {
  const model = sources.models[value.model_slug];
  assert.ok(model, `${file}: ${value.model_slug} is missing from the shared catalog`);
  assert.ok(supportsEngine(model, engine), `${model.id} does not expose its configured ${engine} engine`);
  const sharedQuants = new Set(Object.values(model.repositories).flatMap((repository) => Object.keys(repository.quants ?? {})));
  for (const quant of Object.keys(value.quants)) {
    assert.ok(sharedQuants.has(quant), `${model.id} is missing engine-local ${engine} quant ${quant}`);
    const centralQuants = Object.values(model.repositories).flatMap((repository) => repository.quants?.[quant] ? [repository.quants[quant]] : []);
    if (engine === "llama.cpp") {
      const expected = merge(value.shared?.settings, value.quants[quant].settings);
      for (const key of ["model", "model-draft", "mmproj"]) delete expected[key];
      assert.ok(centralQuants.some((source) => {
        const actual = merge(model.engines?.["llama.cpp"]?.settings?.launcher, source.settings?.launcher);
        return contains(actual, expected);
      }), `${model.id}/${quant} is missing model-specific llama.cpp settings`);
    }
    if (engine === "audio.cpp" && value.quants[quant].server) {
      assert.ok(centralQuants.some((source) => contains(source.settings?.launcher, value.quants[quant].server)),
        `${model.id}/${quant} is missing model-specific Audio settings`);
    }
  }
  if (engine === "stable-diffusion.cpp" && value.shared?.args) {
    assert.deepEqual(model.engines?.[engine]?.settings?.launcher?.args, value.shared.args,
      `${model.id} is missing model-specific image defaults`);
  }
}

const llamaModelIds = new Set(engineModels.filter(({ engine }) => engine === "llama.cpp").map(({ value }) => value.model_slug));
for (const modelId of llamaModelIds) {
  const model = sources.models[modelId];
  for (const engine of ["llama.cpp", "sglang", "vllm"]) {
    assert.ok(supportsEngine(model, engine), `${modelId} must expose its text artifacts to ${engine}`);
  }
}

const authoredQuants = new Set();
for (const model of Object.values(sources.models)) {
  assert.ok(model.profile, `${model.id} must provide a prompt-ready profile`);
  assert.ok(model.profile.summary, `${model.id} profile must provide a summary`);
  assert.ok(model.profile.roles?.preferred?.length, `${model.id} profile must describe preferred roles`);
  assert.ok(model.profile.roles?.avoid?.length, `${model.id} profile must describe roles to avoid`);
  assert.ok(model.profile.strengths?.length, `${model.id} profile must describe strengths`);
  assert.ok(model.profile.limitations?.length, `${model.id} profile must describe limitations`);
  assert.ok(model.profile.prompting?.length, `${model.id} profile must provide prompting guidance`);
  assert.ok(model.profile.evidence?.confidence, `${model.id} profile must state evidence confidence`);
  assert.ok(model.capabilities?.length, `${model.id} must advertise capabilities`);
  assert.ok(!(model.aliases ?? []).includes(model.id), `${model.id} repeats its filename-derived canonical id as an alias`);
  assert.ok(!model.settings?.profile, `${model.id} profile belongs at the model root, not in runtime settings`);
  assert.notEqual(model.settings?.routing?.request_model_id, model.id, `${model.id} repeats its canonical id as request routing data`);
  assertNoRedundantSettings(model.settings, sources.defaults.global, model.id);
  for (const [engine, choice] of Object.entries(model.engines ?? {})) {
    const inherited = engine === "all"
      ? merge(sources.defaults.global, model.settings)
      : merge(
          sources.defaults.global,
          sources.defaults.engines?.[engine],
          model.settings,
          model.engines?.all?.settings
        );
    assertNoRedundantSettings(choice.settings, inherited, `${model.id}/${engine}`);
  }

  for (const [repositoryId, repository] of Object.entries(model.repositories)) {
    if (repositoryId !== "audio-cpp/audio.cpp-gguf" && hasPrimaryGguf(repository)) {
      assert.equal(repository.discover, "gguf", `${model.id}/${repositoryId} must expose its published GGUF quants`);
    }
    assertNoRedundantSettings(
      repository.settings,
      merge(sources.defaults.global, model.settings),
      `${model.id}/${repositoryId}`
    );
    for (const [quant, quantSource] of Object.entries(repository.quants ?? {})) {
      authoredQuants.add(quant);
      assertNoRedundantSettings(
        quantSource.settings,
        merge(
          sources.defaults.global,
          model.settings,
          repository.settings
        ),
        `${model.id}/${quant}`
      );
      const artifactEngines = new Set([
        ...Object.keys(model.engines ?? {}),
        ...Object.keys(quantSource.engines ?? {})
      ].filter((engine) => engine !== "all"));
      for (const artifact of quantSource.artifacts ?? []) {
        if (!artifact.role || !artifact.settings) continue;
        for (const engine of artifactEngines) {
          assertNoRedundantSettings(
            artifact.settings,
            sources.defaults.engine_artifact_roles?.[engine]?.[artifact.role],
            `${model.id}/${quant}/${engine}/${artifact.role}`
          );
        }
      }
      for (const [engine, choice] of Object.entries(quantSource.engines ?? {})) {
        const defaultSettings = engine === "all"
          ? merge(
              sources.defaults.global,
              model.settings,
              model.engines?.all?.settings,
              repository.settings,
              quantSource.settings
            )
          : merge(
              sources.defaults.global,
              sources.defaults.engines?.[engine],
              model.settings,
              model.engines?.all?.settings,
              model.engines?.[engine]?.settings,
              repository.settings,
              quantSource.settings,
              quantSource.engines?.all?.settings
            );
        assertNoRedundantSettings(choice.settings, defaultSettings, `${model.id}/${quant}/${engine}`);
      }
    }
  }
}

process.stdout.write(`shared catalog covers ${catalogIds.length} models across ${engineRoots.length} engines and ${authoredQuants.size} authored quant families\n`);

function supportsEngine(model, engine) {
  if (model.engines?.all || model.engines?.[engine]) return true;
  return Object.values(model.repositories).some((repository) =>
    Object.values(repository.quants ?? {}).some((quant) => quant.engines?.all || quant.engines?.[engine])
  );
}

function assertNoRedundantSettings(value, defaults, label, path = []) {
  if (!isObject(value) || !isObject(defaults)) return;
  for (const [key, child] of Object.entries(value)) {
    const inherited = defaults[key];
    if (isObject(child) && isObject(inherited)) {
      assertNoRedundantSettings(child, inherited, label, [...path, key]);
    } else if (JSON.stringify(child) === JSON.stringify(inherited)) {
      assert.fail(`${label} repeats inherited setting ${[...path, key].join(".")}`);
    }
  }
}

function merge(...values) {
  const result = {};
  for (const value of values) mergeInto(result, value);
  return result;
}

function mergeInto(target, source) {
  if (!isObject(source)) return;
  for (const [key, value] of Object.entries(source)) {
    if (isObject(value) && isObject(target[key])) mergeInto(target[key], value);
    else target[key] = structuredClone(value);
  }
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function contains(actual, expected) {
  if (!isObject(expected)) return JSON.stringify(actual) === JSON.stringify(expected);
  if (!isObject(actual)) return false;
  return Object.entries(expected).every(([key, value]) => contains(actual[key], value));
}

function hasPrimaryGguf(repository) {
  return Object.values(repository.quants ?? {}).some((quant) => {
    if ((quant.files ?? []).some((path) => path.toLowerCase().endsWith(".gguf"))) return true;
    return (quant.artifacts ?? []).some((artifact) =>
      !artifact.repository && [undefined, "model", "target", "checkpoint"].includes(artifact.role) &&
      (artifact.files ?? []).some((path) => path.toLowerCase().endsWith(".gguf"))
    );
  });
}

async function modelFiles(root) {
  const result = [];
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const path = resolve(root, entry.name);
    if (entry.isDirectory()) result.push(...await modelFiles(path));
    else if (basename(path) === "model.json") result.push(path);
  }
  return result.sort();
}
