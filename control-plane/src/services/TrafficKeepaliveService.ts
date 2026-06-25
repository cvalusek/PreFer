import type { ReservationRepository, TargetStatusRepository } from "../domain/interfaces.js";
import type { CapacityTarget } from "../domain/types.js";

export class TrafficKeepaliveService {
  constructor(
    private readonly repository: ReservationRepository,
    private readonly statuses: TargetStatusRepository
  ) {}

  async recordTraffic(target: CapacityTarget, modelIds: string[], now = new Date()): Promise<boolean> {
    const status = this.statuses.get(target.id);
    if (status?.observed === "failed") return false;

    const active = await this.repository.listActive(now);
    const hasRealReservation = active.some((reservation) => !reservation.synthetic && reservation.targetIds.includes(target.id));
    const alreadyHealthy = status?.observed === "healthy";
    if (!hasRealReservation && !alreadyHealthy) return false;

    const existing = active.find((reservation) => reservation.synthetic && reservation.username === "traffic" && reservation.targetIds.includes(target.id));
    const expiresAt = new Date(now.getTime() + 5 * 60_000);
    if (existing) {
      await this.repository.update(existing.id, { expiresAt, modelIds: Array.from(new Set([...existing.modelIds, ...modelIds])) });
    } else {
      await this.repository.create({
        username: "traffic",
        modelIds,
        targetIds: [target.id],
        createdAt: now,
        expiresAt,
        status: "active",
        synthetic: true
      });
    }
    return true;
  }
}
