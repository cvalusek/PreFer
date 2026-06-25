import type { CapacityTarget, ModelDefinition } from "../domain/types.js";

export class ModelCatalog {
  private readonly modelById: Map<string, ModelDefinition>;
  private readonly modelByLookupId = new Map<string, ModelDefinition>();
  private readonly targetById: Map<string, CapacityTarget>;

  constructor(models: ModelDefinition[], targets: CapacityTarget[]) {
    this.modelById = new Map(models.map((model) => [model.id, model]));
    this.targetById = new Map(targets.map((target) => [target.id, target]));
    for (const model of models) this.addModelLookups(model);
  }

  listModels(): ModelDefinition[] {
    return Array.from(this.modelById.values());
  }

  getModel(modelId: string): ModelDefinition | undefined {
    return this.modelByLookupId.get(modelId);
  }

  listTargets(): CapacityTarget[] {
    return Array.from(this.targetById.values());
  }

  listModelsForTarget(targetId: string): ModelDefinition[] {
    return this.listModels().filter((model) => model.targetIds.includes(targetId));
  }

  getTarget(id: string): CapacityTarget | undefined {
    return this.targetById.get(id);
  }

  recordRuntimeModels(targetId: string, runtimeModelIds: string[]): void {
    const runtimeIds = Array.from(new Set(runtimeModelIds));
    for (const model of this.modelById.values()) {
      if (!model.targetIds.includes(targetId)) continue;
      const expected = new Set([model.id, ...model.aliases, ...(model.backendModelIds ?? [])]);
      const matches = runtimeIds.filter((runtimeId) => expected.has(runtimeId));
      model.runtimeModelIds = matches.length > 0 ? matches : model.runtimeModelIds;
      this.addModelLookups(model);
    }
  }

  targetsForModels(modelIds: string[]): CapacityTarget[] {
    const targetIds = new Set<string>();
    for (const modelId of modelIds) {
      const model = this.modelByLookupId.get(modelId);
      if (!model) throw new Error(`Unknown model ID: ${modelId}`);
      for (const targetId of model.targetIds) targetIds.add(targetId);
    }
    return Array.from(targetIds)
      .map((id) => this.targetById.get(id))
      .filter((target): target is CapacityTarget => Boolean(target));
  }

  validateModelIds(modelIds: string[]): void {
    if (modelIds.length === 0) throw new Error("At least one model ID is required");
    for (const modelId of modelIds) {
      if (!this.modelByLookupId.has(modelId)) throw new Error(`Unknown model ID: ${modelId}`);
    }
  }

  canonicalModelIds(modelIds: string[]): string[] {
    return Array.from(
      new Set(
        modelIds.map((modelId) => {
          const model = this.modelByLookupId.get(modelId);
          if (!model) throw new Error(`Unknown model ID: ${modelId}`);
          return model.id;
        })
      )
    );
  }

  private addModelLookups(model: ModelDefinition): void {
    const lookupIds = [model.id, ...model.aliases, ...(model.backendModelIds ?? []), ...(model.runtimeModelIds ?? [])];
    for (const lookupId of lookupIds) this.modelByLookupId.set(lookupId, model);
  }
}
