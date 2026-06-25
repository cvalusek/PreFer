import { readFile } from "node:fs/promises";
import path from "node:path";
import type { ModelDefinition } from "../domain/types.js";

interface IniSection {
  name: string;
  values: Map<string, string>;
}

export function parsePresetIni(contents: string): IniSection[] {
  const sections: IniSection[] = [];
  let current: IniSection | undefined;
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || line.startsWith(";")) continue;
    const sectionMatch = line.match(/^\[(.+)]$/);
    if (sectionMatch) {
      current = { name: sectionMatch[1], values: new Map() };
      sections.push(current);
      continue;
    }
    const equalsIndex = line.indexOf("=");
    if (equalsIndex === -1 || !current) continue;
    current.values.set(line.slice(0, equalsIndex).trim(), line.slice(equalsIndex + 1).trim());
  }
  return sections;
}

export function modelDefinitionsFromPreset(contents: string): ModelDefinition[] {
  return parsePresetIni(contents)
    .filter((section) => section.name !== "*")
    .map((section) => {
      const aliases = (section.values.get("alias") ?? "")
        .split(",")
        .map((alias) => alias.trim())
        .filter(Boolean);
      const fallbackId = normalizeModelId(section.name.split(":")[0]);
      const id = aliases[0] ?? fallbackId;
      return {
        id,
        displayName: readableModelName(id),
        modelFamily: inferModelFamily(id),
        aliases: Array.from(new Set([id, ...aliases])),
        targetIds: [],
        contextLabel: inferContextLabel(id),
        presetSection: section.name,
        modelPath: section.values.get("model")
      };
    });
}

export async function loadModelsFromPreset(repoRoot: string, presetPath: string): Promise<ModelDefinition[]> {
  const absolutePath = path.isAbsolute(presetPath) ? presetPath : path.join(repoRoot, presetPath);
  return modelDefinitionsFromPreset(await readFile(absolutePath, "utf8"));
}

function normalizeModelId(value: string): string {
  return value
    .split("/")
    .pop()!
    .replace(/-GGUF$/i, "")
    .replace(/-qat/i, "")
    .replace(/_/g, "-")
    .toLowerCase();
}

function readableModelName(id: string): string {
  return id
    .split("-")
    .map((part) => (part.length <= 3 ? part.toUpperCase() : part[0].toUpperCase() + part.slice(1)))
    .join(" ");
}

function inferContextLabel(modelId: string): string | undefined {
  return modelId.match(/(?:^|-)(\d+k)(?:$|-)/i)?.[1].toLowerCase();
}

function inferModelFamily(value: string): string | undefined {
  const normalized = value.toLowerCase();
  if (normalized.includes("gemma-4") || normalized.includes("gemma 4")) return "Gemma 4";
  if (normalized.includes("qwen3.6") || normalized.includes("qwen-3.6") || normalized.includes("qwen 3.6")) return "Qwen 3.6";
  if (normalized.includes("glm-4.7-flash") || normalized.includes("glm 4.7 flash")) return "GLM 4.7 Flash";
  return undefined;
}
