import { arch, cpus, freemem, totalmem } from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type {
  AcceleratorResource,
  HardwareProfileCatalog,
  HardwareProfileSource,
  MemoryResource,
  MemoryTopology,
  ResourceProfile,
  RuntimeResourceObservation
} from "./types.js";
import { isObject, readJson, requireObject, requireString } from "./utils.js";

const GIB = 1024 ** 3;
const MIB = 1024 ** 2;
const execFileAsync = promisify(execFile);
const DERIVED_RESOURCE_CAPABILITIES = new Set([
  "gpu", "cpu", "multi-gpu", "unified-memory", "discrete-vram", "host-memory",
  "cuda", "rocm", "bf16", "fp8", "nvfp4"
]);

export interface DetectRuntimeResourcesOptions {
  base?: ResourceProfile;
  runNvidiaSmi?: (() => Promise<string>) | undefined;
  runRocmSmi?: (() => Promise<string>) | undefined;
  runNvidiaCudaVersion?: (() => Promise<string>) | undefined;
}

const HARDWARE_PROFILE_RECORD_FIELDS = new Set(["provider", "hardware", "compatibility"]);
const HARDWARE_PROFILE_FIELDS = new Set([
  "provider_sku",
  "provider_gpu_type_id",
  "gpu_slug",
  "gpu_name",
  "accelerator_vendor",
  "gpu_count",
  "vram_gb_each",
  "architecture",
  "compute_capability",
  "vcpu",
  "host_ram_gb",
  "local_nvme_gb",
  "observed_vcpu",
  "observed_host_ram_gb",
  "advertised_hourly_usd_per_gpu",
  "pricing_observed_on",
  "pricing_reference"
]);
const HARDWARE_COMPATIBILITY_FIELDS = new Set([
  "container_runtime",
  "cuda_runtime_majors",
  "cuda_compatibility_observed_on",
  "cuda_compatibility_reference",
  "model_storage",
  "provisioning_api",
  "minimum_host_ram_gb",
  "minimum_volume_gb"
]);

export function validateHardwareProfileCatalog(value: unknown): asserts value is HardwareProfileCatalog {
  const catalog = requireObject(value, "hardware profile catalog");
  if (catalog.schema_version !== "prefer.hardware-profile-catalog.v1") {
    throw new Error("hardware profile catalog schema is incompatible");
  }
  const profiles = requireObject(catalog.profiles, "hardware profile catalog profiles");
  if (!Object.keys(profiles).length) throw new Error("hardware profile catalog is empty");
  for (const [id, raw] of Object.entries(profiles)) {
    if (!/^(aws|runpod)\/[a-z0-9][a-z0-9./-]*$/u.test(id)) {
      throw new Error(`invalid provider hardware profile id ${id}`);
    }
    const profile = requireObject(raw, `hardware profile ${id}`);
    for (const field of Object.keys(profile)) {
      if (!HARDWARE_PROFILE_RECORD_FIELDS.has(field)) {
        throw new Error(`hardware profile ${id} contains unsupported field ${field}`);
      }
    }
    const provider = requireString(profile.provider, `hardware profile ${id} provider`);
    if (provider !== "aws" && provider !== "runpod") {
      throw new Error(`hardware profile ${id} must use provider aws or runpod`);
    }
    if (!id.startsWith(`${provider}/`)) throw new Error(`hardware profile ${id} provider does not match its id`);
    const hardware = requireObject(profile.hardware, `hardware profile ${id} hardware`);
    for (const field of Object.keys(hardware)) {
      if (!HARDWARE_PROFILE_FIELDS.has(field)) {
        throw new Error(`hardware profile ${id} contains unsupported hardware field ${field}`);
      }
    }
    if (!Number.isInteger(hardware.gpu_count) || Number(hardware.gpu_count) < 1) {
      throw new Error(`hardware profile ${id} must declare a positive gpu_count`);
    }
    if (typeof hardware.vram_gb_each !== "number" || hardware.vram_gb_each <= 0) {
      throw new Error(`hardware profile ${id} must declare positive vram_gb_each`);
    }
    const vendor = hardware.accelerator_vendor;
    if (vendor !== undefined && vendor !== "nvidia" && vendor !== "amd") {
      throw new Error(`hardware profile ${id} has an invalid accelerator vendor`);
    }
    const compute = stringValue(hardware.compute_capability);
    if ((vendor === "amd" && compute?.startsWith("sm_")) || (vendor === "nvidia" && compute?.startsWith("gfx"))) {
      throw new Error(`hardware profile ${id} mixes accelerator vendors`);
    }
    if (profile.compatibility !== undefined) {
      const compatibility = requireObject(profile.compatibility, `hardware profile ${id} compatibility`);
      for (const field of Object.keys(compatibility)) {
        if (!HARDWARE_COMPATIBILITY_FIELDS.has(field)) {
          throw new Error(`hardware profile ${id} contains unsupported compatibility field ${field}`);
        }
      }
      if (vendor === "amd" && compatibility.container_runtime === "nvidia") {
        throw new Error(`hardware profile ${id} mixes accelerator vendors`);
      }
      if (compatibility.cuda_runtime_majors !== undefined) {
        const majors = compatibility.cuda_runtime_majors;
        if (!Array.isArray(majors) || !majors.length || new Set(majors).size !== majors.length || majors.some((major) => major !== 12 && major !== 13) || acceleratorVendor(hardware, compatibility) !== "nvidia"
          || !/^\d{4}-\d{2}-\d{2}$/u.test(String(compatibility.cuda_compatibility_observed_on ?? ""))
          || !/^https:\/\//u.test(String(compatibility.cuda_compatibility_reference ?? ""))) {
          throw new Error(`hardware profile ${id} has invalid CUDA runtime compatibility`);
        }
      }
    }
  }
}

export async function readHardwareProfileCatalog(path: string): Promise<HardwareProfileCatalog> {
  const value = await readJson(path);
  validateHardwareProfileCatalog(value);
  return value;
}

export function resolveHardwareProfile(
  catalog: HardwareProfileCatalog,
  id: string,
  observation?: RuntimeResourceObservation
): ResourceProfile {
  validateHardwareProfileCatalog(catalog);
  const profile = catalog.profiles[id] as HardwareProfileSource | undefined;
  if (!profile) throw new Error(`unknown provider hardware profile ${id}`);
  return normalizeDeploymentResources(profile, observation);
}

export function normalizeDeploymentResources(
  value: unknown,
  observation?: RuntimeResourceObservation
): ResourceProfile {
  const deployment = isObject(value) ? value : {};
  if (deployment.schema_version === "prefer.resources.v1") {
    return observation
      ? mergeRuntimeResources(deployment as unknown as ResourceProfile, observation)
      : structuredClone(deployment as unknown as ResourceProfile);
  }
  const hardware = isObject(deployment.hardware) ? deployment.hardware : deployment;
  const compatibility = isObject(deployment.compatibility) ? deployment.compatibility : {};
  const provider = stringValue(deployment.provider) ?? stringValue(hardware.provider);
  const providerSku = stringValue(hardware.provider_sku) ?? stringValue(hardware.host_shape);
  const count = positiveInteger(hardware.gpu_count) ?? 0;
  const totalEach = bytesFromGiB(hardware.vram_gb_each) ?? bytesFromGiB(hardware.vram_gb);
  const topology = memoryTopology(hardware, count);
  const acceleratorCapabilities = deriveAcceleratorCapabilities(hardware, compatibility);
  const vendor = acceleratorVendor(hardware, compatibility);
  const accelerators: AcceleratorResource[] = Array.from({ length: count }, (_, index) => ({
    ...(count > 1 ? { id: `deployment-gpu-${index}` } : {}),
    ...(vendor ? { vendor } : {}),
    ...(stringValue(hardware.gpu_slug) ? { slug: stringValue(hardware.gpu_slug)! } : {}),
    ...(stringValue(hardware.gpu_id) ? { canonical_id: stringValue(hardware.gpu_id)! } : {}),
    ...(stringValue(hardware.provider_gpu_type_id) ? { provider_id: stringValue(hardware.provider_gpu_type_id)! } : {}),
    ...(stringValue(hardware.gpu_name) ?? stringValue(hardware.gpu_type_id)
      ? { name: (stringValue(hardware.gpu_name) ?? stringValue(hardware.gpu_type_id))! }
      : {}),
    ...(stringValue(hardware.architecture) ? { architecture: stringValue(hardware.architecture)! } : {}),
    ...(stringValue(hardware.compute_capability) ?? stringValue(compatibility.minimum_compute_capability)
      ? { compute_capability: (stringValue(hardware.compute_capability) ?? stringValue(compatibility.minimum_compute_capability))! }
      : {}),
    ...(totalEach !== undefined ? { total_bytes: totalEach } : {}),
    capabilities: [...acceleratorCapabilities]
  }));
  const unifiedTotal = bytesFromGiB(hardware.unified_memory_gb) ?? (topology === "unified" ? totalEach : undefined);
  const hostTotal = bytesFromGiB(hardware.host_ram_gb) ?? bytesFromGiB(hardware.observed_host_ram_gb);
  const storageTotal = bytesFromGiB(hardware.local_nvme_gb);
  const logicalCores = positiveInteger(hardware.vcpu) ?? positiveInteger(hardware.observed_vcpu);
  const profile: ResourceProfile = {
    schema_version: "prefer.resources.v1",
    source: "deployment",
    ...(provider ? { provider } : {}),
    ...(providerSku ? { provider_sku: providerSku } : {}),
    memory_topology: topology,
    accelerators,
    ...(unifiedTotal !== undefined ? { unified_memory: { total_bytes: unifiedTotal } } : {}),
    ...(hostTotal !== undefined ? { host_memory: { total_bytes: hostTotal } } : {}),
    ...(logicalCores !== undefined ? { cpu: { logical_cores: logicalCores } } : {}),
    ...(storageTotal !== undefined ? { storage: { total_bytes: storageTotal, kind: "local" } } : {}),
    capabilities: deriveProfileCapabilities(topology, accelerators, hardware, compatibility)
  };
  return observation ? mergeRuntimeResources(profile, observation) : profile;
}

export function mergeRuntimeResources(
  base: ResourceProfile,
  observation: RuntimeResourceObservation
): ResourceProfile {
  const acceleratorObservationSupplied = observation.accelerators !== undefined;
  const observedAccelerators = observation.accelerators?.map(normalizeAccelerator);
  const accelerators = acceleratorObservationSupplied
    ? (observedAccelerators ?? []).map((observed, index) => mergeAccelerator(base.accelerators[index], observed))
    : base.accelerators.map((entry) => structuredClone(entry));
  const topology = observation.unified_memory
    ? "unified"
    : acceleratorObservationSupplied
      ? accelerators.length
        ? base.memory_topology === "unified" ? "unified" : "discrete"
        : "host"
      : base.memory_topology;
  const unifiedMemory = mergeMemory(base.unified_memory, observation.unified_memory);
  const hostMemory = mergeMemory(base.host_memory, observation.host_memory);
  const baseCapabilities = acceleratorObservationSupplied
    ? base.capabilities.filter((capability) => !DERIVED_RESOURCE_CAPABILITIES.has(capability))
    : base.capabilities;
  const structuralCapabilities = [
    accelerators.length ? "gpu" : "cpu",
    ...(accelerators.length > 1 ? ["multi-gpu"] : []),
    topology === "unified" ? "unified-memory" : topology === "discrete" ? "discrete-vram" : "host-memory"
  ];
  const result: ResourceProfile = {
    ...structuredClone(base),
    source: "merged",
    memory_topology: topology,
    accelerators,
    ...(unifiedMemory ? { unified_memory: unifiedMemory } : {}),
    ...(hostMemory ? { host_memory: hostMemory } : {}),
    ...(observation.cpu ? { cpu: { ...base.cpu, ...observation.cpu } } : {}),
    ...(observation.storage ? { storage: { ...base.storage, ...observation.storage } } : {}),
    ...(observation.runtime_compatibility ? { runtime_compatibility: observation.runtime_compatibility } : {}),
    capabilities: [...new Set([
      ...baseCapabilities,
      ...structuralCapabilities,
      ...(observation.capabilities ?? []),
      ...accelerators.flatMap((entry) => entry.capabilities)
    ])].sort()
  };
  if (!unifiedMemory) delete result.unified_memory;
  if (!hostMemory) delete result.host_memory;
  if (acceleratorObservationSupplied && !observation.runtime_compatibility) delete result.runtime_compatibility;
  return result;
}

export async function detectRuntimeResources(
  options: DetectRuntimeResourcesOptions = {}
): Promise<ResourceProfile> {
  let accelerators: AcceleratorResource[] = [];
  let acceleratorProbeSucceeded = false;
  try {
    accelerators = parseNvidiaSmi(await (options.runNvidiaSmi ?? defaultNvidiaSmi)());
    acceleratorProbeSucceeded = true;
  }
  catch { /* Try ROCm before falling back to host-only resources. */ }
  if (!acceleratorProbeSucceeded) {
    try {
      accelerators = parseRocmSmi(await (options.runRocmSmi ?? defaultRocmSmi)());
      acceleratorProbeSucceeded = true;
    }
    catch { /* CPU-only and restricted containers are valid resource probes. */ }
  }
  let runtimeCompatibility: RuntimeResourceObservation["runtime_compatibility"];
  if (accelerators.some((entry) => entry.vendor === "nvidia")) {
    try { runtimeCompatibility = { cuda_max_major: parseNvidiaCudaVersion(await (options.runNvidiaCudaVersion ?? defaultNvidiaCudaVersion)()) }; }
    catch { /* Driver compatibility remains unknown until the controller observes it. */ }
  }
  const observation: RuntimeResourceObservation = {
    ...(acceleratorProbeSucceeded ? { accelerators } : {}),
    ...(runtimeCompatibility ? { runtime_compatibility: runtimeCompatibility } : {}),
    host_memory: { total_bytes: totalmem(), available_bytes: freemem() },
    cpu: {
      architecture: arch(),
      logical_cores: cpus().length,
      ...(cpus()[0]?.model ? { model: cpus()[0]!.model } : {})
    },
    ...(acceleratorProbeSucceeded ? { capabilities: accelerators.length ? ["gpu"] : ["cpu"] } : {})
  };
  if (options.base) return mergeRuntimeResources(options.base, observation);
  return {
    schema_version: "prefer.resources.v1",
    source: "runtime",
    memory_topology: accelerators.length ? "discrete" : "host",
    accelerators,
    ...(runtimeCompatibility ? { runtime_compatibility: runtimeCompatibility } : {}),
    host_memory: observation.host_memory!,
    cpu: observation.cpu!,
    capabilities: [...new Set([
      accelerators.length ? "gpu" : "cpu",
      ...(observation.capabilities ?? []),
      ...accelerators.flatMap((entry) => entry.capabilities)
    ])].sort()
  };
}

export function parseNvidiaSmi(output: string): AcceleratorResource[] {
  return output.split(/\r?\n/u).map((line) => line.trim()).filter(Boolean).map((line, index) => {
    const fields = line.split(",").map((field) => field.trim());
    if (fields.length < 4) throw new Error(`invalid nvidia-smi row ${index + 1}`);
    const [name, id, totalMiB, freeMiB, computeCapability] = fields;
    const total = Number(totalMiB);
    const available = Number(freeMiB);
    if (!name || !Number.isFinite(total) || !Number.isFinite(available)) {
      throw new Error(`invalid nvidia-smi memory row ${index + 1}`);
    }
    const hardware: Record<string, unknown> = {
      gpu_name: name,
      ...(computeCapability ? { compute_capability: `sm_${computeCapability.replace(".", "")}` } : {})
    };
    return {
      ...(id ? { id } : {}),
      vendor: "nvidia",
      name,
      total_bytes: Math.round(total * MIB),
      available_bytes: Math.round(available * MIB),
      ...(computeCapability ? { compute_capability: `sm_${computeCapability.replace(".", "")}` } : {}),
      capabilities: [...deriveAcceleratorCapabilities(hardware, {})]
    };
  });
}

export function parseRocmSmi(output: string): AcceleratorResource[] {
  const parsed: unknown = JSON.parse(output);
  if (!isObject(parsed)) throw new Error("rocm-smi must return a JSON object");
  return Object.entries(parsed).map(([id, value]) => {
    if (!/^card\d+$/u.test(id) || !isObject(value)) throw new Error(`invalid rocm-smi GPU record ${id}`);
    const total = Number(value["VRAM Total Memory (B)"]);
    const used = Number(value["VRAM Total Used Memory (B)"]);
    if (!Number.isSafeInteger(total) || total <= 0 || !Number.isSafeInteger(used) || used < 0 || used > total) {
      throw new Error(`invalid rocm-smi VRAM for ${id}`);
    }
    const name = stringValue(value["Card series"]) ?? stringValue(value["Card model"]) ?? id;
    const gfx = stringValue(value["GPU architecture"]);
    return { id, vendor: "amd", name,
      ...(gfx && /^gfx[0-9a-z]+$/u.test(gfx) ? { compute_capability: gfx } : {}),
      total_bytes: total, available_bytes: total - used, capabilities: ["rocm"] };
  });
}

function memoryTopology(hardware: Record<string, unknown>, count: number): MemoryTopology {
  const explicit = stringValue(hardware.memory_topology) ?? stringValue(hardware.memory_model);
  if (explicit === "unified" || explicit === "discrete" || explicit === "host") return explicit;
  if (hardware.unified_memory === true || hardware.unified_memory_gb !== undefined) return "unified";
  return count > 0 ? "discrete" : "host";
}

function deriveProfileCapabilities(
  topology: MemoryTopology,
  accelerators: AcceleratorResource[],
  hardware: Record<string, unknown>,
  compatibility: Record<string, unknown>
): string[] {
  return [...new Set([
    ...(accelerators.length ? ["gpu"] : ["cpu"]),
    ...(accelerators.length > 1 ? ["multi-gpu"] : []),
    topology === "unified" ? "unified-memory" : topology === "discrete" ? "discrete-vram" : "host-memory",
    ...stringArray(hardware.capabilities),
    ...stringArray(compatibility.capabilities),
    ...accelerators.flatMap((entry) => entry.capabilities)
  ])].sort();
}

function acceleratorVendor(hardware: Record<string, unknown>, compatibility: Record<string, unknown>): "nvidia" | "amd" | undefined {
  const explicit = stringValue(hardware.accelerator_vendor);
  if (explicit === "nvidia" || explicit === "amd") return explicit;
  const compute = stringValue(hardware.compute_capability) ?? "";
  if (compute.startsWith("sm_")) return "nvidia";
  if (compute.startsWith("gfx")) return "amd";
  if (compatibility.container_runtime === "nvidia") return "nvidia";
  const identity = [hardware.gpu_name, hardware.gpu_slug, hardware.architecture]
    .filter((part): part is string => typeof part === "string").join(" ").toLowerCase();
  if (/\b(?:nvidia|rtx|blackwell|hopper|ampere|tesla|l40s)\b/u.test(identity)) return "nvidia";
  return undefined;
}

function deriveAcceleratorCapabilities(hardware: Record<string, unknown>, compatibility: Record<string, unknown>): Set<string> {
  const result = new Set<string>([...stringArray(hardware.capabilities), ...stringArray(compatibility.capabilities)]);
  const vendor = acceleratorVendor(hardware, compatibility);
  const architecture = (stringValue(hardware.architecture) ?? stringValue(hardware.gpu_name) ?? "").toLowerCase();
  const compute = stringValue(hardware.compute_capability) ?? stringValue(compatibility.minimum_compute_capability) ?? "";
  const computeNumber = Number(compute.toLowerCase().replace(/^sm_/u, ""));
  if (vendor === "nvidia" && (architecture.includes("blackwell") || computeNumber >= 100)) {
    result.add("bf16"); result.add("fp8"); result.add("nvfp4");
  } else if (vendor === "nvidia" && (architecture.includes("hopper") || (computeNumber >= 89 && computeNumber < 100))) {
    result.add("bf16"); result.add("fp8");
  } else if (vendor === "nvidia" && (architecture.includes("ampere") || (computeNumber >= 80 && computeNumber < 89))) {
    result.add("bf16");
  }
  if (vendor === "nvidia") result.add("cuda");
  if (vendor === "amd") result.add("rocm");
  return result;
}

function mergeAccelerator(base: AcceleratorResource | undefined, observed: AcceleratorResource): AcceleratorResource {
  const preserveBase = base !== undefined && acceleratorIdentityMatches(base, observed);
  return {
    ...(preserveBase ? base : {}),
    ...observed,
    capabilities: [...new Set([...(preserveBase ? base.capabilities : []), ...observed.capabilities])].sort()
  };
}

function acceleratorIdentityMatches(base: AcceleratorResource, observed: AcceleratorResource): boolean {
  if (base.compute_capability && observed.compute_capability) return base.compute_capability === observed.compute_capability;
  if (base.name && observed.name) {
    const left = base.name.toLowerCase().replaceAll(/[^a-z0-9]/gu, "");
    const right = observed.name.toLowerCase().replaceAll(/[^a-z0-9]/gu, "");
    return left.includes(right) || right.includes(left);
  }
  return true;
}

function normalizeAccelerator(value: AcceleratorResource): AcceleratorResource {
  return { ...structuredClone(value), capabilities: [...new Set(value.capabilities ?? [])].sort() };
}

function mergeMemory(base: MemoryResource | undefined, observed: MemoryResource | undefined): MemoryResource | undefined {
  if (!base && !observed) return undefined;
  return { ...base, ...observed };
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function positiveInteger(value: unknown): number | undefined {
  return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : undefined;
}

function bytesFromGiB(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? Math.round(value * GIB) : undefined;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];
}

export function parseNvidiaCudaVersion(output: string): number {
  const match = /CUDA Version:\s*(\d+)(?:\.\d+)?/u.exec(output);
  if (!match) throw new Error("nvidia-smi did not report a CUDA driver API version");
  const major = Number(match[1]);
  if (!Number.isSafeInteger(major) || major < 1) throw new Error("nvidia-smi CUDA version is invalid");
  return major;
}

async function defaultNvidiaCudaVersion(): Promise<string> {
  const { stdout } = await execFileAsync("nvidia-smi", [], { encoding: "utf8", timeout: 10_000 });
  return stdout;
}

async function defaultRocmSmi(): Promise<string> {
  const { stdout } = await execFileAsync("rocm-smi", ["--showproductname", "--showmeminfo", "vram", "--json"], {
    encoding: "utf8", timeout: 10_000
  });
  return stdout;
}

async function defaultNvidiaSmi(): Promise<string> {
  const { stdout } = await execFileAsync("nvidia-smi", [
    "--query-gpu=name,uuid,memory.total,memory.free,compute_cap",
    "--format=csv,noheader,nounits"
  ], { encoding: "utf8", timeout: 10_000 });
  return stdout;
}
