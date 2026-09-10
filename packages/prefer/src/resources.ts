import { arch, cpus, freemem, totalmem } from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type {
  AcceleratorResource,
  MemoryResource,
  MemoryTopology,
  ResourceProfile,
  RuntimeResourceObservation
} from "./types.js";
import { isObject } from "./utils.js";

const GIB = 1024 ** 3;
const MIB = 1024 ** 2;
const execFileAsync = promisify(execFile);
const DERIVED_RESOURCE_CAPABILITIES = new Set([
  "gpu", "cpu", "multi-gpu", "unified-memory", "discrete-vram", "host-memory",
  "cuda", "bf16", "fp8", "nvfp4"
]);

export interface DetectRuntimeResourcesOptions {
  base?: ResourceProfile;
  runNvidiaSmi?: (() => Promise<string>) | undefined;
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
  const accelerators: AcceleratorResource[] = Array.from({ length: count }, (_, index) => ({
    ...(count > 1 ? { id: `deployment-gpu-${index}` } : {}),
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
    capabilities: [...new Set([
      ...baseCapabilities,
      ...structuralCapabilities,
      ...(observation.capabilities ?? []),
      ...accelerators.flatMap((entry) => entry.capabilities)
    ])].sort()
  };
  if (!unifiedMemory) delete result.unified_memory;
  if (!hostMemory) delete result.host_memory;
  return result;
}

export async function detectRuntimeResources(
  options: DetectRuntimeResourcesOptions = {}
): Promise<ResourceProfile> {
  const run = options.runNvidiaSmi ?? defaultNvidiaSmi;
  let accelerators: AcceleratorResource[] = [];
  let acceleratorProbeSucceeded = false;
  try {
    accelerators = parseNvidiaSmi(await run());
    acceleratorProbeSucceeded = true;
  }
  catch { /* CPU-only and restricted containers are valid resource probes. */ }
  const observation: RuntimeResourceObservation = {
    ...(acceleratorProbeSucceeded ? { accelerators } : {}),
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
      name,
      total_bytes: Math.round(total * MIB),
      available_bytes: Math.round(available * MIB),
      ...(computeCapability ? { compute_capability: `sm_${computeCapability.replace(".", "")}` } : {}),
      capabilities: [...deriveAcceleratorCapabilities(hardware, {})]
    };
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

function deriveAcceleratorCapabilities(hardware: Record<string, unknown>, compatibility: Record<string, unknown>): Set<string> {
  const result = new Set<string>([...stringArray(hardware.capabilities), ...stringArray(compatibility.capabilities)]);
  const architecture = (stringValue(hardware.architecture) ?? stringValue(hardware.gpu_name) ?? "").toLowerCase();
  const compute = stringValue(hardware.compute_capability) ?? stringValue(compatibility.minimum_compute_capability) ?? "";
  const computeNumber = Number(compute.toLowerCase().replace(/^sm_/u, ""));
  if (architecture.includes("blackwell") || computeNumber >= 100) {
    result.add("bf16"); result.add("fp8"); result.add("nvfp4");
  } else if (architecture.includes("hopper") || (computeNumber >= 89 && computeNumber < 100)) {
    result.add("bf16"); result.add("fp8");
  } else if (architecture.includes("ampere") || (computeNumber >= 80 && computeNumber < 89)) {
    result.add("bf16");
  }
  if (compute || architecture) result.add("cuda");
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

async function defaultNvidiaSmi(): Promise<string> {
  const { stdout } = await execFileAsync("nvidia-smi", [
    "--query-gpu=name,uuid,memory.total,memory.free,compute_cap",
    "--format=csv,noheader,nounits"
  ], { encoding: "utf8", timeout: 10_000 });
  return stdout;
}
