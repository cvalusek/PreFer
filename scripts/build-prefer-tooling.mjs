#!/usr/bin/env node
import { spawn } from "node:child_process";
import { cp, mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import {
  readModelCatalog,
  refreshModelCatalog,
  sha256,
  writeJsonAtomic
} from "../packages/prefer/dist/index.js";

const flags = parseFlags(process.argv.slice(2));
const commit = (optional(flags, "commit") ?? process.env.GITHUB_SHA ?? await gitRevision()).toLowerCase();
if (!/^[0-9a-f]{40}$/u.test(commit)) throw new Error("--commit must be a full source commit SHA");
const outputDir = resolve(optional(flags, "output-dir") ?? "build/prefer-tooling");
const catalogRoot = resolve(optional(flags, "catalog-root") ?? "catalog");
const fallbackPath = optional(flags, "fallback");
const sourceDate = optional(flags, "source-date") ?? await gitCommitTime(commit);
const sourceClock = () => new Date(sourceDate);
if (!Number.isFinite(sourceClock().getTime())) throw new Error("source date is invalid");
if (outputDir === resolve(".") || outputDir === dirname(outputDir)) {
  throw new Error("tooling output directory may not be the repository or filesystem root");
}

const previous = fallbackPath ? await readModelCatalog(resolve(fallbackPath)) : undefined;

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });

const refreshed = await refreshModelCatalog(catalogRoot, {
  ...(previous ? { previous } : {}),
  token: process.env.HF_TOKEN?.trim() || undefined,
  cacheDir: optional(flags, "hf-cache"),
  concurrency: Number(optional(flags, "concurrency") ?? "4"),
  now: sourceClock
});

const catalogPath = resolve(outputDir, "prefer-model-catalog.json");
await writeJsonAtomic(catalogPath, refreshed.catalog);
const schemaAssets = [
  ["catalog/model-catalog.schema.json", "prefer-model-catalog.schema.json"],
  ["catalog/model-catalog-extension.schema.json", "prefer-model-catalog-extension.schema.json"],
  ["catalog/resource-profile.schema.json", "prefer-resource-profile.schema.json"],
  ["catalog/model-plan.schema.json", "prefer-model-plan.schema.json"]
];
for (const [source, name] of schemaAssets) await copySchemaAsset(source, resolve(outputDir, name));

const cliPath = resolve(outputDir, "prefer.mjs");
await cp(resolve("packages/prefer/dist/prefer.mjs"), cliPath);
const installerPath = resolve(outputDir, "install-prefer-node.sh");
await cp(resolve("scripts/install-prefer-node.sh"), installerPath);

const packageStage = resolve(outputDir, ".package-stage");
await mkdir(resolve(packageStage, "dist"), { recursive: true });
await mkdir(resolve(packageStage, "schemas"), { recursive: true });
await cp(resolve("packages/prefer/dist"), resolve(packageStage, "dist"), { recursive: true });
await cp(resolve("packages/prefer/README.md"), resolve(packageStage, "README.md"));
await cp(resolve("packages/prefer/LICENSE"), resolve(packageStage, "LICENSE"));
for (const [source, name] of schemaAssets) await copySchemaAsset(source, resolve(packageStage, "schemas", name));
const packageJson = JSON.parse(await readFile(resolve("packages/prefer/package.json"), "utf8"));
packageJson.version = `0.0.0-g${commit.slice(0, 7)}`;
delete packageJson.scripts;
await writeFile(resolve(packageStage, "package.json"), `${JSON.stringify(packageJson, null, 2)}\n`, "utf8");
const packed = await npmPack(packageStage, outputDir);
const packagePath = resolve(outputDir, "prefer-inference-core.tgz");
await rename(resolve(outputDir, packed), packagePath);
await rm(packageStage, { recursive: true, force: true });

const assets = Object.fromEntries(await Promise.all([
  ["package", packagePath],
  ["cli", cliPath],
  ["model_catalog", catalogPath],
  ["model_catalog_schema", resolve(outputDir, "prefer-model-catalog.schema.json")],
  ["model_catalog_extension_schema", resolve(outputDir, "prefer-model-catalog-extension.schema.json")],
  ["resource_profile_schema", resolve(outputDir, "prefer-resource-profile.schema.json")],
  ["model_plan_schema", resolve(outputDir, "prefer-model-plan.schema.json")]
].map(async ([key, path]) => {
  const bytes = await readFile(path);
  return [key, { asset: basename(path), bytes: bytes.byteLength, sha256: sha256(bytes) }];
})));

const manifest = {
  schema_version: "prefer.tooling-build.v1",
  source_revision: commit,
  package_version: packageJson.version,
  generated_at: sourceClock().toISOString(),
  huggingface_refresh: refreshed.reused_previous ? "last-successful" : "live",
  catalog_fingerprint: refreshed.catalog.catalog_fingerprint,
  source_fingerprint: refreshed.catalog.source_fingerprint,
  distribution: {
    model_weights_embedded: false,
    metadata_only: true
  },
  assets
};
await writeJsonAtomic(resolve(outputDir, "prefer-tooling-build.json"), manifest);
for (const context of [
  "docker/llama-cpp",
  "docker/audio-cpp",
  "docker/stable-diffusion-cpp",
  "docker/sglang",
  "docker/vllm"
]) {
  const destination = resolve(context, ".prefer-tooling");
  await rm(destination, { recursive: true, force: true });
  await mkdir(destination, { recursive: true });
  for (const name of [
    "install-prefer-node.sh",
    "prefer.mjs",
    "prefer-model-catalog.json",
    "prefer-model-catalog.schema.json",
    "prefer-model-catalog-extension.schema.json",
    "prefer-resource-profile.schema.json",
    "prefer-model-plan.schema.json"
  ]) await cp(resolve(outputDir, name), resolve(destination, name));
}
process.stdout.write(`${JSON.stringify(manifest)}\n`);

function parseFlags(args) {
  const result = new Map();
  for (let index = 0; index < args.length; index += 1) {
    const raw = args[index];
    if (!raw?.startsWith("--")) throw new Error(`unexpected argument ${raw ?? ""}`);
    const equals = raw.indexOf("=");
    const key = raw.slice(2, equals === -1 ? undefined : equals);
    const value = equals === -1 ? args[++index] : raw.slice(equals + 1);
    if (!value || value.startsWith("--")) throw new Error(`--${key} requires a value`);
    if (result.has(key)) throw new Error(`--${key} may only be supplied once`);
    result.set(key, value);
  }
  return result;
}

function optional(flags, key) { return flags.get(key); }

async function gitRevision() {
  return await new Promise((accept, reject) => {
    const child = spawn("git", ["rev-parse", "HEAD"], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (chunk) => { stdout += chunk; });
    child.stderr.setEncoding("utf8").on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (code) => code === 0 ? accept(stdout.trim()) : reject(new Error(`git rev-parse failed (${code}): ${stderr.trim()}`)));
  });
}

async function gitCommitTime(revision) {
  return await new Promise((accept, reject) => {
    const child = spawn("git", ["show", "-s", "--format=%cI", revision], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (chunk) => { stdout += chunk; });
    child.stderr.setEncoding("utf8").on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (code) => code === 0 ? accept(stdout.trim()) : reject(new Error(`git show failed (${code}): ${stderr.trim()}`)));
  });
}

async function npmPack(directory, destination) {
  const npmCli = process.env.npm_execpath;
  const cache = process.env.NPM_CONFIG_CACHE || resolve(".npm-cache");
  const command = npmCli ? process.execPath : process.platform === "win32" ? "npm.cmd" : "npm";
  const args = npmCli
    ? [npmCli, "pack", directory, "--pack-destination", destination, "--cache", cache, "--json"]
    : ["pack", directory, "--pack-destination", destination, "--cache", cache, "--json"];
  const output = await new Promise((accept, reject) => {
    const child = spawn(command, args, {
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        npm_config_cache: cache
      }
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (chunk) => { stdout += chunk; });
    child.stderr.setEncoding("utf8").on("data", (chunk) => { stderr += chunk; });
    child.on("error", reject);
    child.on("close", (code) => code === 0 ? accept(stdout) : reject(new Error(`npm pack failed (${code}): ${stderr.trim()}`)));
  });
  const parsed = JSON.parse(output);
  const filename = parsed?.[0]?.filename;
  if (typeof filename !== "string" || !filename.endsWith(".tgz")) throw new Error("npm pack did not report its package filename");
  return filename;
}

async function copySchemaAsset(source, destination) {
  let contents = await readFile(resolve(source), "utf8");
  if (source === "catalog/model-plan.schema.json") {
    contents = contents.replace('"$ref": "resource-profile.schema.json"', '"$ref": "prefer-resource-profile.schema.json"');
  }
  await writeFile(destination, contents, "utf8");
}
