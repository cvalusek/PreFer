import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildApp } from "./app.js";
import { loadConfig } from "./config/loadConfig.js";

const appDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(appDir, "..", "..", "..");
const { config, models } = await loadConfig(repoRoot);
const { app, reconciler, trafficPoller, bootstrapRuntimeModels } = await buildApp(config, models);
await bootstrapRuntimeModels();
reconciler.start(config.reconcilerIntervalSeconds);
trafficPoller?.start(config.litellmTrafficPollSeconds);
await app.listen({ port: config.port, host: "0.0.0.0" });
