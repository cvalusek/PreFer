import { describe, expect, it } from "vitest";
import { FakeCapacityProvider } from "../capacity/FakeCapacityProvider.js";
import type { CapacityTarget, ModelDefinition } from "../domain/types.js";
import { NoopBackendConfigSync } from "../litellm/LiteLlmBackendConfigSync.js";
import { Reconciler } from "../reconciler/Reconciler.js";
import { InMemoryReservationRepository } from "../repository/InMemoryReservationRepository.js";
import { InMemoryTargetStatusRepository } from "../repository/InMemoryTargetStatusRepository.js";
import { ModelCatalog } from "../services/ModelCatalog.js";
import { ReservationService } from "../services/ReservationService.js";
import { TrafficKeepaliveService } from "../services/TrafficKeepaliveService.js";

const target: CapacityTarget = {
  id: "multiple-moe-96gb",
  displayName: "Multiple MoE 96GB",
  provider: "aws-ecs",
  modelIds: ["qwen", "gemma"],
  healthCheckUrl: "http://example.test/health"
};

const models: ModelDefinition[] = [
  { id: "qwen", displayName: "Qwen", aliases: ["qwen"], targetIds: [target.id] },
  { id: "gemma", displayName: "Gemma", aliases: ["gemma"], targetIds: [target.id] }
];

function harness() {
  const repository = new InMemoryReservationRepository();
  const statuses = new InMemoryTargetStatusRepository();
  const provider = new FakeCapacityProvider();
  const catalog = new ModelCatalog(models, [target]);
  const reservations = new ReservationService(repository, catalog);
  const reconciler = new Reconciler([target], repository, statuses, provider, new NoopBackendConfigSync());
  return { repository, statuses, provider, catalog, reservations, reconciler };
}

describe("reservation behavior", () => {
  it("expires old reservations", async () => {
    const { repository } = harness();
    await repository.create({ username: "clint", modelIds: ["qwen"], targetIds: [target.id], createdAt: new Date(0), expiresAt: new Date(1), status: "active" });
    await repository.expireReservations(new Date(2));
    expect((await repository.list())[0].status).toBe("expired");
  });

  it("keeps capacity on for overlapping reservations when one is done", async () => {
    const { reservations, reconciler, provider } = harness();
    const userA = { username: "alice", isAdmin: false };
    const userB = { username: "bob", isAdmin: false };
    const first = await reservations.createForUser(userA, { modelIds: ["qwen"], durationMinutes: 30 });
    await reservations.createForUser(userB, { modelIds: ["gemma"], durationMinutes: 30 });
    await reservations.markDone(first.id, userA);
    await reconciler.reconcile();
    expect(provider.desired.get(target.id)).toBe("on");
  });

  it("selecting multiple models from one target only turns on that target once", async () => {
    const { reservations, repository } = harness();
    await reservations.createForUser({ username: "clint", isAdmin: false }, { modelIds: ["qwen", "gemma"], durationMinutes: 30 });
    expect((await repository.list())[0].targetIds).toEqual([target.id]);
  });

  it("computes aggregate desired capacity from active reservations", async () => {
    const { reservations, reconciler, provider } = harness();
    await reservations.createForUser({ username: "clint", isAdmin: false }, { modelIds: ["qwen"], durationMinutes: 30 });
    await reconciler.reconcile();
    expect(provider.desired.get(target.id)).toBe("on");
  });

  it("marks active reservations failed when provider reports failure", async () => {
    const { reservations, reconciler, provider, repository } = harness();
    provider.statuses.set(target.id, { observed: "failed", message: "boom" });
    await reservations.createForUser({ username: "clint", isAdmin: false }, { modelIds: ["qwen"], durationMinutes: 30 });
    await reconciler.reconcile();
    expect((await repository.list())[0].status).toBe("failed");
  });
});

describe("traffic keepalive", () => {
  it("extends already healthy capacity with a synthetic reservation", async () => {
    const { repository, statuses } = harness();
    statuses.set({ targetId: target.id, desired: "on", observed: "healthy", message: "Ready" });
    const service = new TrafficKeepaliveService(repository, statuses);
    expect(await service.recordTraffic(target, ["qwen"], new Date())).toBe(true);
    expect((await repository.list())[0].username).toBe("traffic");
  });

  it("does not resurrect failed target by itself", async () => {
    const { repository, statuses } = harness();
    statuses.set({ targetId: target.id, desired: "on", observed: "failed", message: "boom" });
    const service = new TrafficKeepaliveService(repository, statuses);
    expect(await service.recordTraffic(target, ["qwen"], new Date())).toBe(false);
    expect(await repository.list()).toHaveLength(0);
  });
});
