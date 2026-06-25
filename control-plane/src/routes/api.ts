import type { FastifyInstance } from "fastify";
import { z } from "zod";
import type { CapacityProvider, ReservationRepository, TargetStatusRepository } from "../domain/interfaces.js";
import { Reconciler } from "../reconciler/Reconciler.js";
import { ModelCatalog } from "../services/ModelCatalog.js";
import { ReservationService } from "../services/ReservationService.js";
import { TrafficKeepaliveService } from "../services/TrafficKeepaliveService.js";
import { requireUser, reservationJson, sendError, targetJson } from "../utils/http.js";

export function registerApiRoutes(
  app: FastifyInstance,
  catalog: ModelCatalog,
  reservations: ReservationRepository,
  statuses: TargetStatusRepository,
  reservationService: ReservationService,
  trafficKeepalive: TrafficKeepaliveService,
  reconciler: Reconciler,
  capacityProvider: CapacityProvider
) {
  app.get("/healthz", async () => ({ ok: true }));
  app.get("/api/models", async () => ({ models: catalog.listModels() }));

  app.post("/api/reservations", async (request, reply) => {
    try {
      const body = z.object({ modelIds: z.array(z.string()), durationMinutes: z.number() }).parse(request.body);
      const reservation = await reservationService.createForUser(requireUser(request), body);
      return reply.code(201).send(reservationJson(reservation, statuses.list()));
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.get("/api/reservations/:id", async (request, reply) => reservationEndpoint(request, reply, reservationService, statuses));
  app.get("/api/reservations/:id/status", async (request, reply) => reservationEndpoint(request, reply, reservationService, statuses));

  app.post("/api/reservations/:id/done", async (request, reply) => {
    try {
      const { id } = z.object({ id: z.string() }).parse(request.params);
      const reservation = await reservationService.markDone(id, requireUser(request));
      return reservationJson(reservation, statuses.list());
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/reservations/:id/extend", async (request, reply) => {
    try {
      const { id } = z.object({ id: z.string() }).parse(request.params);
      const { durationMinutes } = z.object({ durationMinutes: z.number() }).parse(request.body);
      const reservation = await reservationService.extend(id, requireUser(request), durationMinutes);
      return reservationJson(reservation, statuses.list());
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.get("/api/status", async () => statusPayload(catalog, reservations, statuses));
  app.get("/api/admin/reservations", async () => ({ reservations: (await reservations.list()).map((reservation) => reservationJson(reservation, statuses.list())) }));
  app.get("/api/admin/targets", async () => ({ capacityTargets: await targetsPayload(catalog, reservations, statuses) }));
  app.get("/api/admin/status", async () => statusPayload(catalog, reservations, statuses));

  app.post("/api/admin/targets/:id/reconcile", async (request, reply) => {
    try {
      const { id } = z.object({ id: z.string() }).parse(request.params);
      await reconciler.reconcileTarget(id);
      return { ok: true };
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/admin/targets/:id/force-stop", async (request, reply) => {
    try {
      const { id } = z.object({ id: z.string() }).parse(request.params);
      const target = catalog.getTarget(id);
      if (!target) throw new Error("Target not found");
      await capacityProvider.forceStopTarget(target);
      statuses.set({ targetId: id, desired: "off", observed: "stopped", message: "Force stopped", lastCheckedAt: new Date() });
      return { ok: true };
    } catch (error) {
      return sendError(reply, error);
    }
  });

  app.post("/api/internal/traffic", async (request, reply) => {
    try {
      const body = z.object({ targetId: z.string(), modelIds: z.array(z.string()).default([]) }).parse(request.body);
      const target = catalog.getTarget(body.targetId);
      if (!target) throw new Error("Target not found");
      return { recorded: await trafficKeepalive.recordTraffic(target, body.modelIds) };
    } catch (error) {
      return sendError(reply, error);
    }
  });
}

async function reservationEndpoint(request: { params: unknown }, reply: { code: (code: number) => { send: (body: unknown) => unknown } }, service: ReservationService, statuses: TargetStatusRepository) {
  try {
    const { id } = z.object({ id: z.string() }).parse(request.params);
    const reservation = await service.getOwned(id, requireUser(request as never));
    return reservationJson(reservation, statuses.list());
  } catch (error) {
    return sendError(reply as never, error, 404);
  }
}

async function statusPayload(catalog: ModelCatalog, reservations: ReservationRepository, statuses: TargetStatusRepository) {
  const allReservations = await reservations.list();
  return {
    reservations: allReservations.map((reservation) => reservationJson(reservation, statuses.list())),
    activeReservations: (await reservations.listActive(new Date())).map((reservation) => reservationJson(reservation, statuses.list())),
    capacityTargets: await targetsPayload(catalog, reservations, statuses)
  };
}

async function targetsPayload(catalog: ModelCatalog, reservations: ReservationRepository, statuses: TargetStatusRepository) {
  const active = await reservations.listActive(new Date());
  return catalog.listTargets().map((target) =>
    targetJson(
      target,
      statuses.get(target.id),
      Array.from(new Set(active.filter((reservation) => reservation.targetIds.includes(target.id)).map((reservation) => reservation.username)))
    )
  );
}
