#!/usr/bin/env python3
"""Generate vLLM server configs, staging maps, and the deployment inventory."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


ROOT = Path(__file__).resolve().parent
MODELS_ROOT = ROOT / "models"
RUNTIME_PATH = ROOT / "runtime.json"
SCENARIOS_ROOT = ROOT / "deployment-scenarios"
CONFIGS_ROOT = ROOT / "server-configs"

MODEL_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REPO_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"
)
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
STAGING_SOURCES = {"huggingface-only", "s3-then-huggingface"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(*sources: dict) -> dict:
    result: dict = {}
    for source in sources:
        for key, value in source.items():
            if isinstance(result.get(key), dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
    return result


def artifact_identity(artifact: dict) -> dict:
    return {
        "repo": artifact["repo"],
        "revision": artifact["revision"],
        "path": artifact["path"],
        "size": artifact["size"],
        "sha256": artifact["sha256"],
    }


def artifact_download_id(artifact: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            artifact_identity(artifact), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def validate_artifact(key: str, artifact: dict, destinations: dict) -> None:
    repo = artifact.get("repo")
    if not isinstance(repo, str) or not REPO_PATTERN.fullmatch(repo):
        raise ValueError(f"{key}: artifact repo must be a safe owner/name")
    revision = artifact.get("revision")
    if not isinstance(revision, str) or not SHA1_PATTERN.fullmatch(revision):
        raise ValueError(f"{key}: artifact revision must be an immutable SHA")
    sha256 = artifact.get("sha256")
    if not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256):
        raise ValueError(f"{key}: artifact sha256 is invalid")
    size = artifact.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError(f"{key}: artifact size must be a positive integer")
    artifact_path = artifact.get("path")
    path = PurePosixPath(str(artifact_path or ""))
    if (
        not isinstance(artifact_path, str)
        or not artifact_path
        or "\\" in artifact_path
        or path.is_absolute()
        or ".." in path.parts
    ):
        raise ValueError(f"{key}: artifact path must remain relative")
    role = artifact.get("role")
    if role is not None and (not isinstance(role, str) or not role):
        raise ValueError(f"{key}: artifact role must be a non-empty string")
    destination = (repo, artifact_path)
    identity = artifact_identity(artifact)
    previous = destinations.get(destination)
    if previous is not None and previous != identity:
        raise ValueError(f"{key}: conflicting immutable identity for {repo}/{artifact_path}")
    destinations[destination] = identity


def model_lanes() -> list[dict]:
    lanes: list[dict] = []
    seen_keys: set[str] = set()
    seen_ids: set[str] = set()
    destinations: dict[tuple[str, str], dict] = {}
    for path in sorted(MODELS_ROOT.glob("*/*/model.json")):
        source = load_json(path)
        family, model_slug, _ = path.relative_to(MODELS_ROOT).parts
        if source.get("schema_version") != 1:
            raise ValueError(f"{path}: schema_version must be 1")
        if source.get("family") != family or source.get("model_slug") != model_slug:
            raise ValueError(f"{path}: family/model_slug must match its directory")
        shared = source.get("shared")
        if not isinstance(shared, dict):
            raise ValueError(f"{path}: shared must be an object")
        model_id = shared.get("id")
        if not isinstance(model_id, str) or not model_id:
            raise ValueError(f"{path}: shared.id must be a non-empty string")
        tasks = shared.get("tasks", [shared.get("task")])
        if (
            not isinstance(tasks, list)
            or not tasks
            or any(not isinstance(task, str) or not task for task in tasks)
        ):
            raise ValueError(f"{path}: shared.tasks must be a non-empty list of strings")
        capabilities = shared.get("capabilities")
        modalities = shared.get("modalities")
        if not isinstance(capabilities, list) or not capabilities:
            raise ValueError(f"{path}: shared.capabilities must be a non-empty list")
        if not isinstance(modalities, dict):
            raise ValueError(f"{path}: shared.modalities must be an object")
        profile = shared.get("profile")
        if not isinstance(profile, dict):
            raise ValueError(f"{path}: shared.profile must be an object")
        profile_id = shared.get("profile_id", model_slug)
        if not isinstance(profile_id, str) or not profile_id:
            raise ValueError(f"{path}: shared.profile_id must be a non-empty string")
        quants = source.get("quants")
        if not isinstance(quants, dict) or not quants:
            raise ValueError(f"{path}: quants must be a non-empty object")
        primary = [quant for quant in quants.values() if quant.get("primary")]
        if len(primary) != 1:
            raise ValueError(f"{path}: exactly one primary quant is required")

        for quant_slug, quant in quants.items():
            if not isinstance(quant, dict):
                raise ValueError(f"{path}: quant {quant_slug} must be an object")
            key = quant.get("key")
            if not isinstance(key, str) or not MODEL_KEY_PATTERN.fullmatch(key):
                raise ValueError(f"{path}: quant {quant_slug} has an unsafe key")
            if key in seen_keys:
                raise ValueError(f"duplicate model key: {key}")
            if quant.get("primary") and model_id in seen_ids:
                raise ValueError(f"duplicate configured model id: {model_id}")
            artifacts = quant.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                raise ValueError(f"{key}: artifacts must be a non-empty list")
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    raise ValueError(f"{key}: every artifact must be an object")
                validate_artifact(key, artifact, destinations)
            repos = {artifact["repo"] for artifact in artifacts}
            if len(repos) != 1:
                raise ValueError(f"{key}: all artifacts must share one repository")
            server = copy.deepcopy(shared.get("server", {}))
            quant_server = quant.get("server", {})
            if not isinstance(server, dict) or not isinstance(quant_server, dict):
                raise ValueError(f"{key}: server settings must be objects")
            server.update(copy.deepcopy(quant_server))
            request_model_id = quant.get("request_model_id", model_id)
            aliases = quant.get("aliases", [request_model_id])
            if (
                not isinstance(request_model_id, str)
                or not request_model_id
                or not isinstance(aliases, list)
                or not aliases
                or any(not isinstance(alias, str) or not alias for alias in aliases)
                or request_model_id not in aliases
            ):
                raise ValueError(f"{key}: request_model_id and aliases are invalid")
            lane = {
                "key": key,
                "quant_slug": quant_slug,
                "precision": quant.get("precision", "unspecified"),
                "primary": bool(quant.get("primary")),
                "request_model_id": request_model_id,
                "aliases": aliases,
                "family": family,
                "model_slug": model_slug,
                "profile_id": profile_id,
                "tasks": copy.deepcopy(tasks),
                "capabilities": copy.deepcopy(capabilities),
                "modalities": copy.deepcopy(modalities),
                **shared,
                "artifacts": copy.deepcopy(artifacts),
                "container_path": f"/models/{next(iter(repos))}",
                "server": server,
            }
            lanes.append(lane)
            seen_keys.add(key)
            if lane["primary"]:
                seen_ids.add(model_id)
    if not lanes:
        raise ValueError("no vLLM model catalogs found")
    lanes.sort(key=lambda lane: lane["key"])
    return lanes


def validate_scenario_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise ValueError(f"unsafe or non-JSON vLLM scenario path: {value!r}")
    return path.as_posix()


def load_scenarios(primary_by_key: dict[str, dict]) -> list[dict]:
    source_paths = sorted(SCENARIOS_ROOT.rglob("*.json"))
    if not source_paths:
        raise ValueError("deployment-scenarios/**/*.json files are required")
    records: list[dict] = []
    seen_paths: set[str] = set()
    for source_path in source_paths:
        source = load_json(source_path)
        if source.get("schema_version") != 1:
            raise ValueError(f"{source_path}: schema_version must be 1")
        provider = source.get("provider")
        output_root = str(source.get("output_root", "")).strip("/")
        if not isinstance(provider, str) or not provider or not output_root:
            raise ValueError(f"{source_path}: provider and output_root are required")
        hardware = source.get("hardware")
        if (
            not isinstance(hardware, dict)
            or not isinstance(hardware.get("gpu_count"), int)
            or hardware["gpu_count"] <= 0
            or not isinstance(hardware.get("gpu_type_id"), str)
            or not hardware.get("compute_capability")
        ):
            raise ValueError(f"{source_path}: hardware must declare GPU id/count/capability")
        compatibility = source.get("compatibility", {})
        staging = source.get("staging", {"source": "huggingface-only"})
        if not isinstance(compatibility, dict):
            raise ValueError(f"{source_path}: compatibility must be an object")
        if not isinstance(staging, dict) or staging.get("source") not in STAGING_SOURCES:
            raise ValueError(f"{source_path}: staging must declare a supported source")
        configs = source.get("configs")
        if not isinstance(configs, list) or not configs:
            raise ValueError(f"{source_path}: configs must be a non-empty list")
        for config in configs:
            if not isinstance(config, dict):
                raise ValueError(f"{source_path}: every config must be an object")
            name = config.get("name")
            keys = config.get("model_keys")
            if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
                raise ValueError(f"{source_path}: config name is unsafe")
            if not isinstance(keys, list) or not keys or len(set(keys)) != len(keys):
                raise ValueError(f"{source_path}/{name}: model_keys must be unique and non-empty")
            unknown = sorted(set(keys) - set(primary_by_key))
            if unknown:
                raise ValueError(f"{source_path}/{name}: unknown primary keys: {', '.join(unknown)}")
            server = config.get("server", {})
            if not isinstance(server, dict):
                raise ValueError(f"{source_path}/{name}: server must be an object")
            generated_path = validate_scenario_path(f"{output_root}/{name}.json")
            if generated_path in seen_paths:
                raise ValueError(f"duplicate generated vLLM config path: {generated_path}")
            seen_paths.add(generated_path)
            records.append(
                {
                    "path": generated_path,
                    "name": name,
                    "provider": provider,
                    "hardware": copy.deepcopy(hardware),
                    "compatibility": copy.deepcopy(compatibility),
                    "staging": copy.deepcopy(staging),
                    "verification_status": source.get("verification", "configuration-only"),
                    "description": config.get("description", ""),
                    "model_keys": list(keys),
                    "server": copy.deepcopy(server),
                    "source": source_path.relative_to(ROOT).as_posix(),
                }
            )
    return records


def effective_server(lane: dict, overrides: dict | None = None) -> dict:
    server = copy.deepcopy(lane["server"])
    server.update(copy.deepcopy(overrides or {}))
    server.setdefault("backend_host", "127.0.0.1")
    server.setdefault("backend_port", 8001)
    server.setdefault("public_port", 8000)
    return server


def json_arg(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def server_command(lane: dict, server: dict) -> list[str]:
    command = [
        "vllm",
        "serve",
        lane["container_path"],
        "--host",
        str(server["backend_host"]),
        "--port",
        str(server["backend_port"]),
        "--served-model-name",
        lane["request_model_id"],
    ]
    for key, flag in (
        ("tensor_parallel_size", "--tensor-parallel-size"),
        ("pipeline_parallel_size", "--pipeline-parallel-size"),
        ("max_model_len", "--max-model-len"),
        ("max_num_seqs", "--max-num-seqs"),
        ("max_num_batched_tokens", "--max-num-batched-tokens"),
        ("gpu_memory_utilization", "--gpu-memory-utilization"),
        ("kv_cache_dtype", "--kv-cache-dtype"),
        ("quantization", "--quantization"),
        ("load_format", "--load-format"),
        ("reasoning_parser", "--reasoning-parser"),
        ("tool_call_parser", "--tool-call-parser"),
        ("attention_backend", "--attention-backend"),
        ("max_num_partial_prefills", "--max-num-partial-prefills"),
    ):
        if server.get(key) is not None:
            command.extend([flag, str(server[key])])
    for key, flag in (
        ("enable_auto_tool_choice", "--enable-auto-tool-choice"),
        ("enable_prefix_caching", "--enable-prefix-caching"),
        ("enforce_eager", "--enforce-eager"),
        ("trust_remote_code", "--trust-remote-code"),
        ("disable_log_requests", "--disable-log-requests"),
    ):
        if server.get(key):
            command.append(flag)
    lora_modules = server.get("lora_modules", [])
    if not isinstance(lora_modules, list) or any(not isinstance(value, str) or not value for value in lora_modules):
        raise ValueError(f"{lane['key']}: lora_modules must contain strings")
    if lora_modules:
        command.append("--enable-lora")
        command.append("--lora-modules")
        command.extend(lora_modules)
    for key, flag in (("compilation_config", "--compilation-config"), ("hf_overrides", "--hf-overrides")):
        if server.get(key) is not None:
            command.extend([flag, json_arg(server[key])])
    speculative = server.get("speculative", {})
    if speculative is None:
        speculative = {}
    if not isinstance(speculative, dict):
        raise ValueError(f"{lane['key']}: speculative settings must be an object")
    if speculative.get("enabled"):
        config = {key: value for key, value in speculative.items() if key != "enabled"}
        for required in ("method", "num_speculative_tokens"):
            if required not in config:
                raise ValueError(f"{lane['key']}: speculative setting {required} is required")
        command.extend(["--speculative-config", json_arg(config)])
    extra_args = server.get("extra_args", [])
    if not isinstance(extra_args, list) or any(not isinstance(value, str) for value in extra_args):
        raise ValueError(f"{lane['key']}: extra_args must contain strings")
    command.extend(extra_args)
    return command


def model_config_record(lane: dict) -> dict:
    return {
        "key": lane["key"],
        "request_model_id": lane["request_model_id"],
        "model_slug": lane["model_slug"],
        "quant_slug": lane["quant_slug"],
        "aliases": lane["aliases"],
        "profile_id": lane["profile_id"],
        "tasks": lane["tasks"],
        "precision": lane["precision"],
        "capabilities": lane["capabilities"],
        "modalities": lane["modalities"],
        "native_context_length": lane["native_context_length"],
        "max_context_length": lane["max_context_length"],
    }


def server_config(lane: dict, overrides: dict | None = None) -> dict:
    server = effective_server(lane, overrides)
    return {
        "schema_version": 1,
        "runtime": "vllm",
        "host": "0.0.0.0",
        "port": server["public_port"],
        "backend_host": server["backend_host"],
        "backend_port": server["backend_port"],
        "command": server_command(lane, server),
        "server": server,
        "models": [model_config_record(lane)],
        "served_model_name": lane["request_model_id"],
    }


def residency(server: dict) -> dict:
    speculative = server.get("speculative", {}) or {}
    return {
        "runtime_mode": "text",
        "context_length": server.get("max_model_len"),
        "max_num_seqs": server.get("max_num_seqs"),
        "max_num_batched_tokens": server.get("max_num_batched_tokens"),
        "gpu_memory_utilization": server.get("gpu_memory_utilization"),
        "tensor_parallel_size": server.get("tensor_parallel_size"),
        "pipeline_parallel_size": server.get("pipeline_parallel_size", 1),
        "kv_cache_dtype": server.get("kv_cache_dtype"),
        "prefix_caching": bool(server.get("enable_prefix_caching")),
        "capacity": {
            "effective_admitted_concurrency": "unknown-until-smoke",
            "token_pool": "vLLM scheduler-managed",
            "request_context_length": server.get("max_model_len"),
        },
        "speculative": {
            "enabled": bool(speculative.get("enabled")),
            "method": speculative.get("method"),
            "num_speculative_tokens": speculative.get("num_speculative_tokens"),
        },
    }


def lane_inventory(lane: dict) -> dict:
    artifacts = [
        {
            **artifact_identity(artifact),
            "id": artifact_download_id(artifact),
            "role": artifact.get("role"),
        }
        for artifact in lane["artifacts"]
    ]
    return {
        "key": lane["key"],
        "request_model_id": lane["request_model_id"],
        "quant_slug": lane["quant_slug"],
        "aliases": lane["aliases"],
        "profile_id": lane["profile_id"],
        "family": lane["family"],
        "model_slug": lane["model_slug"],
        "tasks": lane["tasks"],
        "precision": lane["precision"],
        "capabilities": lane["capabilities"],
        "modalities": lane["modalities"],
        "native_context_length": lane["native_context_length"],
        "max_context_length": lane["max_context_length"],
        "server": lane["server"],
        "server_model_path": lane["container_path"],
        "artifact_bytes": sum(artifact["size"] for artifact in lane["artifacts"]),
        "artifacts": artifacts,
    }


def deployment_model_records(lanes: list[dict]) -> list[dict]:
    return [model_config_record(lane) for lane in lanes]


def deployment_inventory(runtime: dict, lanes: list[dict], scenarios: list[dict]) -> dict:
    primary = [lane for lane in lanes if lane["primary"]]
    primary_by_key = {lane["key"]: lane for lane in primary}
    if not primary:
        raise ValueError("at least one primary vLLM model is required")

    default_lane = primary[0]
    default_config = server_config(default_lane)
    deployments = [
        {
            "id": "vllm/cuda13",
            "runtime": "vllm",
            "kind": "runtime-default",
            "selection_scope": "runtime-default",
            "provider": "unspecified",
            "image": "vllm-cuda13",
            "server_config": "/app/server.json",
            "prestage_manifest": "/app/server.prestage",
            "environment": {
                "VLLM_SERVER_CONFIG": "/app/server.json",
                "VLLM_PRESTAGE_MODELS": "",
            },
            "models": deployment_model_records([default_lane]),
            "server": default_config["server"],
            "server_command": default_config["command"],
            "residency": residency(default_config["server"]),
            "staging": {"source": "huggingface-only", "manifest_selection": "server sidecar"},
            "verification_status": "configuration-only",
            "runtime_modes": ["text"],
            "description": "Provider-neutral Blackwell starting lane; use a hardware scenario for tuned context and concurrency.",
        }
    ]
    for scenario in scenarios:
        selected = [primary_by_key[key] for key in scenario["model_keys"]]
        if len(selected) != 1:
            raise ValueError(f"{scenario['path']}: vLLM configs must contain exactly one model")
        config = server_config(selected[0], scenario["server"])
        config_path = f"/server-configs/{scenario['path']}"
        deployments.append(
            {
                "id": scenario["path"][:-5],
                "runtime": "vllm",
                "kind": "hardware-scenario",
                "provider": scenario["provider"],
                "hardware": scenario["hardware"],
                "compatibility": scenario["compatibility"],
                "image": "vllm-cuda13",
                "server_config": config_path,
                "prestage_manifest": config_path[:-5] + ".prestage",
                "environment": {
                    "VLLM_SERVER_CONFIG": config_path,
                    "VLLM_PRESTAGE_MODELS": "",
                },
                "models": deployment_model_records(selected),
                "server": config["server"],
                "server_command": config["command"],
                "residency": residency(config["server"]),
                "staging": scenario["staging"],
                "verification_status": scenario["verification_status"],
                "runtime_modes": ["text"],
                "description": scenario["description"],
                "source": scenario["source"],
            }
        )

    payload = {
        "schema_version": "prefer.vllm-deployment-inventory.v1",
        "runtime": runtime["runtime"],
        "composition": {
            "schema_version": "prefer.runtime-composition.v1",
            "activation": "opt-in; existing VLLM_SERVER_CONFIG remains compatible when no composition variable is set",
            "multi_model": False,
            "effective_config_path": "/run/prefer/vllm.json",
            "effective_plan_path": "/run/prefer/plan.json",
            "effective_handoff_path": "/run/prefer/handoff.json",
            "runtime_handoff_schema": "prefer.runtime-handoff.v1",
            "compose_environment_prefix": "VLLM",
            "override_merge": "objects merge recursively; scalar and array values replace",
            "environment": {
                "PREFER_DEPLOYMENT": {"type": "string", "source": "deployments[].id"},
                "PREFER_BUNDLE": {"type": "unsupported"},
                "PREFER_MODELS": {"type": "single-string", "source": "models key, model_slug, request_model_id, or alias"},
                "PREFER_SERVER_OVERRIDES": {"type": "json-object", "applies_to": "vLLM server settings"},
                "PREFER_MODEL_OVERRIDES": {"type": "json-object-map", "applies_to": "the selected model's server settings"},
                "PREFER_RUNTIME_HANDOFF": {"type": "path", "source": "immutable release-matched runtime handoff"},
            },
            "selection_rules": [
                "one model is allowed per vLLM process",
                "a friendly model selection uses its primary catalog lane",
                "switching models inherits a matching config from the selected hardware deployment when available",
                "a runtime handoff replaces model selection and may include controller-extension artifacts",
            ],
            "precedence": [
                "catalog model and lane defaults",
                "hardware deployment defaults",
                "PREFER_SERVER_OVERRIDES",
                "PREFER_MODEL_OVERRIDES",
                "raw engine arguments",
            ],
            "setting_sources": {"server": "deployments[].server", "model": "models[].server"},
        },
        "base_image": runtime["base_image"],
        "requirements": runtime["requirements"],
        "staging": runtime["staging"],
        "features": runtime["features"],
        "experimental_routes": runtime.get("experimental_routes", {}),
        "known_limitations": runtime["known_limitations"],
        "api": {
            "health": "GET /health",
            "ready": "GET /readyz",
            "models": "GET /v1/models",
            "chat": "POST /v1/chat/completions",
            "completion": "POST /v1/completions",
        },
        "runtime_modes": ["text"],
        "model_profiles": {lane["profile_id"]: lane["profile"] for lane in primary},
        "models": {lane["key"]: lane_inventory(lane) for lane in primary},
        "deployments": deployments,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"catalog_fingerprint": fingerprint, **payload}


def download_script(lanes: list[dict]) -> str:
    primary = [lane for lane in lanes if lane["primary"]]
    artifacts: dict[str, dict] = {}
    model_artifact_ids: dict[str, list[str]] = {}
    for lane in lanes:
        ids = []
        for artifact in lane["artifacts"]:
            artifact_id = artifact_download_id(artifact)
            artifacts.setdefault(artifact_id, artifact)
            ids.append(artifact_id)
        model_artifact_ids[lane["key"]] = ids

    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"readonly VLLM_GENERATED_MODEL_KEYS=\"{','.join(lane['key'] for lane in primary)}\"",
        "GENERATED_MODEL_KEYS=$VLLM_GENERATED_MODEL_KEYS",
        "LEGACY_SMALL_MODELS=$VLLM_GENERATED_MODEL_KEYS",
        "",
        "vllm_model_key_artifact_ids() {",
        '  case "$1" in',
    ]
    for key, ids in model_artifact_ids.items():
        lines.append(f"  {key}) printf '%s\\n' {' '.join(json.dumps(item) for item in ids)} ;;")
    lines.extend([
        '    *) echo "[vllm-download] unknown model key: $1" >&2; return 2 ;;',
        "  esac",
        "}",
        "",
        "vllm_download_artifact_id() {",
        '  case "$1" in',
    ])
    for artifact_id, artifact in artifacts.items():
        lines.extend(
            [
                f"  {artifact_id})",
                f"    prefer_download_hf_artifact \"vllm-download\" \"$1\" \"{artifact['repo']}\" \"{artifact['revision']}\" \"{artifact['path']}\" {artifact['size']} \"{artifact['sha256']}\"",
                "    ;;",
            ]
        )
    lines.extend([
        '    *) echo "[vllm-download] unknown artifact id: $1" >&2; return 2 ;;',
        "  esac",
        "}",
        "",
        "vllm_download_artifact_id_s3() {",
        '  case "$1" in',
    ])
    for artifact_id, artifact in artifacts.items():
        lines.extend(
            [
                f"  {artifact_id})",
                f"    prefer_download_s3_artifact \"vllm-s3\" \"$1\" \"{artifact['repo']}\" \"{artifact['path']}\" {artifact['size']} \"{artifact['sha256']}\" \"$VLLM_S3_BUCKET_NAME\" \"${{VLLM_S3_MODEL_PREFIX:-}}\"",
                "    ;;",
            ]
        )
    lines.extend([
        '    *) echo "[vllm-download] unknown artifact id: $1" >&2; return 2 ;;',
        "  esac",
        "}",
        "",
        "vllm_s3_stage_artifact() {",
        '  local artifact_id="$1"',
        "  local status=0",
        '  if vllm_download_artifact_id_s3 "$artifact_id"; then return 0; else status=$?; fi',
        '  echo "[vllm-download] artifact $artifact_id: S3 unavailable or invalid (status $status); falling back to Hugging Face" >&2',
        '  vllm_download_artifact_id "$artifact_id"',
        "}",
        "",
        "vllm_download_model_keys() {",
        "  prefer_download_model_keys \\",
        "    \"vllm-download\" \"${VLLM_DOWNLOAD_JOBS:-4}\" 8 \\",
        "    vllm_model_key_artifact_ids vllm_download_artifact_id \"$@\"",
        "}",
        "",
        "vllm_download_model_keys_s3() {",
        "  prefer_download_model_keys \\",
        "    \"vllm-s3-download\" \"${VLLM_DOWNLOAD_JOBS:-4}\" 8 \\",
        "    vllm_model_key_artifact_ids vllm_s3_stage_artifact \"$@\"",
        "}",
        "",
        "vllm_download_model_key() { vllm_download_model_keys \"$1\"; }",
        "download_model_key() { vllm_download_model_key \"$1\"; }",
        "",
    ])
    return "\n".join(lines)


def rendered_outputs() -> dict[Path, str]:
    runtime = load_json(RUNTIME_PATH)
    if runtime.get("schema_version") != 1:
        raise ValueError("runtime.json schema_version must be 1")
    lanes = model_lanes()
    primary_by_key = {lane["key"]: lane for lane in lanes if lane["primary"]}
    scenarios = load_scenarios(primary_by_key)
    default_lane = next(iter(primary_by_key.values()))
    outputs: dict[Path, str] = {
        ROOT / "server.generated.json": json.dumps(server_config(default_lane), indent=2) + "\n",
        ROOT / "server.generated.prestage": ",".join(primary_by_key) + "\n",
        ROOT / "model-downloads.generated.sh": download_script(lanes),
        ROOT / "deployment-inventory.generated.json": json.dumps(
            deployment_inventory(runtime, lanes, scenarios), indent=2
        )
        + "\n",
    }
    for scenario in scenarios:
        selected = [primary_by_key[key] for key in scenario["model_keys"]]
        if len(selected) != 1:
            raise ValueError(f"{scenario['path']}: vLLM configs must contain exactly one model")
        config = server_config(selected[0], scenario["server"])
        config_path = CONFIGS_ROOT / scenario["path"]
        outputs[config_path] = json.dumps(config, indent=2) + "\n"
        outputs[config_path.with_suffix(".prestage")] = ",".join(scenario["model_keys"]) + "\n"
    return outputs


def parse_composition_list(value: str) -> list[str]:
    result: list[str] = []
    for item in re.split(r"[,\r\n]+", value or ""):
        item = item.strip()
        if item and item not in result:
            result.append(item)
    return result


def parse_composition_object(value: str, label: str) -> dict:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def normalize_runtime_config(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    for prefix in ("/server-configs/", "server-configs/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    if normalized in {"/app/server.json", "server.json", "default", "vllm/cuda13"}:
        return "default"
    if not normalized.endswith(".json"):
        normalized += ".json"
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe vLLM deployment: {value!r}")
    return path.as_posix()


def vllm_selection_names(lane: dict) -> set[str]:
    return {
        lane["key"],
        lane["id"],
        lane["request_model_id"],
        lane["model_slug"],
        *lane.get("aliases", []),
    }


def compose_runtime_config(
    *,
    base: str,
    bundle_value: str,
    model_value: str,
    server_overrides_value: str,
    model_overrides_value: str,
) -> tuple[dict, list[str], dict]:
    requested_bundles = parse_composition_list(bundle_value)
    if requested_bundles:
        raise ValueError("vLLM does not define multi-model bundles; select one PREFER_MODELS entry")
    requested_models = parse_composition_list(model_value)
    if len(requested_models) > 1:
        raise ValueError("vLLM runtime composition accepts exactly one model")
    server_overrides = parse_composition_object(server_overrides_value, "PREFER_SERVER_OVERRIDES")
    model_overrides = parse_composition_object(model_overrides_value, "PREFER_MODEL_OVERRIDES")
    if any(not isinstance(value, dict) for value in model_overrides.values()):
        raise ValueError("PREFER_MODEL_OVERRIDES values must be JSON objects")

    lanes = model_lanes()
    primary = [lane for lane in lanes if lane["primary"]]
    lanes_by_key = {lane["key"]: lane for lane in lanes}
    primary_by_key = {lane["key"]: lane for lane in primary}
    scenarios = load_scenarios(primary_by_key)
    scenario_by_path = {scenario["path"]: scenario for scenario in scenarios}
    normalized = normalize_runtime_config(base)
    explicit_base_path = Path(base)

    if normalized == "default" or explicit_base_path.is_file():
        base_path = explicit_base_path
        if not base_path.is_file():
            installed_default = Path("/app/server.json")
            base_path = installed_default if installed_default.is_file() else ROOT / "server.generated.json"
        base_config = load_json(base_path)
        model_records = base_config.get("models", [])
        if len(model_records) != 1 or model_records[0].get("key") not in primary_by_key:
            raise ValueError("cannot map the vLLM base config to one primary catalog model")
        base_lane = primary_by_key[model_records[0]["key"]]
        base_server = copy.deepcopy(base_config.get("server", {}))
        base_deployment = (
            PurePosixPath(normalized).with_suffix("").as_posix()
            if normalized != "default"
            else "vllm/cuda13"
        )
        cohort: list[dict] = []
    else:
        scenario = scenario_by_path.get(normalized)
        if scenario is None:
            raise ValueError(f"unknown vLLM deployment: {base!r}")
        if len(scenario["model_keys"]) != 1:
            raise ValueError(f"{normalized}: vLLM deployment must contain one model")
        base_lane = primary_by_key[scenario["model_keys"][0]]
        base_server = copy.deepcopy(scenario["server"])
        base_deployment = PurePosixPath(normalized).with_suffix("").as_posix()
        parent = PurePosixPath(normalized).parent
        cohort = [record for record in scenarios if PurePosixPath(record["path"]).parent == parent]

    selected = base_lane
    selected_server = base_server
    if requested_models:
        selection = requested_models[0]
        matches = [lane for lane in lanes if selection in vllm_selection_names(lane)]
        if not matches:
            raise ValueError(f"unknown vLLM model selection: {selection!r}")
        if selection in lanes_by_key:
            selected = lanes_by_key[selection]
        else:
            primary_matches = [lane for lane in matches if lane["primary"]]
            if len(primary_matches) != 1:
                raise ValueError(
                    f"ambiguous vLLM model {selection!r}; choose an exact lane: "
                    + ", ".join(lane["key"] for lane in matches)
                )
            selected = primary_matches[0]
        if selected["key"] != base_lane["key"]:
            matching_scenarios = [
                record
                for record in cohort
                if any(primary_by_key[key]["model_slug"] == selected["model_slug"] for key in record["model_keys"])
            ]
            selected_server = copy.deepcopy(
                matching_scenarios[0]["server"]
                if matching_scenarios
                else base_server if selected["model_slug"] == base_lane["model_slug"] else {}
            )

    matching_overrides = [
        value for name, value in model_overrides.items() if name in vllm_selection_names(selected)
    ]
    if len(matching_overrides) > 1:
        raise ValueError(f"multiple PREFER_MODEL_OVERRIDES entries target {selected['key']}")
    unknown_targets = [name for name in model_overrides if name not in vllm_selection_names(selected)]
    if unknown_targets:
        raise ValueError("PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown_targets))
    model_override = matching_overrides[0] if matching_overrides else {}
    effective_overrides = deep_merge(selected_server, server_overrides, model_override)
    config = server_config(selected, effective_overrides)
    prestage = [selected["key"]]
    plan = {
        "schema_version": "prefer.runtime-plan.v1",
        "runtime": "vllm",
        "base_deployment": base_deployment,
        "bundles": [],
        "requested_models": requested_models,
        "resolved_model_keys": prestage,
        "server_overrides": server_overrides,
        "model_overrides": {selected["key"]: model_override} if model_override else {},
        "precedence": [
            "catalog model and lane defaults",
            "hardware deployment defaults",
            "PREFER_SERVER_OVERRIDES",
            "PREFER_MODEL_OVERRIDES",
            "vLLM command arguments",
        ],
    }
    return config, prestage, plan


def resolve_handoff_base(base: str, default_base: str, handoff: dict, primary_by_key: dict[str, dict]) -> tuple[dict, str]:
    reference = base or str(handoff.get("base_deployment") or default_base)
    normalized = normalize_runtime_config(reference or "default")
    explicit = Path(reference) if reference else Path()
    if normalized == "default":
        config_path = explicit if explicit.is_file() else ROOT / "server.generated.json"
        config = load_json(config_path)
        server = copy.deepcopy(config.get("server", {}))
        for name in (
            "served_model_name", "quantization", "load_format", "reasoning_parser",
            "tool_call_parser", "trust_remote_code", "speculative", "lora_modules", "extra_args",
        ):
            server.pop(name, None)
        return server, "vllm/cuda13"
    if explicit.is_file():
        config = load_json(explicit)
        server = copy.deepcopy(config.get("server", {}))
        for name in (
            "served_model_name", "quantization", "load_format", "reasoning_parser",
            "tool_call_parser", "trust_remote_code", "speculative", "lora_modules", "extra_args",
        ):
            server.pop(name, None)
        return server, PurePosixPath(normalized).with_suffix("").as_posix()
    scenarios = load_scenarios(primary_by_key)
    scenario = next((record for record in scenarios if record["path"] == normalized), None)
    if scenario is None:
        raise ValueError(f"unknown vLLM runtime handoff deployment: {reference!r}")
    server = copy.deepcopy(scenario["server"])
    server.pop("speculative", None)
    return server, PurePosixPath(normalized).with_suffix("").as_posix()


def handoff_vllm_lane(model: dict, artifacts: dict[str, dict]) -> dict:
    model_id = model.get("model_id")
    request_model_id = model.get("request_model_id")
    if not isinstance(model_id, str) or not model_id or not isinstance(request_model_id, str) or not request_model_id:
        raise ValueError("runtime handoff model identity is invalid")
    raw_settings = model.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise ValueError(f"runtime handoff model {model_id} settings must be an object")
    model_settings = copy.deepcopy(raw_settings.get("model", {}))
    launcher = copy.deepcopy(raw_settings.get("launcher", {}))
    if not isinstance(model_settings, dict) or not isinstance(launcher, dict):
        raise ValueError(f"runtime handoff model {model_id} model and launcher settings must be objects")
    protected = {"model_path", "served_model_name", "lora_modules"} & launcher.keys()
    if protected:
        raise ValueError(f"runtime handoff launcher cannot replace {sorted(protected)[0]}")
    selected_artifacts = []
    for artifact_id in model.get("artifact_ids", []):
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            raise ValueError(f"runtime handoff model {model_id} references unknown artifact {artifact_id}")
        selected_artifacts.append(artifact)
    repository_path = model.get("repository_path")
    if not isinstance(repository_path, str) or not repository_path.startswith("/"):
        raise ValueError(f"runtime handoff model {model_id} has no materialized repository path")
    ggufs = [
        artifact for artifact in selected_artifacts
        if str(artifact.get("local_path", "")).lower().endswith(".gguf")
        and str(artifact.get("role", "")).lower() not in {"projector", "mmproj", "draft", "mtp", "dspark", "dflash"}
    ]
    container_path = ggufs[0]["local_path"] if launcher.get("load_format") == "gguf" and ggufs else repository_path
    lora_modules = handoff_lora_modules(selected_artifacts, model_id)
    if lora_modules:
        launcher["lora_modules"] = lora_modules
    task = str(model_settings.get("task", "chat"))
    tasks = model_settings.get("tasks", [task, "completion"] if task == "chat" else [task])
    if not isinstance(tasks, list) or any(not isinstance(value, str) for value in tasks):
        raise ValueError(f"runtime handoff model {model_id} tasks must contain strings")
    capabilities = model.get("capabilities", [])
    modalities = model_settings.get("modalities", {})
    if not isinstance(capabilities, list) or not isinstance(modalities, dict):
        raise ValueError(f"runtime handoff model {model_id} capability metadata is invalid")
    return {
        "key": model_id,
        "request_model_id": request_model_id,
        "model_slug": model_id,
        "quant_slug": model.get("quant", "unknown"),
        "aliases": [request_model_id],
        "profile_id": model_id,
        "tasks": tasks,
        "precision": model.get("quant", "unknown"),
        "capabilities": capabilities,
        "modalities": modalities,
        "native_context_length": model_settings.get("native_context_length"),
        "max_context_length": model_settings.get("max_context_length"),
        "container_path": container_path,
        "server": launcher,
    }


def handoff_lora_modules(artifacts: list[dict], model_id: str) -> list[str]:
    modules: dict[str, str] = {}
    for artifact in artifacts:
        if str(artifact.get("role", "")).lower() not in {"lora", "adapter"}:
            continue
        settings = artifact.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError(f"runtime handoff LoRA settings for {model_id} must be an object")
        name = settings.get("adapter_name", settings.get("name"))
        if name is None:
            name = str(artifact.get("repository", "")).split("/")[-1]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError(f"runtime handoff LoRA name for {model_id} is invalid")
        local_path = artifact.get("local_path")
        if not isinstance(local_path, str) or not local_path.startswith("/"):
            raise ValueError(f"runtime handoff LoRA path for {model_id} is invalid")
        adapter_root = str(PurePosixPath(local_path).parent)
        previous = modules.get(name)
        if previous is not None and previous != adapter_root:
            raise ValueError(f"runtime handoff LoRA name {name} maps to multiple directories")
        modules[name] = adapter_root
    return [f"{name}={path}" for name, path in sorted(modules.items())]


def compose_runtime_handoff_config(
    *,
    handoff_path: str,
    base: str,
    default_base: str,
    server_overrides_value: str,
    model_overrides_value: str,
) -> tuple[dict, list[str], dict]:
    handoff = load_json(Path(handoff_path))
    if handoff.get("schema_version") != "prefer.runtime-handoff.v1" or handoff.get("engine") != "vllm":
        raise ValueError("materialized runtime handoff is not for vLLM")
    models = handoff.get("models")
    raw_artifacts = handoff.get("artifacts")
    if not isinstance(models, list) or len(models) != 1 or not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ValueError("vLLM runtime handoff requires exactly one model and at least one artifact")
    artifacts = {artifact.get("id"): artifact for artifact in raw_artifacts if isinstance(artifact, dict)}
    if len(artifacts) != len(raw_artifacts):
        raise ValueError("materialized runtime handoff has duplicate or invalid artifacts")
    lanes = model_lanes()
    primary_by_key = {lane["key"]: lane for lane in lanes if lane["primary"]}
    base_server, base_deployment = resolve_handoff_base(base, default_base, handoff, primary_by_key)
    lane = handoff_vllm_lane(models[0], artifacts)
    handoff_server = handoff.get("server_settings", {})
    server_overrides = parse_composition_object(server_overrides_value, "PREFER_SERVER_OVERRIDES")
    model_overrides = parse_composition_object(model_overrides_value, "PREFER_MODEL_OVERRIDES")
    if not isinstance(handoff_server, dict) or any(not isinstance(value, dict) for value in model_overrides.values()):
        raise ValueError("runtime handoff server and model overrides must be objects")
    names = {lane["key"], lane["request_model_id"]}
    matching = [value for name, value in model_overrides.items() if name in names]
    if len(matching) > 1:
        raise ValueError(f"multiple PREFER_MODEL_OVERRIDES entries target {lane['key']}")
    unknown = [name for name in model_overrides if name not in names]
    if unknown:
        raise ValueError("PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown))
    model_override = matching[0] if matching else {}
    protected = {"model_path", "served_model_name", "lora_modules"}
    for source in (handoff_server, server_overrides, model_override):
        conflict = protected & source.keys()
        if conflict:
            raise ValueError(f"runtime overrides cannot replace {sorted(conflict)[0]}")
    effective = deep_merge(lane["server"], base_server, handoff_server, server_overrides, model_override)
    config = server_config(lane, effective)
    artifact_ids = [artifact["id"] for artifact in raw_artifacts]
    plan = {
        "schema_version": "prefer.runtime-plan.v1",
        "runtime": "vllm",
        "base_deployment": base_deployment,
        "handoff_fingerprint": handoff.get("handoff_fingerprint"),
        "bundles": [],
        "requested_models": [lane["key"]],
        "resolved_model_keys": [],
        "resolved_artifact_ids": artifact_ids,
        "server_overrides": server_overrides,
        "model_overrides": {lane["key"]: model_override} if model_override else {},
        "precedence": [
            "runtime handoff model and artifact settings",
            "hardware deployment defaults",
            "runtime handoff server settings",
            "PREFER_SERVER_OVERRIDES",
            "PREFER_MODEL_OVERRIDES",
            "vLLM command arguments",
        ],
    }
    return config, artifact_ids, plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--compose", action="store_true")
    parser.add_argument("--compose-handoff", action="store_true")
    parser.add_argument("--handoff-input", default="")
    parser.add_argument("--default-base", default="")
    parser.add_argument("--base", default="")
    parser.add_argument("--bundles", default="")
    parser.add_argument("--models", default="")
    parser.add_argument("--server-overrides", default="")
    parser.add_argument("--model-overrides", default="")
    parser.add_argument("--output")
    parser.add_argument("--prestage-output")
    parser.add_argument("--plan-output")
    args = parser.parse_args()
    if args.compose_handoff:
        if args.check or args.compose or not args.handoff_input or not args.output or not args.prestage_output or not args.plan_output:
            parser.error("--compose-handoff requires --handoff-input, --output, --prestage-output, and --plan-output")
        config, artifact_ids, plan = compose_runtime_handoff_config(
            handoff_path=args.handoff_input,
            base=args.base,
            default_base=args.default_base,
            server_overrides_value=args.server_overrides,
            model_overrides_value=args.model_overrides,
        )
        for value in (args.output, args.prestage_output, args.plan_output):
            Path(value).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
        Path(args.prestage_output).write_text(",".join(artifact_ids) + "\n", encoding="utf-8", newline="\n")
        Path(args.plan_output).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"composed vLLM runtime config from immutable handoff {plan['handoff_fingerprint']}")
        return
    if args.compose:
        if args.check or not args.base or not args.output or not args.prestage_output or not args.plan_output:
            parser.error("--compose requires --base, --output, --prestage-output, and --plan-output")
        config, prestage, plan = compose_runtime_config(
            base=args.base,
            bundle_value=args.bundles,
            model_value=args.models,
            server_overrides_value=args.server_overrides,
            model_overrides_value=args.model_overrides,
        )
        for value in (args.output, args.prestage_output, args.plan_output):
            Path(value).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
        Path(args.prestage_output).write_text(",".join(prestage) + "\n", encoding="utf-8", newline="\n")
        Path(args.plan_output).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"composed vLLM runtime config from {plan['base_deployment']}: {', '.join(prestage)}")
        return
    try:
        outputs = rendered_outputs()
        failures: list[str] = []
        for path, content in outputs.items():
            if args.check:
                if not path.is_file():
                    failures.append(f"missing {path.relative_to(ROOT)}")
                elif path.read_text(encoding="utf-8") != content:
                    failures.append(f"stale {path.relative_to(ROOT)}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
        if failures:
            raise ValueError("; ".join(failures))
        if args.check:
            print(f"vLLM generated files are current ({len(outputs)} files)")
        else:
            print(f"generated {len(outputs)} vLLM files")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"generate.py: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
