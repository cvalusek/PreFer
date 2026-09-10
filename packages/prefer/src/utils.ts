import { createHash } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import type { JsonObject, JsonValue } from "./types.js";

export function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function requireObject(value: unknown, label: string): Record<string, unknown> {
  if (!isObject(value)) throw new Error(`${label} must be an object`);
  return value;
}

export function requireString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be a non-empty string`);
  return value.trim();
}

export function deepMerge<T extends JsonObject>(...values: Array<T | undefined>): T {
  const result: JsonObject = {};
  for (const value of values) mergeInto(result, value);
  return result as T;
}

function mergeInto(target: JsonObject, source: JsonObject | undefined): void {
  if (!source) return;
  for (const [key, value] of Object.entries(source)) {
    const existing = target[key];
    if (isObject(value) && isObject(existing)) {
      const child = { ...(existing as JsonObject) };
      mergeInto(child, value as JsonObject);
      target[key] = child;
    } else {
      target[key] = structuredClone(value) as JsonValue;
    }
  }
}

export function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (isObject(value)) {
    return `{${Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entry]) => `${JSON.stringify(key)}:${stableStringify(entry)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function sha256(value: string | Uint8Array): string {
  return createHash("sha256").update(value).digest("hex");
}

export async function readJson(path: string): Promise<unknown> {
  return JSON.parse(await readFile(path, "utf8")) as unknown;
}

export async function writeJsonAtomic(path: string, value: unknown): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const temporary = `${path}.tmp-${process.pid}-${Date.now()}`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await rename(temporary, path);
}

export function repositoryKey(repository: string, revision: string): string {
  return `${repository}@${revision}`;
}

export function validateRepository(value: string): string {
  const repository = value.trim();
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/u.test(repository)) {
    throw new Error(`invalid Hugging Face repository: ${value}`);
  }
  return repository;
}

export function validateRevision(value: string, { immutable = false } = {}): string {
  const revision = value.trim();
  const pattern = immutable ? /^[0-9a-f]{40}$/iu : /^[A-Za-z0-9._/-]+$/u;
  if (!pattern.test(revision) || revision.includes("..") || revision.startsWith("/")) {
    throw new Error(`invalid ${immutable ? "immutable " : ""}revision: ${value}`);
  }
  return revision;
}

export function parseRepositorySelection(value: string): { repository: string; revision?: string } {
  const split = value.lastIndexOf("@");
  if (split <= 0) return { repository: validateRepository(value) };
  return {
    repository: validateRepository(value.slice(0, split)),
    revision: validateRevision(value.slice(split + 1))
  };
}

export function globMatch(path: string, pattern: string): boolean {
  let expression = "^";
  for (let index = 0; index < pattern.length;) {
    if (pattern.slice(index, index + 3) === "**/") {
      expression += "(?:.*/)?";
      index += 3;
      continue;
    }
    if (pattern.slice(index, index + 2) === "**") {
      expression += ".*";
      index += 2;
      continue;
    }
    const character = pattern.charAt(index);
    if (character === "*") expression += "[^/]*";
    else if (character === "?") expression += "[^/]";
    else expression += character.replace(/[.+^${}()|[\]\\]/u, "\\$&");
    index += 1;
  }
  return new RegExp(`${expression}$`, "u").test(path);
}
