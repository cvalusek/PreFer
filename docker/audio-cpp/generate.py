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


def model_lanes() -> list[dict]:
    lanes: list[dict] = []
    seen_keys: set[str] = set()
    seen_ids: set[str] = set()
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
                if not re.fullmatch(r"[0-9a-f]{40}", artifact["revision"]):
                    raise ValueError(f"{key}: artifact revision must be an immutable SHA")
                if not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
                    raise ValueError(f"{key}: artifact sha256 is invalid")
                if not isinstance(artifact["size"], int) or artifact["size"] <= 0:
                    raise ValueError(f"{key}: artifact size must be positive")
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
    config.update(overrides)
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
            "workflow_artifact_name_pattern": (
                "prefer-audio-deployment-inventory-<commit-sha>"
            ),
            "oci_labels": {
                "path": "io.prefer.deployment-inventory.path",
                "schema": "io.prefer.deployment-inventory.schema",
            },
        },
        "runtime": runtime["runtime"],
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
    cases = []
    for lane in lanes:
        commands = []
        for artifact in lane["artifacts"]:
            commands.append(
                f"    audio_download_artifact {json.dumps(lane['key'])} "
                f"{json.dumps(artifact['repo'])} {json.dumps(artifact['revision'])} "
                f"{json.dumps(artifact['path'])} {artifact['size']} {json.dumps(artifact['sha256'])}"
            )
        cases.append(f"  {lane['key']})\n{chr(10).join(commands)}\n    ;;")
    return f'''#!/usr/bin/env bash
set -euo pipefail

readonly AUDIO_GENERATED_MODEL_KEYS={json.dumps(keys)}

audio_verify_artifact() {{
  local path="$1"
  local expected_size="$2"
  local expected_sha256="$3"
  [ -f "$path" ] || return 1
  [ "$(stat -c '%s' "$path")" = "$expected_size" ] || return 1
  [ "$(sha256sum "$path" | cut -d ' ' -f 1)" = "$expected_sha256" ]
}}

audio_download_artifact() {{
  local key="$1"
  local repo="$2"
  local revision="$3"
  local artifact="$4"
  local expected_size="$5"
  local expected_sha256="$6"
  local destination="/models/$repo/$artifact"
  local partial="${{destination}}.partial"
  local url="https://huggingface.co/$repo/resolve/$revision/$artifact?download=true"

  mkdir -p "$(dirname "$destination")"
  if audio_verify_artifact "$destination" "$expected_size" "$expected_sha256"; then
    echo "[audio-download] $key: exact artifact already present"
    return
  fi

  rm -f "$destination"
  echo "[audio-download] $key: downloading pinned artifact"
  curl --fail --location --retry 5 --retry-all-errors --continue-at - --output "$partial" "$url"
  if ! audio_verify_artifact "$partial" "$expected_size" "$expected_sha256"; then
    echo "[audio-download] $key: size or SHA-256 validation failed" >&2
    rm -f "$partial"
    return 1
  fi
  mv -f "$partial" "$destination"
}}

audio_download_model_key() {{
  case "$1" in
{chr(10).join(cases)}
    *) echo "[audio-download] unknown model key: $1" >&2; return 2 ;;
  esac
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PreFer audio.cpp runtime artifacts")
    parser.add_argument("--check", action="store_true", help="fail if generated files are stale")
    args = parser.parse_args()
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
