import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import type { PreferReleaseAsset, PreferReleaseManifest, PreferReleaseRecord } from "./types.js";
import { isObject, requireString, sha256, validateRepository } from "./utils.js";

const MAX_RELEASE_HISTORY_BYTES = 10 * 1024 * 1024;
const MAX_MANIFEST_BYTES = 2 * 1024 * 1024;
const MAX_TOOLING_ASSET_BYTES = 100 * 1024 * 1024;

export interface GitHubReleaseOptions {
  token?: string | undefined;
  fetch?: typeof fetch | undefined;
  apiBaseUrl?: string | undefined;
  timeoutMs?: number | undefined;
  cacheDir?: string | undefined;
}

export interface ResolveReleaseOptions extends GitHubReleaseOptions {
  repository: string;
  channel?: "stable" | "preview" | undefined;
  revision?: string | undefined;
}

export interface DownloadedPreferRelease {
  release: PreferReleaseRecord;
  manifest: PreferReleaseManifest;
}

export async function listPreferReleases(repositoryInput: string, options: GitHubReleaseOptions & { channel?: "stable" | "preview"; limit?: number } = {}): Promise<PreferReleaseRecord[]> {
  const repository = validateRepository(repositoryInput);
  const limit = options.limit ?? 20;
  if (!Number.isInteger(limit) || limit < 1 || limit > 30) throw new Error("release limit must be between 1 and 30");
  const base = (options.apiBaseUrl ?? "https://api.github.com").replace(/\/+$/u, "");
  const response = await githubFetch(`${base}/repos/${repository}/releases?per_page=30`, options);
  const raw = await responseJson(response, MAX_RELEASE_HISTORY_BYTES, "GitHub release history");
  if (!Array.isArray(raw)) throw new Error("GitHub release history is not an array");
  const releases = raw.flatMap((entry): PreferReleaseRecord[] => {
    if (!isObject(entry) || entry.draft !== false || typeof entry.prerelease !== "boolean") return [];
    const id = typeof entry.tag_name === "string" ? entry.tag_name : "";
    const revision = typeof entry.target_commitish === "string" ? entry.target_commitish.toLowerCase() : "";
    if (!/^sha-[0-9a-f]{7}$/u.test(id) || !/^[0-9a-f]{40}$/u.test(revision) || id !== `sha-${revision.slice(0, 7)}`) return [];
    const channel = entry.prerelease ? "preview" : "stable";
    if (options.channel && channel !== options.channel) return [];
    const published = typeof entry.published_at === "string" ? new Date(entry.published_at) : new Date(Number.NaN);
    if (!Number.isFinite(published.getTime())) return [];
    const assets: Record<string, PreferReleaseAsset> = {};
    if (Array.isArray(entry.assets)) {
      for (const rawAsset of entry.assets) {
        if (!isObject(rawAsset) || (rawAsset.state !== undefined && rawAsset.state !== "uploaded")) continue;
        const name = typeof rawAsset.name === "string" ? rawAsset.name : "";
        const url = typeof rawAsset.browser_download_url === "string" ? rawAsset.browser_download_url : "";
        if (!/^[a-z0-9][a-z0-9._-]{0,199}$/iu.test(name) || !validAssetUrl(url, repository, id, name)) continue;
        const size = typeof rawAsset.size === "number" && Number.isSafeInteger(rawAsset.size) && rawAsset.size >= 0 ? rawAsset.size : undefined;
        const digest = typeof rawAsset.digest === "string" && /^sha256:[0-9a-f]{64}$/u.test(rawAsset.digest) ? rawAsset.digest : undefined;
        assets[name] = { name, url, ...(size !== undefined ? { size } : {}), ...(digest ? { digest } : {}) };
      }
    }
    if (!assets["prefer-release.json"]) return [];
    return [{
      id,
      revision,
      channel,
      published_at: published.toISOString(),
      title: typeof entry.name === "string" && entry.name ? entry.name.slice(0, 160) : id,
      url: `https://github.com/${repository}/releases/tag/${id}`,
      assets
    }];
  });
  return releases.sort((left, right) => right.published_at.localeCompare(left.published_at)).slice(0, limit);
}

export async function resolvePreferRelease(options: ResolveReleaseOptions): Promise<DownloadedPreferRelease> {
  const repository = validateRepository(options.repository);
  let release: PreferReleaseRecord | undefined;
  if (options.revision) {
    const revision = options.revision.trim().toLowerCase();
    if (!/^[0-9a-f]{40}$/u.test(revision)) throw new Error("PreFer release revision must be a full commit SHA");
    const tag = `sha-${revision.slice(0, 7)}`;
    const base = (options.apiBaseUrl ?? "https://api.github.com").replace(/\/+$/u, "");
    const response = await githubFetch(`${base}/repos/${repository}/releases/tags/${tag}`, options);
    const entry = await responseJson(response, MAX_RELEASE_HISTORY_BYTES, `GitHub release ${tag}`);
    release = parseSingleRelease(entry, repository);
    if (release.revision !== revision) throw new Error(`PreFer release ${tag} does not match the requested revision`);
  } else {
    [release] = await listPreferReleases(repository, { ...options, channel: options.channel ?? "stable", limit: 1 });
  }
  if (!release) throw new Error(`no completed ${options.channel ?? "stable"} PreFer release was found`);
  const manifestAsset = release.assets["prefer-release.json"]!;
  const manifestBytes = await downloadReleaseAsset(release, manifestAsset.name, { ...options, expectedSha256: digestHex(manifestAsset.digest), maxBytes: MAX_MANIFEST_BYTES });
  let manifestValue: unknown;
  try { manifestValue = JSON.parse(new TextDecoder().decode(manifestBytes)) as unknown; }
  catch { throw new Error("PreFer release manifest is not valid JSON"); }
  const manifest = validatePreferReleaseManifest(manifestValue, release, repository);
  return { release, manifest };
}

export async function downloadReleaseAsset(
  release: PreferReleaseRecord,
  name: string,
  options: GitHubReleaseOptions & { expectedSha256?: string | undefined; maxBytes?: number | undefined } = {}
): Promise<Uint8Array> {
  requireAssetName(name);
  const asset = release.assets[name];
  if (!asset) throw new Error(`PreFer release ${release.id} is missing ${name}`);
  const expected = options.expectedSha256 ?? digestHex(asset.digest);
  const cachePath = options.cacheDir ? resolve(options.cacheDir, release.revision, name) : undefined;
  if (cachePath) {
    try {
      const cached = new Uint8Array(await readFile(cachePath));
      if (!expected || sha256(cached) === expected) return cached;
    } catch (error) {
      if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error;
    }
  }
  const response = await githubFetch(asset.url, options, "application/octet-stream");
  const bytes = await responseBytes(response, options.maxBytes ?? MAX_TOOLING_ASSET_BYTES, name);
  if (expected && sha256(bytes) !== expected) throw new Error(`${name} does not match its expected SHA-256`);
  if (cachePath) {
    await mkdir(dirname(cachePath), { recursive: true });
    await writeFile(cachePath, bytes);
  }
  return bytes;
}

export async function downloadPreferTooling(
  options: ResolveReleaseOptions & { outputDir: string }
): Promise<DownloadedPreferRelease & { files: Record<string, string> }> {
  const resolvedRelease = await resolvePreferRelease(options);
  const tooling = objectValue(resolvedRelease.manifest.tooling, "PreFer release tooling");
  if (tooling.schema_version !== "prefer.release-tooling.v1") throw new Error("PreFer release tooling schema is incompatible");
  const packageVersion = requireString(tooling.package_version, "PreFer release tooling package version");
  if (packageVersion !== `0.0.0-g${resolvedRelease.release.revision.slice(0, 7)}`) {
    throw new Error("PreFer release tooling package version does not match its release");
  }
  requireSha256(tooling.catalog_fingerprint, "PreFer release tooling catalog fingerprint");
  requireSha256(tooling.source_fingerprint, "PreFer release tooling source fingerprint");
  const files: Record<string, string> = {};
  for (const key of [
    "package",
    "cli",
    "model_catalog",
    "model_catalog_schema",
    "model_catalog_extension_schema",
    "resource_profile_schema",
    "model_plan_schema"
  ]) {
    const binding = objectValue(tooling[key], `PreFer release tooling ${key}`);
    const asset = requireAssetName(requireString(binding.asset, `PreFer release tooling ${key} asset`));
    const expectedBytes = requireNonnegativeInteger(binding.bytes, `PreFer release tooling ${key} bytes`);
    const expectedSha256 = requireSha256(binding.sha256, `PreFer release tooling ${key} SHA-256`);
    const bytes = await downloadReleaseAsset(resolvedRelease.release, asset, { ...options, expectedSha256 });
    if (bytes.byteLength !== expectedBytes) throw new Error(`${asset} does not match its expected size`);
    const path = resolve(options.outputDir, asset);
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, bytes);
    files[key] = path;
  }
  return { ...resolvedRelease, files };
}

export function validatePreferReleaseManifest(value: unknown, release?: PreferReleaseRecord, repositoryInput?: string): PreferReleaseManifest {
  const manifest = objectValue(value, "PreFer release manifest") as unknown as PreferReleaseManifest;
  if (manifest.schema_version !== "prefer.release.v1") throw new Error("PreFer release manifest schema is incompatible");
  const revision = requireString(manifest.release?.source_revision, "PreFer release source revision").toLowerCase();
  const id = requireString(manifest.release?.id, "PreFer release id");
  if (!/^[0-9a-f]{40}$/u.test(revision) || id !== `sha-${revision.slice(0, 7)}`) throw new Error("PreFer release manifest identity is invalid");
  if (release && (release.id !== id || release.revision !== revision)) throw new Error("PreFer release manifest does not match its GitHub release");
  if (repositoryInput) {
    const repository = validateRepository(repositoryInput);
    const source = manifest.release.source_repository.replace(/^https:\/\/github\.com\//u, "").replace(/\/$/u, "");
    if (source.toLowerCase() !== repository.toLowerCase()) throw new Error("PreFer release source repository is invalid");
  }
  if (manifest.distribution?.model_weights_embedded !== false
    || manifest.distribution.models_stage_at_runtime !== true
    || manifest.distribution.all_engine_images_share_release_revision !== true) {
    throw new Error("PreFer release distribution contract is incompatible");
  }
  objectValue(manifest.engines, "PreFer release engines");
  return manifest;
}

async function githubFetch(url: string, options: GitHubReleaseOptions, accept = "application/vnd.github+json"): Promise<Response> {
  const headers: Record<string, string> = { accept, "user-agent": "prefer-inference-core", "x-github-api-version": "2022-11-28" };
  if (options.token?.trim()) headers.authorization = `Bearer ${options.token.trim()}`;
  const response = await (options.fetch ?? fetch)(url, { headers, signal: AbortSignal.timeout(options.timeoutMs ?? 30_000) });
  if (!response.ok) {
    const reset = response.headers.get("x-ratelimit-reset");
    const retry = response.headers.get("retry-after");
    const rateLimit = response.status === 429 || (response.status === 403 && response.headers.get("x-ratelimit-remaining") === "0")
      ? `; rate limited${retry ? `, retry after ${retry}s` : reset ? `, reset at ${new Date(Number(reset) * 1000).toISOString()}` : ""}`
      : "";
    throw new Error(`${url} returned HTTP ${response.status}${rateLimit}`);
  }
  return response;
}

async function responseJson(response: Response, maxBytes: number, label: string): Promise<unknown> {
  const bytes = await responseBytes(response, maxBytes, label);
  try { return JSON.parse(new TextDecoder().decode(bytes)) as unknown; }
  catch { throw new Error(`${label} returned invalid JSON`); }
}

async function responseBytes(response: Response, maxBytes: number, label: string): Promise<Uint8Array> {
  const declared = Number(response.headers.get("content-length") ?? "0");
  if (declared > maxBytes) throw new Error(`${label} exceeds the response size limit`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength > maxBytes) throw new Error(`${label} exceeds the response size limit`);
  return bytes;
}

function parseSingleRelease(value: unknown, repository: string): PreferReleaseRecord {
  const entry = objectValue(value, "GitHub release");
  const id = requireString(entry.tag_name, "GitHub release tag");
  const revision = requireString(entry.target_commitish, "GitHub release target").toLowerCase();
  if (entry.draft !== false || typeof entry.prerelease !== "boolean" || !/^sha-[0-9a-f]{7}$/u.test(id) || !/^[0-9a-f]{40}$/u.test(revision)) {
    throw new Error("GitHub release is not a completed immutable PreFer release");
  }
  const published = new Date(requireString(entry.published_at, "GitHub release publication time"));
  if (!Number.isFinite(published.getTime())) throw new Error("GitHub release publication time is invalid");
  const assets: Record<string, PreferReleaseAsset> = {};
  if (!Array.isArray(entry.assets)) throw new Error("GitHub release assets are invalid");
  for (const rawAsset of entry.assets) {
    if (!isObject(rawAsset)) continue;
    const name = typeof rawAsset.name === "string" ? rawAsset.name : "";
    const url = typeof rawAsset.browser_download_url === "string" ? rawAsset.browser_download_url : "";
    if (!validAssetName(name) || !validAssetUrl(url, repository, id, name)) continue;
    assets[name] = {
      name,
      url,
      ...(typeof rawAsset.size === "number" ? { size: rawAsset.size } : {}),
      ...(typeof rawAsset.digest === "string" ? { digest: rawAsset.digest } : {})
    };
  }
  if (!assets["prefer-release.json"]) throw new Error("GitHub release is missing prefer-release.json");
  return {
    id,
    revision,
    channel: entry.prerelease ? "preview" : "stable",
    published_at: published.toISOString(),
    title: typeof entry.name === "string" && entry.name ? entry.name : id,
    url: `https://github.com/${repository}/releases/tag/${id}`,
    assets
  };
}

function validAssetUrl(value: string, repository: string, tag: string, name: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:"
      && url.hostname.toLowerCase() === "github.com"
      && !url.username && !url.password && !url.search && !url.hash
      && decodeURIComponent(url.pathname).toLowerCase() === `/${repository}/releases/download/${tag}/${name}`.toLowerCase();
  } catch { return false; }
}

function digestHex(value: string | undefined): string | undefined {
  return value?.startsWith("sha256:") ? value.slice(7) : undefined;
}

function requireSha256(value: unknown, label: string): string {
  const result = requireString(value, label).toLowerCase();
  if (!/^[0-9a-f]{64}$/u.test(result)) throw new Error(`${label} is invalid`);
  return result;
}

function requireNonnegativeInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Error(`${label} is invalid`);
  return value;
}

function validAssetName(value: string): boolean {
  return /^[a-z0-9][a-z0-9._-]{0,199}$/iu.test(value);
}

function requireAssetName(value: string): string {
  if (!validAssetName(value)) throw new Error(`invalid PreFer release asset name ${value}`);
  return value;
}

function objectValue(value: unknown, label: string): Record<string, unknown> {
  if (!isObject(value)) throw new Error(`${label} must be an object`);
  return value;
}
