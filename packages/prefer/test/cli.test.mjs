import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";
import { createRuntimeHandoff, encodeRuntimeHandoffBase64 } from "../dist/index.js";
import { sha256, stableStringify } from "../dist/utils.js";

const run = promisify(execFile);

test("the bundled standalone CLI starts without npm or TypeScript", async () => {
  const { stdout } = await run(process.execPath, [fileURLToPath(new URL("../dist/prefer.mjs", import.meta.url)), "help"]);
  assert.match(stdout, /PreFer catalog and release CLI/u);
  assert.match(stdout, /catalog extend/u);
});

test("the standalone CLI reads a runtime handoff from one base64 environment variable", async () => {
  const root = await mkdtemp(join(tmpdir(), "prefer-cli-handoff-"));
  try {
    const defaults = { schema_version: "prefer.model-defaults.v1" };
    const models = {};
    const repositories = {};
    const catalog = {
      schema_version: "prefer.model-catalog.v1",
      generated_at: "2026-09-10T00:00:00.000Z",
      source_fingerprint: sha256(stableStringify({ defaults, models })),
      catalog_fingerprint: sha256(stableStringify({ defaults, models, repositories })),
      defaults,
      models,
      repositories,
    };
    const variant = {
      model_id: "controller-model",
      family: "controller",
      display_name: "Controller Model",
      engine: "vllm",
      repository: "owner/model",
      repository_path: "/models/owner/model",
      revision: "a".repeat(40),
      quant: "bf16",
      files: ["config.json"],
      artifacts: [{
        repository: "owner/model",
        revision: "a".repeat(40),
        path: "config.json",
        size: 2,
        blob_oid: "b".repeat(40),
        local_path: "/models/owner/model/config.json",
      }],
      artifact_bytes: 2,
      capabilities: ["text-generation"],
      settings: {},
    };
    const handoff = createRuntimeHandoff(catalog, { engine: "vllm", models: [{ variant }] });
    const catalogPath = join(root, "catalog.json");
    await writeFile(catalogPath, JSON.stringify(catalog), "utf8");
    const cli = fileURLToPath(new URL("../dist/prefer.mjs", import.meta.url));
    const environment = {
      ...process.env,
      PREFER_ENGINE: "vllm",
      PREFER_MODEL_CATALOG: catalogPath,
      PREFER_RUNTIME_HANDOFF_BASE64: encodeRuntimeHandoffBase64(handoff),
    };
    const { stdout } = await run(process.execPath, [
      cli,
      "runtime",
      "validate",
      "--handoff-base64-env",
      "PREFER_RUNTIME_HANDOFF_BASE64",
    ], { env: environment });
    assert.equal(JSON.parse(stdout).handoff_fingerprint, handoff.handoff_fingerprint);

    await assert.rejects(
      run(process.execPath, [
        cli,
        "runtime",
        "validate",
        "--handoff",
        catalogPath,
        "--handoff-base64-env",
        "PREFER_RUNTIME_HANDOFF_BASE64",
      ], { env: environment }),
      /requires exactly one/u,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
