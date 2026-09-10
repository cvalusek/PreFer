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
RUNTIME_MODES = {"text", "diffusion"}


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


def validate_artifact(key: str, artifact: dict, artifacts_by_destination: dict) -> None:
    repo = artifact.get("repo")
    if not isinstance(repo, str) or not REPO_PATTERN.fullmatch(repo):
        raise ValueError(f"{key}: artifact repo must be a safe owner/name")
    revision = artifact.get("revision")
    if not isinstance(revision, str) or not SHA1_PATTERN.fullmatch(revision):
        raise ValueError(f"{key}: artifact revision must be an immutable SHA")
    artifact_sha = artifact.get("sha256")
    if not isinstance(artifact_sha, str) or not SHA256_PATTERN.fullmatch(artifact_sha):
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
    previous = artifacts_by_destination.get(destination)
    if previous is not None and previous != identity:
        raise ValueError(
            f"{key}: artifact destination {repo}/{artifact_path} has conflicting immutable identities"
        )
    artifacts_by_destination[destination] = identity


def model_lanes() -> list[dict]:
    lanes: list[dict] = []
    seen_keys: set[str] = set()
    seen_ids: set[str] = set()
    artifacts_by_destination: dict[tuple[str, str], dict] = {}
    for path in sorted(MODELS_ROOT.glob("*/*/model.json")):
        source = load_json(path)
        relative = path.relative_to(MODELS_ROOT)
        family, model_slug, _ = relative.parts
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
        runtime_mode = shared.get("runtime_mode", "text")
        if runtime_mode not in RUNTIME_MODES:
            raise ValueError(f"{path}: shared.runtime_mode must be text or diffusion")
        profile_id = shared.get("profile_id", model_slug)
        if not isinstance(profile_id, str) or not profile_id:
            raise ValueError(f"{path}: shared.profile_id must be a non-empty string")
        base_model = shared.get("base_model")
        if base_model is not None:
            if not isinstance(base_model, dict):
                raise ValueError(f"{path}: shared.base_model must be an object")
            if not REPO_PATTERN.fullmatch(str(base_model.get("repo", ""))):
                raise ValueError(f"{path}: shared.base_model.repo must be a safe owner/name")
            if not SHA1_PATTERN.fullmatch(str(base_model.get("revision", ""))):
                raise ValueError(f"{path}: shared.base_model.revision must be an immutable SHA")
            if not isinstance(base_model.get("model_path", base_model["repo"]), str):
                raise ValueError(f"{path}: shared.base_model.model_path must be a string")
        tasks = shared.get("tasks", [shared.get("task")])
        if (
            not isinstance(tasks, list)
            or not tasks
            or any(not isinstance(task, str) or not task for task in tasks)
        ):
            raise ValueError(f"{path}: shared.tasks must be a non-empty list of strings")
        capability_aliases = shared.get("capability_aliases", {})
        if not isinstance(capability_aliases, dict) or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or not key
            or not value
            for key, value in capability_aliases.items()
        ):
            raise ValueError(f"{path}: shared.capability_aliases must map strings to strings")
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
                validate_artifact(key, artifact, artifacts_by_destination)
            artifact_repos = {artifact["repo"] for artifact in artifacts}
            server_repo = quant.get("server_repo")
            if server_repo is None:
                if len(artifact_repos) != 1:
                    raise ValueError(
                        f"{key}: multi-repository packages require server_repo"
                    )
                server_repo = next(iter(artifact_repos))
            elif (
                not isinstance(server_repo, str)
                or not REPO_PATTERN.fullmatch(server_repo)
                or server_repo not in artifact_repos
            ):
                raise ValueError(
                    f"{key}: server_repo must name one of the package artifact repositories"
                )
            server_path = quant.get("server_path", ".")
            server_path_obj = PurePosixPath(str(server_path))
            if (
                not isinstance(server_path, str)
                or not server_path
                or "\\" in server_path
                or server_path_obj.is_absolute()
                or ".." in server_path_obj.parts
            ):
                raise ValueError(f"{key}: server_path must stay inside the server repository")
            container_path = (
                f"/models/{server_repo}"
                if server_path == "."
                else f"/models/{server_repo}/{server_path}"
            )
            server = copy.deepcopy(shared.get("server", {}))
            quant_server = quant.get("server", {})
            if not isinstance(server, dict) or not isinstance(quant_server, dict):
                raise ValueError(f"{key}: server settings must be objects")
            server.update(copy.deepcopy(quant_server))
            server.setdefault("runtime_mode", runtime_mode)
            if runtime_mode == "diffusion":
                server.setdefault("model_path", base_model.get("model_path") if base_model else None)
                server.setdefault("model_revision", base_model.get("revision") if base_model else None)
                if not server.get("model_path") or not server.get("model_revision"):
                    raise ValueError(f"{key}: diffusion lanes require server model_path and model_revision")
            request_model_id = quant.get("request_model_id", model_id)
            if not isinstance(request_model_id, str) or not request_model_id:
                raise ValueError(f"{key}: request_model_id must be a non-empty string")
            aliases = quant.get("aliases", [request_model_id])
            if (
                not isinstance(aliases, list)
                or not aliases
                or any(not isinstance(alias, str) or not alias for alias in aliases)
                or request_model_id not in aliases
            ):
                raise ValueError(f"{key}: aliases must include request_model_id")
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
                "runtime_mode": runtime_mode,
                "tasks": copy.deepcopy(tasks),
                "capability_aliases": copy.deepcopy(capability_aliases),
                "base_model": copy.deepcopy(base_model),
                "input_contract": copy.deepcopy(shared.get("input_contract", {})),
                "output_contract": copy.deepcopy(shared.get("output_contract", {})),
                **shared,
                "artifacts": copy.deepcopy(artifacts),
                "server_repo": server_repo,
                "server_path": server_path,
                "container_path": container_path,
                "server": server,
            }
            lanes.append(lane)
            seen_keys.add(key)
            if lane["primary"]:
                seen_ids.add(model_id)
    if not lanes:
        raise ValueError("no SGLang model catalogs found")
    lanes.sort(key=lambda lane: lane["key"])
    return lanes


def validate_scenario_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise ValueError(f"unsafe or non-JSON SGLang scenario path: {value!r}")
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
            or not hardware.get("compute_capability")
        ):
            raise ValueError(f"{source_path}: hardware with GPU count and capability is required")
        compatibility = source.get("compatibility", {})
        if not isinstance(compatibility, dict):
            raise ValueError(f"{source_path}: compatibility must be an object")
        staging = source.get("staging", {"source": "huggingface-only"})
        if not isinstance(staging, dict) or staging.get("source") not in STAGING_SOURCES:
            raise ValueError(f"{source_path}: staging must declare a supported source")
        configs = source.get("configs")
        if not isinstance(configs, list) or not configs:
            raise ValueError(f"{source_path}: configs must be a non-empty list")
        for config in configs:
            if not isinstance(config, dict):
                raise ValueError(f"{source_path}: every config must be an object")
            name = config.get("name")
            if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
                raise ValueError(f"{source_path}: config name is unsafe")
            keys = config.get("model_keys")
            if not isinstance(keys, list) or not keys or len(set(keys)) != len(keys):
                raise ValueError(f"{source_path}/{name}: model_keys must be unique and non-empty")
            unknown = sorted(set(keys) - set(primary_by_key))
            if unknown:
                raise ValueError(
                    f"{source_path}/{name}: unknown primary model keys: {', '.join(unknown)}"
                )
            server = config.get("server", {})
            if not isinstance(server, dict):
                raise ValueError(f"{source_path}/{name}: server must be an object")
            generated_path = validate_scenario_path(f"{output_root}/{name}.json")
            if generated_path in seen_paths:
                raise ValueError(f"duplicate generated SGLang server config path: {generated_path}")
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
    return server


def default_server_overrides() -> dict:
    return {
        "mem_fraction_static": 0.8,
        "max_running_requests": 1,
        "cuda_graph_max_bs": 1,
        "mamba_ssm_dtype": "bfloat16",
        "mamba_full_memory_ratio": 1.5,
        "mamba_radix_cache_strategy": "extra_buffer_lazy",
        "max_mamba_cache_size": 24,
        "speculative": {"enabled": False},
    }


def server_command(lane: dict, server: dict) -> list[str]:
    if lane.get("runtime_mode", "text") == "diffusion":
        command = [
            "sglang",
            "serve",
            "--model-type",
            "diffusion",
            "--host",
            "0.0.0.0",
            "--port",
            "30001",
            "--model-path",
            str(server["model_path"]),
            "--model-variant",
            str(server["model_variant"]),
            "--revision",
            str(server["model_revision"]),
        ]
        for key, flag in (
            ("num_gpus", "--num-gpus"),
            ("tp_size", "--tp-size"),
            ("sp_degree", "--sp-degree"),
            ("ulysses_degree", "--ulysses-degree"),
            ("encoder_parallel", "--encoder-parallel"),
            ("performance_mode", "--performance-mode"),
            ("quantization", "--quantization"),
            ("attention_backend", "--attention-backend"),
            ("layerwise_offload_components", "--layerwise-offload-components"),
            ("dit_offload_prefetch_size", "--dit-offload-prefetch-size"),
            ("dit_layerwise_resident_layers", "--dit-layerwise-resident-layers"),
            ("pin_cpu_memory", "--pin-cpu-memory"),
            ("output_path", "--output-path"),
            ("lora_path", "--lora-path"),
            ("lora_weight_name", "--lora-weight-name"),
            ("lora_nickname", "--lora-nickname"),
            ("lora_scale", "--lora-scale"),
            ("lora_alpha", "--lora-alpha"),
            ("lora_merge_mode", "--lora-merge-mode"),
        ):
            value = server.get(key)
            if value is None:
                continue
            if isinstance(value, bool):
                value = str(value).lower()
            command.extend([flag, str(value)])
        component_paths = server.get("component_weights_paths", {})
        if component_paths is not None:
            if not isinstance(component_paths, dict):
                raise ValueError(f"{lane['key']}: component_weights_paths must be an object")
            for component, path in sorted(component_paths.items()):
                if not isinstance(component, str) or not component or not isinstance(path, str) or not path:
                    raise ValueError(f"{lane['key']}: component weight paths must be non-empty strings")
                command.extend([f"--component-weights-paths.{component}", path])
        if "enable_torch_compile" in server:
            command.extend(["--enable-torch-compile", str(server["enable_torch_compile"]).lower()])
        if server.get("trust_remote_code", False):
            command.append("--trust-remote-code")
        return command

    command = [
        "python3",
        "-m",
        "sglang.launch_server",
        "--host",
        "0.0.0.0",
        "--port",
        "30000",
        "--model-path",
        lane["container_path"],
        "--served-model-name",
        lane["request_model_id"],
    ]
    if server.get("trust_remote_code", False):
        command.append("--trust-remote-code")
    for key, flag in (
        ("quantization", "--quantization"),
        ("tp_size", "--tp-size"),
        ("context_length", "--context-length"),
        ("mem_fraction_static", "--mem-fraction-static"),
        ("max_running_requests", "--max-running-requests"),
        ("cuda_graph_max_bs", "--cuda-graph-max-bs"),
        ("chunked_prefill_size", "--chunked-prefill-size"),
        ("attention_backend", "--attention-backend"),
        ("kv_cache_dtype", "--kv-cache-dtype"),
        ("mamba_ssm_dtype", "--mamba-ssm-dtype"),
        ("mamba_full_memory_ratio", "--mamba-full-memory-ratio"),
        ("mamba_radix_cache_strategy", "--mamba-radix-cache-strategy"),
        ("max_mamba_cache_size", "--max-mamba-cache-size"),
        ("quantization_param_path", "--quantization-param-path"),
        ("reasoning_parser", "--reasoning-parser"),
        ("tool_call_parser", "--tool-call-parser"),
    ):
        value = server.get(key)
        if value is None:
            continue
        command.extend([flag, str(value)])
    speculative = server.get("speculative", {})
    if speculative is None:
        speculative = {}
    if not isinstance(speculative, dict):
        raise ValueError(f"{lane['key']}: speculative settings must be an object")
    if speculative.get("enabled"):
        required = {
            "algorithm": "--speculative-algorithm",
            "num_steps": "--speculative-num-steps",
            "eagle_topk": "--speculative-eagle-topk",
            "num_draft_tokens": "--speculative-num-draft-tokens",
        }
        for key, flag in required.items():
            if key not in speculative:
                raise ValueError(f"{lane['key']}: speculative setting {key} is required")
            command.extend([flag, str(speculative[key])])
    return command


def model_config_record(lane: dict) -> dict:
    return {
        "key": lane["key"],
        "request_model_id": lane["request_model_id"],
        "model_slug": lane["model_slug"],
        "quant_slug": lane["quant_slug"],
        "aliases": lane["aliases"],
        "profile_id": lane.get("profile_id", lane["model_slug"]),
        "runtime_mode": lane.get("runtime_mode", "text"),
        "tasks": lane.get("tasks", [lane["task"]]),
        "capability_aliases": lane.get("capability_aliases", {}),
        "precision": lane["precision"],
        "capabilities": lane["capabilities"],
        "modalities": lane["modalities"],
        "native_context_length": lane["native_context_length"],
        "max_context_length": lane["max_context_length"],
    }


def server_config(lanes: list[dict], overrides: dict | None = None) -> dict:
    if len(lanes) != 1:
        raise ValueError("SGLang server configs must contain exactly one model")
    lane = lanes[0]
    server = effective_server(lane, overrides)
    runtime_mode = lane.get("runtime_mode", "text")
    model_path = server.get("model_path", lane["container_path"])
    config = {
        "schema_version": 2,
        "runtime": "sglang",
        "mode": runtime_mode,
        "host": "0.0.0.0",
        "port": 30000,
        "model_path": model_path,
        "command": server_command(lane, server),
        "server": server,
        "models": [model_config_record(lane)],
    }
    if runtime_mode == "text":
        config["served_model_name"] = lane["request_model_id"]
    else:
        config["gateway"] = {
            "upstream_host": "127.0.0.1",
            "upstream_port": 30001,
            "model_id": lane["request_model_id"],
            "input_mount": "/inputs",
            "output_mount": "/outputs",
        }
    return config


def lane_inventory(lane: dict) -> dict:
    artifacts = [
        {
            **artifact,
            "container_path": f"/models/{artifact['repo']}/{artifact['path']}",
            "download_id": artifact_download_id(artifact),
        }
        for artifact in lane["artifacts"]
    ]
    download_fingerprint = lane_download_fingerprint(lane)
    return {
        "key": lane["key"],
        "id": lane["id"],
        "request_model_id": lane["request_model_id"],
        "model_slug": lane["model_slug"],
        "quant_slug": lane["quant_slug"],
        "aliases": lane["aliases"],
        "profile_id": lane.get("profile_id", lane["model_slug"]),
        "runtime_mode": lane.get("runtime_mode", "text"),
        "tasks": lane.get("tasks", [lane["task"]]),
        "capability_aliases": lane.get("capability_aliases", {}),
        "family": lane["family"],
        "task": lane["task"],
        "mode": lane["mode"],
        "description": lane["description"],
        "precision": lane["precision"],
        "primary": lane["primary"],
        "license": lane["license"],
        "lineage": lane["lineage"],
        "modalities": lane["modalities"],
        "input_contract": copy.deepcopy(lane.get("input_contract", {})),
        "output_contract": copy.deepcopy(lane.get("output_contract", {})),
        "base_model": copy.deepcopy(lane.get("base_model")),
        "native_context_length": lane["native_context_length"],
        "max_context_length": lane["max_context_length"],
        "reasoning_controls": lane["reasoning_controls"],
        "template": lane["template"],
        "speculative": lane["speculative"],
        "kv_cache_scaling": copy.deepcopy(lane.get("kv_cache_scaling")),
        "artifact_variant": copy.deepcopy(lane.get("artifact_variant")),
        "lora_options": copy.deepcopy(lane.get("lora_options")),
        "server_path": lane["container_path"],
        "server": lane["server"],
        "download_fingerprint": download_fingerprint,
        "artifact_bytes": sum(artifact["size"] for artifact in lane["artifacts"]),
        "artifacts": artifacts,
    }


def lane_download_fingerprint(lane: dict) -> str:
    fingerprint_payload = {
        "schema_version": 1,
        "key": lane["key"],
        "artifacts": [artifact_identity(artifact) for artifact in lane["artifacts"]],
    }
    return hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def residency(server: dict) -> dict:
    if server.get("runtime_mode") == "diffusion":
        return {
            "runtime_mode": "diffusion",
            "max_running_requests": server.get("max_running_requests", 1),
            "gpu_parallelism": {
                "num_gpus": server.get("num_gpus"),
                "tp_size": server.get("tp_size"),
                "sp_degree": server.get("sp_degree"),
                "ulysses_degree": server.get("ulysses_degree"),
                "encoder_parallel": server.get("encoder_parallel"),
            },
            "offload": {
                "components": server.get("layerwise_offload_components"),
                "prefetch_size": server.get("dit_offload_prefetch_size"),
                "resident_layers": server.get("dit_layerwise_resident_layers"),
            },
            "effective_admitted_concurrency": "unknown-until-smoke",
        }
    speculative = server.get("speculative", {})
    return {
        "context_length": server.get("context_length"),
        "max_running_requests": server.get("max_running_requests"),
        "cuda_graph_max_bs": server.get("cuda_graph_max_bs"),
        "mem_fraction_static": server.get("mem_fraction_static"),
        "kv_cache_dtype": server.get("kv_cache_dtype"),
        "mamba_ssm_dtype": server.get("mamba_ssm_dtype"),
        "mamba_full_memory_ratio": server.get("mamba_full_memory_ratio"),
        "mamba_radix_cache_strategy": server.get("mamba_radix_cache_strategy"),
        "max_mamba_cache_size": server.get("max_mamba_cache_size"),
        "capacity": {
            "request_context_length": server.get("context_length"),
            "configured_max_running_requests": server.get("max_running_requests"),
            "effective_admitted_concurrency": "unknown-until-smoke",
            "token_pool": "dynamically shared",
            "total_kv_pool_tokens": "runtime-sized; verify from SGLang server info and boot logs",
        },
        "speculative": copy.deepcopy(speculative),
    }


def container_metadata() -> dict:
    return {
        "name": "prefer-sglang",
        "internal_port": 30000,
        "health_path": "/health",
        "ready_path": "/readyz",
        "model_mount": "/models",
        "input_mount": "/inputs",
        "output_mount": "/outputs",
    }


def deployment_model_records(lanes: list[dict]) -> list[dict]:
    return [model_config_record(lane) for lane in lanes]


def deployment_inventory(runtime: dict, lanes: list[dict], scenarios: list[dict]) -> dict:
    primary = [lane for lane in lanes if lane["primary"]]
    text_primary = [lane for lane in primary if lane.get("runtime_mode", "text") == "text"]
    primary_by_key = {lane["key"]: lane for lane in primary}
    models = {lane["key"]: lane_inventory(lane) for lane in lanes}
    profiles = {}
    for lane in primary:
        profile_id = lane.get("profile_id", lane["model_slug"])
        profile = copy.deepcopy(lane["profile"])
        profile.update(
            {
                "model_slug": lane["model_slug"],
                "profile_id": profile_id,
                "license": lane["license"],
                "lineage": lane["lineage"],
                "native_context_length": lane["native_context_length"],
                "max_context_length": lane["max_context_length"],
                "native_modalities": lane["modalities"]["native"],
                "configured_modalities": lane["modalities"]["configured"],
                "runtime_modes": [lane.get("runtime_mode", "text")],
                "tasks": copy.deepcopy(lane.get("tasks", [lane["task"]])),
                "input_contract": copy.deepcopy(lane.get("input_contract", {})),
                "output_contract": copy.deepcopy(lane.get("output_contract", {})),
            }
        )
        if profile_id in profiles:
            existing = profiles[profile_id]
            existing["runtime_modes"] = sorted(
                set(existing.get("runtime_modes", [])) | {lane.get("runtime_mode", "text")}
            )
            existing["tasks"] = sorted(set(existing.get("tasks", [])) | set(profile["tasks"]))
            existing["configured_capabilities"] = sorted(
                set(existing.get("configured_capabilities", []))
                | set(profile.get("configured_capabilities", []))
            )
        else:
            profiles[profile_id] = profile

    default_overrides = default_server_overrides()
    if not text_primary:
        raise ValueError("at least one primary text model is required for /app/server.json")
    default_config = server_config([text_primary[0]], default_overrides)
    default_artifact_bytes = sum(
        artifact["size"] for lane in text_primary for artifact in lane["artifacts"]
    )
    deployments = [
        {
            "id": "sglang/cuda13",
            "runtime": "sglang",
            "backend": "cuda13",
            "image_tag": "sglang-cuda13",
            "base_image": runtime["base_image"]["reference"],
            "requires_gpu": True,
            "provider": "unspecified",
            "kind": "runtime-default",
            "selection_scope": "runtime-default",
            "description": "Provider-neutral CUDA 13 fallback for unverified SM100+ Blackwell; target-only, one slot, and FP8 KV.",
            "server_config": "/app/server.json",
            "prestage_manifest": "/app/server.prestage",
            "container": container_metadata(),
            "environment": {
                "SGLANG_SERVER_CONFIG": "/app/server.json",
                "SGLANG_PRESTAGE_MODELS": ",".join(lane["key"] for lane in text_primary),
            },
            "server": default_config["server"],
            "server_command": default_config["command"],
            "residency": residency(default_config["server"]),
            "staging": {
                "source": "huggingface-only",
                "reason": "Provider-neutral runtime default; AWS S3 read-through requires an explicit AWS staging environment.",
            },
            "runtime_modes": ["text"],
            "capabilities": sorted({capability for lane in text_primary for capability in lane["capabilities"]}),
            "models": deployment_model_records([text_primary[0]]),
            "prestage_models": [text_primary[0]["key"]],
            "staged_artifact_bytes": default_artifact_bytes,
            "verification_status": "configuration-only",
            "verification": "configuration-only",
        }
    ]
    for scenario in scenarios:
        selected = [primary_by_key[key] for key in scenario["model_keys"]]
        config = server_config(selected, scenario["server"])
        config_path = f"/server-configs/{scenario['path']}"
        prestage_path = str(PurePosixPath(config_path).with_suffix(".prestage"))
        artifact_bytes = sum(
            artifact["size"] for lane in selected for artifact in lane["artifacts"]
        )
        deployments.append(
            {
                "id": PurePosixPath(scenario["path"]).with_suffix("").as_posix(),
                "runtime": "sglang",
                "backend": "cuda13",
                "image_tag": "sglang-cuda13",
                "base_image": runtime["base_image"]["reference"],
                "requires_gpu": True,
                "provider": scenario["provider"],
                "hardware": scenario["hardware"],
                "compatibility": scenario["compatibility"],
                "kind": "single-model",
                "selection_scope": "concrete-hardware-scenario",
                "description": scenario["description"],
                "source": scenario["source"],
                "server_config": config_path,
                "prestage_manifest": prestage_path,
                "container": {
                    **container_metadata(),
                    "server_config": config_path,
                    "prestage_manifest": prestage_path,
                },
                "environment": {
                    "SGLANG_SERVER_CONFIG": config_path,
                    "SGLANG_PRESTAGE_MODELS": "",
                    "SGLANG_DOWNLOAD_JOBS": "4",
                },
                "server": config["server"],
                "server_command": config["command"],
                "residency": residency(config["server"]),
                "staging": scenario["staging"],
                "capabilities": sorted(
                    {capability for lane in selected for capability in lane["capabilities"]}
                ),
                "runtime_modes": sorted({lane.get("runtime_mode", "text") for lane in selected}),
                "models": deployment_model_records(selected),
                "prestage_models": scenario["model_keys"],
                "staged_artifact_bytes": artifact_bytes,
                "verification_status": scenario["verification_status"],
                "verification": scenario["verification_status"],
            }
        )

    catalog_payload = {
        "runtime": runtime,
        "model_profiles": profiles,
        "models": models,
        "deployments": deployments,
    }
    catalog_fingerprint = hashlib.sha256(
        json.dumps(catalog_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "prefer.sglang-deployment-inventory.v2",
        "catalog_fingerprint": catalog_fingerprint,
        "product": "PreFer",
        "distribution": {
            "embedded_image_path": "/deployment-inventory.json",
            "workflow_artifact_name_pattern": "prefer-release-<commit-sha>",
            "github_release_tag_pattern": "sha-<short-commit>",
            "release_inventory_asset": "prefer-sglang-deployment-inventory.json",
            "oci_labels": {
                "path": "io.prefer.deployment-inventory.path",
                "schema": "io.prefer.deployment-inventory.schema",
            },
        },
        "runtime": runtime["runtime"],
        "composition": {
            "schema_version": "prefer.runtime-composition.v1",
            "activation": "opt-in; existing SGLANG_SERVER_CONFIG remains compatible when no composition variable is set",
            "multi_model": False,
            "effective_config_path": "/run/prefer/sglang.json",
            "effective_plan_path": "/run/prefer/plan.json",
            "compose_environment_prefix": "SGLANG",
            "override_merge": "objects merge recursively; scalar and array values replace",
            "environment": {
                "PREFER_DEPLOYMENT": {"type": "string", "source": "deployments[].id"},
                "PREFER_BUNDLE": {"type": "unsupported"},
                "PREFER_MODELS": {"type": "single-string", "source": "models key, model_slug, request_model_id, or alias"},
                "PREFER_SERVER_OVERRIDES": {"type": "json-object", "applies_to": "SGLang server settings"},
                "PREFER_MODEL_OVERRIDES": {"type": "json-object-map", "applies_to": "the selected model's server settings"},
            },
            "selection_rules": [
                "one model is allowed per SGLang process",
                "a friendly model selection uses its primary catalog lane",
                "switching models inherits a matching config from the selected hardware deployment when available",
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
        "staging": runtime.get("staging", {}),
        "features": runtime.get("features", {}),
        "provenance_audit": runtime.get("provenance_audit", {}),
        "experimental_routes": runtime.get("experimental_routes", {}),
        "known_limitations": runtime["known_limitations"],
        "runtime_modes": sorted({lane.get("runtime_mode", "text") for lane in lanes}),
        "api": {
            "health": "GET /health",
            "ready": "GET /readyz",
            "models": "GET /v1/models",
            "chat_completions": "POST /v1/chat/completions",
            "completions": "POST /v1/completions",
            "anthropic_messages": "POST /v1/messages",
            "videos": "POST /v1/videos",
            "video_status": "GET /v1/videos/{id}",
            "video_content": "GET /v1/videos/{id}/content",
        },
        "model_profiles": profiles,
        "models": models,
        "deployments": deployments,
    }


def download_script(lanes: list[dict]) -> str:
    primary_keys = ",".join(
        lane["key"]
        for lane in lanes
        if lane["primary"] and lane.get("runtime_mode", "text") == "text"
    )
    model_cases = []
    for lane in lanes:
        artifact_ids = " ".join(
            json.dumps(artifact_download_id(artifact)) for artifact in lane["artifacts"]
        )
        model_cases.append(
            f"  {lane['key']})\n    printf '%s\\n' {artifact_ids}\n    ;;"
        )

    artifacts: dict[tuple[str, str], dict] = {}
    for lane in lanes:
        for artifact in lane["artifacts"]:
            artifacts.setdefault((artifact["repo"], artifact["path"]), artifact)
    artifact_cases = []
    artifact_s3_cases = []
    for artifact in artifacts.values():
        artifact_id = artifact_download_id(artifact)
        artifact_cases.append(
            f"  {artifact_id})\n"
            f"    prefer_download_hf_artifact \"sglang-download\" \"$1\" "
            f"{json.dumps(artifact['repo'])} {json.dumps(artifact['revision'])} "
            f"{json.dumps(artifact['path'])} {artifact['size']} {json.dumps(artifact['sha256'])}\n"
            "    ;;"
        )
        artifact_s3_cases.append(
            f"  {artifact_id})\n"
            f"    prefer_download_s3_artifact \"sglang-s3\" \"$1\" "
            f"{json.dumps(artifact['repo'])} {json.dumps(artifact['path'])} "
            f"{artifact['size']} {json.dumps(artifact['sha256'])} "
            f"\"$SGLANG_S3_BUCKET_NAME\" \"${{SGLANG_S3_MODEL_PREFIX:-}}\"\n"
            "    ;;"
        )
    fingerprint_cases = []
    artifact_path_cases = []
    artifact_record_cases = []
    for lane in lanes:
        fingerprint_cases.append(
            f"  {lane['key']}) printf '%s\\n' {lane_download_fingerprint(lane)} ;;"
        )
        artifact_lines = "\n".join(
            f"      printf '%s\\n' {json.dumps(artifact['repo'] + '/' + artifact['path'])}"
            for artifact in lane["artifacts"]
        )
        artifact_path_cases.append(f"  {lane['key']})\n{artifact_lines}\n      ;;")
        record_lines = "\n".join(
            f"      printf '%s\\t%s\\n' {artifact['size']} {json.dumps(artifact['repo'] + '/' + artifact['path'])}"
            for artifact in lane["artifacts"]
        )
        artifact_record_cases.append(f"  {lane['key']})\n{record_lines}\n      ;;")
    return f'''#!/usr/bin/env bash
set -euo pipefail

readonly SGLANG_GENERATED_MODEL_KEYS={json.dumps(primary_keys)}
GENERATED_MODEL_KEYS=$SGLANG_GENERATED_MODEL_KEYS
LEGACY_SMALL_MODELS=$SGLANG_GENERATED_MODEL_KEYS

model_key_fingerprint() {{
  case "$1" in
{chr(10).join(fingerprint_cases)}
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}}

model_key_artifacts() {{
  case "$1" in
{chr(10).join(artifact_path_cases)}
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}}

model_key_artifact_records() {{
  case "$1" in
{chr(10).join(artifact_record_cases)}
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}}

sglang_model_artifact_ids() {{
  case "$1" in
{chr(10).join(model_cases)}
    *) echo "[sglang-download] unknown model key: $1" >&2; return 2 ;;
  esac
}}

sglang_download_artifact_id() {{
  case "$1" in
{chr(10).join(artifact_cases)}
    *) echo "[sglang-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}}

sglang_s3_download_artifact_id() {{
  if [ -z "${{SGLANG_S3_BUCKET_NAME:-}}" ]; then
    echo "[sglang-download] SGLANG_S3_BUCKET_NAME is required for S3 staging" >&2
    return 2
  fi
  case "$1" in
{chr(10).join(artifact_s3_cases)}
    *) echo "[sglang-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}}

sglang_s3_stage_artifact() {{
  local artifact_id="$1"
  local status=0
  if sglang_s3_download_artifact_id "$artifact_id"; then
    return 0
  else
    status=$?
  fi
  echo "[sglang-download] artifact $artifact_id: S3 staging unavailable or invalid (status $status); falling back to Hugging Face" >&2
  sglang_download_artifact_id "$artifact_id"
}}

sglang_download_model_keys() {{
  prefer_download_model_keys \\
    "sglang-download" "${{SGLANG_DOWNLOAD_JOBS:-4}}" 8 \\
    sglang_model_artifact_ids sglang_download_artifact_id "$@"
}}

sglang_download_model_keys_s3() {{
  prefer_download_model_keys \\
    "sglang-s3-download" "${{SGLANG_DOWNLOAD_JOBS:-4}}" 8 \\
    sglang_model_artifact_ids sglang_s3_stage_artifact "$@"
}}

sglang_download_model_key() {{
  sglang_download_model_keys "$1"
}}

download_model_key() {{
  sglang_download_model_key "$1"
}}
'''


def rendered_outputs() -> dict[Path, str]:
    runtime = load_json(RUNTIME_PATH)
    if runtime.get("schema_version") != 1:
        raise ValueError("runtime.json schema_version must be 1")
    lanes = model_lanes()
    primary = [lane for lane in lanes if lane["primary"]]
    text_primary = [lane for lane in primary if lane.get("runtime_mode", "text") == "text"]
    primary_by_key = {lane["key"]: lane for lane in primary}
    scenarios = load_scenarios(primary_by_key)
    default_overrides = default_server_overrides()
    outputs: dict[Path, str] = {
        ROOT / "server.generated.json": json.dumps(
            server_config([text_primary[0]], default_overrides), indent=2
        )
        + "\n",
        ROOT / "server.generated.prestage": ",".join(lane["key"] for lane in text_primary) + "\n",
        ROOT / "deployment-inventory.generated.json": json.dumps(
            deployment_inventory(runtime, lanes, scenarios), indent=2
        )
        + "\n",
        ROOT / "model-downloads.generated.sh": download_script(lanes),
    }
    for scenario in scenarios:
        selected = [primary_by_key[key] for key in scenario["model_keys"]]
        config_path = CONFIGS_ROOT / PurePosixPath(scenario["path"])
        outputs[config_path] = json.dumps(
            server_config(selected, scenario["server"]), indent=2
        ) + "\n"
        outputs[config_path.with_suffix(".prestage")] = ",".join(
            scenario["model_keys"]
        ) + "\n"
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
    if normalized in {"/app/server.json", "server.json", "default", "sglang/cuda13"}:
        return "default"
    if not normalized.endswith(".json"):
        normalized += ".json"
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe SGLang deployment: {value!r}")
    return path.as_posix()


def sglang_selection_names(lane: dict) -> set[str]:
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
        raise ValueError("SGLang does not define multi-model bundles; select one PREFER_MODELS entry")
    requested_models = parse_composition_list(model_value)
    if len(requested_models) > 1:
        raise ValueError("SGLang runtime composition accepts exactly one model")
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
            raise ValueError("cannot map the SGLang base config to one primary catalog model")
        base_lane = primary_by_key[model_records[0]["key"]]
        base_server = copy.deepcopy(base_config.get("server", {}))
        base_deployment = (
            PurePosixPath(normalized).with_suffix("").as_posix()
            if normalized != "default"
            else "sglang/cuda13"
        )
        cohort: list[dict] = []
    else:
        scenario = scenario_by_path.get(normalized)
        if scenario is None:
            raise ValueError(f"unknown SGLang deployment: {base!r}")
        if len(scenario["model_keys"]) != 1:
            raise ValueError(f"{normalized}: SGLang deployment must contain one model")
        base_lane = primary_by_key[scenario["model_keys"][0]]
        base_server = copy.deepcopy(scenario["server"])
        base_deployment = PurePosixPath(normalized).with_suffix("").as_posix()
        parent = PurePosixPath(normalized).parent
        cohort = [record for record in scenarios if PurePosixPath(record["path"]).parent == parent]

    selected = base_lane
    selected_server = base_server
    if requested_models:
        selection = requested_models[0]
        matches = [lane for lane in lanes if selection in sglang_selection_names(lane)]
        if not matches:
            raise ValueError(f"unknown SGLang model selection: {selection!r}")
        if selection in lanes_by_key:
            selected = lanes_by_key[selection]
        else:
            primary_matches = [lane for lane in matches if lane["primary"]]
            if len(primary_matches) != 1:
                raise ValueError(
                    f"ambiguous SGLang model {selection!r}; choose an exact lane: "
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
        value for name, value in model_overrides.items() if name in sglang_selection_names(selected)
    ]
    if len(matching_overrides) > 1:
        raise ValueError(f"multiple PREFER_MODEL_OVERRIDES entries target {selected['key']}")
    unknown_targets = [name for name in model_overrides if name not in sglang_selection_names(selected)]
    if unknown_targets:
        raise ValueError("PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown_targets))
    model_override = matching_overrides[0] if matching_overrides else {}
    effective_overrides = deep_merge(selected_server, server_overrides, model_override)
    config = server_config([selected], effective_overrides)
    prestage = [selected["key"]]
    plan = {
        "schema_version": "prefer.runtime-plan.v1",
        "runtime": "sglang",
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
            "SGLang command arguments",
        ],
    }
    return config, prestage, plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--compose", action="store_true")
    parser.add_argument("--base", default="")
    parser.add_argument("--bundles", default="")
    parser.add_argument("--models", default="")
    parser.add_argument("--server-overrides", default="")
    parser.add_argument("--model-overrides", default="")
    parser.add_argument("--output")
    parser.add_argument("--prestage-output")
    parser.add_argument("--plan-output")
    args = parser.parse_args()
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
        print(f"composed SGLang runtime config from {plan['base_deployment']}: {', '.join(prestage)}")
        return
    outputs = rendered_outputs()
    mismatches = []
    for path, content in outputs.items():
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            mismatches.append(path)
    if args.check:
        if mismatches:
            for path in mismatches:
                print(f"out of date: {path}")
            raise SystemExit(1)
        return
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"generated {len(outputs)} SGLang files")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"generate.py: {error}", file=sys.stderr)
        raise SystemExit(1)
