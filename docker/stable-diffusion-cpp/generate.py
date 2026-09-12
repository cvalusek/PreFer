#!/usr/bin/env python3
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
SCENARIOS_ROOT = ROOT / "deployment-scenarios"
CONFIGS_ROOT = ROOT / "server-configs"
RUNTIME_PATH = ROOT / "runtime.json"
BUNDLES_PATH = ROOT / "deployment-bundles.json"


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


def artifact_download_identity(artifact: dict) -> dict:
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
            artifact_download_identity(artifact),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def container_path(artifact: dict) -> str:
    return f"/models/{artifact['repo']}/{artifact['path']}"


def load_lanes() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    lanes: list[dict] = []
    by_key: dict[str, dict] = {}
    primary_by_id: dict[str, dict] = {}
    seen_ids: set[str] = set()
    artifacts_by_destination: dict[tuple[str, str], dict] = {}
    for path in sorted(MODELS_ROOT.glob("*/*/model.json")):
        source = load_json(path)
        family, model_slug, _ = path.relative_to(MODELS_ROOT).parts
        if source.get("schema_version") != 1:
            raise ValueError(f"{path}: schema_version must be 1")
        if source.get("family") != family or source.get("model_slug") != model_slug:
            raise ValueError(f"{path}: family/model_slug must match its directory")
        shared = source.get("shared")
        quants = source.get("quants")
        if not isinstance(shared, dict) or not isinstance(quants, dict) or not quants:
            raise ValueError(f"{path}: shared and non-empty quants are required")
        model_id = shared.get("id")
        if not isinstance(model_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", model_id):
            raise ValueError(f"{path}: unsafe model id")
        if model_id in seen_ids:
            raise ValueError(f"duplicate image model id: {model_id}")
        seen_ids.add(model_id)
        primary_count = 0
        for quant_slug, quant in quants.items():
            key = quant.get("key")
            if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", key):
                raise ValueError(f"{path}: unsafe quant key")
            if key in by_key:
                raise ValueError(f"duplicate image quant key: {key}")
            artifacts = quant.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                raise ValueError(f"{key}: artifacts must be a non-empty list")
            args: list[str] = []
            required_files = []
            for artifact in artifacts:
                repo = artifact.get("repo")
                if not isinstance(repo, str) or not re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*", repo
                ):
                    raise ValueError(f"{key}: artifact repo must be a safe owner/name")
                if not re.fullmatch(r"[0-9a-f]{40}", str(artifact.get("revision", ""))):
                    raise ValueError(f"{key}: artifact revision must be an immutable SHA")
                if not re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("sha256", ""))):
                    raise ValueError(f"{key}: artifact sha256 is invalid")
                if not isinstance(artifact.get("size"), int) or artifact["size"] <= 0:
                    raise ValueError(f"{key}: artifact size must be positive")
                artifact_value = artifact.get("path")
                artifact_path = PurePosixPath(str(artifact_value or ""))
                if (
                    not isinstance(artifact_value, str)
                    or not artifact_value
                    or "\\" in artifact_value
                    or artifact_path.is_absolute()
                    or ".." in artifact_path.parts
                ):
                    raise ValueError(f"{key}: artifact path must remain relative")
                destination = (repo, artifact_value)
                identity = artifact_download_identity(artifact)
                previous = artifacts_by_destination.get(destination)
                if previous is not None and previous != identity:
                    raise ValueError(
                        f"{key}: artifact destination {repo}/{artifact_value} has conflicting immutable identities"
                    )
                artifacts_by_destination[destination] = identity
                argument = artifact.get("argument")
                if not isinstance(argument, str) or not argument.startswith("--"):
                    raise ValueError(f"{key}: artifact argument must be a long option")
                path_in_container = container_path(artifact)
                args.extend([argument, path_in_container])
                required_files.append({**artifact, "container_path": path_in_container})
            shared_args = shared.get("args", [])
            quant_args = quant.get("args", [])
            if not all(isinstance(value, str) for value in [*shared_args, *quant_args]):
                raise ValueError(f"{key}: args must contain only strings")
            primary = bool(quant.get("primary"))
            primary_count += int(primary)
            lane = {
                "key": key,
                "quant_slug": quant_slug,
                "precision": quant["precision"],
                "primary": primary,
                "family": family,
                "model_slug": model_slug,
                **shared,
                "artifacts": copy.deepcopy(artifacts),
                "required_files": required_files,
                "args": [*args, *shared_args, *quant_args],
                "source": path.relative_to(ROOT).as_posix(),
            }
            lanes.append(lane)
            by_key[key] = lane
            if primary:
                primary_by_id[model_id] = lane
        if primary_count != 1:
            raise ValueError(f"{path}: exactly one primary quant is required")
    if not lanes:
        raise ValueError("no image model catalogs found")
    lanes.sort(key=lambda lane: (lane["id"], lane["key"]))
    return lanes, by_key, primary_by_id


def load_bundles(model_ids: set[str]) -> dict[str, dict]:
    source = load_json(BUNDLES_PATH)
    if source.get("schema_version") != 1:
        raise ValueError("deployment-bundles.json schema_version must be 1")
    bundles = source.get("bundles")
    if not isinstance(bundles, dict) or not bundles:
        raise ValueError("deployment-bundles.json requires bundles")
    for name, bundle in bundles.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise ValueError(f"unsafe image bundle name: {name}")
        models = bundle.get("models")
        if not isinstance(models, list) or not models or len(models) != len(set(models)):
            raise ValueError(f"bundle {name}: models must be a non-empty unique list")
        unknown = sorted(set(models) - model_ids)
        if unknown:
            raise ValueError(f"bundle {name}: unknown models: {', '.join(unknown)}")
    return bundles


def default_server() -> dict:
    return {
        "host": "0.0.0.0",
        "port": 8080,
        "backend_host": "127.0.0.1",
        "backend_port": 8083,
        "backend_binary": "/sd-server",
        "lazy_load": True,
        "max_loaded_models": 1,
        "idle_unload_ms": 1800000,
        "startup_timeout_ms": 1800000,
        "busy_timeout_ms": 3600000,
        "backend_request_timeout_ms": 3600000,
        "max_request_body_bytes": 268435456,
        "model_args_append": [],
    }


def server_config(lanes: list[dict], overrides: dict | None = None) -> dict:
    config = default_server()
    overrides = copy.deepcopy(overrides or {})
    forbidden = {"models", "max_loaded_models", "lazy_load"} & overrides.keys()
    if forbidden:
        raise ValueError(f"server overrides cannot replace: {', '.join(sorted(forbidden))}")
    config = deep_merge(config, overrides)
    append_args = config.pop("model_args_append", [])
    if not isinstance(append_args, list) or not all(isinstance(value, str) for value in append_args):
        raise ValueError("model_args_append must contain strings")
    config["models"] = [
        {
            "id": lane["id"],
            "display_name": lane["display_name"],
            "family": lane["family"],
            "description": lane["description"],
            "capabilities": lane["capabilities"],
            "precision": lane["precision"],
            "license": lane["license"],
            "catalog_key": lane["key"],
            "args": [*lane["args"], *append_args],
            "required_files": lane["required_files"],
        }
        for lane in lanes
    ]
    return config


def safe_output_root(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe image output root: {value!r}")
    return path.as_posix()


def load_scenarios(by_key: dict[str, dict], bundles: dict[str, dict]) -> list[dict]:
    records: list[dict] = []
    seen_paths: set[str] = set()
    for source_path in sorted(SCENARIOS_ROOT.rglob("*.json")):
        source = load_json(source_path)
        if source.get("schema_version") != 1:
            raise ValueError(f"{source_path}: schema_version must be 1")
        provider = source.get("provider")
        lane_map = source.get("lanes")
        variants = source.get("variants")
        if not isinstance(provider, str) or not isinstance(lane_map, dict) or not lane_map:
            raise ValueError(f"{source_path}: provider and lanes are required")
        if not isinstance(variants, list) or not variants:
            raise ValueError(f"{source_path}: variants must be a non-empty list")
        selected_by_id: dict[str, dict] = {}
        for model_id, key in lane_map.items():
            lane = by_key.get(key)
            if lane is None or lane["id"] != model_id:
                raise ValueError(f"{source_path}: invalid lane {model_id} -> {key}")
            selected_by_id[model_id] = lane
        bundle_names = source.get("bundles", [])
        unknown_bundles = sorted(set(bundle_names) - set(bundles))
        if unknown_bundles:
            raise ValueError(f"{source_path}: unknown bundles: {', '.join(unknown_bundles)}")
        singles = source.get("single_models", [])
        if singles == "all":
            single_ids = list(selected_by_id)
        elif isinstance(singles, list):
            single_ids = singles
        else:
            raise ValueError(f"{source_path}: single_models must be 'all' or a list")
        unknown_singles = sorted(set(single_ids) - set(selected_by_id))
        if unknown_singles:
            raise ValueError(f"{source_path}: unknown single models: {', '.join(unknown_singles)}")
        for variant in variants:
            output_root = safe_output_root(variant.get("output_root", ""))
            hardware = variant.get("hardware")
            if not isinstance(hardware, dict) or not hardware.get("gpu_count"):
                raise ValueError(f"{source_path}: each variant requires hardware and gpu_count")
            compatibility = {
                **copy.deepcopy(source.get("compatibility", {})),
                **copy.deepcopy(variant.get("compatibility", {})),
            }
            verification = variant.get("verification", source.get("verification", "configuration-only"))
            specs: list[tuple[str, str, list[dict], str]] = []
            for bundle_name in bundle_names:
                model_ids = [model_id for model_id in bundles[bundle_name]["models"] if model_id in selected_by_id]
                if not model_ids:
                    continue
                specs.append((bundle_name, "bundle", [selected_by_id[model_id] for model_id in model_ids], bundles[bundle_name]["description"]))
            for model_id in single_ids:
                lane = selected_by_id[model_id]
                specs.append((model_id, "single-model", [lane], lane["description"]))
            for name, kind, selected, description in specs:
                config_path = f"{output_root}/{name}.json"
                if config_path in seen_paths:
                    raise ValueError(f"duplicate generated image config path: {config_path}")
                seen_paths.add(config_path)
                records.append(
                    {
                        "path": config_path,
                        "name": name,
                        "kind": kind,
                        "provider": provider,
                        "hardware": copy.deepcopy(hardware),
                        "compatibility": compatibility,
                        "verification": verification,
                        "description": description,
                        "lanes": selected,
                        "server": copy.deepcopy(source.get("server", {})),
                        "source": source_path.relative_to(ROOT).as_posix(),
                    }
                )
    if not records:
        raise ValueError("no image deployment scenarios found")
    return records


def unique_artifacts(lanes: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result = []
    for lane in lanes:
        for artifact in lane["required_files"]:
            identity = (artifact["repo"], artifact["revision"], artifact["path"])
            if identity not in seen:
                seen.add(identity)
                result.append(artifact)
    return result


def lane_inventory(lane: dict) -> dict:
    payload = {"key": lane["key"], "artifacts": lane["artifacts"]}
    return {
        "request_model_id": lane["id"],
        "model_slug": lane["model_slug"],
        "quant_slug": lane["quant_slug"],
        "display_name": lane["display_name"],
        "family": lane["family"],
        "description": lane["description"],
        "capabilities": lane["capabilities"],
        "precision": lane["precision"],
        "primary": lane["primary"],
        "license": lane["license"],
        "lineage": lane["lineage"],
        "source": lane["source"],
        "server_args": lane["args"],
        "artifact_bytes": sum(artifact["size"] for artifact in lane["artifacts"]),
        "download_fingerprint": hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "artifacts": lane["required_files"],
    }


def deployment_record(
    deployment_id: str,
    lanes: list[dict],
    config_path: str,
    prestage_path: str,
    runtime: dict,
    server_overrides: dict | None = None,
    **extra: object,
) -> dict:
    artifacts = unique_artifacts(lanes)
    append_args = (server_overrides or {}).get("model_args_append", [])
    offload_components = []
    if "--offload-to-cpu" in append_args:
        offload_components.append("model")
    if "--clip-on-cpu" in append_args:
        offload_components.append("text_encoder")
    if "--vae-on-cpu" in append_args:
        offload_components.append("vae")
    return {
        "id": deployment_id,
        "runtime": "stable-diffusion.cpp",
        "backend": "cuda12",
        "image_tag": "image-cuda12",
        "base_image": runtime["base_image"]["reference"],
        "requires_gpu": True,
        "container": {
            "name": "prefer-image",
            "internal_port": 8080,
            "health_path": "/health",
            "model_mount": "/models",
            "server_config": config_path,
            "prestage_manifest": prestage_path,
        },
        "environment": {"IMAGE_SERVER_CONFIG": config_path, "IMAGE_PRESTAGE_MODELS": ""},
        "residency": {
            "lazy_load": True,
            "max_loaded_models": 1,
            "idle_unload_ms": 1800000,
            **({"offload": {"enabled": True, "components": offload_components}} if offload_components else {}),
        },
        "capabilities": sorted({capability for lane in lanes for capability in lane["capabilities"]}),
        "models": [
            {
                "key": lane["key"],
                "request_model_id": lane["id"],
                "model_slug": lane["model_slug"],
                "quant_slug": lane["quant_slug"],
                "precision": lane["precision"],
                "capabilities": lane["capabilities"],
            }
            for lane in lanes
        ],
        "prestage_models": [lane["key"] for lane in lanes],
        "staged_artifact_bytes": sum(artifact["size"] for artifact in artifacts),
        **extra,
    }


def deployment_inventory(runtime: dict, lanes: list[dict], scenarios: list[dict], bundles: dict[str, dict]) -> dict:
    primary = [lane for lane in lanes if lane["primary"]]
    deployments = [
        deployment_record(
            "image/cuda12",
            primary,
            "/app/server.json",
            "/app/server.prestage",
            runtime,
            server_overrides={"model_args_append": ["--offload-to-cpu"]},
            kind="default",
            description="All primary image capabilities with capacity-oriented CPU offload",
            verification_status="configuration-only",
            verification="configuration-only",
        )
    ]
    for scenario in scenarios:
        config_path = f"/server-configs/{scenario['path']}"
        prestage_path = str(PurePosixPath(config_path).with_suffix(".prestage"))
        deployments.append(
            deployment_record(
                PurePosixPath(scenario["path"]).with_suffix("").as_posix(),
                scenario["lanes"],
                config_path,
                prestage_path,
                runtime,
                server_overrides=scenario["server"],
                provider=scenario["provider"],
                hardware=scenario["hardware"],
                compatibility=scenario["compatibility"],
                kind=scenario["kind"],
                description=scenario["description"],
                source=scenario["source"],
                verification_status=scenario["verification"],
                verification=scenario["verification"],
            )
        )
    bundle_inventory = {
        name: {"description": bundle["description"], "models": bundle["models"]}
        for name, bundle in bundles.items()
    }
    payload = {
        "runtime": runtime,
        "bundles": bundle_inventory,
        "models": {lane["key"]: lane_inventory(lane) for lane in lanes},
        "deployments": deployments,
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schema_version": "prefer.image-deployment-inventory.v1",
        "catalog_fingerprint": fingerprint,
        "product": "PreFer",
        "distribution": {
            "embedded_image_path": "/deployment-inventory.json",
            "workflow_artifact_name_pattern": "prefer-release-<commit-sha>",
            "github_release_tag_pattern": "sha-<short-commit>",
            "release_inventory_asset": "prefer-image-deployment-inventory.json",
            "oci_labels": {"path": "io.prefer.deployment-inventory.path", "schema": "io.prefer.deployment-inventory.schema"},
        },
        "runtime": runtime["runtime"],
        "composition": {
            "schema_version": "prefer.runtime-composition.v1",
            "activation": "opt-in; existing IMAGE_SERVER_CONFIG remains compatible when no composition variable is set",
            "multi_model": True,
            "effective_config_path": "/run/prefer/image.json",
            "effective_plan_path": "/run/prefer/plan.json",
            "effective_handoff_path": "/run/prefer/handoff.json",
            "runtime_handoff_schema": "prefer.runtime-handoff.v1",
            "runtime_handoff_transports": ["path", "base64"],
            "compose_environment_prefix": "IMAGE",
            "override_merge": "objects merge recursively; scalar and array values replace",
            "environment": {
                "PREFER_DEPLOYMENT": {"type": "string", "source": "deployments[].id"},
                "PREFER_BUNDLE": {"type": "string-list", "source": "bundles keys"},
                "PREFER_MODELS": {"type": "string-list", "source": "models key, model_slug, or request_model_id"},
                "PREFER_SERVER_OVERRIDES": {"type": "json-object", "applies_to": "image router settings"},
                "PREFER_MODEL_OVERRIDES": {
                    "type": "json-object-map",
                    "applies_to": "selected model args",
                    "keys": ["args", "args_append", "args_remove"],
                },
                "PREFER_RUNTIME_HANDOFF": {"type": "path", "source": "immutable release-matched runtime handoff"},
                "PREFER_RUNTIME_HANDOFF_BASE64": {
                    "type": "base64-json",
                    "source": "immutable release-matched runtime handoff",
                    "encoding": "RFC 4648 base64 of compact UTF-8 JSON",
                    "max_characters": 98304,
                },
            },
            "selection_rules": [
                "bundle and model selections are additive",
                "an exact quant key replaces another lane for the same logical model",
                "a friendly model selection inherits the selected hardware deployment's lane",
                "a runtime handoff replaces bundle/model selection and may include controller-extension artifacts",
                "path and base64 runtime handoff inputs are mutually exclusive",
            ],
            "precedence": [
                "catalog model and lane defaults",
                "hardware deployment defaults",
                "PREFER_SERVER_OVERRIDES",
                "PREFER_MODEL_OVERRIDES",
                "raw engine arguments",
            ],
            "setting_sources": {
                "server": "composition.server_defaults plus deployment config",
                "model": "models[].server_args",
            },
            "server_defaults": default_server(),
        },
        "base_image": runtime["base_image"],
        "platforms": ["linux/amd64"],
        "api": {
            "health": "GET /health",
            "models": "GET /v1/models",
            "generations": "POST /v1/images/generations",
            "edits": "POST /v1/images/edits",
        },
        "residency": {"discovery_loads_models": False, "max_loaded_models": 1, "idle_unload_ms": 1800000},
        "bundles": bundle_inventory,
        "models": payload["models"],
        "deployments": deployments,
    }


def download_script(lanes: list[dict]) -> str:
    primary_keys = ",".join(lane["key"] for lane in lanes if lane["primary"])
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
    artifact_record_cases = []
    for artifact in artifacts.values():
        artifact_id = artifact_download_id(artifact)
        artifact_cases.append(
            f"  {artifact_id})\n"
            f"    prefer_download_hf_artifact \"image-download\" \"$1\" "
            f"{json.dumps(artifact['repo'])} {json.dumps(artifact['revision'])} "
            f"{json.dumps(artifact['path'])} {artifact['size']} {json.dumps(artifact['sha256'])}\n"
            "    ;;"
        )
        artifact_record_cases.append(
            f"  {artifact_id})\n"
            f"    printf '%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n' \"$1\" "
            f"{json.dumps(artifact['repo'])} {json.dumps(artifact['revision'])} "
            f"{json.dumps(artifact['path'])} {artifact['size']} sha256 {json.dumps(artifact['sha256'])}\n"
            "    ;;"
        )
    return f'''#!/usr/bin/env bash
set -euo pipefail

readonly IMAGE_GENERATED_MODEL_KEYS={json.dumps(primary_keys)}

image_model_artifact_ids() {{
  case "$1" in
{chr(10).join(model_cases)}
    *) echo "[image-download] unknown catalog key: $1" >&2; return 2 ;;
  esac
}}

image_download_artifact_id() {{
  case "$1" in
{chr(10).join(artifact_cases)}
    *) echo "[image-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}}

image_artifact_record() {{
  case "$1" in
{chr(10).join(artifact_record_cases)}
    *) echo "[image-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}}

image_download_model_keys() {{
  prefer_download_model_keys_hf \
    "image-download" "${{IMAGE_DOWNLOAD_JOBS:-4}}" 8 \
    image_model_artifact_ids image_artifact_record "$@"
}}

image_download_model_key() {{
  image_download_model_keys "$1"
}}
'''


def render_json(value: dict) -> str:
    return json.dumps(value, indent=2, sort_keys=False) + "\n"


def expected_outputs() -> dict[Path, str]:
    runtime = load_json(RUNTIME_PATH)
    if runtime.get("schema_version") != 1:
        raise ValueError("runtime.json schema_version must be 1")
    lanes, by_key, primary_by_id = load_lanes()
    bundles = load_bundles(set(primary_by_id))
    scenarios = load_scenarios(by_key, bundles)
    primary = [primary_by_id[model_id] for model_id in sorted(primary_by_id)]
    outputs: dict[Path, str] = {
        ROOT / "server.generated.json": render_json(server_config(primary, {"model_args_append": ["--offload-to-cpu"]})),
        ROOT / "server.generated.prestage": ",".join(lane["key"] for lane in primary) + "\n",
        ROOT / "deployment-inventory.generated.json": render_json(deployment_inventory(runtime, lanes, scenarios, bundles)),
        ROOT / "model-downloads.generated.sh": download_script(lanes),
    }
    for scenario in scenarios:
        config_path = CONFIGS_ROOT / PurePosixPath(scenario["path"])
        outputs[config_path] = render_json(server_config(scenario["lanes"], scenario["server"]))
        outputs[config_path.with_suffix(".prestage")] = ",".join(lane["key"] for lane in scenario["lanes"]) + "\n"
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
    if normalized in {"/app/server.json", "server.json", "default", "image/cuda12"}:
        return "default"
    if not normalized.endswith(".json"):
        normalized += ".json"
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe image deployment: {value!r}")
    return path.as_posix()


def image_selection_names(lane: dict) -> set[str]:
    return {lane["key"], lane["id"], lane["model_slug"]}


def remove_image_args(args: list[str], flags: list[str]) -> list[str]:
    remove = set(flags)
    result: list[str] = []
    index = 0
    while index < len(args):
        value = args[index]
        if value in remove:
            index += 1
            if index < len(args) and not args[index].startswith("--"):
                index += 1
            continue
        result.append(value)
        index += 1
    return result


def compose_runtime_config(
    *,
    base: str,
    bundle_value: str,
    model_value: str,
    server_overrides_value: str,
    model_overrides_value: str,
) -> tuple[dict, list[str], dict]:
    lanes, by_key, primary_by_id = load_lanes()
    bundles = load_bundles(set(primary_by_id))
    scenarios = load_scenarios(by_key, bundles)
    scenario_by_path = {scenario["path"]: scenario for scenario in scenarios}
    normalized = normalize_runtime_config(base)
    explicit_base_path = Path(base)

    if normalized == "default" or explicit_base_path.is_file():
        base_path = explicit_base_path
        if not base_path.is_file():
            installed_default = Path("/app/server.json")
            base_path = installed_default if installed_default.is_file() else ROOT / "server.generated.json"
        base_config = load_json(base_path)
        base_lanes = []
        for model in base_config.get("models", []):
            lane = by_key.get(model.get("catalog_key"))
            if lane is None:
                raise ValueError(f"cannot map image base model {model.get('id')!r} to the catalog")
            lane = copy.deepcopy(lane)
            lane["args"] = copy.deepcopy(model.get("args", lane["args"]))
            base_lanes.append(lane)
        base_server = {
            key: value
            for key, value in base_config.items()
            if key not in {"models", "lazy_load", "max_loaded_models"}
        }
        base_deployment = (
            PurePosixPath(normalized).with_suffix("").as_posix()
            if normalized != "default"
            else "image/cuda12"
        )
        cohort = []
    else:
        scenario = scenario_by_path.get(normalized)
        if scenario is None:
            raise ValueError(f"unknown image deployment: {base!r}")
        base_lanes = [copy.deepcopy(lane) for lane in scenario["lanes"]]
        base_server = copy.deepcopy(scenario["server"])
        base_deployment = PurePosixPath(normalized).with_suffix("").as_posix()
        base_parent = PurePosixPath(normalized).parent
        cohort = [
            record
            for record in scenarios
            if PurePosixPath(record["path"]).parent == base_parent
        ]

    hardware_lanes = {lane["id"]: lane for record in cohort for lane in record["lanes"]}
    hardware_lanes.update({lane["id"]: lane for lane in base_lanes})
    requested_bundles = parse_composition_list(bundle_value)
    requested_models = parse_composition_list(model_value)
    server_overrides = parse_composition_object(server_overrides_value, "PREFER_SERVER_OVERRIDES")
    model_overrides = parse_composition_object(model_overrides_value, "PREFER_MODEL_OVERRIDES")
    if any(not isinstance(value, dict) for value in model_overrides.values()):
        raise ValueError("PREFER_MODEL_OVERRIDES values must be JSON objects")

    selected: list[dict] = []

    def add_lane(lane: dict) -> None:
        selected[:] = [existing for existing in selected if existing["id"] != lane["id"]]
        selected.append(copy.deepcopy(lane))

    for name in requested_bundles:
        bundle = bundles.get(name)
        if bundle is None:
            raise ValueError(f"unknown image bundle: {name!r}")
        for model_id in bundle["models"]:
            add_lane(hardware_lanes.get(model_id, primary_by_id[model_id]))

    for selection in requested_models:
        matches = [lane for lane in lanes if selection in image_selection_names(lane)]
        if not matches:
            raise ValueError(f"unknown image model selection: {selection!r}")
        if selection in by_key:
            lane = copy.deepcopy(by_key[selection])
            template = hardware_lanes.get(lane["id"])
            primary_lane = primary_by_id[lane["id"]]
            if template and template["args"][: len(primary_lane["args"])] == primary_lane["args"]:
                lane["args"].extend(template["args"][len(primary_lane["args"]) :])
        else:
            model_id = matches[0]["id"]
            lane = hardware_lanes.get(model_id)
            if lane is None:
                if len(matches) != 1:
                    raise ValueError(
                        f"ambiguous image model {selection!r}; choose an exact lane: "
                        + ", ".join(match["key"] for match in matches)
                    )
                lane = matches[0]
        add_lane(lane)

    if not requested_bundles and not requested_models:
        selected = [copy.deepcopy(lane) for lane in base_lanes]
    if not selected:
        raise ValueError("runtime composition selected no image models")

    applied_model_overrides: dict[str, dict] = {}
    for lane in selected:
        matching = [value for name, value in model_overrides.items() if name in image_selection_names(lane)]
        if len(matching) > 1:
            raise ValueError(f"multiple PREFER_MODEL_OVERRIDES entries target {lane['key']}")
        if not matching:
            continue
        override = matching[0]
        unknown = set(override) - {"args", "args_append", "args_remove"}
        if unknown:
            raise ValueError(f"unsupported image model override for {lane['key']}: {sorted(unknown)[0]}")
        if "args" in override:
            if not isinstance(override["args"], list) or not all(isinstance(value, str) for value in override["args"]):
                raise ValueError(f"{lane['key']}: args must be a list of strings")
            lane["args"] = copy.deepcopy(override["args"])
        if "args_remove" in override:
            if not isinstance(override["args_remove"], list) or not all(
                isinstance(value, str) and value.startswith("--") for value in override["args_remove"]
            ):
                raise ValueError(f"{lane['key']}: args_remove must contain long-option names")
            lane["args"] = remove_image_args(lane["args"], override["args_remove"])
        if "args_append" in override:
            if not isinstance(override["args_append"], list) or not all(
                isinstance(value, str) for value in override["args_append"]
            ):
                raise ValueError(f"{lane['key']}: args_append must be a list of strings")
            lane["args"].extend(override["args_append"])
        applied_model_overrides[lane["key"]] = override
    unknown_targets = [
        name
        for name in model_overrides
        if not any(name in image_selection_names(lane) for lane in selected)
    ]
    if unknown_targets:
        raise ValueError("PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown_targets))

    config = server_config(selected, deep_merge(base_server, server_overrides))
    prestage = [lane["key"] for lane in selected]
    plan = {
        "schema_version": "prefer.runtime-plan.v1",
        "runtime": "stable-diffusion.cpp",
        "base_deployment": base_deployment,
        "bundles": requested_bundles,
        "requested_models": requested_models,
        "resolved_model_keys": prestage,
        "server_overrides": server_overrides,
        "model_overrides": applied_model_overrides,
        "precedence": [
            "catalog model and lane defaults",
            "hardware deployment defaults",
            "PREFER_SERVER_OVERRIDES",
            "PREFER_MODEL_OVERRIDES",
            "router command arguments",
        ],
    }
    return config, prestage, plan


def resolve_handoff_base(base: str, default_base: str, handoff: dict) -> tuple[dict, str]:
    reference = base or str(handoff.get("base_deployment") or default_base)
    normalized = normalize_runtime_config(reference or "default")
    explicit = Path(reference) if reference else Path()
    if normalized == "default" or explicit.is_file():
        config_path = explicit if explicit.is_file() else Path(default_base)
        if not config_path.is_file():
            config_path = Path("/app/server.json") if Path("/app/server.json").is_file() else ROOT / "server.generated.json"
        config = load_json(config_path)
        server = {key: copy.deepcopy(value) for key, value in config.items() if key not in {"models", "lazy_load", "max_loaded_models"}}
        return server, "image/cuda12"
    lanes, by_key, primary_by_id = load_lanes()
    bundles = load_bundles(set(primary_by_id))
    scenarios = load_scenarios(by_key, bundles)
    scenario = next((record for record in scenarios if record["path"] == normalized), None)
    if scenario is None:
        raise ValueError(f"unknown image runtime handoff deployment: {reference!r}")
    return copy.deepcopy(scenario["server"]), PurePosixPath(normalized).with_suffix("").as_posix()


def handoff_image_lane(model: dict, artifacts: dict[str, dict]) -> dict:
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
    args = launcher.pop("args", [])
    if not isinstance(args, list) or any(not isinstance(value, str) for value in args):
        raise ValueError(f"runtime handoff model {model_id} launcher args must contain strings")
    if launcher:
        raise ValueError(f"runtime handoff model {model_id} has unsupported image launcher setting {next(iter(launcher))!r}")
    role_arguments = {
        "target": "--diffusion-model",
        "checkpoint": "--model",
        "vae": "--vae",
        "text_encoder": "--llm",
        "text-encoder": "--llm",
        "lora": "--lora-model",
        "adapter": "--lora-model",
    }
    required_files = []
    artifact_args: list[str] = []
    for artifact_id in model.get("artifact_ids", []):
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            raise ValueError(f"runtime handoff model {model_id} references unknown artifact {artifact_id}")
        local_path = artifact.get("local_path")
        if not isinstance(local_path, str) or not local_path.startswith("/"):
            raise ValueError(f"runtime handoff artifact {artifact_id} has no materialized path")
        settings = artifact.get("settings", {})
        argument = settings.get("argument") if isinstance(settings, dict) else None
        if argument is None:
            argument = role_arguments.get(str(artifact.get("role", "")).lower())
        if argument is not None:
            if not isinstance(argument, str) or not re.fullmatch(r"--[a-z0-9][a-z0-9-]*", argument):
                raise ValueError(f"runtime handoff artifact {artifact_id} has an unsafe image argument")
            artifact_args.extend([argument, local_path])
        verification = (
            {"sha256": artifact["sha256"]}
            if isinstance(artifact.get("sha256"), str)
            else {"git_blob_sha1": artifact["git_blob_sha1"]}
        )
        required_files.append({
            "download_id": artifact["id"],
            "repo": artifact["repository"],
            "revision": artifact["revision"],
            "path": artifact["path"],
            "size": artifact["size"],
            **verification,
            "role": artifact.get("role"),
            "container_path": local_path,
        })
    if not artifact_args:
        raise ValueError(f"runtime handoff model {model_id} has no launchable image artifacts")
    capabilities = model.get("capabilities", [])
    if not isinstance(capabilities, list):
        raise ValueError(f"runtime handoff model {model_id} capabilities must be a list")
    return {
        "key": model_id,
        "id": request_model_id,
        "display_name": model.get("display_name", model_id),
        "family": model.get("family", "extension"),
        "description": model_settings.get("description", model.get("display_name", model_id)),
        "capabilities": capabilities,
        "precision": model.get("quant", "unknown"),
        "license": model_settings.get("license", "not supplied by runtime handoff"),
        "model_slug": model_id,
        "quant_slug": model.get("quant", "unknown"),
        "args": [*artifact_args, *args],
        "required_files": required_files,
    }


def compose_runtime_handoff_config(
    *,
    handoff_path: str,
    base: str,
    default_base: str,
    server_overrides_value: str,
    model_overrides_value: str,
) -> tuple[dict, list[str], dict]:
    handoff = load_json(Path(handoff_path))
    if handoff.get("schema_version") != "prefer.runtime-handoff.v1" or handoff.get("engine") != "stable-diffusion.cpp":
        raise ValueError("materialized runtime handoff is not for stable-diffusion.cpp")
    models = handoff.get("models")
    raw_artifacts = handoff.get("artifacts")
    if not isinstance(models, list) or not models or not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ValueError("image runtime handoff requires models and artifacts")
    artifacts = {artifact.get("id"): artifact for artifact in raw_artifacts if isinstance(artifact, dict)}
    if len(artifacts) != len(raw_artifacts):
        raise ValueError("materialized runtime handoff has duplicate or invalid artifacts")
    base_server, base_deployment = resolve_handoff_base(base, default_base, handoff)
    selected = [handoff_image_lane(model, artifacts) for model in models]
    ids = [lane["id"] for lane in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("image runtime handoff request model ids must be unique")
    handoff_server = handoff.get("server_settings", {})
    server_overrides = parse_composition_object(server_overrides_value, "PREFER_SERVER_OVERRIDES")
    model_overrides = parse_composition_object(model_overrides_value, "PREFER_MODEL_OVERRIDES")
    if not isinstance(handoff_server, dict) or any(not isinstance(value, dict) for value in model_overrides.values()):
        raise ValueError("runtime handoff server and model overrides must be objects")
    forbidden = {"models", "max_loaded_models", "lazy_load"}
    for source in (handoff_server, server_overrides):
        conflict = forbidden & source.keys()
        if conflict:
            raise ValueError(f"image runtime server settings cannot replace {sorted(conflict)[0]}")
    applied: dict[str, dict] = {}
    known_names: set[str] = set()
    for lane in selected:
        names = {lane["key"], lane["id"]}
        known_names.update(names)
        matching = [value for name, value in model_overrides.items() if name in names]
        if len(matching) > 1:
            raise ValueError(f"multiple PREFER_MODEL_OVERRIDES entries target {lane['key']}")
        if not matching:
            continue
        override = matching[0]
        unknown_keys = set(override) - {"args", "args_append", "args_remove"}
        if unknown_keys:
            raise ValueError(f"unsupported image model override for {lane['key']}: {sorted(unknown_keys)[0]}")
        if "args" in override:
            if not isinstance(override["args"], list) or any(not isinstance(value, str) for value in override["args"]):
                raise ValueError(f"{lane['key']}: args must contain strings")
            lane["args"] = copy.deepcopy(override["args"])
        if "args_remove" in override:
            if not isinstance(override["args_remove"], list) or any(not isinstance(value, str) for value in override["args_remove"]):
                raise ValueError(f"{lane['key']}: args_remove must contain strings")
            lane["args"] = remove_image_args(lane["args"], override["args_remove"])
        if "args_append" in override:
            if not isinstance(override["args_append"], list) or any(not isinstance(value, str) for value in override["args_append"]):
                raise ValueError(f"{lane['key']}: args_append must contain strings")
            lane["args"].extend(override["args_append"])
        applied[lane["key"]] = override
    unknown = [name for name in model_overrides if name not in known_names]
    if unknown:
        raise ValueError("PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown))
    config = server_config(selected, deep_merge(base_server, handoff_server, server_overrides))
    artifact_ids = [artifact["id"] for artifact in raw_artifacts]
    plan = {
        "schema_version": "prefer.runtime-plan.v1",
        "runtime": "stable-diffusion.cpp",
        "base_deployment": base_deployment,
        "handoff_fingerprint": handoff.get("handoff_fingerprint"),
        "bundles": [],
        "requested_models": [lane["key"] for lane in selected],
        "resolved_model_keys": [],
        "resolved_artifact_ids": artifact_ids,
        "server_overrides": server_overrides,
        "model_overrides": applied,
        "precedence": [
            "runtime handoff model and artifact settings",
            "hardware deployment defaults",
            "runtime handoff server settings",
            "PREFER_SERVER_OVERRIDES",
            "PREFER_MODEL_OVERRIDES",
            "router command arguments",
        ],
    }
    return config, artifact_ids, plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PreFer stable-diffusion.cpp configs and inventory")
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
        try:
            config, artifact_ids, plan = compose_runtime_handoff_config(
                handoff_path=args.handoff_input,
                base=args.base,
                default_base=args.default_base,
                server_overrides_value=args.server_overrides,
                model_overrides_value=args.model_overrides,
            )
            for value in (args.output, args.prestage_output, args.plan_output):
                Path(value).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(render_json(config), encoding="utf-8", newline="\n")
            Path(args.prestage_output).write_text(",".join(artifact_ids) + "\n", encoding="utf-8", newline="\n")
            Path(args.plan_output).write_text(render_json(plan), encoding="utf-8", newline="\n")
            print(f"composed image runtime config from immutable handoff {plan['handoff_fingerprint']}")
            return 0
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
            print(f"image composition failed: {exc}", file=sys.stderr)
            return 1
    if args.compose:
        if args.check or not args.base or not args.output or not args.prestage_output or not args.plan_output:
            parser.error("--compose requires --base, --output, --prestage-output, and --plan-output")
        try:
            config, prestage, plan = compose_runtime_config(
                base=args.base,
                bundle_value=args.bundles,
                model_value=args.models,
                server_overrides_value=args.server_overrides,
                model_overrides_value=args.model_overrides,
            )
            for value in (args.output, args.prestage_output, args.plan_output):
                Path(value).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(render_json(config), encoding="utf-8", newline="\n")
            Path(args.prestage_output).write_text(",".join(prestage) + "\n", encoding="utf-8", newline="\n")
            Path(args.plan_output).write_text(render_json(plan), encoding="utf-8", newline="\n")
            print(f"composed image runtime config from {plan['base_deployment']}: {', '.join(prestage)}")
            return 0
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
            print(f"image composition failed: {exc}", file=sys.stderr)
            return 1
    try:
        outputs = expected_outputs()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"image generation failed: {exc}", file=sys.stderr)
        return 1
    stale = []
    if CONFIGS_ROOT.exists():
        expected_config_paths = {path.resolve() for path in outputs if CONFIGS_ROOT in path.parents}
        stale = [path for path in CONFIGS_ROOT.rglob("*") if path.is_file() and path.resolve() not in expected_config_paths]
    mismatches = [path for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
    if args.check:
        for path in [*mismatches, *stale]:
            print(f"generated image file is stale: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if mismatches or stale else 0
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    for path in stale:
        path.unlink()
    print(f"generated {len(outputs)} image configuration and inventory files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
