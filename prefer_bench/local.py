from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import subprocess
import time
import uuid
from typing import Any

from .contract import load_contract, load_corpus, model_record
from .diagnostics import classify_runtime_failure, linux_amd64_manifest_digests, manifest_failure_code
from .http_client import ClientTimeout, TransportError, request_json
from .memory import gpu_inventory
from .paths import COMPOSE_PATH, REPO_ROOT
from .report import write_report
from .results import empty_cell, finish_result, skip_cell, utc_now, write_json
from .runner import LiveConfig, run_live_suite


LANES = {
    "current": {
        "base_image_tag": "ghcr.io/ggml-org/llama.cpp:server-cuda-b9843",
        "base_image": "ghcr.io/ggml-org/llama.cpp@sha256:3af9b6f556151848ce221c63a63f87c04832d6666361babca20ee6295255f1c6",
        "image": "prefer-bench:b9843",
        "revision": "b9843",
        "manifest_digest": "sha256:3af9b6f556151848ce221c63a63f87c04832d6666361babca20ee6295255f1c6",
        "source_commit": "86b94708f22478f900b76ca02e316f4f3418faff",
        "release_url": "https://github.com/ggml-org/llama.cpp/releases/tag/b9843",
        "comparison_lane": False,
    },
    "b9982": {
        "base_image_tag": "ghcr.io/ggml-org/llama.cpp:server-cuda-b9982",
        "base_image": "ghcr.io/ggml-org/llama.cpp@sha256:3a8429364531aa324a477f5fd3f9a9472ca16164c9c5fbc5b202629068263e76",
        "image": "prefer-bench:b9982",
        "revision": "b9982",
        "manifest_digest": "sha256:3a8429364531aa324a477f5fd3f9a9472ca16164c9c5fbc5b202629068263e76",
        "source_commit": "99f3dc32296f825fec94f202da1e9fede1e78cf9",
        "release_url": "https://github.com/ggml-org/llama.cpp/releases/tag/b9982",
        "comparison_lane": True,
    },
}


CACHE_MODELS = {
    "gemma-4-e2b": {
        "request_id": "gemma-4-e2b",
        "files": [
            "unsloth/gemma-4-E2B-it-qat-GGUF/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
            "unsloth/gemma-4-E2B-it-qat-GGUF/mtp-gemma-4-E2B-it.gguf",
            "unsloth/gemma-4-E2B-it-qat-GGUF/mmproj-F16.gguf",
        ],
    },
    "gemma-4-e4b": {
        "request_id": "gemma-4-e4b",
        "files": [
            "unsloth/gemma-4-E4B-it-qat-GGUF/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf",
            "unsloth/gemma-4-E4B-it-qat-GGUF/mtp-gemma-4-E4B-it.gguf",
            "unsloth/gemma-4-E4B-it-qat-GGUF/mmproj-F16.gguf",
        ],
    },
    "smol": {
        "request_id": "smol",
        "files": ["unsloth/SmolLM2-135M-Instruct-GGUF/SmolLM2-135M-Instruct-Q8_0.gguf"],
    },
}


class CommandError(RuntimeError):
    def __init__(self, args: list[str], returncode: int, output: str) -> None:
        super().__init__(f"command failed ({returncode}): {' '.join(args[:4])}; {output[-1000:]}")
        self.args_list = args
        self.returncode = returncode
        self.output = output


class EnvironmentSkip(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _safe_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    allow = {
        "PATH",
        "Path",
        "SystemRoot",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "COMSPEC",
        "ComSpec",
        "PATHEXT",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramW6432",
        "CommonProgramFiles",
        "CommonProgramFiles(x86)",
        "CommonProgramW6432",
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_CONFIG",
    }
    environment = {key: value for key, value in os.environ.items() if key in allow}
    environment["COMPOSE_DISABLE_ENV_FILE"] = "1"
    if extra:
        environment.update(extra)
    return environment


def run_command(
    args: list[str],
    *,
    environment: dict[str, str] | None = None,
    check: bool = True,
    timeout: float = 600,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=REPO_ROOT,
        env=_safe_environment(environment),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        raise CommandError(args, completed.returncode, completed.stdout + completed.stderr)
    return completed


def _free_port() -> int:
    # Docker Desktop/Hyper-V can reject otherwise-free ports from Windows'
    # high ephemeral range. Keep benchmark ports in a dedicated scanned range.
    for port in range(18080, 19000):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise EnvironmentSkip("no_benchmark_port", "No free loopback port was found in 18080-18999.")


def _scrub_local_paths(output: str) -> str:
    candidates = {str(REPO_ROOT), str(Path.home())}
    for key in ("USERPROFILE", "HOME", "TEMP", "TMP", "TMPDIR"):
        value = os.environ.get(key)
        if value:
            candidates.add(value)
    scrubbed = output
    for path in sorted((value for value in candidates if value), key=len, reverse=True):
        scrubbed = scrubbed.replace(path, "<local-path>")
    return scrubbed


def _scrub_command_output(output: str, project: str, volume: str, port: int) -> str:
    scrubbed = _scrub_local_paths(output)
    scrubbed = scrubbed.replace(project, "<project>").replace(volume, "<run-volume>")
    scrubbed = scrubbed.replace(str(port), "<port>")
    lines = [line.strip() for line in scrubbed.splitlines() if line.strip()]
    return " | ".join(lines[-6:])[:800]


def _scrub_runtime_logs(output: str, project: str, volume: str, port: int) -> str:
    scrubbed = _scrub_local_paths(output)
    scrubbed = scrubbed.replace(project, "<project>").replace(volume, "<run-volume>")
    scrubbed = scrubbed.replace(str(port), "<port>")
    scrubbed = re.sub(r"\[[0-9]+\]", "[pid]", scrubbed)
    scrubbed = re.sub(r"0x[0-9a-fA-F]+", "0x<addr>", scrubbed)
    lines = [line.strip() for line in scrubbed.splitlines() if line.strip()]
    keywords = ("error", "failed", "cuda", "memory", "exception", "oom", "alloc", "assert", "fatal")
    selected = [line for line in lines if any(keyword in line.casefold() for keyword in keywords)]
    if not selected:
        selected = lines[-20:]
    return "\n".join(selected[-30:])[-4000:]


def _container_snapshot(name: str) -> dict[str, Any]:
    listing = run_command(
        ["docker", "ps", "-a", "--filter", f"name=^/{name}$", "--format", "{{.ID}}"],
        check=False,
        timeout=20,
    )
    if listing.returncode != 0:
        return {"inspection_ok": False, "present": None, "raw": None, "status": None}
    if not listing.stdout.strip():
        return {"inspection_ok": True, "present": False, "raw": "absent", "status": None}
    completed = run_command(
        ["docker", "container", "inspect", "--format", "{{.Id}}|{{.Image}}|{{.State.Status}}", name],
        check=False,
        timeout=20,
    )
    if completed.returncode != 0:
        return {"inspection_ok": False, "present": None, "raw": None, "status": None}
    raw = completed.stdout.strip()
    parts = raw.split("|")
    return {"inspection_ok": True, "present": True, "raw": raw, "status": parts[-1] if parts else None}


def _compose_environment(project: str, volume: str, port: int, lane: dict[str, Any], preset: str, models_max: int) -> dict[str, str]:
    return {
        "PREFER_BENCH_PROJECT": project,
        "PREFER_BENCH_VOLUME": volume,
        "PREFER_BENCH_PORT": str(port),
        "PREFER_BENCH_BASE_IMAGE": lane["base_image"],
        "PREFER_BENCH_IMAGE": lane["image"],
        "PREFER_BENCH_PRESET": preset,
        "PREFER_BENCH_MODELS_MAX": str(models_max),
    }


def _compose_args(project: str, *args: str) -> list[str]:
    executable = ["docker-compose"] if shutil.which("docker-compose") else ["docker", "compose"]
    return [*executable, "--project-name", project, "-f", str(COMPOSE_PATH), *args]


def _image_revision(image: str, project: str) -> str:
    completed = run_command(
        [
            "docker", "run", "--rm", "--name", f"{project}-version", "--network", "none",
            "--entrypoint", "/app/llama-server", image, "--version",
        ],
        timeout=60,
    )
    output = completed.stdout + completed.stderr
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "unknown")
    return first_line


def _image_id(image: str) -> str:
    return run_command(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=30).stdout.strip()


def _preflight_manifest(lane: dict[str, Any]) -> None:
    completed = run_command(
        ["docker", "manifest", "inspect", "--verbose", lane["base_image_tag"]],
        check=False,
        timeout=90,
    )
    if completed.returncode != 0:
        output = _scrub_local_paths(completed.stdout + completed.stderr)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        diagnostic = " | ".join(lines[-4:])[:600] or "registry returned no diagnostic text"
        code = manifest_failure_code(output)
        raise EnvironmentSkip(
            code,
            f"GHCR manifest preflight failed for {lane['base_image_tag']} (expected {lane['manifest_digest']}, "
            f"source {lane['source_commit']}): {diagnostic}",
        )
    try:
        digests = linux_amd64_manifest_digests(json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise EnvironmentSkip(
            "image_manifest_check_failed",
            f"GHCR returned unparseable manifest metadata for {lane['base_image_tag']}.",
        ) from exc
    if lane["manifest_digest"] not in digests:
        observed = ", ".join(sorted(digests)) or "none"
        raise EnvironmentSkip(
            "image_manifest_digest_mismatch",
            f"GHCR tag {lane['base_image_tag']} did not resolve to the pinned linux/amd64 digest "
            f"{lane['manifest_digest']} (observed: {observed}).",
        )


def _ensure_source_volume(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]+", name):
        raise EnvironmentSkip("invalid_cache_volume", "Cache source volume name contains unsupported characters.")
    completed = run_command(["docker", "volume", "inspect", name], check=False, timeout=20)
    if completed.returncode != 0:
        raise EnvironmentSkip("cache_volume_missing", f"Docker volume {name!r} does not exist.")


def _copy_cached_models(source: str, destination: str, image: str, project: str, model_keys: list[str]) -> None:
    if source == destination:
        raise EnvironmentSkip("unsafe_shared_volume", "Benchmark destination must differ from the operator cache volume.")
    run_command(["docker", "volume", "create", "--label", "io.prefer.benchmark=true", destination], timeout=30)
    helper = f"{project}-cache-copy"
    mounts = [
        "--mount", f"type=volume,source={source},target=/source,readonly",
        "--mount", f"type=volume,source={destination},target=/dest",
    ]
    for key in model_keys:
        for relative in CACHE_MODELS[key]["files"]:
            posix = PurePosixPath(relative)
            source_path = f"/source/{posix.as_posix()}"
            destination_dir = f"/dest/{posix.parent.as_posix()}"
            destination_path = f"/dest/{posix.as_posix()}"
            exists = run_command(
                ["docker", "run", "--rm", "--name", helper, "--network", "none", *mounts, "--entrypoint", "/usr/bin/test", image, "-f", source_path],
                check=False,
                timeout=60,
            )
            if exists.returncode != 0:
                raise EnvironmentSkip("cached_model_file_missing", f"Required cached file is absent: {relative}")
            run_command(
                ["docker", "run", "--rm", "--name", helper, "--network", "none", *mounts, "--entrypoint", "/usr/bin/mkdir", image, "-p", destination_dir],
                timeout=60,
            )
            run_command(
                ["docker", "run", "--rm", "--name", helper, "--network", "none", *mounts, "--entrypoint", "/usr/bin/cp", image, "-p", source_path, destination_path],
                timeout=1800,
            )


def _source_state() -> tuple[str, bool]:
    revision = run_command(["git", "rev-parse", "HEAD"], timeout=20).stdout.strip()
    dirty = bool(run_command(["git", "status", "--porcelain"], timeout=20).stdout.strip())
    return revision, dirty


def _wait_for_readiness(base_url: str, timeout_seconds: float) -> tuple[bool, float, dict[str, Any] | None]:
    started = time.perf_counter()
    last_payload: dict[str, Any] | None = None
    while time.perf_counter() - started < timeout_seconds:
        try:
            response = request_json(base_url, "GET", "/v1/models", timeout=2)
            if response.status == 200:
                last_payload = response.json()
                return True, (time.perf_counter() - started) * 1000, last_payload
        except (ClientTimeout, TransportError, json.JSONDecodeError, OSError):
            pass
        time.sleep(0.5)
    return False, (time.perf_counter() - started) * 1000, last_payload


def _skipped_live_matrix(code: str, detail: str, model_a: str, model_b: str | None) -> list[dict[str, Any]]:
    specifications = [
        ("models-discovery", "models_discovery"),
        ("configured-identity-route-a", "models_discovery"),
        ("first-load-a-router-id", "first_model_load"),
        ("warm-a", "warm_request"),
        ("stream-a", "streaming"),
        ("stream-cancel-a", "cancellation"),
        ("concurrency-2-a", "concurrency"),
        ("structured-aurora-facts-v1", "structured_output"),
        ("structured-cedar-plan-v1", "structured_output"),
        ("tools-a", "tools"),
        ("swap-a-to-b", "model_swap"),
        ("swap-b-to-a", "model_swap"),
        ("models-max", "models_max"),
        ("idle-unload", "idle_unload"),
        ("long-context-8k", "long_context"),
        ("long-context-32k", "long_context"),
        ("long-context-128k", "long_context"),
    ]
    cells = [skip_cell(cell_id, kind, code, detail) for cell_id, kind in specifications]
    def skipped_model(requested_id: str) -> dict[str, Any]:
        record = model_record(requested_id)
        return {
            "requested_id": requested_id,
            "canonical_id": record["canonical_id"] if record else None,
            "discovery_id": record["discovery_id"] if record else None,
            "alias": requested_id if record and requested_id in record["aliases"] else None,
            "quantization": record["quantization"] if record else None,
        }

    for cell in cells:
        if cell["id"].endswith("-a") or cell["id"].startswith(("first", "warm", "stream", "structured", "tools", "idle", "long")):
            cell["model"] = skipped_model(model_a)
        elif "to-b" in cell["id"] and model_b:
            cell["model"] = skipped_model(model_b)
    return cells


@dataclass
class LocalOptions:
    lane: str
    cache_source_volume: str
    model_keys: list[str]
    preset: str
    models_max: int
    contexts: tuple[int, ...]
    concurrency: int
    timeout_seconds: float
    readiness_timeout_seconds: float
    include_tools: bool
    idle_wait_seconds: int
    build: bool
    command: list[str]


def run_local(options: LocalOptions) -> dict[str, Any]:
    if options.lane not in LANES:
        raise ValueError(f"unknown lane: {options.lane}")
    if not options.model_keys or any(key not in CACHE_MODELS for key in options.model_keys):
        raise ValueError(f"models must be selected from {sorted(CACHE_MODELS)}")
    if options.preset not in {path.name for path in (REPO_ROOT / "docker" / "prefer" / "presets").glob("*.ini")}:
        raise ValueError(f"unknown preset: {options.preset}")
    lane = LANES[options.lane]
    suffix = uuid.uuid4().hex[:10]
    project = f"prefer-bench-{suffix}"
    volume = f"prefer-bench-{suffix}-models"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    compose_environment = _compose_environment(project, volume, port, lane, options.preset, options.models_max)
    source_revision, source_dirty = _source_state()
    contract = load_contract()
    corpus = load_corpus()
    hardware = gpu_inventory()
    started_at = utc_now()
    started = time.perf_counter()
    model_a = CACHE_MODELS[options.model_keys[0]]["request_id"]
    model_b = CACHE_MODELS[options.model_keys[1]]["request_id"] if len(options.model_keys) > 1 else None
    result: dict[str, Any] = {
        "schema_version": "prefer.benchmark-result.v1",
        "run": {
            "run_id": f"{options.lane}-{suffix}",
            "started_at": started_at,
            "duration_ms": 0,
            "source_revision": source_revision,
            "source_dirty": source_dirty,
            "backend": {
                "name": "llama.cpp",
                "base_image": lane["base_image"],
                "base_image_tag": lane["base_image_tag"],
                "manifest_digest": lane["manifest_digest"],
                "manifest_status": "not_checked",
                "image_id": None,
                "revision": lane["revision"],
                "source_commit": lane["source_commit"],
                "release_url": lane["release_url"],
                "comparison_lane": lane["comparison_lane"],
            },
            "contract_version": contract["contract_version"],
            "eval_version": corpus["eval_version"],
            "hardware": hardware,
            "preset": options.preset,
            "models_max": options.models_max,
            "command": options.command,
            "cleanup": {},
        },
        "cells": [],
        "summary": {
            "cell_counts": {},
            "schema_contract_attempts": 0,
            "schema_contract_pass_rate": None,
            "semantic_evaluations": 0,
            "semantic_anomaly_rate": None,
        },
    }
    before_prefer = _container_snapshot("prefer")
    before_neuron = _container_snapshot("neuron")
    source_cache_used = False
    phase = "initialization"
    print(f"[prefer-bench] isolated project={project} port={port} lane={options.lane}", flush=True)
    try:
        if options.build:
            phase = "image_manifest_preflight"
            print(f"[prefer-bench] verifying immutable manifest {lane['base_image_tag']}@{lane['manifest_digest']}", flush=True)
            _preflight_manifest(lane)
            result["run"]["backend"]["manifest_status"] = "verified"
            phase = "image_build"
            print(f"[prefer-bench] building {lane['image']} from {lane['base_image']}", flush=True)
            try:
                run_command(_compose_args(project, "build", "router"), environment=compose_environment, timeout=3600)
            except CommandError as exc:
                diagnostic = _scrub_command_output(exc.output, project, volume, port)
                raise EnvironmentSkip(
                    "image_build_failed",
                    f"Could not build the selected {options.lane} lane: {diagnostic}",
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise EnvironmentSkip(
                    "image_build_timeout",
                    f"Building the selected {options.lane} lane exceeded the 3600-second harness deadline.",
                ) from exc
        else:
            phase = "image_check"
            result["run"]["backend"]["manifest_status"] = "pinned_not_checked_cached_image"
            available = run_command(["docker", "image", "inspect", lane["image"]], check=False, timeout=30)
            if available.returncode != 0:
                raise EnvironmentSkip("benchmark_image_missing", f"{lane['image']} is not cached; rerun without --no-build.")
        phase = "image_version"
        version = _image_revision(lane["image"], project)
        result["run"]["backend"]["revision"] = version
        result["run"]["backend"]["image_id"] = _image_id(lane["image"])
        print(f"[prefer-bench] cloning selected cached files from read-only volume {options.cache_source_volume}", flush=True)
        phase = "cache_clone"
        _ensure_source_volume(options.cache_source_volume)
        source_cache_used = True
        _copy_cached_models(options.cache_source_volume, volume, lane["image"], project, options.model_keys)
        print("[prefer-bench] starting isolated router", flush=True)
        phase = "compose_up"
        cold_started = time.perf_counter()
        run_command(_compose_args(project, "up", "-d", "--no-build", "router"), environment=compose_environment, timeout=180)
        compose_up_ms = (time.perf_counter() - cold_started) * 1000
        phase = "readiness"
        ready, readiness_ms, payload = _wait_for_readiness(base_url, options.readiness_timeout_seconds)
        cold = empty_cell("cold-readiness", "cold_readiness")
        cold["measurements"] = {
            "total_ms": round((time.perf_counter() - cold_started) * 1000, 3),
            "compose_up_ms": round(compose_up_ms, 3),
            "readiness_poll_ms": round(readiness_ms, 3),
        }
        cold["evidence"] = {
            "definition": "compose service start through first successful GET /v1/models",
            "endpoint": "/v1/models",
            "operator_port_8080_used": False,
        }
        cold["contract"] = {"pass": ready, "checks": [{"name": "models_ready", "pass": ready}]}
        cold["status"] = "passed" if ready else "failed"
        if not ready:
            cold["error"] = {"category": "environment_unavailable", "code": "readiness_timeout", "detail": f"Router did not return /v1/models within {options.readiness_timeout_seconds}s."}
        result["cells"].append(cold)
        if ready:
            print("[prefer-bench] router ready; running contract, swap, quality, concurrency, and selected context cells", flush=True)
            phase = "live_matrix"
            result["cells"].extend(
                run_live_suite(
                    LiveConfig(
                        base_url=base_url,
                        preset=options.preset,
                        models_max=options.models_max,
                        model_a=model_a,
                        model_b=model_b,
                        timeout_seconds=options.timeout_seconds,
                        concurrency=options.concurrency,
                        contexts_to_run=options.contexts,
                        include_tools=options.include_tools,
                        idle_wait_seconds=options.idle_wait_seconds,
                    )
                )
            )
        else:
            result["cells"].extend(_skipped_live_matrix("readiness_unavailable", "No live cells ran because the isolated router never became ready.", model_a, model_b))
    except EnvironmentSkip as exc:
        print(f"[prefer-bench] skipped live matrix: {exc.code}", flush=True)
        result["cells"].append(skip_cell("environment", "environment", exc.code, exc.detail))
        result["cells"].extend(_skipped_live_matrix(exc.code, exc.detail, model_a, model_b))
    except (CommandError, subprocess.TimeoutExpired) as exc:
        return_code = exc.returncode if isinstance(exc, CommandError) else None
        diagnostic = _scrub_command_output(exc.output, project, volume, port) if isinstance(exc, CommandError) else type(exc).__name__
        print(f"[prefer-bench] orchestration failure phase={phase} return_code={return_code}: {diagnostic}", flush=True)
        orchestration_skip = EnvironmentSkip(
            f"{phase}_failed",
            f"Isolated Docker phase {phase!r} failed"
            + (f" with exit code {return_code}: {diagnostic}" if return_code is not None else "."),
        )
        result["cells"].append(skip_cell("environment", "environment", orchestration_skip.code, orchestration_skip.detail))
        result["cells"].extend(_skipped_live_matrix(orchestration_skip.code, orchestration_skip.detail, model_a, model_b))
    finally:
        cleanup: dict[str, Any] = {}
        print("[prefer-bench] cleaning isolated containers, network, and volume", flush=True)
        failed_cells = [cell for cell in result["cells"] if cell["status"] in {"failed", "error"}]
        if failed_cells:
            logs = run_command(
                _compose_args(project, "logs", "--no-color", "--tail", "250", "router"),
                environment=compose_environment,
                check=False,
                timeout=60,
            )
            excerpt = _scrub_runtime_logs(logs.stdout + logs.stderr, project, volume, port)
            if excerpt:
                for cell in failed_cells:
                    cell.setdefault("evidence", {})["runtime_log_excerpt"] = excerpt
                    error = cell.get("error", {})
                    error_detail = str(error.get("detail", ""))
                    use_log_excerpt = len(failed_cells) == 1 or cell["kind"] in {
                        "cold_readiness",
                        "first_model_load",
                        "model_swap",
                        "long_context",
                    }
                    diagnostic = classify_runtime_failure(
                        excerpt if use_log_excerpt else "",
                        error_detail=error_detail,
                        preset=options.preset,
                        backend_revision=str(result["run"]["backend"]["revision"]),
                    )
                    if diagnostic:
                        cell["diagnostic"] = diagnostic
                        if diagnostic["category"] == "unsupported_combination":
                            original_error = cell.pop("error", None)
                            if original_error:
                                cell.setdefault("evidence", {})["original_error"] = original_error
                            cell["status"] = "unsupported"
                            cell["skip"] = {
                                "category": diagnostic["category"],
                                "code": diagnostic["code"],
                                "detail": diagnostic["detail"],
                            }
                        elif "error" in cell:
                            cell["error"]["category"] = diagnostic["category"]
        down = run_command(
            _compose_args(project, "down", "--volumes", "--remove-orphans"),
            environment=compose_environment,
            check=False,
            timeout=180,
        )
        run_command(["docker", "rm", "-f", f"{project}-cache-copy"], check=False, timeout=30)
        run_command(["docker", "volume", "rm", volume], check=False, timeout=60)
        containers = run_command(
            ["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Names}}"],
            check=False,
            timeout=30,
        )
        networks = run_command(
            ["docker", "network", "ls", "--filter", f"label=com.docker.compose.project={project}", "--format", "{{.Name}}"],
            check=False,
            timeout=30,
        )
        volume_check = run_command(
            ["docker", "volume", "ls", "--filter", f"name=^{volume}$", "--format", "{{.Name}}"],
            check=False,
            timeout=30,
        )
        cleanup["temporary_containers_absent"] = containers.returncode == 0 and not containers.stdout.strip()
        cleanup["temporary_networks_absent"] = networks.returncode == 0 and not networks.stdout.strip()
        cleanup["temporary_volume_absent"] = volume_check.returncode == 0 and not volume_check.stdout.strip()
        cleanup["compose_down"] = down.returncode == 0 or (
            cleanup["temporary_containers_absent"]
            and cleanup["temporary_networks_absent"]
            and cleanup["temporary_volume_absent"]
        )
        after_prefer = _container_snapshot("prefer")
        after_neuron = _container_snapshot("neuron")
        cleanup["operator_prefer_unchanged"] = (
            before_prefer["inspection_ok"]
            and after_prefer["inspection_ok"]
            and before_prefer["raw"] == after_prefer["raw"]
        )
        cleanup["operator_prefer_status_before"] = before_prefer["status"]
        cleanup["operator_prefer_status_after"] = after_prefer["status"]
        cleanup["neuron_unchanged"] = (
            before_neuron["inspection_ok"]
            and after_neuron["inspection_ok"]
            and before_neuron["raw"] == after_neuron["raw"]
        )
        cleanup["neuron_status_before"] = before_neuron["status"]
        cleanup["neuron_status_after"] = after_neuron["status"]
        cleanup["source_cache_mount"] = "read_only" if source_cache_used else "not_mounted"
        cleanup["operator_port_8080_used"] = False
        result["run"]["cleanup"] = cleanup
        required_cleanup = (
            "temporary_containers_absent",
            "temporary_networks_absent",
            "temporary_volume_absent",
            "compose_down",
            "operator_prefer_unchanged",
            "neuron_unchanged",
        )
        cleanup_failures = [name for name in required_cleanup if cleanup.get(name) is not True]
        if cleanup.get("operator_port_8080_used") is not False:
            cleanup_failures.append("operator_port_8080_used")
        if cleanup_failures:
            result["cells"].append(
                error_cell(
                    "isolation-cleanup",
                    "environment",
                    "cleanup_invariant_failed",
                    f"Isolation invariants failed: {', '.join(cleanup_failures)}",
                )
            )
        finish_result(result, started, time.perf_counter())
    return result


def default_output_path(lane: str, models_max: int) -> Path:
    timestamp = utc_now().replace(":", "").replace("-", "").replace(".", "")
    return REPO_ROOT / "benchmark" / "artifacts" / f"{timestamp}-{lane}-models-max-{models_max}.json"


def write_local_outputs(result: dict[str, Any], json_path: Path) -> tuple[Path, Path]:
    json_path = json_path.resolve()
    markdown_path = json_path.with_suffix(".md")
    write_json(result, json_path)
    write_report(result, markdown_path)
    return json_path, markdown_path
