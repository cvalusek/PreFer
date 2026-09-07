#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import sys


ROOT = Path(__file__).resolve().parent
MODELS_ROOT = ROOT / "models"
RUNTIME_PATH = ROOT / "runtime.json"
BUNDLES_PATH = ROOT / "deployment-bundles.json"
SCENARIOS_ROOT = ROOT / "deployment-scenarios"
CONFIGS_ROOT = ROOT / "server-configs"


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
        shared = source["shared"]
        primary = [quant for quant in source["quants"].values() if quant.get("primary")]
        if len(primary) != 1:
            raise ValueError(f"{path}: exactly one primary quant is required")
        for quant_slug, quant in source["quants"].items():
            key = quant["key"]
            model_id = shared["id"]
            if key in seen_keys:
                raise ValueError(f"duplicate model key: {key}")
            if quant.get("primary") and model_id in seen_ids:
                raise ValueError(f"duplicate configured model id: {model_id}")
            if "artifact" in quant and "artifacts" in quant:
                raise ValueError(f"{key}: use artifact or artifacts, not both")
            artifacts = quant.get("artifacts")
            if artifacts is None:
                artifact = quant.get("artifact")
                artifacts = [artifact] if artifact else []
            if not isinstance(artifacts, list) or not artifacts:
                raise ValueError(f"{key}: at least one artifact is required")
            for artifact in artifacts:
                repo = artifact.get("repo")
                if not isinstance(repo, str) or not re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
                    repo,
                ):
                    raise ValueError(f"{key}: artifact repo must be a safe owner/name")
                if not re.fullmatch(r"[0-9a-f]{40}", artifact["revision"]):
                    raise ValueError(f"{key}: artifact revision must be an immutable SHA")
                if not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
                    raise ValueError(f"{key}: artifact sha256 is invalid")
                if not isinstance(artifact["size"], int) or artifact["size"] <= 0:
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
            artifact_repos = {artifact["repo"] for artifact in artifacts}
            if len(artifact_repos) != 1:
                raise ValueError(f"{key}: all package artifacts must share one repository")
            artifact_repo = next(iter(artifact_repos))
            server_path = quant.get("server_path", artifacts[0]["path"])
            if not isinstance(server_path, str) or not server_path:
                raise ValueError(f"{key}: server_path must be a non-empty string")
            if server_path.startswith("/") or ".." in Path(server_path).parts:
                raise ValueError(f"{key}: server_path must stay inside the artifact repository")
            container_path = (
                f"/models/{artifact_repo}"
                if server_path == "."
                else f"/models/{artifact_repo}/{server_path}"
            )
            server_options = dict(shared.get("server", {}))
            for name, value in quant.get("server", {}).items():
                if isinstance(server_options.get(name), dict) and isinstance(value, dict):
                    server_options[name] = {**server_options[name], **value}
                else:
                    server_options[name] = value
            protected_server_keys = {"id", "family", "path", "task", "mode", "lazy"}
            if protected_server_keys & server_options.keys():
                raise ValueError(f"{key}: server options cannot replace model identity fields")
            lane = {
                "key": key,
                "quant_slug": quant_slug,
                "precision": quant["precision"],
                "primary": bool(quant.get("primary")),
                **shared,
                "artifacts": artifacts,
                "server_path": server_path,
                "container_path": container_path,
                "server": server_options,
            }
            lanes.append(lane)
            seen_keys.add(key)
            if lane["primary"]:
                seen_ids.add(model_id)
    if not lanes:
        raise ValueError("no audio model catalogs found")
    lanes.sort(key=lambda lane: (0 if lane["task"] == "tts" else 1, lane["key"]))
    return lanes


def server_config(
    backend: str,
    lanes: list[dict],
    overrides: dict | None = None,
) -> dict:
    config = {
        "host": "0.0.0.0",
        "port": 8080,
        "backend": backend,
        "device": 0,
        "threads": 4,
        "lazy_load": True,
        "max_loaded_models": 1,
        "idle_unload_ms": 1800000,
        # The upstream 1.5x file-size heuristic rejects PersonaPlex Q4 before
        # loading even though its bounded 512 MiB graph arena fits the 12 GB
        # target. This is a curated, single-resident catalog, so rely on the
        # exact per-model settings and the backend allocator instead.
        "min_free_memory_mb": 0,
        "busy_timeout_ms": 300000,
        "max_request_body_bytes": 536870912,
        "log_request_body": False,
    }
    overrides = copy.deepcopy(overrides or {})
    forbidden = {"backend", "models"} & overrides.keys()
    if forbidden:
        raise ValueError(f"server overrides cannot replace: {', '.join(sorted(forbidden))}")
    config = deep_merge(config, overrides)
    lazy = bool(config["lazy_load"])
    config["models"] = [
        {
            "id": lane["id"],
            "family": lane["family"],
            "path": lane["container_path"],
            "task": lane["task"],
            "mode": lane["mode"],
            "lazy": lazy,
            **lane["server"],
        }
        for lane in lanes
    ]
    return config


def load_bundles(primary_by_key: dict[str, dict]) -> dict[str, dict]:
    source = load_json(BUNDLES_PATH)
    if source.get("schema_version") != 1:
        raise ValueError("deployment-bundles.json schema_version must be 1")
    bundles = source.get("bundles")
    if not isinstance(bundles, dict) or not bundles:
        raise ValueError("deployment-bundles.json bundles must be a non-empty object")
    for name, bundle in bundles.items():
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            raise ValueError(f"unsafe audio deployment bundle name: {name!r}")
        keys = bundle.get("models")
        if not isinstance(keys, list) or not keys or len(set(keys)) != len(keys):
            raise ValueError(f"bundle {name}: models must be a non-empty unique list")
        unknown = sorted(set(keys) - set(primary_by_key))
        if unknown:
            raise ValueError(f"bundle {name}: unknown primary model keys: {', '.join(unknown)}")
        server = bundle.get("server", {})
        if not isinstance(server, dict):
            raise ValueError(f"bundle {name}: server must be an object")
    return bundles


def validate_scenario_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".json":
        raise ValueError(f"unsafe or non-JSON audio scenario path: {value!r}")
    return path.as_posix()


def load_scenarios(primary_by_key: dict[str, dict], bundles: dict[str, dict]) -> list[dict]:
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
        if not provider or not output_root:
            raise ValueError(f"{source_path}: provider and output_root are required")
        hardware = source.get("hardware")
        if not isinstance(hardware, dict) or not hardware.get("gpu_count"):
            raise ValueError(f"{source_path}: hardware with gpu_count is required")
        source_server = source.get("server", {})
        if not isinstance(source_server, dict):
            raise ValueError(f"{source_path}: server must be an object")
        bundle_names = source.get("bundles", [])
        if not isinstance(bundle_names, list):
            raise ValueError(f"{source_path}: bundles must be a list")
        unknown_bundles = sorted(set(bundle_names) - set(bundles))
        if unknown_bundles:
            raise ValueError(f"{source_path}: unknown bundles: {', '.join(unknown_bundles)}")

        requested_singles = source.get("single_models", [])
        if requested_singles == "all":
            single_keys = list(primary_by_key)
        elif isinstance(requested_singles, list):
            single_keys = requested_singles
        else:
            raise ValueError(f"{source_path}: single_models must be 'all' or a list")
        unknown_singles = sorted(set(single_keys) - set(primary_by_key))
        if unknown_singles:
            raise ValueError(f"{source_path}: unknown single model keys: {', '.join(unknown_singles)}")

        specs: list[tuple[str, str, list[str], dict, str]] = []
        for bundle_name in bundle_names:
            bundle = bundles[bundle_name]
            specs.append(
                (
                    bundle_name,
                    "bundle",
                    list(bundle["models"]),
                    bundle.get("server", {}),
                    bundle.get("description", ""),
                )
            )
        for key in single_keys:
            lane = primary_by_key[key]
            specs.append((lane["id"], "single-model", [key], {}, lane["description"]))

        for name, kind, keys, bundle_server, description in specs:
            path = validate_scenario_path(f"{output_root}/{name}.json")
            if path in seen_paths:
                raise ValueError(f"duplicate generated audio server config path: {path}")
            seen_paths.add(path)
            records.append(
                {
                    "path": path,
                    "name": name,
                    "kind": kind,
                    "provider": provider,
                    "hardware": copy.deepcopy(hardware),
                    "compatibility": copy.deepcopy(source.get("compatibility", {})),
                    "verification_status": source.get("verification", "configuration-only"),
                    "description": description,
                    "model_keys": keys,
                    "server": {**source_server, **bundle_server},
                    "source": source_path.relative_to(ROOT).as_posix(),
                }
            )
    return records


def lane_inventory(lane: dict) -> dict:
    artifacts = [
        {
            **artifact,
            "container_path": f"/models/{artifact['repo']}/{artifact['path']}",
        }
        for artifact in lane["artifacts"]
    ]
    fingerprint_payload = {
        "schema_version": 1,
        "key": lane["key"],
        "artifacts": lane["artifacts"],
    }
    download_fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return {
        "id": lane["id"],
        "family": lane["family"],
        "task": lane["task"],
        "mode": lane["mode"],
        "description": lane["description"],
        "precision": lane["precision"],
        "primary": lane["primary"],
        "license": lane["license"],
        "lineage": lane["lineage"],
        "server_path": lane["container_path"],
        "server": lane["server"],
        "download_fingerprint": download_fingerprint,
        "artifact_bytes": sum(artifact["size"] for artifact in lane["artifacts"]),
        "artifacts": artifacts,
    }


def deployment_inventory(
    runtime: dict,
    lanes: list[dict],
    scenarios: list[dict],
    bundles: dict[str, dict],
) -> dict:
    primary = [lane for lane in lanes if lane["primary"]]
    primary_by_key = {lane["key"]: lane for lane in primary}
    models = {lane["key"]: lane_inventory(lane) for lane in lanes}
    deployments = []
    for backend, image_tag in (("cuda12", "audio-cuda12"), ("cpu", "audio-cpu")):
        prestage_keys = [lane["key"] for lane in primary]
        deployments.append(
            {
                "id": f"audio/{backend}",
                "runtime": "audio.cpp",
                "backend": "cuda" if backend == "cuda12" else "cpu",
                "image_tag": image_tag,
                "base_image": runtime["base_images"][backend]["reference"],
                "requires_gpu": backend == "cuda12",
                "container": {
                    "name": "prefer-audio",
                    "internal_port": 8080,
                    "health_path": "/health",
                    "model_mount": "/models",
                    "voice_mount": "/voices",
                },
                "server_config": "/app/server.json",
                "prestage_manifest": None,
                "environment": {
                    "AUDIO_PRESTAGE_MODELS": ",".join(prestage_keys),
                },
                "residency": {
                    "lazy_load": True,
                    "max_loaded_models": 1,
                    "idle_unload_ms": 1800000,
                },
                "models": [
                    {
                        "key": lane["key"],
                        "request_model_id": lane["id"],
                        "task": lane["task"],
                        "mode": lane["mode"],
                    }
                    for lane in primary
                ],
                "prestage_models": prestage_keys,
                "verification_status": "configuration-only",
                "verification": "configuration-only",
            }
        )
    for scenario in scenarios:
        selected = [primary_by_key[key] for key in scenario["model_keys"]]
        config_path = f"/server-configs/{scenario['path']}"
        prestage_path = str(PurePosixPath(config_path).with_suffix(".prestage"))
        artifact_bytes = sum(
            artifact["size"] for lane in selected for artifact in lane["artifacts"]
        )
        effective_config = server_config("cuda", selected, scenario["server"])
        deployments.append(
            {
                "id": PurePosixPath(scenario["path"]).with_suffix("").as_posix(),
                "runtime": "audio.cpp",
                "backend": "cuda",
                "image_tag": "audio-cuda12",
                "base_image": runtime["base_images"]["cuda12"]["reference"],
                "requires_gpu": True,
                "provider": scenario["provider"],
                "hardware": scenario["hardware"],
                "compatibility": scenario["compatibility"],
                "kind": scenario["kind"],
                "description": scenario["description"],
                "source": scenario["source"],
                "server_config": config_path,
                "prestage_manifest": prestage_path,
                "container": {
                    "name": "prefer-audio",
                    "internal_port": 8080,
                    "health_path": "/health",
                    "model_mount": "/models",
                    "voice_mount": "/voices",
                    "server_config": config_path,
                    "prestage_manifest": prestage_path,
                },
                "environment": {
                    "AUDIO_SERVER_CONFIG": config_path,
                    "AUDIO_PRESTAGE_MODELS": "",
                },
                "residency": {
                    "lazy_load": effective_config["lazy_load"],
                    "max_loaded_models": effective_config["max_loaded_models"],
                    "idle_unload_ms": effective_config["idle_unload_ms"],
                    "busy_timeout_ms": effective_config["busy_timeout_ms"],
                },
                "capabilities": sorted({lane["task"] for lane in selected}),
                "models": [
                    {
                        "key": lane["key"],
                        "request_model_id": lane["id"],
                        "task": lane["task"],
                        "mode": lane["mode"],
                        "precision": lane["precision"],
                    }
                    for lane in selected
                ],
                "prestage_models": scenario["model_keys"],
                "staged_artifact_bytes": artifact_bytes,
                "verification_status": scenario["verification_status"],
                "verification": scenario["verification_status"],
            }
        )
    bundle_inventory = {
        name: {
            "description": bundle.get("description", ""),
            "models": bundle["models"],
            "server": bundle.get("server", {}),
        }
        for name, bundle in bundles.items()
    }
    catalog_payload = {
        "runtime": runtime,
        "bundles": bundle_inventory,
        "models": models,
        "deployments": deployments,
    }
    catalog_fingerprint = hashlib.sha256(
        json.dumps(catalog_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {
        "schema_version": "prefer.audio-deployment-inventory.v1",
        "catalog_fingerprint": catalog_fingerprint,
        "product": "PreFer",
        "distribution": {
            "embedded_image_path": "/deployment-inventory.json",
            "workflow_artifact_name_pattern": "prefer-release-<commit-sha>",
            "github_release_tag_pattern": "sha-<short-commit>",
            "release_inventory_asset": "prefer-audio-deployment-inventory.json",
            "oci_labels": {
                "path": "io.prefer.deployment-inventory.path",
                "schema": "io.prefer.deployment-inventory.schema",
            },
        },
        "runtime": runtime["runtime"],
        "composition": {
            "schema_version": "prefer.runtime-composition.v1",
            "activation": "opt-in; existing AUDIO_SERVER_CONFIG remains compatible when no composition variable is set",
            "multi_model": True,
            "effective_config_path": "/run/prefer/audio.json",
            "effective_plan_path": "/run/prefer/plan.json",
            "compose_environment_prefix": "AUDIO",
            "override_merge": "objects merge recursively; scalar and array values replace",
            "environment": {
                "PREFER_DEPLOYMENT": {"type": "string", "source": "deployments[].id"},
                "PREFER_BUNDLE": {"type": "string-list", "source": "bundles keys"},
                "PREFER_MODELS": {"type": "string-list", "source": "models key or request_model_id"},
                "PREFER_SERVER_OVERRIDES": {"type": "json-object", "applies_to": "audio.cpp server settings"},
                "PREFER_MODEL_OVERRIDES": {"type": "json-object-map", "applies_to": "selected model session settings"},
            },
            "selection_rules": [
                "bundle and model selections are additive",
                "an exact quant key replaces another lane for the same logical model",
                "a friendly model selection uses its primary catalog lane",
            ],
            "precedence": [
                "catalog model and lane defaults",
                "hardware deployment defaults",
                "bundle defaults",
                "PREFER_SERVER_OVERRIDES",
                "PREFER_MODEL_OVERRIDES",
                "raw engine arguments",
            ],
            "setting_sources": {
                "server": "composition.server_defaults plus bundles[].server and deployment config",
                "model": "models[].server",
            },
            "server_defaults": {
                key: value
                for key, value in server_config("cuda", []).items()
                if key not in {"backend", "models"}
            },
        },
        "base_images": runtime["base_images"],
        "api": {
            "health": "GET /health",
            "models": "GET /v1/models",
            "speech": "POST /v1/audio/speech",
            "live_speech": "POST /v1/audio/speech/live",
            "transcriptions": "POST /v1/audio/transcriptions",
            "live_transcriptions": "POST /v1/audio/transcriptions/live",
            "tasks": "POST /v1/tasks/run",
        },
        "bundles": bundle_inventory,
        "models": models,
        "deployments": deployments,
    }


def download_script(lanes: list[dict]) -> str:
    keys = ",".join(lane["key"] for lane in lanes if lane["primary"])
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
    for artifact in artifacts.values():
        artifact_id = artifact_download_id(artifact)
        artifact_cases.append(
            f"  {artifact_id})\n"
            f"    prefer_download_hf_artifact \"audio-download\" \"$1\" "
            f"{json.dumps(artifact['repo'])} {json.dumps(artifact['revision'])} "
            f"{json.dumps(artifact['path'])} {artifact['size']} {json.dumps(artifact['sha256'])}\n"
            "    ;;"
        )
    return f'''#!/usr/bin/env bash
set -euo pipefail

readonly AUDIO_GENERATED_MODEL_KEYS={json.dumps(keys)}

audio_model_artifact_ids() {{
  case "$1" in
{chr(10).join(model_cases)}
    *) echo "[audio-download] unknown model key: $1" >&2; return 2 ;;
  esac
}}

audio_download_artifact_id() {{
  case "$1" in
{chr(10).join(artifact_cases)}
    *) echo "[audio-download] unknown artifact id: $1" >&2; return 2 ;;
  esac
}}

audio_download_model_keys() {{
  prefer_download_model_keys \
    "audio-download" "${{AUDIO_DOWNLOAD_JOBS:-4}}" 8 \
    audio_model_artifact_ids audio_download_artifact_id "$@"
}}

audio_download_model_key() {{
  audio_download_model_keys "$1"
}}
'''


def rendered_outputs() -> dict[Path, str]:
    runtime = load_json(RUNTIME_PATH)
    if runtime.get("schema_version") != 1:
        raise ValueError("runtime.json schema_version must be 1")
    lanes = model_lanes()
    primary = [lane for lane in lanes if lane["primary"]]
    primary_by_key = {lane["key"]: lane for lane in primary}
    bundles = load_bundles(primary_by_key)
    scenarios = load_scenarios(primary_by_key, bundles)
    outputs = {
        ROOT / "server.cuda.generated.json": json.dumps(server_config("cuda", primary), indent=2) + "\n",
        ROOT / "server.cpu.generated.json": json.dumps(server_config("cpu", primary), indent=2) + "\n",
        ROOT / "deployment-inventory.generated.json": json.dumps(
            deployment_inventory(runtime, lanes, scenarios, bundles), indent=2
        ) + "\n",
        ROOT / "model-downloads.generated.sh": download_script(lanes),
    }
    for scenario in scenarios:
        selected = [primary_by_key[key] for key in scenario["model_keys"]]
        config_path = CONFIGS_ROOT / PurePosixPath(scenario["path"])
        outputs[config_path] = json.dumps(
            server_config("cuda", selected, scenario["server"]), indent=2
        ) + "\n"
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
    if normalized in {"/app/server.json", "server.json", "default", "audio/cuda12", "audio/cpu"}:
        return "default"
    if not normalized.endswith(".json"):
        normalized += ".json"
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe audio deployment: {value!r}")
    return path.as_posix()


def audio_selection_names(lane: dict) -> set[str]:
    return {lane["key"], lane["id"]}


def compose_runtime_config(
    *,
    base: str,
    bundle_value: str,
    model_value: str,
    server_overrides_value: str,
    model_overrides_value: str,
) -> tuple[dict, list[str], dict]:
    lanes = model_lanes()
    primary = [lane for lane in lanes if lane["primary"]]
    primary_by_key = {lane["key"]: lane for lane in primary}
    bundles = load_bundles(primary_by_key)
    scenarios = load_scenarios(primary_by_key, bundles)
    scenario_by_path = {scenario["path"]: scenario for scenario in scenarios}
    normalized = normalize_runtime_config(base)
    explicit_base_path = Path(base)

    if normalized == "default" or explicit_base_path.is_file():
        base_path = explicit_base_path
        if not base_path.is_file():
            installed_default = Path("/app/server.json")
            if installed_default.is_file():
                base_path = installed_default
            else:
                generated_name = "server.cpu.generated.json" if base.strip() == "audio/cpu" else "server.cuda.generated.json"
                base_path = ROOT / generated_name
        base_config = load_json(base_path)
        by_id = {lane["id"]: lane for lane in primary}
        base_lanes = []
        for model in base_config.get("models", []):
            lane = by_id.get(model.get("id"))
            if lane is None:
                raise ValueError(f"cannot map audio base model {model.get('id')!r} to the catalog")
            base_lanes.append(lane)
        backend = base_config.get("backend", "cuda")
        base_server = {key: value for key, value in base_config.items() if key not in {"backend", "models"}}
        base_deployment = (
            PurePosixPath(normalized).with_suffix("").as_posix()
            if normalized != "default"
            else ("audio/cuda12" if backend == "cuda" else "audio/cpu")
        )
    else:
        scenario = scenario_by_path.get(normalized)
        if scenario is None:
            raise ValueError(f"unknown audio deployment: {base!r}")
        base_lanes = [primary_by_key[key] for key in scenario["model_keys"]]
        backend = "cuda"
        base_server = scenario["server"]
        base_deployment = PurePosixPath(normalized).with_suffix("").as_posix()

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

    bundle_server: dict = {}
    for name in requested_bundles:
        bundle = bundles.get(name)
        if bundle is None:
            raise ValueError(f"unknown audio bundle: {name!r}")
        bundle_server = deep_merge(bundle_server, bundle.get("server", {}))
        for key in bundle["models"]:
            add_lane(primary_by_key[key])

    for selection in requested_models:
        matches = [lane for lane in lanes if selection in audio_selection_names(lane)]
        if not matches:
            raise ValueError(f"unknown audio model selection: {selection!r}")
        if selection in {lane["key"] for lane in matches}:
            lane = next(lane for lane in matches if lane["key"] == selection)
        elif len(matches) == 1:
            lane = matches[0]
        else:
            raise ValueError(
                f"ambiguous audio model {selection!r}; choose an exact lane: "
                + ", ".join(lane["key"] for lane in matches)
            )
        add_lane(lane)

    if not requested_bundles and not requested_models:
        selected = [copy.deepcopy(lane) for lane in base_lanes]
    if not selected:
        raise ValueError("runtime composition selected no audio models")

    applied_model_overrides: dict[str, dict] = {}
    for lane in selected:
        matching = [value for name, value in model_overrides.items() if name in audio_selection_names(lane)]
        if len(matching) > 1:
            raise ValueError(f"multiple PREFER_MODEL_OVERRIDES entries target {lane['key']}")
        if matching:
            protected = {"id", "family", "path", "task", "mode", "lazy"} & matching[0].keys()
            if protected:
                raise ValueError(
                    f"audio model overrides cannot replace identity fields: {', '.join(sorted(protected))}"
                )
            lane["server"] = deep_merge(lane.get("server", {}), matching[0])
            applied_model_overrides[lane["key"]] = matching[0]
    unknown_targets = [
        name
        for name in model_overrides
        if not any(name in audio_selection_names(lane) for lane in selected)
    ]
    if unknown_targets:
        raise ValueError("PREFER_MODEL_OVERRIDES targets are not selected: " + ", ".join(unknown_targets))

    effective_server = deep_merge(base_server, bundle_server, server_overrides)
    config = server_config(backend, selected, effective_server)
    prestage = [lane["key"] for lane in selected]
    plan = {
        "schema_version": "prefer.runtime-plan.v1",
        "runtime": "audio.cpp",
        "base_deployment": base_deployment,
        "bundles": requested_bundles,
        "requested_models": requested_models,
        "resolved_model_keys": prestage,
        "server_overrides": server_overrides,
        "model_overrides": applied_model_overrides,
        "precedence": [
            "catalog model and lane defaults",
            "hardware deployment defaults",
            "bundle defaults",
            "PREFER_SERVER_OVERRIDES",
            "PREFER_MODEL_OVERRIDES",
            "audio.cpp command arguments",
        ],
    }
    return config, prestage, plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PreFer audio.cpp runtime artifacts")
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    parser.add_argument("--compose", action="store_true", help="write an ephemeral runtime-composed config")
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
            Path(args.output).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
            Path(args.prestage_output).write_text(",".join(prestage) + "\n", encoding="utf-8", newline="\n")
            Path(args.plan_output).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(f"composed audio.cpp runtime config from {plan['base_deployment']}: {', '.join(prestage)}")
            return 0
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"generate.py: {error}", file=sys.stderr)
            return 1
    stale = []
    outputs = rendered_outputs()
    expected_scenario_files = {path for path in outputs if CONFIGS_ROOT in path.parents}
    actual_scenario_files = (
        {path for path in CONFIGS_ROOT.rglob("*") if path.is_file()}
        if CONFIGS_ROOT.exists()
        else set()
    )
    unexpected = sorted(actual_scenario_files - expected_scenario_files)
    if args.check:
        stale.extend(path.relative_to(ROOT).as_posix() for path in unexpected)
    else:
        for path in unexpected:
            path.unlink()
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("stale generated audio.cpp files: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
