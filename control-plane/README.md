# NeurOn

NeurOn is a lightweight control plane for shared self-hosted LLM capacity. It
is the light switch: developers reserve the models they expect to use, NeurOn
keeps the matching runtime on while reservations or recent traffic need it,
and it scales the runtime back down when demand is gone.

It is intentionally small:

- Fastify + TypeScript
- server-rendered HTML, not a SPA
- OpenAPI-compatible REST endpoints
- in-memory v1 state behind repository interfaces
- provider adapters for Docker Compose locally and AWS ECS/ASG in production
- LiteLLM request-log polling for traffic-based keepalive

NeurOn currently lives inside the PreFer repo for local iteration, but it is
designed to split into its own repository.

## Local Run

For pure app development without touching Docker capacity:

```bash
cd control-plane
npm install
SHARED_PASSWORD=dev-password USE_FAKE_PROVIDER=true npm run dev
```

Open `http://localhost:8090`, sign in with any username and `dev-password`, or
use Basic Auth for API calls.

## Local Compose Capacity

From the repository root, NeurOn starts by default. The inference container is
behind the `llm-capacity` profile and only starts when a reservation needs it.

```bash
docker compose up --build control-plane
```

Then open `http://localhost:8090`.

The local Docker provider starts capacity with:

```bash
docker compose -p llm-hosting -f docker-compose.yml up -d --no-build multiple-moe
```

And stops it with:

```bash
docker compose -p llm-hosting -f docker-compose.yml stop multiple-moe
```

Models live in a named Docker volume mounted at `/models`, defaulting to
`llm-hosting-model-cache`. Set `LLM_MODEL_VOLUME` to use a different cache.

## Netskope Builds

If local Docker builds fail with certificate errors, export your Netskope or
corporate root/intermediate CA as `.crt` files under:

```bash
docker/certs/
```

Then build/run with the overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.netskope.yml --profile llm-capacity build multiple-moe
docker compose -f docker-compose.yml -f docker-compose.netskope.yml up --build -d control-plane
```

With the overlay, NeurOn uses
`control-plane/examples/capacity-targets.local-netskope.json`, so nested
Compose starts capacity with both compose files.

## UI

`GET /` is the main workspace:

- current user's active reservation
- selectable model buttons
- quick duration buttons plus custom duration
- per-server capacity status
- reservations grouped under the target they use

Target status cards include a recent startup estimate once NeurOn has observed
one or more provisioning-to-healthy transitions, shown as a usual time plus a
min/max range. This state is in memory for v1 and resets when NeurOn restarts.

`GET /admin` adds target controls such as reconcile and force-stop.

Reservation detail pages still exist at `/reservations/:id` for direct links,
but normal create/done/extend flows return to `/`.

## Configuration

Environment variables:

| Name | Default | Notes |
| --- | --- | --- |
| `PORT` | `8090` | HTTP port inside the container |
| `SHARED_PASSWORD` | required in production | Basic/cookie auth password |
| `COOKIE_SECRET` | unset | Enables login cookie auth |
| `ADMIN_USERS` | any authenticated user | Comma-separated admin usernames |
| `CAPACITY_TARGETS_JSON` | unset | JSON array of targets |
| `CAPACITY_TARGET_KEYS` | unset | Comma-separated target keys for env-expanded config |
| `CAPACITY_TARGETS_FILE` | `examples/capacity-targets.example.json` | Local target config file |
| `RECONCILER_INTERVAL_SECONDS` | `60` | Background reconcile loop |
| `RESERVATION_STATUS_POLL_SECONDS` | `10` | Reservation detail polling |
| `ADMIN_STATUS_POLL_SECONDS` | `30` | Main/admin status polling |
| `HEALTH_CHECK_TIMEOUT_SECONDS` | `5` | Per-target health check timeout |
| `HEALTH_CHECK_INTERVAL_SECONDS` | `15` | Reserved for health tuning |
| `AWS_REGION` | `us-east-1` | AWS region for ECS/ASG provider |
| `LITELLM_API_BASE_URL` | unset | LiteLLM admin API base URL |
| `LITELLM_API_KEY` | unset | LiteLLM admin API key |
| `LITELLM_TRAFFIC_POLL_SECONDS` | `60` | Poll `/spend/logs/v2`; set `0` to disable |
| `LITELLM_TRAFFIC_LOOKBACK_SECONDS` | `300` | Recent traffic window |
| `USE_FAKE_PROVIDER` | `false` | Local fake provider for app development |

Model choices are configuration-first. Put the user-facing choices in each
target's `models` array with display names, aliases, backend model IDs, and
context metadata. The start page asks users to choose a capacity target first,
then the models they expect to use on that target. When a target becomes
healthy, NeurOn polls the target's OpenAI-compatible `/v1/models` endpoint and
records matching runtime model IDs from `backendModelIds`/`aliases`; that
enriches status and traffic mapping without creating surprise UI options or
changing capacity decisions.

`modelPresetPath` still exists as a convenience fallback for colocated PreFer
development, but it is not the recommended production source of truth. For
split repositories, keep the model list in NeurOn config. If you want NeurOn
to briefly start a target once to discover runtime model IDs, enable
`modelDiscovery.bootstrapOnStartup`.

Config precedence is:

1. `CAPACITY_TARGETS_JSON`
2. `CAPACITY_TARGET_KEYS` and scoped environment variables
3. `CAPACITY_TARGETS_FILE`

The scoped env pattern uses stable keys. For a target key `MULTIPLE_MOE_96GB`,
target variables start with `CAPACITY_TARGET_MULTIPLE_MOE_96GB_`. Model keys
are declared per target and nested under that same prefix.

Env-only AWS example:

```env
CAPACITY_TARGET_KEYS=MULTIPLE_MOE_96GB
CAPACITY_TARGET_MULTIPLE_MOE_96GB_ID=multiple-moe-96gb
CAPACITY_TARGET_MULTIPLE_MOE_96GB_DISPLAY_NAME=Multiple MoE 96GB
CAPACITY_TARGET_MULTIPLE_MOE_96GB_PROVIDER=aws-ecs
CAPACITY_TARGET_MULTIPLE_MOE_96GB_HEALTH_CHECK_URL=http://llm-96gb.internal:8080/health
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODELS_MAX=2

CAPACITY_TARGET_MULTIPLE_MOE_96GB_AWS_CLUSTER=arn:aws:ecs:us-east-1:123456789012:cluster/llm-cluster
CAPACITY_TARGET_MULTIPLE_MOE_96GB_AWS_SERVICE=arn:aws:ecs:us-east-1:123456789012:service/llm-cluster/llama-cpp-multiple-moe-96gb
CAPACITY_TARGET_MULTIPLE_MOE_96GB_AWS_ASG_NAME=llm-multiple-moe-96gb-asg

CAPACITY_TARGET_MULTIPLE_MOE_96GB_LITELLM_BACKEND_NAME=ecs-llama-96gb
CAPACITY_TARGET_MULTIPLE_MOE_96GB_LITELLM_API_BASE_URL=http://llm-96gb.internal:8080/v1

CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_KEYS=QWEN_36,GEMMA_4,GLM_47

CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_ID=qwen-3.6-35b-a3b
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_DISPLAY_NAME=Qwen3.6 35B A3B
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_FAMILY=Qwen 3.6
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_DESCRIPTION=General coding and reasoning model
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_ALIASES=qwen-3.6
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_BACKEND_MODEL_IDS=qwen-3.6,qwen-3.6-35b-a3b
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_QWEN_36_CONTEXT_LABEL=256k

CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GEMMA_4_ID=gemma-4-26b-a4b
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GEMMA_4_DISPLAY_NAME=Gemma 4 26B A4B
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GEMMA_4_FAMILY=Gemma 4
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GEMMA_4_ALIASES=gemma-4
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GEMMA_4_BACKEND_MODEL_IDS=gemma-4,gemma-4-26b-a4b
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GEMMA_4_CONTEXT_LABEL=128k

CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GLM_47_ID=glm-4.7-flash
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GLM_47_DISPLAY_NAME=GLM 4.7 Flash
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GLM_47_FAMILY=GLM 4.7 Flash
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GLM_47_BACKEND_MODEL_IDS=glm-4.7-flash
CAPACITY_TARGET_MULTIPLE_MOE_96GB_MODEL_GLM_47_CONTEXT_LABEL=198k
```

For ECS, `AWS_CLUSTER` and `AWS_SERVICE` may be names or ARNs. The Auto
Scaling Group still uses its group name because the ASG APIs require
`AutoScalingGroupName`.

Example target config:

```json
[
  {
    "id": "multiple-moe-96gb",
    "displayName": "Multiple MoE 96GB",
    "provider": "aws-ecs",
    "models": [
      {
        "id": "qwen-3.6-35b-a3b",
        "displayName": "Qwen3.6 35B A3B",
        "modelFamily": "Qwen 3.6",
        "description": "General coding and reasoning model",
        "aliases": ["qwen-3.6"],
        "backendModelIds": ["qwen-3.6", "qwen-3.6-35b-a3b"],
        "contextLabel": "256k"
      },
      {
        "id": "qwen-3.6-35b-a3b-1m",
        "displayName": "Qwen3.6 35B A3B 1M",
        "modelFamily": "Qwen 3.6",
        "description": "Long-context Qwen profile",
        "backendModelIds": ["qwen-3.6-35b-a3b-1m"],
        "contextLabel": "1m"
      },
      {
        "id": "gemma-4-26b-a4b",
        "displayName": "Gemma 4 26B A4B",
        "modelFamily": "Gemma 4",
        "description": "Gemma 4 with MTP draft support",
        "aliases": ["gemma-4"],
        "backendModelIds": ["gemma-4", "gemma-4-26b-a4b"],
        "contextLabel": "128k"
      },
      {
        "id": "glm-4.7-flash",
        "displayName": "GLM 4.7 Flash",
        "modelFamily": "GLM 4.7 Flash",
        "description": "GLM flash/reasoning MoE model",
        "backendModelIds": ["glm-4.7-flash"],
        "contextLabel": "198k"
      }
    ],
    "modelDiscovery": {
      "bootstrapOnStartup": false,
      "bootstrapTimeoutSeconds": 600
    },
    "modelsMax": 2,
    "aws": {
      "cluster": "llm-cluster",
      "service": "llama-cpp-multiple-moe-96gb",
      "autoScalingGroupName": "llm-multiple-moe-96gb-asg"
    },
    "healthCheckUrl": "http://llm-96gb.internal:8080/health",
    "litellm": {
      "backendName": "ecs-llama-96gb",
      "apiBaseUrl": "http://llm-96gb.internal:8080/v1"
    }
  }
]
```

## API Examples

```bash
curl -u clint:dev-password http://localhost:8090/api/models
```

```bash
curl -u clint:dev-password -H 'content-type: application/json' \
  -d '{"modelIds":["qwen-3.6-35b-a3b"],"durationMinutes":15}' \
  http://localhost:8090/api/reservations
```

```bash
curl -u clint:dev-password http://localhost:8090/api/status
curl -u clint:dev-password -X POST http://localhost:8090/api/reservations/<id>/done
```

OpenAPI UI is available at `/docs`.

## Traffic Keepalive

NeurOn can keep healthy capacity warm from LiteLLM request logs. Enable:

```env
LITELLM_API_BASE_URL=http://litellm.internal:4000
LITELLM_API_KEY=sk-...
LITELLM_TRAFFIC_POLL_SECONDS=60
LITELLM_TRAFFIC_LOOKBACK_SECONDS=300
```

When `LITELLM_API_BASE_URL` and `LITELLM_API_KEY` are set, the poller reads
`GET /spend/logs/v2`, maps recent `model` values to NeurOn model IDs, and
refreshes a synthetic `traffic` reservation. It will not resurrect a failed
target by itself. The reconciler also performs one immediate traffic poll
before shutting a target down, so a recent request has a chance to extend the
keepalive before capacity is stopped.

## Deployment Notes

Run NeurOn separately from the LLM host, for example as its own ECS/Fargate
service. It scales the configured LLM ECS service and Auto Scaling Group; it
should not run on the same capacity that it turns off.

The app is intended for internal/Tailscale access. v1 auth is shared-password
Basic Auth plus optional signed HTTP-only login cookie. `AuthProvider` is
isolated so GitHub/AuthentiK/Okta/Tailscale identity can replace it later.

## IAM

For AWS ECS/ASG targets, the task role needs:

- `autoscaling:SetDesiredCapacity`
- `autoscaling:DescribeAutoScalingGroups`
- `ecs:UpdateService`
- `ecs:DescribeServices`

If LiteLLM credentials are stored in AWS Secrets Manager or SSM Parameter
Store, grant read access and inject `LITELLM_API_KEY` at runtime.

## Development

```bash
npm run typecheck
npm test
npm run lint
docker build -t llm-capacity-control-plane .
```

State is in memory for v1. Restarting NeurOn loses reservations, but the
reconciler reads provider state and tolerates restart without request
handlers owning infrastructure lifecycle transitions.
