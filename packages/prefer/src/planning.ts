import type {
  ModelCatalogSnapshot,
  ModelPlanRequest,
  ModelSelectionHints,
  ModelPlanSelection,
  ModelPlanSkip,
  ModelSetPlan,
  PlanModelSetOptions,
  QuantQuality,
  QuantQualityTier,
  ResolvedModelVariant,
  ResourceProfile,
  VariantFitEstimate,
  VariantFitOptions,
  WorkloadTuningRequest,
  WorkloadTuningResult
} from "./types.js";
import { listModelVariants, resolveCatalogModelId, resolveModelVariant } from "./catalog.js";
import { isObject } from "./utils.js";

const GIB = 1024 ** 3;
const DEFAULT_HEADROOM_FRACTION = 0.04;
const DEFAULT_MINIMUM_HEADROOM_BYTES = 1.5 * GIB;
const DEFAULT_MAXIMUM_HEADROOM_BYTES = 4 * GIB;
const QUALITY_SCORES: Record<QuantQualityTier, number> = {
  reference: 100,
  "near-lossless": 90,
  high: 80,
  deployment: 60,
  compromise: 45,
  "fit-floor": 25,
  extreme: 10,
  unknown: 0
};

export function quantQuality(quant: string): QuantQuality {
  const normalized = quant.toLowerCase().replaceAll("_", "-");
  const scores: number[] = [];
  if (/(?:^|-)(?:f32|fp32|f16|fp16|bf16)(?:-|$)/u.test(normalized)) scores.push(100);
  if (/(?:^|-)(?:fp8|q8|int8)(?:-|$)/u.test(normalized)) scores.push(90);
  if (/(?:^|-)(?:q6|iq6)(?:-|$)/u.test(normalized)) scores.push(80);
  if (/(?:^|-)(?:q5|iq5)(?:-|$)/u.test(normalized)) scores.push(70);
  if (/(?:^|-)(?:nvfp4|mxfp4|w4a16|q4|iq4|int4)(?:-|$)/u.test(normalized)) scores.push(60);
  if (/(?:^|-)(?:q3|iq3)(?:-|$)/u.test(normalized)) scores.push(45);
  if (/(?:^|-)(?:q2|iq2)(?:-|$)/u.test(normalized)) scores.push(25);
  if (/(?:^|-)(?:q1|iq1)(?:-|$)/u.test(normalized)) scores.push(10);
  if (!scores.length) return { tier: "unknown", score: 0 };
  let score = Math.min(...scores);
  if (normalized.includes("xl")) score += 3;
  else if (normalized.includes("k-m")) score += 2;
  else if (normalized.includes("k-s")) score += 1;
  if (normalized.includes("iq") && score >= 45) score -= 1;
  return { tier: tierForScore(score), score };
}

export function estimateVariantFit(
  variant: ResolvedModelVariant,
  resources: ResourceProfile,
  options: VariantFitOptions = {}
): VariantFitEstimate {
  const capacity = acceleratorCapacity(resources, options.allow_multi_gpu ?? true);
  const weightBytes = options.device_weight_bytes ?? variant.artifact_bytes;
  const runtimeOverhead = options.runtime_overhead_bytes ?? Math.max(512 * 1024 ** 2, Math.ceil(weightBytes * 0.02));
  const workloadBytes = workloadMemory(options);
  const required = weightBytes + runtimeOverhead + workloadBytes;
  const reasons: string[] = [];
  const confidence = options.workload?.source === "measured"
    ? "measured"
    : options.workload?.source === "architecture"
      ? "architecture"
      : capacity === undefined
        ? "unknown"
        : "artifact-only";
  if (capacity === undefined) {
    return {
      status: "unknown",
      confidence,
      weight_bytes: weightBytes,
      runtime_overhead_bytes: runtimeOverhead,
      workload_bytes: workloadBytes,
      required_device_bytes: required,
      reasons: ["No usable accelerator or unified-memory capacity was supplied."]
    };
  }
  const headroom = reservedHeadroom(capacity, options);
  const usable = Math.max(0, capacity - headroom);
  const remaining = capacity - required;
  if (required <= usable) {
    reasons.push(`Estimated device use leaves ${formatGiB(remaining)} GiB before the reserved headroom boundary.`);
    return fitResult("fits", confidence, capacity, usable, weightBytes, runtimeOverhead, workloadBytes, required, remaining, reasons);
  }
  const deficit = Math.max(0, required - usable);
  const hostAvailable = hostCapacity(resources);
  const maximumOffload = options.maximum_host_offload_bytes ?? hostAvailable;
  if (options.allow_host_offload && resources.memory_topology === "discrete" && deficit > 0) {
    if (
      hostAvailable !== undefined &&
      maximumOffload !== undefined &&
      deficit <= Math.min(hostAvailable, maximumOffload)
    ) {
      reasons.push(`The route requires approximately ${formatGiB(deficit)} GiB of host offload.`);
      return {
        ...fitResult("host-offload", confidence, capacity, usable, weightBytes, runtimeOverhead, workloadBytes, required, remaining, reasons),
        host_offload_bytes: deficit
      };
    }
    if (
      hostAvailable === undefined
      && options.allow_unknown_host_offload
      && (maximumOffload === undefined || deficit <= maximumOffload)
    ) {
      reasons.push(
        `The configured offload route needs approximately ${formatGiB(deficit)} GiB of host memory; runtime host capacity has not been observed.`
      );
      return {
        ...fitResult("unknown", "unknown", capacity, usable, weightBytes, runtimeOverhead, workloadBytes, required, remaining, reasons),
        host_offload_bytes: deficit
      };
    }
  }
  if (required <= capacity) {
    reasons.push(`The variant fits nominal capacity but leaves less than the ${formatGiB(headroom)} GiB reserve.`);
    return fitResult("tight", confidence, capacity, usable, weightBytes, runtimeOverhead, workloadBytes, required, remaining, reasons);
  }
  reasons.push(`Estimated device use exceeds the usable device pool by ${formatGiB(deficit)} GiB.`);
  return fitResult("does-not-fit", confidence, capacity, usable, weightBytes, runtimeOverhead, workloadBytes, required, remaining, reasons);
}

export function planModelSet(catalog: ModelCatalogSnapshot, options: PlanModelSetOptions): ModelSetPlan {
  const selected: ModelPlanSelection[] = [];
  const skipped: ModelPlanSkip[] = [];
  const floor = typeof options.quality_floor === "number"
    ? options.quality_floor
    : QUALITY_SCORES[options.quality_floor ?? "deployment"];
  const maximumModels = options.max_models
    ?? (options.engine === "sglang" || options.engine === "vllm" ? 1 : Number.POSITIVE_INFINITY);
  const storageCapacity = options.max_staged_bytes ?? options.resources.storage?.available_bytes ?? options.resources.storage?.total_bytes ?? Number.POSITIVE_INFINITY;
  let stagedBytes = 0;
  const hints = normalizeHints(options.hints);
  if (options.workload) validateWorkload(options.workload);
  const ordered = options.models.map((request, index) => ({ request, index })).sort((left, right) =>
    requestUtility(catalog, right.request, hints) - requestUtility(catalog, left.request, hints) || left.index - right.index
  );
  for (const { request } of ordered) {
    if (request.workload) validateWorkload(request.workload);
    if (selected.length >= maximumModels) {
      skipped.push(skip(request, "model-limit", [`The deployment is limited to ${maximumModels} selected models.`]));
      continue;
    }
    let candidates: ResolvedModelVariant[];
    try { candidates = variantCandidates(catalog, request, options, floor); }
    catch (error) {
      skipped.push(skip(request, "no-compatible-variant", [message(error)]));
      continue;
    }
    if (!candidates.length) {
      skipped.push(skip(request, "no-compatible-variant", [`No ${options.engine} variant satisfies the quantization floor.`]));
      continue;
    }
    const capabilityCandidates = candidates.filter((variant) => !missingModelCapabilities(variant, hints).length);
    if (!capabilityCandidates.length) {
      skipped.push(skip(request, "missing-capability", [
        `The model does not provide required capabilities: ${hints.required_capabilities?.join(", ") ?? "unknown"}.`
      ]));
      continue;
    }
    const attempted: string[] = [];
    const workloadRequest = request.workload ?? options.workload;
    const baseFit = mergeFit(options.fit, request.fit);
    const desiredFit = workloadRequest ? fitForWorkload(baseFit, workloadRequest) : baseFit;
    let choice: { variant: ResolvedModelVariant; fit: VariantFitEstimate; workload?: WorkloadTuningResult } | undefined;
    for (const variant of capabilityCandidates) {
      const missing = missingCapabilities(variant, options.resources);
      if (missing.length) {
        attempted.push(`${variant.quant}: missing ${missing.join(", ")}`);
        continue;
      }
      const fit = estimateVariantFit(variant, options.resources, desiredFit);
      attempted.push(`${variant.quant}: ${fit.status}`);
      if (acceptableFit(fit, desiredFit, options.accept_tight)) {
        choice = { variant, fit };
        break;
      }
    }
    if (!choice && workloadRequest) {
      for (const variant of capabilityCandidates) {
        if (missingCapabilities(variant, options.resources).length) continue;
        const workload = tuneWorkloadToFit(variant, options.resources, workloadRequest, omitWorkload(baseFit));
        if (!workload.fits) {
          attempted.push(`${variant.quant}: minimum workload does not fit`);
          continue;
        }
        const fit = estimateVariantFit(variant, options.resources, fitForWorkload(baseFit, {
          ...workloadRequest,
          desired_context_tokens: workload.context_tokens,
          desired_concurrency: workload.concurrency
        }));
        if (acceptableFit(fit, baseFit, options.accept_tight)) {
          choice = { variant, fit, workload };
          attempted.push(`${variant.quant}: ${workload.reason}`);
          break;
        }
      }
    }
    if (!choice) {
      skipped.push(skip(request, "insufficient-memory", attempted));
      continue;
    }
    if (stagedBytes + choice.variant.artifact_bytes > storageCapacity) {
      skipped.push(skip(request, "storage-budget", [
        `${choice.variant.quant} needs ${choice.variant.artifact_bytes} artifact bytes; ${Math.max(0, storageCapacity - stagedBytes)} remain.`
      ]));
      continue;
    }
    const preferredQuant = preferredVariant(catalog, request, options).quant;
    const quantChanged = choice.variant.quant !== preferredQuant;
    selected.push({
      model_id: choice.variant.model_id,
      preferred_quant: preferredQuant,
      ...(request.quant ? { requested_quant: request.quant } : {}),
      selected: choice.variant,
      fit: choice.fit,
      quant_changed: quantChanged,
      ...(workloadRequest ? { workload_request: structuredClone(workloadRequest) } : {}),
      ...(choice.workload ? { workload: choice.workload } : {}),
      reason: quantChanged
        ? `${preferredQuant} did not meet the resource policy; selected ${choice.variant.quant}.`
        : `${choice.variant.quant} meets the resource policy.`
    });
    stagedBytes += choice.variant.artifact_bytes;
  }
  const requiredSkipped = skipped.some((entry) => entry.required);
  return {
    schema_version: "prefer.model-plan.v1",
    engine: options.engine,
    resources: structuredClone(options.resources),
    selected,
    skipped,
    capabilities: [...new Set(selected.flatMap((entry) => entry.selected.capabilities))].sort(),
    staged_artifact_bytes: stagedBytes,
    complete: !requiredSkipped,
    ...(Object.keys(hints).length ? { hints } : {})
  };
}

/** Convert a generated engine deployment's existing model or bundle members
 * into planner requests. Bundle members are optional by default; single-model
 * deployments remain required. A deployment quant is a starting point, not an
 * exact lock, so constrained hardware may choose a smaller published lane. */
export function modelRequestsFromDeployment(value: unknown): ModelPlanRequest[] {
  if (!isObject(value) || !Array.isArray(value.models)) return [];
  const bundle = value.kind === "bundle"
    || String(value.id ?? "").endsWith("/general")
    || (value.models.length > 1 && value.kind !== "single-model");
  const result = new Map<string, ModelPlanRequest>();
  const total = value.models.length;
  for (const [index, raw] of value.models.entries()) {
    if (!isObject(raw)) continue;
    const modelId = firstString(raw.request_model_id, raw.model_slug, raw.profile_id);
    if (!modelId || result.has(modelId)) continue;
    const preferredQuant = firstString(raw.quant_slug, raw.quant);
    const configuredOffload = hasConfiguredHostOffload(raw) || hasConfiguredHostOffload(value);
    result.set(modelId, {
      model_id: modelId,
      ...(preferredQuant ? { preferred_quant: preferredQuant } : {}),
      required: !bundle,
      priority: total - index,
      ...(configuredOffload ? {
        fit: {
          allow_host_offload: true,
          allow_unknown_host_offload: true
        }
      } : {})
    });
  }
  return [...result.values()];
}

export function tuneWorkloadToFit(
  variant: ResolvedModelVariant,
  resources: ResourceProfile,
  request: WorkloadTuningRequest,
  options: Omit<VariantFitOptions, "workload"> = {}
): WorkloadTuningResult {
  if (!Number.isFinite(request.bytes_per_token) || request.bytes_per_token <= 0) {
    throw new Error("bytes_per_token must be greater than zero");
  }
  const desiredContext = positive(request.desired_context_tokens, "desired_context_tokens");
  const desiredConcurrency = positive(request.desired_concurrency, "desired_concurrency");
  const minimumContext = positive(request.minimum_context_tokens ?? 1, "minimum_context_tokens");
  const minimumConcurrency = positive(request.minimum_concurrency ?? 1, "minimum_concurrency");
  const capacity = acceleratorCapacity(resources, options.allow_multi_gpu ?? true);
  if (capacity === undefined) return {
    fits: false,
    context_tokens: 0,
    concurrency: 0,
    aggregate_token_capacity: 0,
    changed: true,
    reason: "No usable device capacity is known."
  };
  const weightBytes = options.device_weight_bytes ?? variant.artifact_bytes;
  const runtimeOverhead = options.runtime_overhead_bytes ?? Math.max(512 * 1024 ** 2, Math.ceil(weightBytes * 0.02));
  const headroom = reservedHeadroom(capacity, options);
  const tokenBudgetBytes = capacity - headroom - weightBytes - runtimeOverhead - (request.fixed_device_bytes ?? 0);
  const aggregateCapacity = Math.max(0, Math.floor(tokenBudgetBytes / request.bytes_per_token));
  const desiredTotal = desiredContext * desiredConcurrency;
  if (desiredTotal <= aggregateCapacity) return {
    fits: true,
    context_tokens: desiredContext,
    concurrency: desiredConcurrency,
    aggregate_token_capacity: aggregateCapacity,
    changed: false,
    reason: "The requested context and concurrency fit the estimated token pool."
  };
  let context = desiredContext;
  let concurrency = desiredConcurrency;
  if ((request.priority ?? "context") === "context") {
    concurrency = Math.min(desiredConcurrency, Math.floor(aggregateCapacity / desiredContext));
    concurrency = Math.max(minimumConcurrency, concurrency);
    context = Math.min(desiredContext, Math.floor(aggregateCapacity / concurrency));
  } else {
    context = Math.min(desiredContext, Math.floor(aggregateCapacity / desiredConcurrency));
    context = Math.max(minimumContext, context);
    concurrency = Math.min(desiredConcurrency, Math.floor(aggregateCapacity / context));
  }
  const fits = context >= minimumContext && concurrency >= minimumConcurrency && context * concurrency <= aggregateCapacity;
  return {
    fits,
    context_tokens: fits ? context : 0,
    concurrency: fits ? concurrency : 0,
    aggregate_token_capacity: aggregateCapacity,
    changed: true,
    reason: fits
      ? `Adjusted to ${concurrency} request slot(s) at ${context} tokens each.`
      : "The minimum context and concurrency do not fit the estimated token pool."
  };
}

function variantCandidates(
  catalog: ModelCatalogSnapshot,
  request: ModelPlanRequest,
  options: PlanModelSetOptions,
  floor: number
): ResolvedModelVariant[] {
  const preferred = preferredVariant(catalog, request, options);
  if (request.quant) return [preferred];
  const bias = options.hints?.quant_bias ?? "balanced";
  const preferredScore = quantQuality(preferred.quant).score;
  const variants = listModelVariants(catalog, request.model_id, options.engine)
    .filter((variant) => request.repository
      ? variant.repository === request.repository
      : bias === "balanced"
        ? variant.repository === preferred.repository || variant.artifact_bytes < preferred.artifact_bytes
        : true)
    .filter((variant) => options.use_nvfp4 || variant.quant === preferred.quant || !variant.quant.toLowerCase().includes("nvfp4"))
    .filter((variant) => {
      const score = quantQuality(variant.quant).score;
      return variant.quant === preferred.quant || (
        score >= floor && (bias !== "balanced" || preferredScore === 0 || score <= preferredScore)
      );
    })
    .sort((left, right) => {
      if (bias === "capacity") {
        return left.artifact_bytes - right.artifact_bytes || quantQuality(right.quant).score - quantQuality(left.quant).score;
      }
      if (bias === "quality") {
        return quantQuality(right.quant).score - quantQuality(left.quant).score || left.artifact_bytes - right.artifact_bytes;
      }
      if (left.repository === preferred.repository && right.repository !== preferred.repository) return -1;
      if (right.repository === preferred.repository && left.repository !== preferred.repository) return 1;
      return quantQuality(right.quant).score - quantQuality(left.quant).score || right.artifact_bytes - left.artifact_bytes;
    });
  const deduped = new Map<string, ResolvedModelVariant>();
  if (bias === "balanced") deduped.set(`${preferred.repository}@${preferred.quant}`, preferred);
  for (const variant of variants) deduped.set(`${variant.repository}@${variant.quant}`, variant);
  if (!deduped.has(`${preferred.repository}@${preferred.quant}`)) {
    deduped.set(`${preferred.repository}@${preferred.quant}`, preferred);
  }
  return [...deduped.values()];
}

function preferredVariant(catalog: ModelCatalogSnapshot, request: ModelPlanRequest, options: PlanModelSetOptions): ResolvedModelVariant {
  return resolveModelVariant(catalog, request.model_id, {
    engine: options.engine,
    ...(request.repository ? { repository: request.repository } : {}),
    ...(request.quant ?? request.preferred_quant ? { quant: (request.quant ?? request.preferred_quant)! } : {}),
    useNvfp4: options.use_nvfp4,
    overrides: request.overrides
  });
}

function missingCapabilities(variant: ResolvedModelVariant, resources: ResourceProfile): string[] {
  const normalized = variant.quant.toLowerCase().replaceAll("_", "-");
  const required: string[] = [];
  if (normalized.includes("nvfp4")) required.push("nvfp4");
  if (normalized === "fp8" && (variant.engine === "sglang" || variant.engine === "vllm")) required.push("fp8");
  return required.filter((capability) => !resources.capabilities.includes(capability));
}

function missingModelCapabilities(variant: ResolvedModelVariant, hints: ModelSelectionHints): string[] {
  return (hints.required_capabilities ?? []).filter((capability) => !variant.capabilities.includes(capability));
}

function requestUtility(catalog: ModelCatalogSnapshot, request: ModelPlanRequest, hints: ModelSelectionHints): number {
  let modelId: string;
  try { modelId = resolveCatalogModelId(catalog, request.model_id); }
  catch { return request.priority ?? 0; }
  const model = catalog.models[modelId]!;
  const capabilities = new Set(model.capabilities ?? []);
  const preferredRoles = new Set(model.profile?.roles?.preferred ?? []);
  const capableRoles = new Set(model.profile?.roles?.capable ?? []);
  const avoidRoles = new Set(model.profile?.roles?.avoid ?? []);
  let score = request.priority ?? 0;
  for (const capability of hints.preferred_capabilities ?? []) if (capabilities.has(capability)) score += 100;
  for (const role of hints.preferred_roles ?? []) {
    if (preferredRoles.has(role)) score += 80;
    else if (capableRoles.has(role)) score += 40;
    if (avoidRoles.has(role)) score -= 80;
  }
  const speedImportance = hints.speed_importance ?? 0;
  if (speedImportance > 0) {
    if (request.speed_score !== undefined && (!Number.isFinite(request.speed_score) || request.speed_score < 0 || request.speed_score > 100)) {
      throw new Error(`${request.model_id} speed_score must be between 0 and 100`);
    }
    const activeParameters = model.profile?.architecture?.active_parameters_b;
    const inferredSpeed = typeof activeParameters === "number" && activeParameters > 0
      ? 100 / (1 + Math.log2(1 + activeParameters))
      : 0;
    score += speedImportance * (request.speed_score ?? inferredSpeed);
  }
  const qualityImportance = hints.quality_importance ?? 0;
  if (qualityImportance > 0 && request.quality_score !== undefined) {
    if (!Number.isFinite(request.quality_score) || request.quality_score < 0 || request.quality_score > 100) {
      throw new Error(`${request.model_id} quality_score must be between 0 and 100`);
    }
    score += qualityImportance * request.quality_score;
  }
  return score;
}

function normalizeHints(value: ModelSelectionHints | undefined): ModelSelectionHints {
  if (!value) return {};
  if (value.speed_importance !== undefined && (
    !Number.isFinite(value.speed_importance) || value.speed_importance < 0 || value.speed_importance > 1
  )) throw new Error("speed_importance must be between 0 and 1");
  if (value.quality_importance !== undefined && (
    !Number.isFinite(value.quality_importance) || value.quality_importance < 0 || value.quality_importance > 1
  )) throw new Error("quality_importance must be between 0 and 1");
  if (value.quant_bias && !["quality", "balanced", "capacity"].includes(value.quant_bias)) {
    throw new Error("quant_bias must be quality, balanced, or capacity");
  }
  return {
    ...(value.required_capabilities?.length ? { required_capabilities: uniqueStrings(value.required_capabilities) } : {}),
    ...(value.preferred_capabilities?.length ? { preferred_capabilities: uniqueStrings(value.preferred_capabilities) } : {}),
    ...(value.preferred_roles?.length ? { preferred_roles: uniqueStrings(value.preferred_roles) } : {}),
    ...(value.speed_importance !== undefined ? { speed_importance: value.speed_importance } : {}),
    ...(value.quality_importance !== undefined ? { quality_importance: value.quality_importance } : {}),
    ...(value.quant_bias ? { quant_bias: value.quant_bias } : {})
  };
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function validateWorkload(value: WorkloadTuningRequest): void {
  positive(value.desired_context_tokens, "desired_context_tokens");
  positive(value.desired_concurrency, "desired_concurrency");
  positive(value.minimum_context_tokens ?? 1, "minimum_context_tokens");
  positive(value.minimum_concurrency ?? 1, "minimum_concurrency");
  if (!Number.isFinite(value.bytes_per_token) || value.bytes_per_token <= 0) {
    throw new Error("bytes_per_token must be greater than zero");
  }
  if (value.fixed_device_bytes !== undefined && (!Number.isFinite(value.fixed_device_bytes) || value.fixed_device_bytes < 0)) {
    throw new Error("fixed_device_bytes must be non-negative");
  }
  if ((value.minimum_context_tokens ?? 1) > value.desired_context_tokens) {
    throw new Error("minimum_context_tokens may not exceed desired_context_tokens");
  }
  if ((value.minimum_concurrency ?? 1) > value.desired_concurrency) {
    throw new Error("minimum_concurrency may not exceed desired_concurrency");
  }
}

function acceleratorCapacity(resources: ResourceProfile, allowMultiGpu: boolean): number | undefined {
  if (resources.memory_topology === "unified") {
    const unified = resources.unified_memory?.available_bytes ?? resources.unified_memory?.total_bytes;
    const host = resources.host_memory?.available_bytes ?? resources.host_memory?.total_bytes;
    const accelerator = resources.accelerators
      .map((entry) => entry.available_bytes ?? entry.total_bytes)
      .filter((entry): entry is number => entry !== undefined)
      .reduce<number | undefined>((minimum, entry) => minimum === undefined ? entry : Math.min(minimum, entry), undefined);
    const observations = [unified, host, accelerator].filter((entry): entry is number => entry !== undefined);
    return observations.length ? Math.min(...observations) : undefined;
  }
  if (resources.memory_topology === "host" && !resources.accelerators.length) {
    return resources.host_memory?.available_bytes ?? resources.host_memory?.total_bytes;
  }
  const deviceCapacities = resources.accelerators
    .map((entry) => entry.available_bytes ?? entry.total_bytes)
    .filter((entry): entry is number => entry !== undefined);
  if (!deviceCapacities.length) return undefined;
  return allowMultiGpu ? deviceCapacities.reduce((total, entry) => total + entry, 0) : Math.max(...deviceCapacities);
}

function hostCapacity(resources: ResourceProfile): number | undefined {
  return resources.host_memory?.available_bytes ?? resources.host_memory?.total_bytes;
}

function workloadMemory(options: VariantFitOptions): number {
  const workload = options.workload;
  if (!workload) return 0;
  const fixed = workload.fixed_device_bytes ?? 0;
  const perToken = workload.bytes_per_token ?? 0;
  const context = workload.context_tokens ?? 0;
  const concurrency = workload.concurrency ?? 1;
  return fixed + perToken * context * concurrency;
}

function reservedHeadroom(capacity: number, options: VariantFitOptions): number {
  const fraction = options.headroom_fraction ?? DEFAULT_HEADROOM_FRACTION;
  const minimum = options.minimum_headroom_bytes ?? DEFAULT_MINIMUM_HEADROOM_BYTES;
  const maximum = options.maximum_headroom_bytes ?? DEFAULT_MAXIMUM_HEADROOM_BYTES;
  if (!Number.isFinite(fraction) || fraction < 0 || fraction > 1) {
    throw new Error("headroom_fraction must be between 0 and 1");
  }
  for (const [label, value] of [["minimum_headroom_bytes", minimum], ["maximum_headroom_bytes", maximum]] as const) {
    if (!Number.isFinite(value) || value < 0) throw new Error(`${label} must be non-negative`);
  }
  if (minimum > maximum) throw new Error("minimum_headroom_bytes may not exceed maximum_headroom_bytes");
  return Math.min(capacity, Math.max(minimum, Math.min(maximum, Math.floor(capacity * fraction))));
}

function acceptableFit(fit: VariantFitEstimate, options: VariantFitOptions, acceptTight = false): boolean {
  return fit.status === "fits"
    || fit.status === "host-offload"
    || (acceptTight && fit.status === "tight")
    || (
      fit.status === "unknown"
      && fit.host_offload_bytes !== undefined
      && options.allow_unknown_host_offload === true
    );
}

function hasConfiguredHostOffload(value: Record<string, unknown>): boolean {
  const settings = isObject(value.settings) ? value.settings : undefined;
  if (settings && Number(settings["n-cpu-moe"] ?? 0) > 0) return true;
  const server = isObject(value.server) ? value.server : undefined;
  if (server && Number(server.cpu_offload_gb ?? 0) > 0) return true;
  const residency = isObject(value.residency) ? value.residency : undefined;
  const offload = residency && isObject(residency.offload) ? residency.offload : undefined;
  if (!offload) return false;
  if (offload.enabled === true) return true;
  return typeof offload.components === "string"
    ? offload.components.trim().length > 0
    : Array.isArray(offload.components) && offload.components.length > 0;
}

function fitResult(
  status: VariantFitEstimate["status"],
  confidence: VariantFitEstimate["confidence"],
  capacity: number,
  usable: number,
  weight: number,
  runtime: number,
  workload: number,
  required: number,
  remaining: number,
  reasons: string[]
): VariantFitEstimate {
  return {
    status,
    confidence,
    capacity_bytes: capacity,
    usable_capacity_bytes: usable,
    weight_bytes: weight,
    runtime_overhead_bytes: runtime,
    workload_bytes: workload,
    required_device_bytes: required,
    remaining_device_bytes: remaining,
    reasons
  };
}

function mergeFit(base: VariantFitOptions | undefined, exact: VariantFitOptions | undefined): VariantFitOptions {
  return {
    ...base,
    ...exact,
    ...(base?.workload || exact?.workload ? { workload: { ...base?.workload, ...exact?.workload } } : {})
  };
}

function fitForWorkload(base: VariantFitOptions, workload: WorkloadTuningRequest): VariantFitOptions {
  const fixed = workload.fixed_device_bytes ?? base.workload?.fixed_device_bytes;
  const source = workload.source ?? base.workload?.source;
  return {
    ...base,
    workload: {
      ...(base.workload ?? {}),
      ...(fixed !== undefined ? { fixed_device_bytes: fixed } : {}),
      bytes_per_token: workload.bytes_per_token,
      context_tokens: workload.desired_context_tokens,
      concurrency: workload.desired_concurrency,
      ...(source ? { source } : {})
    }
  };
}

function omitWorkload(value: VariantFitOptions): Omit<VariantFitOptions, "workload"> {
  const { workload: _workload, ...result } = value;
  return result;
}

function skip(request: ModelPlanRequest, reason: ModelPlanSkip["reason"], details: string[]): ModelPlanSkip {
  return { model_id: request.model_id, required: request.required ?? false, reason, details };
}

function tierForScore(score: number): QuantQualityTier {
  if (score >= 100) return "reference";
  if (score >= 90) return "near-lossless";
  if (score >= 75) return "high";
  if (score >= 55) return "deployment";
  if (score >= 35) return "compromise";
  if (score >= 20) return "fit-floor";
  return "extreme";
}

function positive(value: number, label: string): number {
  if (!Number.isInteger(value) || value <= 0) throw new Error(`${label} must be a positive integer`);
  return value;
}

function formatGiB(bytes: number): string { return (bytes / GIB).toFixed(2); }
function message(error: unknown): string { return error instanceof Error ? error.message : String(error); }
function firstString(...values: unknown[]): string | undefined {
  return values.find((value): value is string => typeof value === "string" && value.length > 0);
}
