#!/usr/bin/env node
import { resolve } from "node:path";
import {
  createCatalogExtension,
  detectRuntimeResources,
  downloadPreferTooling,
  listModelVariants,
  listPreferReleases,
  loadCatalogSources,
  modelRequestsFromDeployment,
  normalizeDeploymentResources,
  parseRepositorySelection,
  planModelSet,
  readJson,
  readModelCatalog,
  refreshModelCatalog,
  resolveModelVariant,
  validateModelCatalog,
  writeJsonAtomic
} from "./index.js";
import type {
  HuggingFaceSelection,
  JsonObject,
  ModelCatalogSnapshot,
  ModelPlanRequest,
  QuantQualityTier,
  QuantSelectionBias,
  ResourceProfile
} from "./types.js";

const [, , ...argv] = process.argv;

try {
  await main(argv);
} catch (error) {
  process.stderr.write(`prefer: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}

async function main(args: string[]): Promise<void> {
  const [area, command, ...rest] = args;
  if (!area || area === "help" || area === "--help" || area === "-h") return help();
  if (area === "catalog" && command === "refresh") return refresh(rest);
  if (area === "catalog" && command === "validate") return validate(rest);
  if (area === "catalog" && command === "extend") return extend(rest);
  if (area === "model" && command === "resolve") return resolveModel(rest);
  if (area === "model" && command === "list") return listModels(rest);
  if (area === "model" && command === "plan") return planModels(rest);
  if (area === "hardware" && command === "normalize") return normalizeHardware(rest);
  if (area === "hardware" && command === "detect") return detectHardware(rest);
  if (area === "release" && command === "list") return listReleases(rest);
  if (area === "release" && command === "fetch-tooling") return fetchTooling(rest);
  throw new Error(`unknown command ${[area, command].filter(Boolean).join(" ")}`);
}

async function refresh(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const source = one(flags, "source") ?? "catalog";
  const output = one(flags, "output", true)!;
  let previous: ModelCatalogSnapshot | undefined;
  const fallback = one(flags, "fallback");
  if (fallback) previous = await readModelCatalog(fallback);
  const result = await refreshModelCatalog(source, {
    previous,
    token: token(flags, "hf-token-env", "HF_TOKEN"),
    cacheDir: one(flags, "cache"),
    concurrency: integer(flags, "concurrency", 4)
  });
  await writeJsonAtomic(output, result.catalog);
  process.stdout.write(`${JSON.stringify({ output: resolve(output), reused_previous: result.reused_previous, catalog_fingerprint: result.catalog.catalog_fingerprint })}\n`);
}

async function validate(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const path = one(flags, "catalog", true)!;
  const catalog = await readModelCatalog(path);
  const source = one(flags, "source");
  if (source) {
    const sources = await loadCatalogSources(source);
    if (catalog.source_fingerprint !== sources.source_fingerprint) throw new Error("catalog does not match the authored source fingerprint");
  }
  validateModelCatalog(catalog);
  process.stdout.write(`${JSON.stringify({ valid: true, catalog_fingerprint: catalog.catalog_fingerprint })}\n`);
}

async function extend(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const output = one(flags, "output", true)!;
  const selections: HuggingFaceSelection[] = many(flags, "repo").map((value) => parseRepositorySelection(value));
  for (const value of many(flags, "model")) {
    const split = value.indexOf("=");
    if (split < 1) throw new Error("--model must use model-id=owner/repository[@revision]");
    selections.push({ ...parseRepositorySelection(value.slice(split + 1)), model_id: value.slice(0, split) });
  }
  if (!selections.length) throw new Error("catalog extend requires at least one --repo or --model selection");
  const extension = await createCatalogExtension(selections, {
    token: token(flags, "hf-token-env", "HF_TOKEN"),
    cacheDir: one(flags, "cache"),
    preferCache: bool(flags, "prefer-cache"),
    concurrency: integer(flags, "concurrency", 4)
  });
  await writeJsonAtomic(output, extension);
  process.stdout.write(`${JSON.stringify({ output: resolve(output), repositories: Object.keys(extension.repositories).length, models: Object.keys(extension.models).length })}\n`);
}

async function resolveModel(args: string[]): Promise<void> {
  const [modelId, ...tail] = args;
  if (!modelId || modelId.startsWith("--")) throw new Error("model resolve requires a PreFer model id");
  const flags = parseFlags(tail);
  const catalog = await readModelCatalog(one(flags, "catalog") ?? process.env.PREFER_MODEL_CATALOG ?? "/prefer-model-catalog.json");
  const engine = one(flags, "engine") ?? process.env.PREFER_ENGINE;
  if (!engine) throw new Error("model resolve requires --engine outside a PreFer engine image");
  const overrides = jsonObject(one(flags, "overrides") ?? "{}", "--overrides");
  const result = resolveModelVariant(catalog, modelId, {
    engine,
    ...(one(flags, "repository") ? { repository: one(flags, "repository")! } : {}),
    ...(one(flags, "quant") ? { quant: one(flags, "quant")! } : {}),
    modelRoot: one(flags, "model-root") ?? process.env.PREFER_MODELS_DIR ?? "/models",
    useNvfp4: bool(flags, "use-nvfp4") || environmentBoolean("USE_NVFP4"),
    overrides
  });
  await outputJson(flags, result);
}

async function listModels(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const catalog = await readModelCatalog(one(flags, "catalog") ?? process.env.PREFER_MODEL_CATALOG ?? "/prefer-model-catalog.json");
  const engine = one(flags, "engine") ?? process.env.PREFER_ENGINE;
  const modelId = one(flags, "model");
  const output = modelId
    ? listModelVariants(catalog, modelId, engine)
    : Object.values(catalog.models).map((model) => ({ id: model.id, family: model.family, display_name: model.display_name, aliases: model.aliases ?? [] }));
  await outputJson(flags, output);
}

async function normalizeHardware(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const value = await deploymentInput(one(flags, "input", true)!, one(flags, "deployment"));
  await outputJson(flags, normalizeDeploymentResources(value));
}

async function detectHardware(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const basePath = one(flags, "base");
  const base = basePath
    ? normalizeDeploymentResources(await deploymentInput(basePath, one(flags, "deployment")))
    : undefined;
  await outputJson(flags, await detectRuntimeResources({ ...(base ? { base } : {}) }));
}

async function planModels(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const catalog = await readModelCatalog(one(flags, "catalog") ?? process.env.PREFER_MODEL_CATALOG ?? "/prefer-model-catalog.json");
  const engine = one(flags, "engine") ?? process.env.PREFER_ENGINE;
  if (!engine) throw new Error("model plan requires --engine outside a PreFer engine image");
  const resourceValue = await deploymentInput(one(flags, "resources", true)!, one(flags, "deployment"));
  let resources: ResourceProfile = normalizeDeploymentResources(resourceValue);
  if (bool(flags, "detect")) resources = await detectRuntimeResources({ base: resources });
  const required = new Set(many(flags, "required-model"));
  const speedScores = namedScores(flags, "speed-score");
  const qualityScores = namedScores(flags, "quality-score");
  const rawModels = [...many(flags, "model"), ...many(flags, "models").flatMap(commaList)];
  const models: ModelPlanRequest[] = rawModels.map((value) => {
    const separator = value.indexOf(":");
    const modelId = separator > 0 ? value.slice(0, separator) : value;
    const quant = separator > 0 ? value.slice(separator + 1) : undefined;
    return {
      model_id: modelId,
      ...(quant ? { quant } : {}),
      ...(required.has(modelId) ? { required: true } : {})
    };
  });
  if (!models.length) models.push(...modelRequestsFromDeployment(resourceValue));
  if (!models.length) throw new Error("model plan requires --model selections or a deployment containing models");
  for (const model of models) {
    if (required.has(model.model_id)) model.required = true;
    const speedScore = speedScores.get(model.model_id);
    const qualityScore = qualityScores.get(model.model_id);
    if (speedScore !== undefined) model.speed_score = speedScore;
    if (qualityScore !== undefined) model.quality_score = qualityScore;
  }
  for (const modelId of [...speedScores.keys(), ...qualityScores.keys()]) {
    if (!models.some((model) => model.model_id === modelId)) throw new Error(`score supplied for unselected model ${modelId}`);
  }
  const floor = choice(flags, "quality-floor", ["reference", "near-lossless", "high", "deployment", "compromise", "fit-floor", "extreme", "unknown"] as const) as QuantQualityTier | undefined;
  const quantBias = choice(flags, "quant-bias", ["quality", "balanced", "capacity"] as const) as QuantSelectionBias | undefined;
  const requiredCapabilities = many(flags, "required-capability").flatMap(commaList);
  const preferredCapabilities = many(flags, "preferred-capability").flatMap(commaList);
  const preferredRoles = many(flags, "preferred-role").flatMap(commaList);
  const speedImportance = numberValue(flags, "speed-importance");
  const qualityImportance = numberValue(flags, "quality-importance");
  const desiredContext = positiveIntegerOptional(flags, "context-tokens");
  const desiredConcurrency = positiveIntegerOptional(flags, "concurrency");
  const bytesPerToken = numberValue(flags, "bytes-per-token");
  const minimumContext = positiveIntegerOptional(flags, "minimum-context-tokens");
  const minimumConcurrency = positiveIntegerOptional(flags, "minimum-concurrency");
  const fixedDeviceBytes = integerOptional(flags, "fixed-device-bytes");
  const workloadPriority = choice(flags, "workload-priority", ["context", "concurrency"] as const);
  const workloadSource = choice(flags, "workload-source", ["measured", "architecture", "operator", "estimate"] as const);
  const workloadSpecified = desiredContext !== undefined || desiredConcurrency !== undefined || bytesPerToken !== undefined
    || minimumContext !== undefined || minimumConcurrency !== undefined || fixedDeviceBytes !== undefined
    || workloadPriority !== undefined || workloadSource !== undefined;
  if (workloadSpecified && (desiredContext === undefined || desiredConcurrency === undefined || bytesPerToken === undefined)) {
    throw new Error("workload planning requires --context-tokens, --concurrency, and --bytes-per-token together");
  }
  const headroomPercent = numberValue(flags, "headroom-percent");
  const headroomGiB = numberValue(flags, "headroom-gib");
  if (headroomGiB !== undefined && (!Number.isFinite(headroomGiB) || headroomGiB < 0)) {
    throw new Error("--headroom-gib must be non-negative");
  }
  const result = planModelSet(catalog, {
    engine,
    resources,
    models,
    use_nvfp4: bool(flags, "use-nvfp4") || environmentBoolean("USE_NVFP4"),
    ...(floor ? { quality_floor: floor } : {}),
    ...(integerOptional(flags, "max-models") !== undefined ? { max_models: integerOptional(flags, "max-models")! } : {}),
    ...(integerOptional(flags, "max-staged-bytes") !== undefined ? { max_staged_bytes: integerOptional(flags, "max-staged-bytes")! } : {}),
    accept_tight: bool(flags, "accept-tight"),
    ...(requiredCapabilities.length || preferredCapabilities.length || preferredRoles.length || quantBias
      || speedImportance !== undefined || qualityImportance !== undefined ? {
      hints: {
        ...(requiredCapabilities.length ? { required_capabilities: requiredCapabilities } : {}),
        ...(preferredCapabilities.length ? { preferred_capabilities: preferredCapabilities } : {}),
        ...(preferredRoles.length ? { preferred_roles: preferredRoles } : {}),
        ...(speedImportance !== undefined ? { speed_importance: speedImportance } : {}),
        ...(qualityImportance !== undefined ? { quality_importance: qualityImportance } : {}),
        ...(quantBias ? { quant_bias: quantBias } : {})
      }
    } : {}),
    ...(workloadSpecified ? {
      workload: {
        desired_context_tokens: desiredContext!,
        desired_concurrency: desiredConcurrency!,
        bytes_per_token: bytesPerToken!,
        ...(minimumContext !== undefined ? { minimum_context_tokens: minimumContext } : {}),
        ...(minimumConcurrency !== undefined ? { minimum_concurrency: minimumConcurrency } : {}),
        ...(fixedDeviceBytes !== undefined ? { fixed_device_bytes: fixedDeviceBytes } : {}),
        ...(workloadPriority ? { priority: workloadPriority } : {}),
        ...(workloadSource ? { source: workloadSource } : {})
      }
    } : {}),
    fit: {
      allow_host_offload: bool(flags, "allow-host-offload"),
      allow_unknown_host_offload: bool(flags, "allow-host-offload"),
      ...(headroomPercent !== undefined ? { headroom_fraction: headroomPercent / 100 } : {}),
      ...(headroomGiB !== undefined ? {
        minimum_headroom_bytes: Math.floor(headroomGiB * 1024 ** 3),
        maximum_headroom_bytes: Math.floor(headroomGiB * 1024 ** 3)
      } : {})
    }
  });
  await outputJson(flags, result);
}

async function listReleases(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const repository = one(flags, "repository") ?? "cvalusek/PreFer";
  const channel = (one(flags, "channel") ?? "stable") as "stable" | "preview";
  if (channel !== "stable" && channel !== "preview") throw new Error("--channel must be stable or preview");
  const releases = await listPreferReleases(repository, {
    channel,
    limit: integer(flags, "limit", 20),
    token: token(flags, "github-token-env", "GITHUB_TOKEN")
  });
  await outputJson(flags, releases.map(({ assets: _assets, ...release }) => release));
}

async function fetchTooling(args: string[]): Promise<void> {
  const flags = parseFlags(args);
  const channel = one(flags, "channel") as "stable" | "preview" | undefined;
  const outputDir = one(flags, "output-dir", true)!;
  const result = await downloadPreferTooling({
    repository: one(flags, "repository") ?? "cvalusek/PreFer",
    ...(channel ? { channel } : {}),
    ...(one(flags, "revision") ? { revision: one(flags, "revision")! } : {}),
    outputDir,
    cacheDir: one(flags, "cache"),
    token: token(flags, "github-token-env", "GITHUB_TOKEN")
  });
  process.stdout.write(`${JSON.stringify({ release: result.release, files: result.files })}\n`);
}

function parseFlags(args: string[]): Map<string, string[]> {
  const result = new Map<string, string[]>();
  for (let index = 0; index < args.length; index += 1) {
    const raw = args[index]!;
    if (!raw.startsWith("--")) throw new Error(`unexpected argument ${raw}`);
    const equals = raw.indexOf("=");
    const key = raw.slice(2, equals > 0 ? equals : undefined);
    const value = equals > 0 ? raw.slice(equals + 1) : args[index + 1]?.startsWith("--") === false ? args[++index]! : "true";
    result.set(key, [...(result.get(key) ?? []), value]);
  }
  return result;
}

function one(flags: Map<string, string[]>, key: string, required = false): string | undefined {
  const values = flags.get(key) ?? [];
  if (values.length > 1) throw new Error(`--${key} may only be supplied once`);
  if (required && !values[0]) throw new Error(`--${key} is required`);
  return values[0];
}

function many(flags: Map<string, string[]>, key: string): string[] { return flags.get(key) ?? []; }

function namedScores(flags: Map<string, string[]>, key: string): Map<string, number> {
  const result = new Map<string, number>();
  for (const value of many(flags, key)) {
    const separator = value.lastIndexOf("=");
    if (separator < 1) throw new Error(`--${key} must use model-id=0..100`);
    const modelId = value.slice(0, separator);
    const score = Number(value.slice(separator + 1));
    if (!Number.isFinite(score) || score < 0 || score > 100) throw new Error(`--${key} must use a score from 0 to 100`);
    if (result.has(modelId)) throw new Error(`--${key} may only score ${modelId} once`);
    result.set(modelId, score);
  }
  return result;
}

function choice<const T extends readonly string[]>(flags: Map<string, string[]>, key: string, allowed: T): T[number] | undefined {
  const value = one(flags, key);
  if (value === undefined) return undefined;
  if (!allowed.includes(value)) throw new Error(`--${key} must be one of ${allowed.join(", ")}`);
  return value;
}

function integer(flags: Map<string, string[]>, key: string, fallback: number): number {
  const value = one(flags, key);
  if (value === undefined) return fallback;
  const result = Number(value);
  if (!Number.isInteger(result)) throw new Error(`--${key} must be an integer`);
  return result;
}

function integerOptional(flags: Map<string, string[]>, key: string): number | undefined {
  const value = one(flags, key);
  if (value === undefined) return undefined;
  const result = Number(value);
  if (!Number.isSafeInteger(result) || result < 0) throw new Error(`--${key} must be a non-negative safe integer`);
  return result;
}

function positiveIntegerOptional(flags: Map<string, string[]>, key: string): number | undefined {
  const result = integerOptional(flags, key);
  if (result === 0) throw new Error(`--${key} must be greater than zero`);
  return result;
}

function numberValue(flags: Map<string, string[]>, key: string): number | undefined {
  const value = one(flags, key);
  if (value === undefined) return undefined;
  const result = Number(value);
  if (!Number.isFinite(result)) throw new Error(`--${key} must be a number`);
  return result;
}

function bool(flags: Map<string, string[]>, key: string): boolean {
  const value = one(flags, key);
  return value === "true" || value === "1";
}

function environmentBoolean(name: string): boolean {
  const value = process.env[name]?.trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

function token(flags: Map<string, string[]>, key: string, fallbackName: string): string | undefined {
  const name = one(flags, key) ?? fallbackName;
  return process.env[name]?.trim() || undefined;
}

function jsonObject(value: string, label: string): JsonObject {
  let parsed: unknown;
  try { parsed = JSON.parse(value) as unknown; }
  catch { throw new Error(`${label} must be valid JSON`); }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(`${label} must be a JSON object`);
  return parsed as JsonObject;
}

async function outputJson(flags: Map<string, string[]>, value: unknown): Promise<void> {
  const output = one(flags, "output");
  if (output) await writeJsonAtomic(output, value);
  else process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

async function deploymentInput(path: string, deploymentId: string | undefined): Promise<unknown> {
  const value = await readJson(path);
  if (!deploymentId) return value;
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${path} is not a deployment inventory`);
  const deployments = (value as { deployments?: unknown }).deployments;
  if (!Array.isArray(deployments)) throw new Error(`${path} does not contain deployments`);
  const deployment = deployments.find((entry) => entry && typeof entry === "object" && !Array.isArray(entry) && (entry as { id?: unknown }).id === deploymentId);
  if (!deployment) throw new Error(`${path} does not contain deployment ${deploymentId}`);
  return deployment;
}

function commaList(value: string): string[] { return value.split(",").map((entry) => entry.trim()).filter(Boolean); }

function help(): void {
  process.stdout.write(`PreFer catalog and release CLI\n\n` +
    `  prefer catalog refresh --source catalog --output catalog.json [--fallback previous.json]\n` +
    `  prefer catalog validate --catalog catalog.json [--source catalog]\n` +
    `  prefer catalog extend --repo owner/model[@revision] --output extension.json\n` +
    `  prefer model list [--catalog catalog.json] [--engine sglang] [--model qwen-3.8-27b]\n` +
    `  prefer model resolve qwen-3.8-27b [--engine llama.cpp] [--quant ud-q6-k-xl] [--use-nvfp4] [--model-root /models]\n` +
    `  prefer model plan --resources inventory.json --deployment aws/g6/xlarge/general [--preferred-role coding] [--speed-importance 0.8] [--quant-bias balanced]\n` +
    `    [--speed-score qwen-3.8-27b=85 --quality-score qwen-3.8-27b=92 --quality-importance 1]\n` +
    `    [--context-tokens 131072 --concurrency 4 --bytes-per-token 65536 --minimum-concurrency 1]\n` +
    `    [--headroom-gib 2 | --headroom-percent 5] [--allow-host-offload] [--accept-tight]\n` +
    `  prefer hardware normalize --input inventory.json [--deployment aws/g6/xlarge/general]\n` +
    `  prefer hardware detect [--base inventory.json --deployment local/gb10/1x/balanced]\n` +
    `  prefer release list [--channel stable|preview]\n` +
    `  prefer release fetch-tooling --output-dir path [--channel stable|preview] [--revision SHA]\n`);
}
