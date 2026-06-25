---
type: Reference
title: Configuration
description: JSON, file, and environment-variable configuration patterns for NeurOn.
tags: [configuration, environment, deployment]
timestamp: 2026-06-25T00:00:00Z
---

# Configuration

NeurOn can run without a mounted config file. Configuration precedence is:

1. `CAPACITY_TARGETS_JSON`
2. `CAPACITY_TARGET_KEYS` and scoped environment variables
3. `CAPACITY_TARGETS_FILE`

Use JSON when that is convenient, but prefer env-expanded config for container
deployments where mounting a file is awkward.

## Core Environment

- `PORT`
- `SHARED_PASSWORD`
- `COOKIE_SECRET`
- `ADMIN_USERS`
- `AWS_REGION`
- `LITELLM_API_BASE_URL`
- `LITELLM_API_KEY`
- `RECONCILER_INTERVAL_SECONDS`
- `RESERVATION_STATUS_POLL_SECONDS`
- `ADMIN_STATUS_POLL_SECONDS`
- `HEALTH_CHECK_TIMEOUT_SECONDS`
- `LITELLM_TRAFFIC_POLL_SECONDS`
- `LITELLM_TRAFFIC_LOOKBACK_SECONDS`

Production-friendly defaults are intentionally calmer than local development:

- Reconciler: 60 seconds
- Reservation page polling: 10 seconds
- Main/admin status polling: 30 seconds
- LiteLLM traffic polling: 60 seconds when LiteLLM API config is present

Local compose overrides the important polling settings for faster iteration.

## Env-Expanded Target Config

Declare target keys:

```env
CAPACITY_TARGET_KEYS=MULTIPLE_MOE_96GB
```

Then define scoped variables:

```env
CAPACITY_TARGET_MULTIPLE_MOE_96GB_ID=multiple-moe-96gb
CAPACITY_TARGET_MULTIPLE_MOE_96GB_DISPLAY_NAME=Multiple MoE 96GB
CAPACITY_TARGET_MULTIPLE_MOE_96GB_PROVIDER=aws-ecs
CAPACITY_TARGET_MULTIPLE_MOE_96GB_HEALTH_CHECK_URL=http://llm-96gb.internal:8080/health
```

Model keys are nested under a target:

```env
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_KEYS=QWEN_36,GEMMA_4
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_ID=qwen-3.6-35b-a3b
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_DISPLAY_NAME=Qwen3.6 35B A3B
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_FAMILY=Qwen 3.6
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_ALIASES=qwen-3.6
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_BACKEND_MODEL_IDS=qwen-3.6,qwen-3.6-35b-a3b
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_CONTEXT_LABEL=256k
```

## AWS Env Fields

```env
CAPACITY_TARGET_MULTIPLE_MOE_96GB_AWS_CLUSTER=llm-cluster
CAPACITY_TARGET_MULTIPLE_MOE_96GB_AWS_SERVICE=llama-cpp-multiple-moe-96gb
CAPACITY_TARGET_MULTIPLE_MOE_96GB_AWS_ASG_NAME=llm-multiple-moe-96gb-asg
```

`AWS_CLUSTER` and `AWS_SERVICE` may be names or ARNs. The Auto Scaling Group
must be supplied by name because Auto Scaling APIs use `AutoScalingGroupName`.

Older JSON fields `clusterName` and `serviceName` are still supported, but new
configs should use `cluster` and `service`.

## Docker Compose Env Fields

```env
CAPACITY_TARGET_LOCAL_PROVIDER=docker-compose
CAPACITY_TARGET_LOCAL_DOCKER_PROJECT_DIRECTORY=/workspace
CAPACITY_TARGET_LOCAL_DOCKER_PROJECT_NAME=llm-hosting
CAPACITY_TARGET_LOCAL_DOCKER_COMPOSE_FILE=docker-compose.yml
CAPACITY_TARGET_LOCAL_DOCKER_SERVICE_NAME=multiple-moe
```

Use `DOCKER_COMPOSE_FILES` as a comma-separated list when an overlay is needed.

## Runtime Model Discovery

Explicit model config is the normal source of truth. Runtime discovery enriches
models with IDs reported by the backend. It should not be treated as a solver.

Optional bootstrap:

```env
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_DISCOVERY_BOOTSTRAP_ON_STARTUP=true
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_DISCOVERY_BOOTSTRAP_TIMEOUT_SECONDS=600
```

When enabled, NeurOn starts the target once before accepting requests, waits for
health, reads `/v1/models`, records runtime IDs, and stops the target again.
