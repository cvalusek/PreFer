import type { PreferReleaseManifest, ResourceProfile } from "./types.js";
import { isObject } from "./utils.js";

export interface ImageSelectionOptions {
  platform?: "linux/amd64" | "linux/arm64";
  backend?: "cuda" | "rocm" | "vulkan" | "cpu";
  variant?: string;
}

export interface SelectedRuntimeImage {
  engine: string;
  variant: string;
  tag: string;
  digest: string;
  reference: string;
  platform: string;
  backend: string;
  cuda_major?: number;
  /** Metadata candidate; driver ABI, model kernels, and APIs still require validation. */
  qualification: "metadata-candidate-only";
}

const ENGINE_KEYS: Record<string, string> = {
  "llama.cpp": "llama", "audio.cpp": "audio", "stable-diffusion.cpp": "image",
  sglang: "sglang", vllm: "vllm"
};

/** Select an immutable engine image before planning model/quant fit. Never infer driver versions from GPU names. */
export function resolveRuntimeImage(
  manifest: PreferReleaseManifest,
  engine: string,
  resources: ResourceProfile,
  options: ImageSelectionOptions = {}
): SelectedRuntimeImage {
  const platform = options.platform ?? "linux/amd64";
  const engineKey = ENGINE_KEYS[engine] ?? engine;
  const record = manifest.engines[engineKey];
  if (!isObject(record) || !isObject(record.images)) throw new Error(`release has no ${engine} images`);
  const images = record.images;
  if (resources.accelerators.some((gpu) =>
    (gpu.vendor === "amd" && (gpu.compute_capability?.startsWith("sm_") || gpu.capabilities.includes("cuda"))) ||
    (gpu.vendor === "nvidia" && (gpu.compute_capability?.startsWith("gfx") || gpu.capabilities.includes("rocm"))))) {
    throw new Error("accelerator vendor conflicts with observed architecture or capabilities");
  }
  const vendors = new Set(resources.accelerators.map((gpu) => gpu.vendor ??
    (gpu.compute_capability?.startsWith("sm_") || gpu.capabilities.includes("cuda") ? "nvidia"
      : gpu.compute_capability?.startsWith("gfx") || gpu.capabilities.includes("rocm") ? "amd" : "unknown")));
  if (vendors.size > 1) throw new Error("mixed accelerator vendors need separate resource profiles and runtime processes");
  const vendor = resources.accelerators.length ? [...vendors][0]! : "cpu";
  if (vendor === "unknown") throw new Error("accelerator vendor must be observed before selecting a runtime image");
  const hasCudaVariant = Object.values(images).some((entry) =>
    isObject(entry) && isObject(entry.accelerator) && entry.accelerator.backend === "cuda");
  if (vendor === "nvidia" && (options.backend === "cuda" || (!options.backend && hasCudaVariant))
    && resources.runtime_compatibility?.cuda_max_major === undefined) {
    throw new Error("NVIDIA host CUDA driver API version is unknown; observe the host driver before selecting an image");
  }
  const candidates: SelectedRuntimeImage[] = [];
  for (const [variant, raw] of Object.entries(images)) {
    if (options.variant && options.variant !== variant) continue;
    if (!isObject(raw) || !isObject(raw.accelerator) || !Array.isArray(raw.platforms) || !raw.platforms.includes(platform)) continue;
    const accelerator = raw.accelerator;
    const backend = accelerator.backend;
    if (typeof backend !== "string" || (options.backend && backend !== options.backend)) continue;
    if (backend === "cpu" && vendor !== "cpu" && options.backend !== "cpu") continue;
    if (backend !== "cpu" && vendor === "cpu") continue;
    if (accelerator.vendor !== "any" && accelerator.vendor !== vendor) continue;
    if (backend === "cuda") {
      const major = accelerator.cuda_major;
      if (typeof major !== "number" || major > (resources.runtime_compatibility?.cuda_max_major ?? 0)) continue;
    }
    const architectures = accelerator.gpu_architectures;
    if (architectures !== undefined) {
      if (!Array.isArray(architectures) ||
        !resources.accelerators.every((gpu) => gpu.compute_capability && architectures.includes(gpu.compute_capability))) continue;
    }
    if (typeof raw.reference !== "string" || typeof raw.digest !== "string" || typeof raw.tag !== "string" ||
      !/^sha256:[0-9a-f]{64}$/u.test(raw.digest) || !raw.reference.endsWith(`:${raw.tag}@${raw.digest}`)) {
      throw new Error(`release ${engine}/${variant} has no valid immutable image identity`);
    }
    candidates.push({ engine, variant, tag: raw.tag, digest: raw.digest, reference: raw.reference,
      platform, backend, ...(backend === "cuda" ? { cuda_major: accelerator.cuda_major as number } : {}),
      qualification: "metadata-candidate-only" });
  }
  const priority: Record<string, number> = { cuda: 4, rocm: 3, vulkan: 2, cpu: 1 };
  candidates.sort((a, b) => (priority[b.backend] ?? 0) - (priority[a.backend] ?? 0)
    || (b.cuda_major ?? 0) - (a.cuda_major ?? 0));
  if (!candidates.length) throw new Error(`no ${engine} image matches ${vendor} ${platform} and the observed driver/architecture`);
  return candidates[0]!;
}
