import type { ReservationRepository } from "../domain/interfaces.js";
import type { AuthenticatedUser, Reservation } from "../domain/types.js";
import { ModelCatalog } from "./ModelCatalog.js";

const MAX_DURATION_MINUTES = 12 * 60;

export class ReservationService {
  constructor(
    private readonly repository: ReservationRepository,
    private readonly catalog: ModelCatalog
  ) {}

  async createForUser(user: AuthenticatedUser, input: { modelIds: string[]; durationMinutes: number }): Promise<Reservation> {
    this.validateInput(input);
    const modelIds = this.catalog.canonicalModelIds(input.modelIds);
    const now = new Date();
    const targets = this.catalog.targetsForModels(modelIds);
    return this.repository.create({
      username: user.username,
      modelIds,
      targetIds: targets.map((target) => target.id),
      createdAt: now,
      expiresAt: new Date(now.getTime() + input.durationMinutes * 60_000),
      status: "active"
    });
  }

  async getOwned(id: string, user: AuthenticatedUser): Promise<Reservation> {
    const reservation = await this.repository.get(id);
    if (!reservation) throw new Error("Reservation not found");
    if (!user.isAdmin && reservation.username !== user.username) throw new Error("Reservation not found");
    return reservation;
  }

  async markDone(id: string, user: AuthenticatedUser): Promise<Reservation> {
    await this.getOwned(id, user);
    return this.repository.update(id, { status: "done", endedAt: new Date() });
  }

  async extend(id: string, user: AuthenticatedUser, durationMinutes: number): Promise<Reservation> {
    if (!Number.isFinite(durationMinutes) || durationMinutes <= 0 || durationMinutes > MAX_DURATION_MINUTES) {
      throw new Error(`Duration must be between 1 and ${MAX_DURATION_MINUTES} minutes`);
    }
    const reservation = await this.getOwned(id, user);
    if (reservation.status !== "active") throw new Error("Only active reservations can be extended");
    return this.repository.update(id, {
      expiresAt: new Date(Math.max(Date.now(), reservation.expiresAt.getTime()) + durationMinutes * 60_000)
    });
  }

  private validateInput(input: { modelIds: string[]; durationMinutes: number }): void {
    this.catalog.validateModelIds(unique(input.modelIds));
    if (!Number.isFinite(input.durationMinutes) || input.durationMinutes <= 0 || input.durationMinutes > MAX_DURATION_MINUTES) {
      throw new Error(`Duration must be between 1 and ${MAX_DURATION_MINUTES} minutes`);
    }
  }
}

function unique(values: string[]): string[] {
  return Array.from(new Set(values));
}
