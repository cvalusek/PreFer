export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export type EngineId = "llama.cpp" | "audio.cpp" | "stable-diffusion.cpp" | "sglang" | "vllm" | (string & {});

export interface EngineChoiceSource {
  capabilities?: string[];
  settings?: JsonObject;
  notes?: string[];
}

export interface QuantSource {
  files?: string[];
  include?: string[];
  exclude?: string[];
  artifacts?: ArtifactSource[];
  settings?: JsonObject;
  engines?: Record<string, EngineChoiceSource>;
}

export interface ArtifactSource {
  repository?: string;
  files?: string[];
  include?: string[];
  exclude?: string[];
  role?: string;
  settings?: JsonObject;
}

export interface RepositorySource {
  revision?: string;
  discover?: "gguf";
  settings?: JsonObject;
  quants?: Record<string, QuantSource>;
}

export interface ModelSource {
  schema_version: "prefer.model-source.v1";
  display_name: string;
  aliases?: string[];
  capabilities?: string[];
  profile?: ModelProfile;
  default: { repository: string; quant: string };
  engine_defaults?: Record<string, { repository?: string; quant?: string }>;
  quant_sources?: Record<string, Record<string, string>>;
  settings?: JsonObject;
  engines?: Record<string, EngineChoiceSource>;
  repositories: Record<string, RepositorySource>;
}

export interface ModelProfile {
  summary: string;
  architecture?: {
    kind: string;
    total_parameters_b?: number | null;
    active_parameters_b?: number | null;
    notes?: string;
  };
  modalities?: {
    native_input?: string[];
    configured_input?: string[];
    output?: string[];
  };
  context?: {
    native_tokens?: number | null;
    notes?: string;
  };
  reasoning?: {
    control?: string;
    notes?: string;
  };
  roles?: {
    preferred?: string[];
    capable?: string[];
    avoid?: string[];
  };
  strengths?: string[];
  limitations?: string[];
  prompting?: string[];
  evidence?: {
    confidence: "high" | "mixed" | "limited";
    basis?: string[];
    notes?: string;
  };
}

export interface DefaultsSource {
  schema_version: "prefer.model-defaults.v1";
  global?: JsonObject;
  engines?: Record<string, JsonObject>;
  engine_artifact_roles?: Record<string, Record<string, JsonObject>>;
}

export interface LoadedModelSource extends ModelSource {
  id: string;
  family: string;
  source_path: string;
}

export interface LoadedCatalogSources {
  defaults: DefaultsSource;
  models: Record<string, LoadedModelSource>;
  source_fingerprint: string;
}

export interface HuggingFaceSelection {
  repository: string;
  revision?: string;
  include?: string[];
  model_id?: string;
}

export interface HuggingFaceFile {
  path: string;
  size: number;
  blob_oid?: string;
  lfs_sha256?: string;
  xet_hash?: string;
}

export interface HuggingFaceRepository {
  repository: string;
  requested_revision: string;
  resolved_revision: string;
  base_models: string[];
  pipeline_tag?: string;
  library_name?: string;
  license?: string;
  gated: boolean | string;
  private: boolean;
  tags: string[];
  files_complete: boolean;
  include_patterns?: string[];
  files: HuggingFaceFile[];
  retrieved_at: string;
}

export interface ModelCatalogSnapshot {
  schema_version: "prefer.model-catalog.v1";
  generated_at: string;
  source_fingerprint: string;
  catalog_fingerprint: string;
  defaults: DefaultsSource;
  models: Record<string, LoadedModelSource>;
  repositories: Record<string, HuggingFaceRepository>;
}

export interface CatalogExtension {
  schema_version: "prefer.model-catalog-extension.v1";
  generated_at: string;
  repositories: Record<string, HuggingFaceRepository>;
  models: Record<string, { repository: string; resolved_revision: string }>;
}

export type RuntimeCatalogModel =
  | { source: "prefer"; definition: LoadedModelSource }
  | { source: "extension"; repository: string; resolved_revision: string };

export interface RuntimeModelCatalog {
  schema_version: "prefer.runtime-model-catalog.v1";
  generated_at: string;
  base_catalog_fingerprint: string;
  defaults: DefaultsSource;
  models: Record<string, RuntimeCatalogModel>;
  repositories: Record<string, HuggingFaceRepository>;
}

export interface ResolvedModelVariant {
  model_id: string;
  family: string;
  display_name: string;
  profile?: ModelProfile;
  engine: EngineId;
  repository: string;
  repository_path: string;
  revision: string;
  quant: string;
  files: string[];
  artifacts: ResolvedModelArtifact[];
  artifact_bytes: number;
  capabilities: string[];
  settings: JsonObject;
}

export interface ResolvedModelArtifact extends HuggingFaceFile {
  repository: string;
  revision: string;
  local_path: string;
  /** Exact file SHA-256 supplied by a controller when Hugging Face metadata does not expose an LFS OID. */
  sha256?: string;
  role?: string;
  settings?: JsonObject;
}

export interface RuntimeHandoffArtifactInput {
  repository: string;
  revision: string;
  path: string;
  size: number;
  sha256?: string;
  git_blob_sha1?: string;
  model_id?: string;
  role?: string;
  settings?: JsonObject;
}

export interface RuntimeHandoffArtifact {
  id: string;
  repository: string;
  revision: string;
  path: string;
  size: number;
  sha256?: string;
  git_blob_sha1?: string;
  model_id?: string;
  role?: string;
  settings?: JsonObject;
}

export interface RuntimeHandoffModel {
  model_id: string;
  request_model_id: string;
  source: "prefer" | "extension";
  family: string;
  display_name: string;
  repository: string;
  revision: string;
  quant: string;
  artifact_ids: string[];
  capabilities: string[];
  settings: JsonObject;
}

/**
 * Immutable controller-to-container launch handoff. Paths are intentionally
 * absent: the receiving image derives them below its selected model root.
 */
export interface RuntimeHandoff {
  schema_version: "prefer.runtime-handoff.v1";
  catalog_fingerprint: string;
  handoff_fingerprint: string;
  engine: EngineId;
  base_deployment?: string;
  server_settings: JsonObject;
  models: RuntimeHandoffModel[];
  artifacts: RuntimeHandoffArtifact[];
}

export interface MaterializedRuntimeHandoffArtifact extends RuntimeHandoffArtifact {
  local_path: string;
}

export interface MaterializedRuntimeHandoffModel extends RuntimeHandoffModel {
  repository_path: string;
}

export interface MaterializedRuntimeHandoff extends Omit<RuntimeHandoff, "models" | "artifacts"> {
  model_root: string;
  models: MaterializedRuntimeHandoffModel[];
  artifacts: MaterializedRuntimeHandoffArtifact[];
}

export type MemoryTopology = "discrete" | "unified" | "host" | "unknown";

export interface MemoryResource {
  total_bytes?: number;
  available_bytes?: number;
}

export interface AcceleratorResource extends MemoryResource {
  id?: string;
  slug?: string;
  canonical_id?: string;
  provider_id?: string;
  name?: string;
  architecture?: string;
  compute_capability?: string;
  capabilities: string[];
}

export interface CpuResource {
  architecture?: string;
  logical_cores?: number;
  model?: string;
  capabilities?: string[];
}

export interface StorageResource extends MemoryResource {
  kind?: "local" | "network" | "unknown";
}

/**
 * Engine-neutral resources derived from a deployment description and, when
 * available, overlaid with facts observed inside the running container.
 * Unified memory is represented once and is never added to host RAM or an
 * accelerator's reported aperture.
 */
export interface ResourceProfile {
  schema_version: "prefer.resources.v1";
  source: "deployment" | "runtime" | "merged";
  provider?: string;
  provider_sku?: string;
  memory_topology: MemoryTopology;
  accelerators: AcceleratorResource[];
  unified_memory?: MemoryResource;
  host_memory?: MemoryResource;
  cpu?: CpuResource;
  storage?: StorageResource;
  capabilities: string[];
}

export interface RuntimeResourceObservation {
  accelerators?: AcceleratorResource[];
  unified_memory?: MemoryResource;
  host_memory?: MemoryResource;
  cpu?: CpuResource;
  storage?: StorageResource;
  capabilities?: string[];
}

export type QuantQualityTier =
  | "reference"
  | "near-lossless"
  | "high"
  | "deployment"
  | "compromise"
  | "fit-floor"
  | "extreme"
  | "unknown";

export interface QuantQuality {
  tier: QuantQualityTier;
  score: number;
}

export interface LinearWorkloadMemory {
  /** Memory already measured or otherwise known outside weights/KV. */
  fixed_device_bytes?: number;
  /** Device memory per aggregate cached token across all admitted requests. */
  bytes_per_token?: number;
  context_tokens?: number;
  concurrency?: number;
  source?: "measured" | "architecture" | "operator" | "estimate";
}

export interface VariantFitOptions {
  headroom_fraction?: number;
  minimum_headroom_bytes?: number;
  maximum_headroom_bytes?: number;
  runtime_overhead_bytes?: number;
  device_weight_bytes?: number;
  workload?: LinearWorkloadMemory;
  allow_multi_gpu?: boolean;
  allow_host_offload?: boolean;
  /** Preserve an explicitly configured offload route until runtime RAM is observed. */
  allow_unknown_host_offload?: boolean;
  maximum_host_offload_bytes?: number;
}

export type VariantFitStatus = "fits" | "tight" | "host-offload" | "does-not-fit" | "unknown";

export interface VariantFitEstimate {
  status: VariantFitStatus;
  confidence: "measured" | "architecture" | "artifact-only" | "unknown";
  capacity_bytes?: number;
  usable_capacity_bytes?: number;
  weight_bytes: number;
  runtime_overhead_bytes: number;
  workload_bytes: number;
  required_device_bytes: number;
  remaining_device_bytes?: number;
  host_offload_bytes?: number;
  reasons: string[];
}

export interface ModelPlanRequest {
  model_id: string;
  repository?: string;
  /** Preferred starting point that may fall back; `quant` is an exact request. */
  preferred_quant?: string;
  quant?: string;
  required?: boolean;
  priority?: number;
  /** Caller-normalized 0..100 route score; higher means faster on the target. */
  speed_score?: number;
  /** Caller-normalized 0..100 model score; higher means better for the workload. */
  quality_score?: number;
  overrides?: JsonObject;
  fit?: VariantFitOptions;
  workload?: WorkloadTuningRequest;
}

export type QuantSelectionBias = "quality" | "balanced" | "capacity";

/**
 * Optional workload hints used to rank otherwise-optional bundle members and
 * quantization lanes. Required capabilities are a hard boundary; preferred
 * capabilities and roles only influence ordering.
 */
export interface ModelSelectionHints {
  required_capabilities?: string[];
  preferred_capabilities?: string[];
  preferred_roles?: string[];
  /** 0 ignores speed; 1 gives it full weight in optional bundle ordering. */
  speed_importance?: number;
  /** 0 ignores caller quality scores; 1 gives them full weight. */
  quality_importance?: number;
  quant_bias?: QuantSelectionBias;
}

export interface ModelPlanSelection {
  model_id: string;
  preferred_quant: string;
  requested_quant?: string;
  selected: ResolvedModelVariant;
  fit: VariantFitEstimate;
  quant_changed: boolean;
  reason: string;
  workload_request?: WorkloadTuningRequest;
  workload?: WorkloadTuningResult;
}

export interface ModelPlanSkip {
  model_id: string;
  required: boolean;
  reason: "no-compatible-variant" | "missing-capability" | "insufficient-memory" | "storage-budget" | "model-limit";
  details: string[];
}

export interface ModelSetPlan {
  schema_version: "prefer.model-plan.v1";
  engine: EngineId;
  resources: ResourceProfile;
  selected: ModelPlanSelection[];
  skipped: ModelPlanSkip[];
  capabilities: string[];
  staged_artifact_bytes: number;
  complete: boolean;
  hints?: ModelSelectionHints;
}

export interface PlanModelSetOptions {
  engine: EngineId;
  resources: ResourceProfile;
  models: ModelPlanRequest[];
  use_nvfp4?: boolean;
  quality_floor?: QuantQualityTier | number;
  max_staged_bytes?: number;
  max_models?: number;
  accept_tight?: boolean;
  hints?: ModelSelectionHints;
  fit?: VariantFitOptions;
  workload?: WorkloadTuningRequest;
}

export interface WorkloadTuningRequest {
  desired_context_tokens: number;
  desired_concurrency: number;
  minimum_context_tokens?: number;
  minimum_concurrency?: number;
  priority?: "context" | "concurrency";
  bytes_per_token: number;
  fixed_device_bytes?: number;
  source?: "measured" | "architecture" | "operator" | "estimate";
}

export interface WorkloadTuningResult {
  fits: boolean;
  context_tokens: number;
  concurrency: number;
  aggregate_token_capacity: number;
  changed: boolean;
  reason: string;
}

export interface PreferReleaseSummary {
  id: string;
  revision: string;
  channel: "stable" | "preview";
  published_at: string;
  title: string;
  url: string;
}

export interface PreferReleaseAsset {
  name: string;
  url: string;
  size?: number;
  digest?: string;
}

export interface PreferReleaseRecord extends PreferReleaseSummary {
  assets: Record<string, PreferReleaseAsset>;
}

export interface PreferReleaseManifest {
  schema_version: string;
  release: {
    id: string;
    source_revision: string;
    source_repository: string;
    source_url: string;
    artifact_name: string;
  };
  distribution: {
    model_weights_embedded: false;
    models_stage_at_runtime: true;
    all_engine_images_share_release_revision: true;
  };
  engines: Record<string, unknown>;
  tooling?: Record<string, unknown>;
}
