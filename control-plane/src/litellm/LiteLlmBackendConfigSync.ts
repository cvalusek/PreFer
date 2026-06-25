import type { BackendConfigSync } from "../domain/interfaces.js";
import type { CapacityTarget } from "../domain/types.js";

export class NoopBackendConfigSync implements BackendConfigSync {
  async syncTargetHealthy(_target: CapacityTarget): Promise<void> {}
  async markTargetUnavailable(_target: CapacityTarget): Promise<void> {}
}

export class LiteLlmBackendConfigSync implements BackendConfigSync {
  constructor(
    private readonly apiBaseUrl: string,
    private readonly apiKey: string
  ) {}

  async syncTargetHealthy(target: CapacityTarget): Promise<void> {
    if (!target.litellm) return;
    await fetch(`${this.apiBaseUrl.replace(/\/$/, "")}/backend/${encodeURIComponent(target.litellm.backendName)}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${this.apiKey}`
      },
      body: JSON.stringify({
        api_base: target.litellm.apiBaseUrl
      })
    });
  }

  async markTargetUnavailable(_target: CapacityTarget): Promise<void> {
    // TODO: Wire this to the exact LiteLLM admin API once the deployment chooses one.
  }
}
