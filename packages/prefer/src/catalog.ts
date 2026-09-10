import { readdir, readFile } from "node:fs/promises";
import { basename, dirname, relative, resolve } from "node:path";
import { parse } from "yaml";
import type {
  DefaultsSource,
  EngineChoiceSource,
  EngineId,
  HuggingFaceSelection,
  JsonObject,
  LoadedCatalogSources,
  LoadedModelSource,
  ModelCatalogSnapshot,
  ModelSource,
  QuantSource,
  ResolvedModelArtifact,
  ResolvedModelVariant
} from "./types.js";
import { deepMerge, globMatch, isObject, readJson, repositoryKey, requireObject, requireString, sha256, stableStringify, validateRepository, validateRevision } from "./utils.js";
import { resolveHuggingFaceSelections, type HuggingFaceResolveOptions } from "./huggingface.js";

const MODEL_ID_PATTERN = /^[a-z0-9]+(?:[.-][a-z0-9]+)*$/u;

export interface RefreshCatalogOptions extends HuggingFaceResolveOptions {
  previous?: ModelCatalogSnapshot | undefined;
  now?: (() => Date) | undefined;
}

export interface ResolveVariantOptions {
  engine: EngineId;
  repository?: string | undefined;
  quant?: string | undefined;
  modelRoot?: string | undefined;
  useNvfp4?: boolean | undefined;
  overrides?: JsonObject | undefined;
}

export async function loadCatalogSources(root: string): Promise<LoadedCatalogSources> {
  const absoluteRoot = resolve(root);
  const defaults = validateDefaults(parse(await readFile(resolve(absoluteRoot, "defaults.yaml"), "utf8")));
  const modelRoot = resolve(absoluteRoot, "models");
  const files = (await yamlFiles(modelRoot)).sort((left, right) => left.localeCompare(right));
  if (!files.length) throw new Error(`${modelRoot} does not contain any model YAML files`);
  const models: Record<string, LoadedModelSource> = {};
  for (const file of files) {
    const id = basename(file).replace(/\.ya?ml$/iu, "");
    if (!MODEL_ID_PATTERN.test(id)) throw new Error(`${file}: filename must be a lowercase PreFer model id`);
    if (models[id]) throw new Error(`duplicate PreFer model id ${id}`);
    const family = relative(modelRoot, dirname(file)).split(/[\\/]/u)[0];
    if (!family || family === "..") throw new Error(`${file}: model must be inside models/<family>/`);
    const parsed = validateModel(parse(await readFile(file, "utf8")), file);
    models[id] = {
      ...parsed,
      id,
      family,
      source_path: relative(absoluteRoot, file).replaceAll("\\", "/")
    };
  }
  const source = { defaults, models };
  return { ...source, source_fingerprint: sha256(stableStringify(source)) };
}

export function listHuggingFaceSelections(sources: LoadedCatalogSources): HuggingFaceSelection[] {
  const selections = new Map<string, HuggingFaceSelection>();
  for (const model of Object.values(sources.models)) {
    for (const [repository, source] of Object.entries(model.repositories)) {
      const revision = source.revision ?? "main";
      const key = repositoryKey(repository, revision);
      if (!selections.has(key)) selections.set(key, { repository, revision });
    }
  }
  return [...selections.values()].sort((left, right) =>
    left.repository.localeCompare(right.repository) || (left.revision ?? "").localeCompare(right.revision ?? "")
  );
}

export async function refreshModelCatalog(root: string, options: RefreshCatalogOptions = {}): Promise<{ catalog: ModelCatalogSnapshot; reused_previous: boolean }> {
  const sources = await loadCatalogSources(root);
  const selections = listHuggingFaceSelections(sources);
  try {
    const resolved = await resolveHuggingFaceSelections(selections, options);
    const repositories = Object.fromEntries(resolved.map((entry) => [repositoryKey(entry.repository, entry.requested_revision), entry]));
    assertCatalogFileBindings(sources, repositories);
    return { catalog: materializeCatalog(sources, repositories, options.now), reused_previous: false };
  } catch (error) {
    if (!options.previous) throw error;
    validateModelCatalog(options.previous);
    const repositories = previousRepositoriesForSources(options.previous, sources);
    assertCatalogFileBindings(sources, repositories);
    return { catalog: materializeCatalog(sources, repositories, options.now), reused_previous: true };
  }
}

export function resolveModelVariant(catalog: ModelCatalogSnapshot, modelId: string, options: ResolveVariantOptions): ResolvedModelVariant {
  validateModelCatalog(catalog);
  const canonicalModelId = resolveCatalogModelId(catalog, modelId);
  return resolveModelVariantUnchecked(catalog, canonicalModelId, options);
}

/** Resolve either a canonical PreFer model id or one unique authored alias. */
export function resolveCatalogModelId(catalog: ModelCatalogSnapshot, modelId: string): string {
  if (catalog.models[modelId]) return modelId;
  const matches = Object.values(catalog.models)
    .filter((model) => model.aliases?.includes(modelId))
    .map((model) => model.id);
  if (!matches.length) throw new Error(`unknown PreFer model ${modelId}`);
  if (matches.length > 1) throw new Error(`ambiguous PreFer model alias ${modelId}: ${matches.join(", ")}`);
  return matches[0]!;
}

function resolveModelVariantUnchecked(
  catalog: ModelCatalogSnapshot,
  modelId: string,
  options: ResolveVariantOptions
): ResolvedModelVariant {
  const model = catalog.models[modelId]!;
  const engineDefault = {
    ...(model.engine_defaults?.all ?? {}),
    ...(model.engine_defaults?.[options.engine] ?? {})
  };
  const quant = options.quant ?? (options.useNvfp4 ? "nvfp4" : undefined) ?? engineDefault.quant ?? model.default.quant;
  const repository = selectRepositoryForQuant(catalog, model, options.engine, quant, options.repository, engineDefault.repository);
  const repositorySource = model.repositories[repository];
  if (!repositorySource) throw new Error(`${modelId} does not define repository ${repository}`);
  const quantSource = quantSourcesForRepository(catalog, model, repository)[quant];
  if (!quantSource) throw new Error(`${modelId} repository ${repository} does not define quant ${quant}`);
  const modelAllEngine = model.engines?.all;
  const modelExactEngine = model.engines?.[options.engine];
  const quantAllEngine = quantSource.engines?.all;
  const quantExactEngine = quantSource.engines?.[options.engine];
  const quantRestrictsEngines = quantSource.engines !== undefined;
  if (quantRestrictsEngines ? !quantAllEngine && !quantExactEngine : !modelAllEngine && !modelExactEngine) {
    throw new Error(`${modelId} ${repository} ${quant} does not expose engine ${options.engine}`);
  }
  const engineChoice = mergeEngineChoice(modelAllEngine, modelExactEngine, quantAllEngine, quantExactEngine);
  const selectedArtifacts = selectQuantArtifacts(model, repository, quant, quantSource, catalog.repositories);
  const inferredSettings = inferVariantSettings(options.engine, quant, selectedArtifacts);
  const settings = deepMerge(
    catalog.defaults.global,
    catalog.defaults.engines?.[options.engine],
    inferredSettings,
    model.settings,
    modelAllEngine?.settings,
    modelExactEngine?.settings,
    repositorySource.settings,
    quantSource.settings,
    quantAllEngine?.settings,
    quantExactEngine?.settings,
    options.overrides
  );
  const modelRoot = options.modelRoot?.trim() || "/models";
  const repositoryPath = storagePath(modelRoot, repository);
  const artifacts: ResolvedModelArtifact[] = selectedArtifacts.map((artifact) => {
    const roleDefaults = artifact.role
      ? catalog.defaults.engine_artifact_roles?.[options.engine]?.[artifact.role]
      : undefined;
    const artifactSettings = deepMerge(roleDefaults, artifact.settings);
    return {
      ...artifact,
      local_path: storagePath(modelRoot, artifact.repository, artifact.path),
      ...(Object.keys(artifactSettings).length ? { settings: artifactSettings } : {})
    };
  });
  return {
    model_id: model.id,
    family: model.family,
    display_name: model.display_name,
    ...(model.profile ? { profile: structuredClone(model.profile) } : {}),
    engine: options.engine,
    repository,
    repository_path: repositoryPath,
    revision: repositoryMetadata(catalog.repositories, repository, repositorySource).resolved_revision,
    quant,
    files: artifacts.map((artifact) => artifact.path),
    artifacts,
    artifact_bytes: artifacts.reduce((total, artifact) => total + artifact.size, 0),
    capabilities: [...new Set([...(model.capabilities ?? []), ...(engineChoice.capabilities ?? [])])],
    settings
  };
}

export function listModelVariants(catalog: ModelCatalogSnapshot, modelId: string, engine?: EngineId): ResolvedModelVariant[] {
  validateModelCatalog(catalog);
  const canonicalModelId = resolveCatalogModelId(catalog, modelId);
  const model = catalog.models[canonicalModelId]!;
  const engines = engine ? [engine] : supportedEngines(model);
  const result: ResolvedModelVariant[] = [];
  for (const [repository, repositorySource] of Object.entries(model.repositories)) {
    for (const quant of Object.keys(quantSourcesForRepository(catalog, model, repository))) {
      for (const selectedEngine of engines) {
        try { result.push(resolveModelVariantUnchecked(catalog, canonicalModelId, { engine: selectedEngine, repository, quant })); }
        catch (error) {
          if (!(error instanceof Error) || !error.message.includes("does not expose engine")) throw error;
        }
      }
    }
  }
  return result;
}

export function validateModelCatalog(value: unknown): asserts value is ModelCatalogSnapshot {
  const catalog = requireObject(value, "model catalog");
  if (catalog.schema_version !== "prefer.model-catalog.v1") throw new Error("model catalog schema is incompatible");
  const generatedAt = requireString(catalog.generated_at, "model catalog generated_at");
  if (!Number.isFinite(new Date(generatedAt).getTime())) throw new Error("model catalog generated_at is invalid");
  const sourceFingerprint = requireString(catalog.source_fingerprint, "model catalog source fingerprint");
  if (!/^[0-9a-f]{64}$/u.test(sourceFingerprint)) throw new Error("model catalog source fingerprint is invalid");
  const fingerprint = requireString(catalog.catalog_fingerprint, "model catalog fingerprint");
  if (!/^[0-9a-f]{64}$/u.test(fingerprint)) throw new Error("model catalog fingerprint is invalid");
  const defaults = requireObject(catalog.defaults, "model catalog defaults");
  const models = requireObject(catalog.models, "model catalog models");
  const repositories = requireObject(catalog.repositories, "model catalog repositories");
  if (sha256(stableStringify({ defaults, models })) !== sourceFingerprint) throw new Error("model catalog source fingerprint does not match its content");
  if (sha256(stableStringify({ defaults, models, repositories })) !== fingerprint) throw new Error("model catalog fingerprint does not match its content");
}

export async function readModelCatalog(path: string): Promise<ModelCatalogSnapshot> {
  const value = await readJson(path);
  validateModelCatalog(value);
  return value;
}

function previousRepositoriesForSources(
  previous: ModelCatalogSnapshot,
  sources: LoadedCatalogSources
): ModelCatalogSnapshot["repositories"] {
  const repositories: ModelCatalogSnapshot["repositories"] = {};
  for (const selection of listHuggingFaceSelections(sources)) {
    const key = repositoryKey(selection.repository, selection.revision ?? "main");
    const repository = previous.repositories[key];
    if (!repository) throw new Error(`last successful model catalog does not contain ${key}`);
    if (repository.requested_revision !== (selection.revision ?? "main")) throw new Error(`last successful model catalog revision does not match ${key}`);
    repositories[key] = repository;
  }
  return repositories;
}

function assertCatalogFileBindings(
  sources: LoadedCatalogSources,
  repositories: ModelCatalogSnapshot["repositories"]
): void {
  for (const model of Object.values(sources.models)) {
    for (const [repository, repositorySource] of Object.entries(model.repositories)) {
      const key = repositoryKey(repository, repositorySource.revision ?? "main");
      const metadata = repositories[key];
      if (!metadata) throw new Error(`materialized catalog does not contain ${key}`);
      for (const [quant, quantSource] of Object.entries(quantSourcesForRepositoryMetadata(model, repository, repositorySource, metadata))) {
        selectQuantArtifacts(model, repository, quant, quantSource, repositories);
      }
    }
  }
}

function materializeCatalog(
  sources: LoadedCatalogSources,
  repositories: ModelCatalogSnapshot["repositories"],
  now: (() => Date) | undefined
): ModelCatalogSnapshot {
  const fingerprintInput = { defaults: sources.defaults, models: sources.models, repositories };
  return {
    schema_version: "prefer.model-catalog.v1",
    generated_at: (now?.() ?? new Date()).toISOString(),
    source_fingerprint: sources.source_fingerprint,
    catalog_fingerprint: sha256(stableStringify(fingerprintInput)),
    defaults: sources.defaults,
    models: sources.models,
    repositories
  };
}

function mergeEngineChoice(...choices: Array<EngineChoiceSource | undefined>): EngineChoiceSource {
  const capabilities = choices.flatMap((choice) => choice?.capabilities ?? []);
  const notes = choices.flatMap((choice) => choice?.notes ?? []);
  return {
    ...(capabilities.length ? { capabilities } : {}),
    settings: deepMerge(...choices.map((choice) => choice?.settings)),
    ...(notes.length ? { notes } : {})
  };
}

function supportedEngines(model: LoadedModelSource): EngineId[] {
  const result = new Set<string>();
  for (const engine of Object.keys(model.engines ?? {})) if (engine !== "all") result.add(engine);
  for (const repository of Object.values(model.repositories)) {
    for (const quant of Object.values(repository.quants ?? {})) {
      for (const engine of Object.keys(quant.engines ?? {})) if (engine !== "all") result.add(engine);
    }
  }
  return [...result];
}

async function yamlFiles(root: string): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const path = resolve(root, entry.name);
    if (entry.isDirectory()) files.push(...await yamlFiles(path));
    else if (/\.ya?ml$/iu.test(entry.name)) files.push(path);
  }
  return files;
}

function validateDefaults(value: unknown): DefaultsSource {
  const source = requireObject(value, "defaults.yaml");
  if (source.schema_version !== "prefer.model-defaults.v1") throw new Error("defaults.yaml schema_version must be prefer.model-defaults.v1");
  return source as unknown as DefaultsSource;
}

function validateModel(value: unknown, path: string): ModelSource {
  const source = requireObject(value, path);
  if ("id" in source) throw new Error(`${path}: id is derived from the filename and must not be repeated`);
  if (source.schema_version !== "prefer.model-source.v1") throw new Error(`${path}: incompatible schema_version`);
  requireString(source.display_name, `${path} display_name`);
  if (source.profile !== undefined) {
    const profile = requireObject(source.profile, `${path} profile`);
    requireString(profile.summary, `${path} profile.summary`);
  }
  const defaults = requireObject(source.default, `${path} default`);
  const defaultRepository = validateRepository(requireString(defaults.repository, `${path} default.repository`));
  const defaultQuant = requireString(defaults.quant, `${path} default.quant`);
  const repositories = requireObject(source.repositories, `${path} repositories`);
  if (!Object.keys(repositories).length) throw new Error(`${path}: repositories must not be empty`);
  if (source.engines !== undefined) validateEngineChoices(source.engines, `${path} engines`);
  for (const [repository, rawRepository] of Object.entries(repositories)) {
    validateRepository(repository);
    const repositorySource = requireObject(rawRepository, `${path} repository ${repository}`);
    if (repositorySource.revision !== undefined) {
      validateRevision(requireString(repositorySource.revision, `${path} repository ${repository} revision`), { immutable: true });
    }
    if (repositorySource.discover !== undefined && repositorySource.discover !== "gguf") {
      throw new Error(`${path}: repository ${repository} has unsupported discovery mode`);
    }
    const quants = repositorySource.quants === undefined
      ? {}
      : requireObject(repositorySource.quants, `${path} repository ${repository} quants`);
    if (repositorySource.discover === "gguf" && !Object.keys(quants).length) {
      throw new Error(`${path}: repository ${repository} needs one authored quant as its GGUF discovery template`);
    }
    for (const [quant, rawQuant] of Object.entries(quants)) {
      const quantSource = requireObject(rawQuant, `${path} ${repository} ${quant}`);
      if (quantSource.engines === undefined && source.engines === undefined) {
        throw new Error(`${path}: ${repository} ${quant} must define engines or inherit model engines`);
      }
      if (quantSource.engines !== undefined) {
        const engines = requireObject(quantSource.engines, `${path} ${repository} ${quant} engines`);
        if (!Object.keys(engines).length) throw new Error(`${path}: ${repository} ${quant} has no engine choices`);
        validateEngineChoices(engines, `${path} ${repository} ${quant} engines`);
      }
      if (quantSource.artifacts !== undefined && (quantSource.files !== undefined || quantSource.include !== undefined || quantSource.exclude !== undefined)) {
        throw new Error(`${path}: ${repository} ${quant} may use artifacts or shorthand file selectors, not both`);
      }
    }
  }
  if (source.quant_sources !== undefined) {
    const quantSources = requireObject(source.quant_sources, `${path} quant_sources`);
    for (const [quant, rawEngines] of Object.entries(quantSources)) {
      const engines = requireObject(rawEngines, `${path} quant_sources.${quant}`);
      if (!Object.keys(engines).length) throw new Error(`${path}: quant_sources.${quant} must not be empty`);
      for (const [engine, rawRepository] of Object.entries(engines)) {
        const repository = validateRepository(requireString(rawRepository, `${path} quant_sources.${quant}.${engine}`));
        if (!(repository in repositories)) throw new Error(`${path}: quant_sources.${quant}.${engine} references undeclared repository ${repository}`);
      }
    }
  }
  const defaultSource = repositories[defaultRepository] as Record<string, unknown> | undefined;
  const defaultQuants = defaultSource && isObject(defaultSource.quants) ? defaultSource.quants : undefined;
  if (!defaultSource || !defaultQuants || !(defaultQuant in defaultQuants)) throw new Error(`${path}: default repository/quant is not defined`);
  return source as unknown as ModelSource;
}

function validateEngineChoices(value: unknown, label: string): void {
  const engines = requireObject(value, label);
  for (const [engine, rawChoice] of Object.entries(engines)) {
    const choice = requireObject(rawChoice, `${label}.${engine}`);
    if ("status" in choice) throw new Error(`${label}.${engine}: status belongs to deployment evidence, not authored model selection`);
  }
}

function selectQuantArtifacts(
  model: LoadedModelSource,
  primaryRepository: string,
  quant: string,
  quantSource: QuantSource,
  repositories: ModelCatalogSnapshot["repositories"]
): Array<Omit<ResolvedModelArtifact, "local_path">> {
  const selections = quantSource.artifacts?.length
    ? quantSource.artifacts
    : [{
        ...(quantSource.files ? { files: quantSource.files } : {}),
        ...(quantSource.include ? { include: quantSource.include } : {}),
        ...(quantSource.exclude ? { exclude: quantSource.exclude } : {})
      }];
  const result: Array<Omit<ResolvedModelArtifact, "local_path">> = [];
  const seen = new Set<string>();
  for (const selection of selections) {
    const repository = selection.repository ?? primaryRepository;
    const repositorySource = model.repositories[repository];
    if (!repositorySource) throw new Error(`${model.id} ${primaryRepository} ${quant} references undeclared repository ${repository}`);
    const metadata = repositoryMetadata(repositories, repository, repositorySource);
    const explicitFiles = selection.files ?? [];
    const include = selection.include ?? [];
    const exclude = selection.exclude ?? [];
    let selected = explicitFiles.length
      ? explicitFiles.map((file) => {
          const match = metadata.files.find((candidate) => candidate.path === file);
          if (!match) throw new Error(`${model.id} ${primaryRepository} ${quant} references missing Hugging Face file ${repository}/${file}`);
          return match;
        })
      : metadata.files.filter((file) => !include.length || include.some((pattern) => globMatch(file.path, pattern)));
    if (exclude.length) selected = selected.filter((file) => !exclude.some((pattern) => globMatch(file.path, pattern)));
    if (!selected.length) throw new Error(`${model.id} ${primaryRepository} ${quant} artifact selector matched no files in ${repository}`);
    for (const file of selected) {
      const identity = `${repository}@${metadata.resolved_revision}/${file.path}`;
      if (seen.has(identity)) throw new Error(`${model.id} ${primaryRepository} ${quant} selects ${identity} more than once`);
      seen.add(identity);
      result.push({
        ...file,
        repository,
        revision: metadata.resolved_revision,
        ...(selection.role ? { role: selection.role } : {}),
        ...(selection.settings ? { settings: selection.settings } : {})
      });
    }
  }
  return result;
}

function selectRepositoryForQuant(
  catalog: ModelCatalogSnapshot,
  model: LoadedModelSource,
  engine: EngineId,
  quant: string,
  explicitRepository?: string,
  engineRepository?: string
): string {
  if (explicitRepository) return explicitRepository;
  const mapped = model.quant_sources?.[quant]?.[engine] ?? model.quant_sources?.[quant]?.all;
  if (mapped) return mapped;
  const preferred = [engineRepository, model.default.repository].filter((value): value is string => Boolean(value));
  for (const repository of preferred) {
    if (quantSourcesForRepository(catalog, model, repository)[quant]) return repository;
  }
  const candidates = Object.keys(model.repositories).filter((repository) => {
    const source = quantSourcesForRepository(catalog, model, repository)[quant];
    return source ? exposesEngine(model, source, engine) : false;
  });
  if (candidates.length === 1) return candidates[0]!;
  if (!candidates.length) throw new Error(`${model.id} does not offer quant ${quant} for engine ${engine}`);
  throw new Error(`${model.id} quant ${quant} is available from multiple repositories for ${engine}; select one of ${candidates.join(", ")}`);
}

function quantSourcesForRepository(
  catalog: ModelCatalogSnapshot,
  model: LoadedModelSource,
  repository: string
): Record<string, QuantSource> {
  const source = model.repositories[repository];
  if (!source) return {};
  return quantSourcesForRepositoryMetadata(model, repository, source, repositoryMetadata(catalog.repositories, repository, source));
}

function quantSourcesForRepositoryMetadata(
  model: LoadedModelSource,
  repository: string,
  source: LoadedModelSource["repositories"][string],
  metadata: ModelCatalogSnapshot["repositories"][string]
): Record<string, QuantSource> {
  const explicit = source.quants ?? {};
  if (source.discover !== "gguf") return explicit;
  const result: Record<string, QuantSource> = { ...explicit };
  const fallbackTemplate = explicit[model.default.repository === repository ? model.default.quant : ""] ?? Object.values(explicit)[0];
  if (!fallbackTemplate) throw new Error(`${model.id} repository ${repository} enables GGUF discovery without a template quant`);
  const secondary = secondaryArtifactPaths(repository, explicit);
  const authoredPrimarySelections = new Set(
    Object.values(explicit)
      .map((quant) => primaryArtifactFiles(repository, quant).sort().join("\n"))
      .filter(Boolean)
  );
  for (const [quant, files] of discoverGgufQuants(metadata.files, secondary)) {
    if (!result[quant] && !authoredPrimarySelections.has(files.join("\n"))) {
      result[quant] = discoveredQuantSource(closestQuantTemplate(explicit, quant) ?? fallbackTemplate, repository, files);
    }
  }
  return result;
}

function closestQuantTemplate(quants: Record<string, QuantSource>, requested: string): QuantSource | undefined {
  const requestedScore = quantScore(requested);
  if (requestedScore === undefined) return undefined;
  return Object.entries(quants)
    .flatMap(([quant, source]) => {
      const score = quantScore(quant);
      return score === undefined ? [] : [{ source, score, distance: Math.abs(score - requestedScore) }];
    })
    .sort((left, right) => left.distance - right.distance || right.score - left.score)[0]?.source;
}

function quantScore(quant: string): number | undefined {
  const normalized = quant.toLowerCase();
  if (/^(?:bf|f|fp)32/u.test(normalized)) return 32;
  if (/^(?:bf|f|fp)16/u.test(normalized)) return 16;
  if (normalized.startsWith("nvfp4") || normalized.startsWith("mxfp4")) return 4;
  const match = /(?:^|-)\D*([1-9])(?:-|$)/u.exec(normalized);
  return match?.[1] ? Number(match[1]) : undefined;
}

function primaryArtifactFiles(repository: string, source: QuantSource): string[] {
  if (source.artifacts?.length) {
    return source.artifacts.flatMap((artifact) =>
      (artifact.repository ?? repository) === repository && isPrimaryRole(artifact.role) ? artifact.files ?? [] : []
    );
  }
  return source.files ?? [];
}

function discoveredQuantSource(template: QuantSource, repository: string, files: string[]): QuantSource {
  const result = structuredClone(template);
  if (result.artifacts?.length) {
    let replaced = false;
    const artifacts = result.artifacts.map((artifact): typeof artifact => {
      const artifactRepository = artifact.repository ?? repository;
      if (!replaced && artifactRepository === repository && isPrimaryRole(artifact.role)) {
        replaced = true;
        const replacement = { ...artifact, files };
        delete replacement.include;
        delete replacement.exclude;
        return replacement;
      }
      return artifact;
    });
    if (!replaced) artifacts.unshift({ files, role: "model" });
    result.artifacts = artifacts;
  } else {
    result.files = files;
    delete result.include;
    delete result.exclude;
  }
  return result;
}

function discoverGgufQuants(
  files: ModelCatalogSnapshot["repositories"][string]["files"],
  secondary: Set<string>
): Array<[string, string[]]> {
  const result = new Map<string, string[]>();
  for (const file of files) {
    if (!file.path.toLowerCase().endsWith(".gguf") || secondary.has(file.path) || looksLikeCompanion(file.path)) continue;
    const quant = quantFromGgufPath(file.path);
    if (!quant) continue;
    result.set(quant, [...(result.get(quant) ?? []), file.path]);
  }
  return [...result.entries()]
    .map(([quant, paths]) => [quant, paths.sort()] as [string, string[]])
    .sort(([left], [right]) => left.localeCompare(right));
}

function quantFromGgufPath(path: string): string | undefined {
  const filename = basename(path).replace(/\.gguf$/iu, "").replace(/-\d{5}-of-\d{5}$/iu, "");
  const match = /(?:^|[-.])((?:UD-)?(?:IQ[1-9](?:_[A-Z0-9]+)*|TQ[1-9](?:_[A-Z0-9]+)*|Q[1-9](?:_[A-Z0-9]+)*|Q4KEXPERTS)|BF16|F16|F32|FP16|FP32|NVFP4|MXFP4)$/iu.exec(filename);
  return match?.[1]?.toLowerCase().replaceAll("_", "-");
}

function secondaryArtifactPaths(repository: string, quants: Record<string, QuantSource>): Set<string> {
  const result = new Set<string>();
  for (const quant of Object.values(quants)) {
    for (const artifact of quant.artifacts ?? []) {
      if ((artifact.repository ?? repository) !== repository || isPrimaryRole(artifact.role)) continue;
      for (const file of artifact.files ?? []) result.add(file);
    }
  }
  return result;
}

function looksLikeCompanion(path: string): boolean {
  return /(?:^|[\/_-])(mmproj|mtp|draft|dspark|dflash|vae|clip|encoder|decoder)(?:[\/_-]|$)/iu.test(path);
}

function isPrimaryRole(role: string | undefined): boolean {
  return role === undefined || role === "model" || role === "target" || role === "checkpoint";
}

function exposesEngine(model: LoadedModelSource, quant: QuantSource, engine: EngineId): boolean {
  const choices = quant.engines ?? model.engines;
  return choices?.all !== undefined || choices?.[engine] !== undefined;
}

function inferVariantSettings(
  engine: EngineId,
  quant: string,
  artifacts: Array<Omit<ResolvedModelArtifact, "local_path">>
): JsonObject {
  const primary = artifacts.filter((artifact) => isPrimaryRole(artifact.role));
  const gguf = primary.length > 0 && primary.every((artifact) => artifact.path.toLowerCase().endsWith(".gguf"));
  return deepMerge(
    (engine === "sglang" || engine === "vllm") && gguf ? { launcher: { load_format: "gguf" } } : undefined,
    (engine === "sglang" || engine === "vllm") && quant === "nvfp4" ? { launcher: { quantization: "modelopt_fp4" } } : undefined
  );
}

function repositoryMetadata(
  repositories: ModelCatalogSnapshot["repositories"],
  repository: string,
  source: LoadedModelSource["repositories"][string]
): ModelCatalogSnapshot["repositories"][string] {
  const requestedRevision = source.revision ?? "main";
  const metadata = repositories[repositoryKey(repository, requestedRevision)];
  if (!metadata) throw new Error(`materialized catalog does not contain ${repository}@${requestedRevision}`);
  return metadata;
}

function storagePath(root: string, ...parts: string[]): string {
  return [root.replace(/\/+$/u, ""), ...parts.map((part) => part.replace(/^\/+|\/+$/gu, ""))]
    .filter(Boolean)
    .join("/");
}
