import type { CapacityProvider } from "../domain/interfaces.js";
import type { CapacityTarget } from "../domain/types.js";
import type { HealthChecker } from "../reconciler/HealthChecker.js";
import { ModelCatalog } from "./ModelCatalog.js";

interface OpenAiModelsResponse {
  data?: Array<{ id?: string }>;
}

export class RuntimeModelDiscovery {
  constructor(private readonly catalog: ModelCatalog) {}

  async refreshTarget(target: CapacityTarget): Promise<void> {
    const url = modelsUrlForTarget(target);
    if (!url) return;
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error(`Runtime models returned ${response.status}`);
    const body = (await response.json()) as OpenAiModelsResponse;
    const runtimeModelIds = (body.data ?? []).map((model) => model.id).filter((id): id is string => Boolean(id));
    this.catalog.recordRuntimeModels(target.id, runtimeModelIds);
  }

  async bootstrapTarget(target: CapacityTarget, capacityProvider: CapacityProvider, healthChecker: HealthChecker): Promise<void> {
    const timeoutMs = (target.modelDiscovery?.bootstrapTimeoutSeconds ?? 600) * 1000;
    const startedAt = Date.now();
    await capacityProvider.ensureTargetOn(target);
    try {
      while (Date.now() - startedAt < timeoutMs) {
        const health = await healthChecker.check(target);
        if (health.ok) {
          await this.refreshTarget(target);
          return;
        }
        await sleep(5000);
      }
      throw new Error(`Timed out waiting for ${target.id} runtime model discovery`);
    } finally {
      await capacityProvider.ensureTargetOff(target);
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function modelsUrlForTarget(target: CapacityTarget): string | undefined {
  if (target.litellm?.apiBaseUrl) {
    return `${target.litellm.apiBaseUrl.replace(/\/$/, "")}/models`;
  }
  try {
    const health = new URL(target.healthCheckUrl);
    return `${health.origin}/v1/models`;
  } catch {
    return undefined;
  }
}
