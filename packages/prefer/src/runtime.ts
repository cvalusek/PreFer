import { posix } from "node:path";
import type {
  CatalogExtension,
  EngineId,
  JsonObject,
  MaterializedRuntimeHandoff,
  ModelCatalogSnapshot,
  ResolvedModelArtifact,
  ResolvedModelVariant,
  RuntimeHandoff,
  RuntimeHandoffArtifact,
  RuntimeHandoffArtifactInput,
  RuntimeHandoffModel,
  RuntimeModelCatalog
} from "./types.js";
import {
  deepMerge,
  isObject,
  readJson,
  repositoryKey,
  requireObject,
  requireString,
  sha256,
  stableStringify,
  validateRepository,
  validateRevision
} from "./utils.js";
import { validateModelCatalog } from "./catalog.js";
import { validateCatalogExtension } from "./huggingface.js";

const MODEL_ID_PATTERN = /^[a-z0-9]+(?:[.-][a-z0-9]+)*$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const SHA1_PATTERN = /^[0-9a-f]{40}$/u;
const CONTROL_PATTERN = /[\u0000-\u001f\u007f]/u;

export interface ResolveExtensionVariantOptions {
  engine: EngineId;
  files: string[];
  quant: string;
  displayName?: string;
  family?: string;
  capabilities?: string[];
  settings?: JsonObject;
  modelRoot?: string;
  sha256?: Record<string, string>;
}

export interface RuntimeHandoffModelInput {
  variant: ResolvedModelVariant;
  request_model_id?: string;
  source?: "prefer" | "extension";
}

export interface CreateRuntimeHandoffOptions {
  engine: EngineId;
  models: RuntimeHandoffModelInput[];
  baseDeployment?: string;
  serverSettings?: JsonObject;
  additionalArtifacts?: RuntimeHandoffArtifactInput[];
}

export interface MaterializeRuntimeHandoffOptions {
  engine: EngineId;
  modelRoot?: string;
}

/** Resolve a controller-owned model id from immutable Hugging Face extension metadata. */
export function resolveExtensionModelVariant(
  extension: CatalogExtension,
  modelId: string,
  options: ResolveExtensionVariantOptions
): ResolvedModelVariant {
  validateCatalogExtension(extension);
  validateModelId(modelId, "extension model id");
  const binding = extension.models[modelId];
  if (!binding) throw new Error(`unknown extension model ${modelId}`);
  const metadata = extension.repositories[repositoryKey(binding.repository, binding.resolved_revision)];
  if (!metadata) throw new Error(`extension model ${modelId} has no immutable repository metadata`);
  if (!Array.isArray(options.files) || !options.files.length) throw new Error("extension variant requires at least one exact file");
  if (new Set(options.files).size !== options.files.length) throw new Error("extension variant files must be unique");
  const byPath = new Map(metadata.files.map((file) => [file.path, file]));
  const modelRoot = normalizeModelRoot(options.modelRoot ?? "/models");
  const artifacts: ResolvedModelArtifact[] = options.files.map((path) => {
    const metadataFile = byPath.get(path);
    if (!metadataFile) throw new Error(`${binding.repository}@${binding.resolved_revision} does not contain ${path}`);
    const suppliedSha = options.sha256?.[path];
    if (suppliedSha !== undefined) validateSha256(suppliedSha, `${path} SHA-256`);
    return {
      ...metadataFile,
      repository: binding.repository,
      revision: binding.resolved_revision,
      local_path: storagePath(modelRoot, binding.repository, path),
      ...(suppliedSha ? { sha256: suppliedSha } : {})
    };
  });
  const inferred = inferExtensionSettings(options.engine, options.quant, artifacts);
  return {
    model_id: modelId,
    family: options.family?.trim() || "extension",
    display_name: options.displayName?.trim() || modelId,
    engine: options.engine,
    repository: binding.repository,
    repository_path: storagePath(modelRoot, binding.repository),
    revision: binding.resolved_revision,
    quant: requireSafeText(options.quant, "extension quant"),
    files: [...options.files],
    artifacts,
    artifact_bytes: artifacts.reduce((sum, artifact) => sum + artifact.size, 0),
    capabilities: uniqueStrings(options.capabilities ?? [], "extension capabilities"),
    settings: deepMerge(inferred, options.settings)
  };
}

/** Build a deterministic, release-bound handoff from already resolved variants. */
export function createRuntimeHandoff(
  catalog: ModelCatalogSnapshot | RuntimeModelCatalog,
  options: CreateRuntimeHandoffOptions
): RuntimeHandoff {
  const catalogFingerprint = catalogFingerprintFor(catalog);
  const engine = requireSafeText(options.engine, "runtime handoff engine") as EngineId;
  if (!Array.isArray(options.models) || !options.models.length) throw new Error("runtime handoff requires at least one model");
  const additional = options.additionalArtifacts ?? [];
  const modelIds = new Set<string>();
  const artifactsById = new Map<string, RuntimeHandoffArtifact>();
  const destinationIdentities = new Map<string, string>();
  const models: RuntimeHandoffModel[] = [];

  for (const input of options.models) {
    const variant = validateResolvedVariant(input.variant, engine);
    validateModelId(variant.model_id, "runtime handoff model id");
    if (modelIds.has(variant.model_id)) throw new Error(`duplicate runtime handoff model ${variant.model_id}`);
    modelIds.add(variant.model_id);
    const artifactIds = variant.artifacts.map((artifact) => addArtifact(
      artifactsById,
      destinationIdentities,
      runtimeArtifactInput(artifact, variant.model_id),
      variant.model_id
    ));
    const requestModelId = requireSafeText(input.request_model_id ?? variant.model_id, `${variant.model_id} request model id`);
    models.push({
      model_id: variant.model_id,
      request_model_id: requestModelId,
      source: input.source ?? "prefer",
      family: requireSafeText(variant.family, `${variant.model_id} family`),
      display_name: requireSafeText(variant.display_name, `${variant.model_id} display name`),
      repository: validateRepository(variant.repository),
      revision: validateRevision(variant.revision, { immutable: true }).toLowerCase(),
      quant: requireSafeText(variant.quant, `${variant.model_id} quant`),
      artifact_ids: artifactIds,
      capabilities: uniqueStrings(variant.capabilities, `${variant.model_id} capabilities`),
      settings: jsonObjectClone(variant.settings, `${variant.model_id} settings`)
    });
  }

  for (const artifact of additional) {
    if (artifact.model_id !== undefined && !modelIds.has(artifact.model_id)) {
      throw new Error(`additional artifact targets unselected model ${artifact.model_id}`);
    }
    const artifactId = addArtifact(artifactsById, destinationIdentities, artifact, artifact.model_id);
    if (artifact.model_id) {
      const model = models.find((candidate) => candidate.model_id === artifact.model_id)!;
      if (!model.artifact_ids.includes(artifactId)) model.artifact_ids.push(artifactId);
    }
  }

  const base = {
    schema_version: "prefer.runtime-handoff.v1" as const,
    catalog_fingerprint: catalogFingerprint,
    engine,
    ...(options.baseDeployment ? { base_deployment: requireSafeText(options.baseDeployment, "base deployment") } : {}),
    server_settings: jsonObjectClone(options.serverSettings ?? {}, "runtime handoff server settings"),
    models,
    artifacts: [...artifactsById.values()]
  };
  return { ...base, handoff_fingerprint: sha256(stableStringify(base)) };
}

export function validateRuntimeHandoff(value: unknown): asserts value is RuntimeHandoff {
  const handoff = requireObject(value, "runtime handoff");
  if (handoff.schema_version !== "prefer.runtime-handoff.v1") throw new Error("runtime handoff schema is incompatible");
  const catalogFingerprint = requireString(handoff.catalog_fingerprint, "runtime handoff catalog fingerprint").toLowerCase();
  validateSha256(catalogFingerprint, "runtime handoff catalog fingerprint");
  const fingerprint = requireString(handoff.handoff_fingerprint, "runtime handoff fingerprint").toLowerCase();
  validateSha256(fingerprint, "runtime handoff fingerprint");
  requireSafeText(handoff.engine, "runtime handoff engine");
  if (handoff.base_deployment !== undefined) requireSafeText(handoff.base_deployment, "runtime handoff base deployment");
  jsonObjectClone(handoff.server_settings, "runtime handoff server settings");
  if (!Array.isArray(handoff.models) || !handoff.models.length) throw new Error("runtime handoff requires at least one model");
  if (!Array.isArray(handoff.artifacts) || !handoff.artifacts.length) throw new Error("runtime handoff requires at least one artifact");

  const artifactIds = new Set<string>();
  const destinations = new Map<string, string>();
  for (const raw of handoff.artifacts) {
    const artifact = validateRuntimeArtifact(raw);
    if (artifactIds.has(artifact.id)) throw new Error(`duplicate runtime handoff artifact id ${artifact.id}`);
    artifactIds.add(artifact.id);
    const identity = stableStringify(artifactIdentity(artifact));
    const destination = `${artifact.repository}/${artifact.path}`;
    const previous = destinations.get(destination);
    if (previous !== undefined && previous !== identity) throw new Error(`conflicting runtime artifact destination ${destination}`);
    destinations.set(destination, identity);
  }

  const modelIds = new Set<string>();
  for (const raw of handoff.models) {
    const model = requireObject(raw, "runtime handoff model");
    const modelId = requireString(model.model_id, "runtime handoff model id");
    validateModelId(modelId, "runtime handoff model id");
    if (modelIds.has(modelId)) throw new Error(`duplicate runtime handoff model ${modelId}`);
    modelIds.add(modelId);
    requireSafeText(model.request_model_id, `${modelId} request model id`);
    if (model.source !== "prefer" && model.source !== "extension") throw new Error(`${modelId} source must be prefer or extension`);
    requireSafeText(model.family, `${modelId} family`);
    requireSafeText(model.display_name, `${modelId} display name`);
    validateRepository(requireString(model.repository, `${modelId} repository`));
    validateRevision(requireString(model.revision, `${modelId} revision`), { immutable: true });
    requireSafeText(model.quant, `${modelId} quant`);
    if (!Array.isArray(model.artifact_ids) || !model.artifact_ids.length) throw new Error(`${modelId} requires artifact ids`);
    if (new Set(model.artifact_ids).size !== model.artifact_ids.length) throw new Error(`${modelId} artifact ids must be unique`);
    for (const artifactId of model.artifact_ids) {
      if (typeof artifactId !== "string" || !artifactIds.has(artifactId)) throw new Error(`${modelId} references unknown artifact ${String(artifactId)}`);
    }
    uniqueStrings(model.capabilities, `${modelId} capabilities`);
    jsonObjectClone(model.settings, `${modelId} settings`);
  }
  for (const raw of handoff.artifacts) {
    const artifact = raw as RuntimeHandoffArtifact;
    if (artifact.model_id !== undefined && !modelIds.has(artifact.model_id)) {
      throw new Error(`runtime artifact ${artifact.id} targets unselected model ${artifact.model_id}`);
    }
  }

  const { handoff_fingerprint: _fingerprint, ...payload } = handoff;
  if (sha256(stableStringify(payload)) !== fingerprint) throw new Error("runtime handoff fingerprint does not match its content");
}

export function materializeRuntimeHandoff(
  handoff: RuntimeHandoff,
  catalog: ModelCatalogSnapshot | RuntimeModelCatalog,
  options: MaterializeRuntimeHandoffOptions
): MaterializedRuntimeHandoff {
  validateRuntimeHandoff(handoff);
  const expectedEngine = requireSafeText(options.engine, "expected runtime engine");
  if (handoff.engine !== expectedEngine) throw new Error(`runtime handoff engine ${handoff.engine} does not match image engine ${expectedEngine}`);
  const catalogFingerprint = catalogFingerprintFor(catalog);
  if (handoff.catalog_fingerprint !== catalogFingerprint) {
    throw new Error(`runtime handoff catalog ${handoff.catalog_fingerprint} does not match image catalog ${catalogFingerprint}`);
  }
  const modelRoot = normalizeModelRoot(options.modelRoot ?? "/models");
  return {
    ...structuredClone(handoff),
    model_root: modelRoot,
    models: handoff.models.map((model) => ({
      ...structuredClone(model),
      repository_path: storagePath(modelRoot, model.repository)
    })),
    artifacts: handoff.artifacts.map((artifact) => ({
      ...structuredClone(artifact),
      local_path: storagePath(modelRoot, artifact.repository, artifact.path)
    }))
  };
}

export async function readRuntimeHandoff(path: string): Promise<RuntimeHandoff> {
  const value = await readJson(path);
  validateRuntimeHandoff(value);
  return value;
}

export function runtimeHandoffArtifactManifest(handoff: MaterializedRuntimeHandoff): string {
  return handoff.artifacts.map((artifact) => {
    const verification = artifactVerification(artifact);
    return [
      artifact.id,
      artifact.repository,
      artifact.revision,
      artifact.path,
      String(artifact.size),
      verification.algorithm,
      verification.digest
    ].join("\t");
  }).join("\n") + "\n";
}

function catalogFingerprintFor(catalog: ModelCatalogSnapshot | RuntimeModelCatalog): string {
  if (catalog.schema_version === "prefer.model-catalog.v1") {
    validateModelCatalog(catalog);
    return catalog.catalog_fingerprint;
  }
  if (catalog.schema_version !== "prefer.runtime-model-catalog.v1") throw new Error("runtime catalog schema is incompatible");
  validateSha256(catalog.base_catalog_fingerprint, "runtime catalog base fingerprint");
  return catalog.base_catalog_fingerprint;
}

function validateResolvedVariant(variant: ResolvedModelVariant, engine: EngineId): ResolvedModelVariant {
  if (!isObject(variant)) throw new Error("runtime handoff variant must be an object");
  if (variant.engine !== engine) throw new Error(`${variant.model_id ?? "model"} resolves for ${variant.engine}, not ${engine}`);
  validateRepository(requireString(variant.repository, "resolved variant repository"));
  validateRevision(requireString(variant.revision, "resolved variant revision"), { immutable: true });
  if (!Array.isArray(variant.artifacts) || !variant.artifacts.length) throw new Error(`${variant.model_id} has no resolved artifacts`);
  jsonObjectClone(variant.settings, `${variant.model_id} settings`);
  return variant;
}

function runtimeArtifactInput(artifact: ResolvedModelArtifact, modelId: string): RuntimeHandoffArtifactInput {
  const exactSha = artifact.sha256 ?? artifact.lfs_sha256;
  const blobSha = artifact.blob_oid;
  if (!exactSha && !(blobSha && SHA1_PATTERN.test(blobSha))) {
    throw new Error(`${artifact.repository}/${artifact.path} has no exact file or Git blob digest`);
  }
  return {
    repository: artifact.repository,
    revision: artifact.revision,
    path: artifact.path,
    size: artifact.size,
    ...(exactSha ? { sha256: exactSha } : { git_blob_sha1: blobSha!.toLowerCase() }),
    model_id: modelId,
    ...(artifact.role ? { role: artifact.role } : {}),
    ...(artifact.settings ? { settings: artifact.settings } : {})
  };
}

function addArtifact(
  byId: Map<string, RuntimeHandoffArtifact>,
  destinations: Map<string, string>,
  input: RuntimeHandoffArtifactInput,
  defaultModelId?: string
): string {
  const repository = validateRepository(input.repository);
  const revision = validateRevision(input.revision, { immutable: true }).toLowerCase();
  const path = validateArtifactPath(input.path);
  if (!Number.isSafeInteger(input.size) || input.size <= 0) throw new Error(`${repository}/${path} size must be a positive safe integer`);
  const verification = artifactVerification(input, `${repository}/${path}`);
  const modelId = input.model_id ?? defaultModelId;
  if (modelId !== undefined) validateModelId(modelId, `${repository}/${path} model id`);
  const identity = { repository, revision, path, size: input.size, ...verification.field };
  const id = sha256(stableStringify(identity));
  const destination = `${repository}/${path}`;
  const identityString = stableStringify(identity);
  const previousDestination = destinations.get(destination);
  if (previousDestination !== undefined && previousDestination !== identityString) {
    throw new Error(`conflicting runtime artifact destination ${destination}`);
  }
  destinations.set(destination, identityString);
  const artifact: RuntimeHandoffArtifact = {
    id,
    ...identity,
    ...(modelId ? { model_id: modelId } : {}),
    ...(input.role ? { role: requireSafeText(input.role, `${destination} role`) } : {}),
    ...(input.settings ? { settings: jsonObjectClone(input.settings, `${destination} settings`) } : {})
  };
  const previous = byId.get(id);
  if (previous && stableStringify(previous) !== stableStringify(artifact)) {
    throw new Error(`runtime artifact ${id} has conflicting metadata`);
  }
  if (!previous) byId.set(id, artifact);
  return id;
}

function validateRuntimeArtifact(value: unknown): RuntimeHandoffArtifact {
  const artifact = requireObject(value, "runtime handoff artifact");
  const repository = validateRepository(requireString(artifact.repository, "runtime artifact repository"));
  const revision = validateRevision(requireString(artifact.revision, `${repository} revision`), { immutable: true }).toLowerCase();
  const path = validateArtifactPath(requireString(artifact.path, `${repository} artifact path`));
  const size = artifact.size;
  if (!Number.isSafeInteger(size) || (size as number) <= 0) throw new Error(`${repository}/${path} size must be a positive safe integer`);
  const verification = artifactVerification(artifact, `${repository}/${path}`);
  const identity = { repository, revision, path, size: size as number, ...verification.field };
  const expectedId = sha256(stableStringify(identity));
  if (artifact.id !== expectedId) throw new Error(`${repository}/${path} artifact id does not match its immutable identity`);
  if (artifact.model_id !== undefined) validateModelId(artifact.model_id, `${repository}/${path} model id`);
  if (artifact.role !== undefined) requireSafeText(artifact.role, `${repository}/${path} role`);
  if (artifact.settings !== undefined) jsonObjectClone(artifact.settings, `${repository}/${path} settings`);
  return value as RuntimeHandoffArtifact;
}

function artifactIdentity(artifact: RuntimeHandoffArtifact): object {
  const verification = artifactVerification(artifact);
  return {
    repository: artifact.repository,
    revision: artifact.revision,
    path: artifact.path,
    size: artifact.size,
    ...verification.field
  };
}

function artifactVerification(
  artifact: Pick<RuntimeHandoffArtifactInput, "sha256" | "git_blob_sha1">,
  label = "runtime artifact"
): { algorithm: "sha256" | "git-blob-sha1"; digest: string; field: { sha256: string } | { git_blob_sha1: string } } {
  const hasSha256 = artifact.sha256 !== undefined;
  const hasBlobSha1 = artifact.git_blob_sha1 !== undefined;
  if (hasSha256 === hasBlobSha1) throw new Error(`${label} must contain exactly one verification digest`);
  if (hasSha256) {
    const digest = validateSha256(artifact.sha256!, `${label} SHA-256`);
    return { algorithm: "sha256", digest, field: { sha256: digest } };
  }
  const digest = validateSha1(artifact.git_blob_sha1!, `${label} Git blob SHA-1`);
  return { algorithm: "git-blob-sha1", digest, field: { git_blob_sha1: digest } };
}

function validateArtifactPath(value: string): string {
  const path = value.trim();
  if (!path || path.includes("\\") || path.startsWith("/") || CONTROL_PATTERN.test(path)) throw new Error(`invalid artifact path: ${value}`);
  const normalized = posix.normalize(path);
  if (normalized !== path || normalized === "." || normalized.startsWith("../") || normalized.includes("/../")) {
    throw new Error(`invalid artifact path: ${value}`);
  }
  return path;
}

function normalizeModelRoot(value: string): string {
  const root = value.trim().replaceAll("\\", "/").replace(/\/+$/u, "");
  if (!root.startsWith("/") || root === "/" || root.includes("/../") || root.endsWith("/..") || CONTROL_PATTERN.test(root)) {
    throw new Error(`model root must be a safe absolute path: ${value}`);
  }
  return root;
}

function storagePath(root: string, repository: string, artifactPath?: string): string {
  const base = `${root}/${validateRepository(repository)}`;
  return artifactPath ? `${base}/${validateArtifactPath(artifactPath)}` : base;
}

function validateModelId(value: unknown, label: string): asserts value is string {
  if (typeof value !== "string" || !MODEL_ID_PATTERN.test(value)) throw new Error(`${label} is invalid`);
}

function requireSafeText(value: unknown, label: string): string {
  const text = requireString(value, label);
  if (CONTROL_PATTERN.test(text)) throw new Error(`${label} contains control characters`);
  return text;
}

function validateSha256(value: string, label: string): string {
  const normalized = value.trim().toLowerCase();
  if (!SHA256_PATTERN.test(normalized)) throw new Error(`${label} is invalid`);
  return normalized;
}

function validateSha1(value: string, label: string): string {
  const normalized = value.trim().toLowerCase();
  if (!SHA1_PATTERN.test(normalized)) throw new Error(`${label} is invalid`);
  return normalized;
}

function uniqueStrings(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || value.some((entry) => typeof entry !== "string" || !entry.trim() || CONTROL_PATTERN.test(entry))) {
    throw new Error(`${label} must contain strings`);
  }
  return [...new Set(value.map((entry) => entry.trim()))];
}

function jsonObjectClone(value: unknown, label: string): JsonObject {
  if (!isObject(value)) throw new Error(`${label} must be an object`);
  assertJsonValue(value, label);
  return structuredClone(value) as JsonObject;
}

function assertJsonValue(value: unknown, label: string): void {
  if (value === null || typeof value === "boolean" || typeof value === "string") return;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error(`${label} contains a non-finite number`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => assertJsonValue(entry, `${label}[${index}]`));
    return;
  }
  if (isObject(value)) {
    for (const [key, entry] of Object.entries(value)) {
      if (!key || CONTROL_PATTERN.test(key)) throw new Error(`${label} contains an invalid key`);
      assertJsonValue(entry, `${label}.${key}`);
    }
    return;
  }
  throw new Error(`${label} contains a non-JSON value`);
}

function inferExtensionSettings(engine: EngineId, quant: string, artifacts: ResolvedModelArtifact[]): JsonObject {
  const launcher: JsonObject = {};
  if ((engine === "sglang" || engine === "vllm") && artifacts.some((artifact) => artifact.path.toLowerCase().endsWith(".gguf"))) {
    launcher.load_format = "gguf";
  }
  if ((engine === "sglang" || engine === "vllm") && quant.toLowerCase().includes("nvfp4")) {
    launcher.quantization = "modelopt_fp4";
  }
  return Object.keys(launcher).length ? { launcher } : {};
}
