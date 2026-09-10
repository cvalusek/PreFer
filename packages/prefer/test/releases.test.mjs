import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { downloadPreferTooling, sha256 } from "../dist/index.js";

const REVISION = "c".repeat(40);
const TAG = `sha-${REVISION.slice(0, 7)}`;

test("release tooling resolves by channel and verifies every downloaded asset", async () => {
  const output = await mkdtemp(join(tmpdir(), "prefer-release-output-"));
  const cache = await mkdtemp(join(tmpdir(), "prefer-release-cache-"));
  try {
    const assets = {
      "prefer-inference-core.tgz": Buffer.from("package"),
      "prefer.mjs": Buffer.from("cli"),
      "prefer-model-catalog.json": Buffer.from("catalog"),
      "prefer-model-catalog.schema.json": Buffer.from("schema"),
      "prefer-model-catalog-extension.schema.json": Buffer.from("extension-schema"),
      "prefer-resource-profile.schema.json": Buffer.from("resource-schema"),
      "prefer-model-plan.schema.json": Buffer.from("plan-schema")
    };
    const manifest = {
      schema_version: "prefer.release.v1",
      release: {
        id: TAG,
        source_revision: REVISION,
        source_repository: "https://github.com/cvalusek/PreFer",
        source_url: `https://github.com/cvalusek/PreFer/commit/${REVISION}`,
        artifact_name: `prefer-release-${REVISION}`
      },
      distribution: {
        model_weights_embedded: false,
        models_stage_at_runtime: true,
        all_engine_images_share_release_revision: true
      },
      engines: {},
      tooling: {
        schema_version: "prefer.release-tooling.v1",
        package_version: `0.0.0-g${REVISION.slice(0, 7)}`,
        huggingface_refresh: "live",
        catalog_fingerprint: "d".repeat(64),
        source_fingerprint: "e".repeat(64),
        package: binding("prefer-inference-core.tgz", assets),
        cli: binding("prefer.mjs", assets),
        model_catalog: binding("prefer-model-catalog.json", assets),
        model_catalog_schema: binding("prefer-model-catalog.schema.json", assets),
        model_catalog_extension_schema: binding("prefer-model-catalog-extension.schema.json", assets),
        resource_profile_schema: binding("prefer-resource-profile.schema.json", assets),
        model_plan_schema: binding("prefer-model-plan.schema.json", assets)
      }
    };
    const manifestBytes = Buffer.from(JSON.stringify(manifest));
    const release = releaseResponse({ ...assets, "prefer-release.json": manifestBytes });
    const fetchedAssets = [];
    const fetch = async (url) => {
      if (url.startsWith("https://api.github.test/")) return jsonResponse([release]);
      const name = decodeURIComponent(new URL(url).pathname.split("/").at(-1));
      fetchedAssets.push(name);
      const bytes = name === "prefer-release.json" ? manifestBytes : assets[name];
      return new Response(bytes, { headers: { "content-length": String(bytes.byteLength) } });
    };
    const result = await downloadPreferTooling({
      repository: "cvalusek/PreFer",
      channel: "preview",
      outputDir: output,
      cacheDir: cache,
      apiBaseUrl: "https://api.github.test",
      fetch
    });
    assert.equal(result.release.revision, REVISION);
    assert.deepEqual(fetchedAssets.sort(), Object.keys({ ...assets, "prefer-release.json": manifestBytes }).sort());
    for (const [key, path] of Object.entries(result.files)) {
      assert.deepEqual(await readFile(path), assets[manifest.tooling[key].asset]);
    }
  } finally {
    await rm(output, { recursive: true, force: true });
    await rm(cache, { recursive: true, force: true });
  }
});

function binding(asset, values) {
  return { asset, bytes: values[asset].byteLength, sha256: sha256(values[asset]) };
}

function releaseResponse(values) {
  return {
    tag_name: TAG,
    target_commitish: REVISION,
    draft: false,
    prerelease: true,
    published_at: "2026-09-09T00:00:00.000Z",
    name: `PreFer ${TAG} (preview)`,
    assets: Object.entries(values).map(([name, bytes]) => ({
      name,
      state: "uploaded",
      size: bytes.byteLength,
      digest: `sha256:${sha256(bytes)}`,
      browser_download_url: `https://github.com/cvalusek/PreFer/releases/download/${TAG}/${name}`
    }))
  };
}

function jsonResponse(value) {
  const body = JSON.stringify(value);
  return new Response(body, { headers: { "content-type": "application/json", "content-length": String(Buffer.byteLength(body)) } });
}
