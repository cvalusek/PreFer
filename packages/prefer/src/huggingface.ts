import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import type {
  CatalogExtension,
  HuggingFaceFile,
  HuggingFaceRepository,
  HuggingFaceSelection,
  ModelCatalogSnapshot,
  RuntimeCatalogModel,
  RuntimeModelCatalog
} from "./types.js";
import { globMatch, isObject, repositoryKey, requireString, sha256, stableStringify, validateRepository, validateRevision } from "./utils.js";

const DEFAULT_API = "https://huggingface.co";
const MAX_RESPONSE_BYTES = 50 * 1024 * 1024;

export interface HuggingFaceResolveOptions {
  token?: string | undefined;
  fetch?: typeof fetch | undefined;
  apiBaseUrl?: string | undefined;
  cacheDir?: string | undefined;
  preferCache?: boolean | undefined;
  concurrency?: number | undefined;
  timeoutMs?: number | undefined;
  now?: (() => Date) | undefined;
}

export async function resolveHuggingFaceRepository(selection: HuggingFaceSelection, options: HuggingFaceResolveOptions = {}): Promise<HuggingFaceRepository> {
  const repository = validateRepository(selection.repository);
  const requestedRevision = validateRevision(selection.revision ?? "main");
  const include = selection.include?.length ? [...new Set(selection.include)].sort() : undefined;
  const cacheIdentity = { repository, requestedRevision, include: include ?? null };
  const cachePath = options.cacheDir ? resolve(options.cacheDir, `${sha256(stableStringify(cacheIdentity))}.json`) : undefined;
  if (cachePath && options.preferCache) {
    try {
      const cached = JSON.parse(await readFile(cachePath, "utf8")) as HuggingFaceRepository;
      if (cached.repository === repository && cached.requested_revision === requestedRevision) return cached;
    } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    }
  }

  const fetchImpl = options.fetch ?? fetch;
  const base = (options.apiBaseUrl ?? DEFAULT_API).replace(/\/+$/u, "");
  const encodedRepository = repository.split("/").map(encodeURIComponent).join("/");
  const encodedRevision = requestedRevision.split("/").map(encodeURIComponent).join("/");
  const headers: Record<string, string> = { accept: "application/json", "user-agent": "prefer-inference-core" };
  if (options.token?.trim()) headers.authorization = `Bearer ${options.token.trim()}`;
  const model = await fetchJson(`${base}/api/models/${encodedRepository}/revision/${encodedRevision}`, fetchImpl, headers, options.timeoutMs);
  const modelObject = objectValue(model, `Hugging Face model ${repository}`);
  const resolvedRevision = requireString(modelObject.sha, `${repository} resolved revision`).toLowerCase();
  if (!/^[0-9a-f]{40}$/u.test(resolvedRevision)) throw new Error(`${repository} did not resolve to an immutable commit`);
  if (/^[0-9a-f]{40}$/u.test(requestedRevision) && resolvedRevision !== requestedRevision.toLowerCase()) {
    throw new Error(`${repository} resolved revision does not match the requested immutable commit`);
  }
  const treeEntries: unknown[] = [];
  let next: string | undefined = `${base}/api/models/${encodedRepository}/tree/${encodeURIComponent(resolvedRevision)}?recursive=true&expand=true`;
  while (next) {
    const response = await fetchResponse(next, fetchImpl, headers, options.timeoutMs);
    const payload = await responseJson(response, `Hugging Face tree ${repository}`);
    if (!Array.isArray(payload)) throw new Error(`${repository} tree response is not an array`);
    treeEntries.push(...payload);
    next = nextLink(response.headers.get("link"));
  }
  const files = treeEntries.flatMap((entry): HuggingFaceFile[] => {
    if (!isObject(entry) || entry.type !== "file") return [];
    const path = typeof entry.path === "string" ? entry.path : "";
    const size = typeof entry.size === "number" ? entry.size : -1;
    if (!path || !Number.isSafeInteger(size) || size < 0 || (include && !include.some((pattern) => globMatch(path, pattern)))) return [];
    const lfs = isObject(entry.lfs) ? entry.lfs : undefined;
    const lfsOid = typeof lfs?.oid === "string" && /^[0-9a-f]{64}$/iu.test(lfs.oid) ? lfs.oid.toLowerCase() : undefined;
    return [{
      path,
      size,
      ...(typeof entry.oid === "string" ? { blob_oid: entry.oid } : {}),
      ...(lfsOid ? { lfs_sha256: lfsOid } : {}),
      ...(typeof entry.xetHash === "string" ? { xet_hash: entry.xetHash } : {})
    }];
  }).sort((left, right) => left.path.localeCompare(right.path));
  const tags = Array.isArray(modelObject.tags) ? modelObject.tags.filter((tag): tag is string => typeof tag === "string") : [];
  const cardData = isObject(modelObject.cardData) ? modelObject.cardData : {};
  const result: HuggingFaceRepository = {
    repository,
    requested_revision: requestedRevision,
    resolved_revision: resolvedRevision,
    base_models: baseModels(cardData.base_model, tags),
    ...(typeof modelObject.pipeline_tag === "string" ? { pipeline_tag: modelObject.pipeline_tag } : {}),
    ...(typeof modelObject.library_name === "string" ? { library_name: modelObject.library_name } : {}),
    ...(typeof cardData.license === "string" ? { license: cardData.license } : {}),
    gated: typeof modelObject.gated === "string" || typeof modelObject.gated === "boolean" ? modelObject.gated : false,
    private: modelObject.private === true,
    tags: [...new Set(tags)].sort(),
    files_complete: include === undefined,
    ...(include ? { include_patterns: include } : {}),
    files,
    retrieved_at: (options.now?.() ?? new Date()).toISOString()
  };
  if (cachePath) {
    await mkdir(dirname(cachePath), { recursive: true });
    await writeFile(cachePath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
  }
  return result;
}

export async function resolveHuggingFaceSelections(selections: HuggingFaceSelection[], options: HuggingFaceResolveOptions = {}): Promise<HuggingFaceRepository[]> {
  const concurrency = options.concurrency ?? 4;
  if (!Number.isInteger(concurrency) || concurrency < 1 || concurrency > 8) throw new Error("Hugging Face concurrency must be between 1 and 8");
  const deduplicated = new Map<string, HuggingFaceSelection>();
  for (const selection of selections) {
    const repository = validateRepository(selection.repository);
    const revision = validateRevision(selection.revision ?? "main");
    const key = repositoryKey(repository, revision);
    const previous = deduplicated.get(key);
    const include = !previous
      ? selection.include?.length ? [...new Set(selection.include)].sort() : undefined
      : previous.include && selection.include
        ? [...new Set([...previous.include, ...selection.include])].sort()
        : undefined;
    deduplicated.set(key, {
      repository,
      revision,
      ...(include ? { include } : {})
    });
  }
  const normalized = [...deduplicated.values()];
  const result = new Array<HuggingFaceRepository>(normalized.length);
  let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(concurrency, normalized.length) }, async () => {
    while (cursor < normalized.length) {
      const index = cursor++;
      result[index] = await resolveHuggingFaceRepository(normalized[index]!, options);
    }
  }));
  return result;
}

export async function createCatalogExtension(selections: HuggingFaceSelection[], options: HuggingFaceResolveOptions = {}): Promise<CatalogExtension> {
  const normalizedSelections = selections.map((selection) => ({
    ...selection,
    repository: validateRepository(selection.repository),
    revision: validateRevision(selection.revision ?? "main")
  }));
  const repositories = await resolveHuggingFaceSelections(normalizedSelections, options);
  const byRequestedKey = Object.fromEntries(repositories.map((entry) => [repositoryKey(entry.repository, entry.requested_revision), entry]));
  const models: CatalogExtension["models"] = {};
  for (const selection of normalizedSelections) {
    if (!selection.model_id) continue;
    if (!/^[a-z0-9]+(?:[.-][a-z0-9]+)*$/u.test(selection.model_id)) throw new Error(`invalid extension model id ${selection.model_id}`);
    if (models[selection.model_id]) throw new Error(`duplicate extension model id ${selection.model_id}`);
    const requestedRevision = selection.revision ?? "main";
    const resolved = byRequestedKey[repositoryKey(selection.repository, requestedRevision)];
    if (!resolved) throw new Error(`could not bind extension model ${selection.model_id}`);
    models[selection.model_id] = { repository: resolved.repository, resolved_revision: resolved.resolved_revision };
  }
  return {
    schema_version: "prefer.model-catalog-extension.v1",
    generated_at: (options.now?.() ?? new Date()).toISOString(),
    repositories: Object.fromEntries(repositories.map((entry) => [repositoryKey(entry.repository, entry.resolved_revision), entry])),
    models
  };
}

export function mergeCatalogExtensions(base: CatalogExtension, overlay: CatalogExtension, conflict: "error" | "keep" | "replace" = "error"): CatalogExtension {
  validateCatalogExtension(base);
  validateCatalogExtension(overlay);
  const repositories = { ...base.repositories };
  for (const [key, value] of Object.entries(overlay.repositories)) {
    const existing = repositories[key];
    if (existing && JSON.stringify(existing) !== JSON.stringify(value) && conflict === "error") throw new Error(`extension repository conflict for ${key}`);
    if (!existing || conflict === "replace") repositories[key] = value;
  }
  const models = { ...base.models };
  for (const [key, value] of Object.entries(overlay.models)) {
    const existing = models[key];
    if (existing && (existing.repository !== value.repository || existing.resolved_revision !== value.resolved_revision)) {
      if (conflict === "error") throw new Error(`extension model id conflict for ${key}`);
      if (conflict === "keep") continue;
    }
    models[key] = value;
  }
  return { ...base, generated_at: overlay.generated_at, repositories, models };
}

export function createRuntimeModelCatalog(
  base: ModelCatalogSnapshot,
  extensions: CatalogExtension[] = [],
  conflict: "error" | "keep" | "replace" = "error"
): RuntimeModelCatalog {
  const repositories: Record<string, HuggingFaceRepository> = {};
  for (const repository of Object.values(base.repositories)) {
    repositories[repositoryKey(repository.repository, repository.resolved_revision)] = repository;
  }
  const models: Record<string, RuntimeCatalogModel> = Object.fromEntries(
    Object.entries(base.models).map(([id, definition]) => [id, { source: "prefer" as const, definition }])
  );
  let generatedAt = base.generated_at;
  for (const extension of extensions) {
    validateCatalogExtension(extension);
    generatedAt = extension.generated_at > generatedAt ? extension.generated_at : generatedAt;
    for (const [key, repository] of Object.entries(extension.repositories)) {
      const existing = repositories[key];
      if (existing && JSON.stringify(existing) !== JSON.stringify(repository)) {
        if (conflict === "error") throw new Error(`runtime catalog repository conflict for ${key}`);
        if (conflict === "keep") continue;
      }
      repositories[key] = repository;
    }
    for (const [id, binding] of Object.entries(extension.models)) {
      const existing = models[id];
      if (existing) {
        if (conflict === "error") throw new Error(`runtime catalog model id conflict for ${id}`);
        if (conflict === "keep") continue;
      }
      models[id] = { source: "extension", ...binding };
    }
  }
  return {
    schema_version: "prefer.runtime-model-catalog.v1",
    generated_at: generatedAt,
    base_catalog_fingerprint: base.catalog_fingerprint,
    defaults: base.defaults,
    models,
    repositories
  };
}

export function validateCatalogExtension(value: unknown): asserts value is CatalogExtension {
  const extension = objectValue(value, "catalog extension");
  if (extension.schema_version !== "prefer.model-catalog-extension.v1") throw new Error("catalog extension schema is incompatible");
  const generatedAt = requireString(extension.generated_at, "catalog extension generated_at");
  if (!Number.isFinite(new Date(generatedAt).getTime())) throw new Error("catalog extension generated_at is invalid");
  const repositories = objectValue(extension.repositories, "catalog extension repositories");
  const models = objectValue(extension.models, "catalog extension models");
  for (const [key, rawRepository] of Object.entries(repositories)) {
    const repository = objectValue(rawRepository, `catalog extension repository ${key}`);
    const repositoryId = validateRepository(requireString(repository.repository, `${key} repository`));
    const resolvedRevision = validateRevision(requireString(repository.resolved_revision, `${key} resolved_revision`), { immutable: true });
    if (key !== repositoryKey(repositoryId, resolvedRevision)) throw new Error(`catalog extension repository key ${key} is invalid`);
  }
  for (const [id, rawBinding] of Object.entries(models)) {
    if (!/^[a-z0-9]+(?:[.-][a-z0-9]+)*$/u.test(id)) throw new Error(`invalid extension model id ${id}`);
    const binding = objectValue(rawBinding, `catalog extension model ${id}`);
    const repository = validateRepository(requireString(binding.repository, `${id} repository`));
    const resolvedRevision = validateRevision(requireString(binding.resolved_revision, `${id} resolved_revision`), { immutable: true });
    if (!repositories[repositoryKey(repository, resolvedRevision)]) throw new Error(`extension model ${id} has no matching repository metadata`);
  }
}

async function fetchJson(url: string, fetchImpl: typeof fetch, headers: Record<string, string>, timeoutMs = 30_000): Promise<unknown> {
  return responseJson(await fetchResponse(url, fetchImpl, headers, timeoutMs), url);
}

async function fetchResponse(url: string, fetchImpl: typeof fetch, headers: Record<string, string>, timeoutMs = 30_000): Promise<Response> {
  const response = await fetchImpl(url, { headers, signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) {
    const retry = response.headers.get("retry-after");
    const suffix = response.status === 429 ? `; rate limited${retry ? `, retry after ${retry}s` : ""}` : "";
    throw new Error(`${url} returned HTTP ${response.status}${suffix}`);
  }
  return response;
}

async function responseJson(response: Response, label: string): Promise<unknown> {
  const declared = Number(response.headers.get("content-length") ?? "0");
  if (declared > MAX_RESPONSE_BYTES) throw new Error(`${label} exceeds the response size limit`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength > MAX_RESPONSE_BYTES) throw new Error(`${label} exceeds the response size limit`);
  try { return JSON.parse(new TextDecoder().decode(bytes)) as unknown; }
  catch { throw new Error(`${label} returned invalid JSON`); }
}

function objectValue(value: unknown, label: string): Record<string, unknown> {
  if (!isObject(value)) throw new Error(`${label} is not an object`);
  return value;
}

function baseModels(value: unknown, tags: string[]): string[] {
  const result = new Set<string>();
  if (typeof value === "string") result.add(value);
  if (Array.isArray(value)) for (const entry of value) if (typeof entry === "string") result.add(entry);
  for (const tag of tags) {
    const match = /^base_model(?::(?:quantized|finetune|adapter))?:(.+)$/u.exec(tag);
    if (match?.[1]) result.add(match[1]);
  }
  return [...result].sort();
}

function nextLink(value: string | null): string | undefined {
  if (!value) return undefined;
  for (const item of value.split(",")) {
    const match = /<([^>]+)>\s*;\s*rel="next"/u.exec(item);
    if (match?.[1]) return match[1];
  }
  return undefined;
}
