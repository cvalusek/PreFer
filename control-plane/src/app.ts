import cookie from "@fastify/cookie";
import formbody from "@fastify/formbody";
import swagger from "@fastify/swagger";
import swaggerUi from "@fastify/swagger-ui";
import Fastify from "fastify";
import { SharedPasswordAuthProvider } from "./auth/SharedPasswordAuthProvider.js";
import { AwsEcsAsgCapacityProvider } from "./capacity/AwsEcsAsgCapacityProvider.js";
import { CompositeCapacityProvider } from "./capacity/CompositeCapacityProvider.js";
import { DockerComposeCapacityProvider } from "./capacity/DockerComposeCapacityProvider.js";
import { FakeCapacityProvider } from "./capacity/FakeCapacityProvider.js";
import type { AppConfig, ModelDefinition } from "./domain/types.js";
import { LiteLlmSpendLogsTrafficSource } from "./litellm/LiteLlmSpendLogsTrafficSource.js";
import { LiteLlmBackendConfigSync, NoopBackendConfigSync } from "./litellm/LiteLlmBackendConfigSync.js";
import { HealthChecker } from "./reconciler/HealthChecker.js";
import { Reconciler } from "./reconciler/Reconciler.js";
import { InMemoryReservationRepository } from "./repository/InMemoryReservationRepository.js";
import { InMemoryTargetStatusRepository } from "./repository/InMemoryTargetStatusRepository.js";
import { registerApiRoutes } from "./routes/api.js";
import { registerUiRoutes } from "./routes/ui.js";
import { ModelCatalog } from "./services/ModelCatalog.js";
import { ReservationService } from "./services/ReservationService.js";
import { RuntimeModelDiscovery } from "./services/RuntimeModelDiscovery.js";
import { TrafficKeepaliveService } from "./services/TrafficKeepaliveService.js";
import { TrafficPoller } from "./services/TrafficPoller.js";

export async function buildApp(config: AppConfig, models: ModelDefinition[]) {
  const app = Fastify({ logger: true });
  const authProvider = new SharedPasswordAuthProvider(config.sharedPassword, config.adminUsers, config.cookieSecret);
  const catalog = new ModelCatalog(models, config.capacityTargets);
  const reservations = new InMemoryReservationRepository();
  const statuses = new InMemoryTargetStatusRepository();
  const capacityProvider =
    process.env.USE_FAKE_PROVIDER === "true"
      ? new FakeCapacityProvider()
      : new CompositeCapacityProvider({
          "aws-ecs": new AwsEcsAsgCapacityProvider(config.awsRegion),
          "docker-compose": new DockerComposeCapacityProvider()
        });
  const backendConfigSync = config.litellmApiBaseUrl && config.litellmApiKey ? new LiteLlmBackendConfigSync(config.litellmApiBaseUrl, config.litellmApiKey) : new NoopBackendConfigSync();
  const reservationService = new ReservationService(reservations, catalog);
  const trafficKeepalive = new TrafficKeepaliveService(reservations, statuses);
  const healthChecker = new HealthChecker(config.healthCheckTimeoutSeconds);
  const runtimeModelDiscovery = new RuntimeModelDiscovery(catalog);
  const trafficPoller =
    config.litellmApiBaseUrl && config.litellmApiKey && config.litellmTrafficPollSeconds > 0
      ? new TrafficPoller(new LiteLlmSpendLogsTrafficSource(config.litellmApiBaseUrl, config.litellmApiKey, config.litellmTrafficLookbackSeconds), catalog, trafficKeepalive)
      : undefined;
  const reconciler = new Reconciler(
    config.capacityTargets,
    reservations,
    statuses,
    capacityProvider,
    backendConfigSync,
    healthChecker,
    runtimeModelDiscovery,
    trafficPoller
  );

  await app.register(cookie);
  await app.register(formbody);
  await app.register(swagger, { openapi: { info: { title: "LLM Capacity Control Plane", version: "0.1.0" } } });
  await app.register(swaggerUi, { routePrefix: "/docs" });

  app.addHook("preHandler", async (request, reply) => {
    if (request.url === "/healthz" || request.url === "/login" || request.url.startsWith("/docs")) return;
    const user = await authProvider.authenticate({ headers: request.headers, cookies: request.cookies });
    if (!user) {
      if (request.url.startsWith("/api/")) return reply.code(401).send({ error: "Authentication required" });
      return reply.redirect("/login");
    }
    request.user = user;
  });

  registerApiRoutes(app, catalog, reservations, statuses, reservationService, trafficKeepalive, reconciler, capacityProvider);
  registerUiRoutes(app, config, authProvider, catalog, reservationService);

  const bootstrapRuntimeModels = async () => {
    for (const target of config.capacityTargets.filter((candidate) => candidate.modelDiscovery?.bootstrapOnStartup)) {
      try {
        await runtimeModelDiscovery.bootstrapTarget(target, capacityProvider, healthChecker);
        app.log.info({ targetId: target.id }, "runtime model discovery bootstrap complete");
      } catch (error) {
        app.log.warn({ targetId: target.id, error }, "runtime model discovery bootstrap failed");
      }
    }
  };

  return { app, reconciler, trafficPoller, bootstrapRuntimeModels };
}
