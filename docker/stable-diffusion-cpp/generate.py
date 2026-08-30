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
    config.update(overrides)
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
    **extra: object,
) -> dict:
    artifacts = unique_artifacts(lanes)
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
        "residency": {"lazy_load": True, "max_loaded_models": 1, "idle_unload_ms": 1800000},
        "capabilities": sorted({capability for lane in lanes for capability in lane["capabilities"]}),
        "models": [
            {"key": lane["key"], "request_model_id": lane["id"], "precision": lane["precision"], "capabilities": lane["capabilities"]}
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
            "workflow_artifact_name_pattern": "prefer-image-deployment-inventory-<commit-sha>",
            "oci_labels": {"path": "io.prefer.deployment-inventory.path", "schema": "io.prefer.deployment-inventory.schema"},
        },
        "runtime": runtime["runtime"],
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
    for artifact in artifacts.values():
        artifact_id = artifact_download_id(artifact)
        artifact_cases.append(
            f"  {artifact_id})\n"
            f"    prefer_download_hf_artifact \"image-download\" \"$1\" "
            f"{json.dumps(artifact['repo'])} {json.dumps(artifact['revision'])} "
            f"{json.dumps(artifact['path'])} {artifact['size']} {json.dumps(artifact['sha256'])}\n"
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

image_download_model_keys() {{
  prefer_download_model_keys \
    "image-download" "${{IMAGE_DOWNLOAD_JOBS:-4}}" 8 \
    image_model_artifact_ids image_download_artifact_id "$@"
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PreFer stable-diffusion.cpp configs and inventory")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
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
