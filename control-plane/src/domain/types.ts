export type ReservationStatus = "active" | "done" | "expired" | "failed";
export type RuntimeState = "stopped" | "provisioning" | "healthy" | "stopping" | "failed";
export type DesiredState = "on" | "off";

export interface AuthenticatedUser {
  username: string;
  isAdmin: boolean;
}

export interface Reservation {
  id: string;
  username: string;
  modelIds: string[];
  targetIds: string[];
  createdAt: Date;
  expiresAt: Date;
  endedAt?: Date;
  status: ReservationStatus;
  failureMessage?: string;
  synthetic?: boolean;
}

export interface AwsTargetConfig {
  cluster?: string;
  service?: string;
  clusterName?: string;
  serviceName?: string;
  autoScalingGroupName: string;
}

export interface LiteLlmTargetConfig {
  backendName: string;
  apiBaseUrl: string;
}

export interface DockerComposeTargetConfig {
  projectDirectory: string;
  projectName?: string;
  composeFile?: string;
  composeFiles?: string[];
  serviceName: string;
}

export interface ConfiguredModel {
  id: string;
  displayName?: string;
  modelFamily?: string;
  aliases?: string[];
  description?: string;
  backendModelIds?: string[];
  contextWindowTokens?: number;
  contextLabel?: string;
}

export interface RuntimeModelDiscoveryConfig {
  bootstrapOnStartup?: boolean;
  bootstrapTimeoutSeconds?: number;
}

export interface CapacityTarget {
  id: string;
  displayName: string;
  provider: "aws-ecs" | string;
  modelIds: string[];
  models?: ConfiguredModel[];
  modelDiscovery?: RuntimeModelDiscoveryConfig;
  modelPresetPath?: string;
  modelsMax?: number;
  aws?: AwsTargetConfig;
  dockerCompose?: DockerComposeTargetConfig;
  healthCheckUrl: string;
  litellm?: LiteLlmTargetConfig;
}

export interface ModelDefinition {
  id: string;
  displayName: string;
  modelFamily?: string;
  aliases: string[];
  targetIds: string[];
  description?: string;
  backendModelIds?: string[];
  runtimeModelIds?: string[];
  contextWindowTokens?: number;
  contextLabel?: string;
  presetSection?: string;
  modelPath?: string;
}

export interface TargetStatus {
  targetId: string;
  desired: DesiredState;
  observed: RuntimeState;
  message: string;
  lastCheckedAt?: Date;
  lastHealthyAt?: Date;
  provisioningStartedAt?: Date;
  startupDurationsSeconds?: number[];
  startupEstimate?: {
    minSeconds: number;
    maxSeconds: number;
    avgSeconds: number;
    sampleCount: number;
  };
}

export interface CapacityProviderStatus {
  observed: RuntimeState;
  message: string;
  details?: Record<string, unknown>;
}

export interface AppConfig {
  port: number;
  sharedPassword: string;
  cookieSecret?: string;
  awsRegion: string;
  litellmApiBaseUrl?: string;
  litellmApiKey?: string;
  litellmTrafficPollSeconds: number;
  litellmTrafficLookbackSeconds: number;
  capacityTargets: CapacityTarget[];
  reconcilerIntervalSeconds: number;
  reservationStatusPollSeconds: number;
  adminStatusPollSeconds: number;
  healthCheckTimeoutSeconds: number;
  healthCheckIntervalSeconds: number;
  adminUsers: string[];
}
