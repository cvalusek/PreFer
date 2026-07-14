from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys

from .contract import inspect_models_max, load_contract, load_corpus, preset_contract_diff
from .local import CACHE_MODELS, LANES, LocalOptions, default_output_path, run_local, write_local_outputs
from .mock_server import contract_mock_server
from .paths import BASELINES_ROOT, REPO_ROOT
from .replay import replay_contract
from .report import write_report
from .results import validate_result


CONTEXT_MAP = {"8k": 8192, "32k": 32768, "128k": 131072}


def _contexts(value: str) -> tuple[int, ...]:
    if value == "all":
        return tuple(CONTEXT_MAP.values())
    if value in {"none", ""}:
        return ()
    labels = [item.strip().lower() for item in value.split(",") if item.strip()]
    unknown = sorted(set(labels) - set(CONTEXT_MAP))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown context labels: {unknown}")
    return tuple(CONTEXT_MAP[label] for label in labels)


def _models(value: str) -> list[str]:
    models = [item.strip().lower() for item in value.split(",") if item.strip()]
    unknown = sorted(set(models) - set(CACHE_MODELS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown model cache keys: {unknown}")
    if not models:
        raise argparse.ArgumentTypeError("at least one model is required")
    return models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m prefer_bench", description="PreFer contract and benchmark harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    contract = subparsers.add_parser("contract", help="Replay the narrow client contract")
    target = contract.add_mutually_exclusive_group(required=True)
    target.add_argument("--mock", action="store_true", help="Use the in-process deterministic fake")
    target.add_argument("--base-url", help="Replay against an already-running isolated endpoint")
    contract.add_argument("--output", type=Path, help="Optional JSON output path")

    validate = subparsers.add_parser("validate", help="Validate schemas, fixtures, corpus, and preset aliases")
    validate.add_argument("--result", type=Path, action="append", default=[], help="Also validate a benchmark result")

    subparsers.add_parser("models-max", help="Print the checked-in models-max precedence facts")

    report = subparsers.add_parser("report", help="Generate Markdown from a benchmark JSON result")
    report.add_argument("result", type=Path)
    report.add_argument("--output", type=Path, required=True)

    local = subparsers.add_parser("local", help="Run an isolated local llama.cpp benchmark")
    local.add_argument("--lane", choices=sorted(LANES), default="current")
    local.add_argument("--cache-source-volume", required=True, help="Existing cache volume mounted read-only only during cloning")
    local.add_argument("--models", type=_models, default=_models("gemma-4-e2b,gemma-4-e4b"))
    local.add_argument("--preset", default="12gb.ini")
    local.add_argument("--models-max", type=int, default=1)
    local.add_argument("--contexts", type=_contexts, default=_contexts("8k"), help="none, 8k, 32k, 128k, comma list, or all")
    local.add_argument("--concurrency", type=int, default=2)
    local.add_argument("--timeout-seconds", type=float, default=180.0)
    local.add_argument("--readiness-timeout-seconds", type=float, default=90.0)
    local.add_argument("--idle-wait-seconds", type=int, default=0)
    local.add_argument("--skip-tools", action="store_true")
    local.add_argument("--no-build", action="store_true")
    local.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    if args.command == "contract":
        manager = contract_mock_server() if args.mock else nullcontext(args.base_url)
        with manager as base_url:
            replay = replay_contract(base_url)
        output = json.dumps(replay, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0 if replay["summary"]["failed"] == 0 else 1
    if args.command == "validate":
        load_contract()
        load_corpus()
        differences = preset_contract_diff()
        if differences:
            print(json.dumps({"preset_contract_differences": differences}, indent=2))
            return 1
        result_paths = args.result or sorted(BASELINES_ROOT.glob("*.json"))
        for result_path in result_paths:
            validate_result(json.loads(result_path.read_text(encoding="utf-8")))
        print(f"contract, corpus, preset aliases, and {len(result_paths)} benchmark results are valid")
        return 0
    if args.command == "models-max":
        print(json.dumps(inspect_models_max(REPO_ROOT), indent=2))
        return 0
    if args.command == "report":
        result = json.loads(args.result.read_text(encoding="utf-8"))
        validate_result(result)
        write_report(result, args.output)
        print(args.output.resolve())
        return 0
    if args.command == "local":
        if args.models_max < 0:
            raise SystemExit("--models-max must be zero or greater")
        if args.concurrency < 1:
            raise SystemExit("--concurrency must be at least one")
        command = ["python", "-m", "prefer_bench", *argv]
        result = run_local(
            LocalOptions(
                lane=args.lane,
                cache_source_volume=args.cache_source_volume,
                model_keys=args.models,
                preset=args.preset,
                models_max=args.models_max,
                contexts=args.contexts,
                concurrency=args.concurrency,
                timeout_seconds=args.timeout_seconds,
                readiness_timeout_seconds=args.readiness_timeout_seconds,
                include_tools=not args.skip_tools,
                idle_wait_seconds=args.idle_wait_seconds,
                build=not args.no_build,
                command=command,
            )
        )
        output_path = args.output or default_output_path(args.lane, args.models_max)
        json_path, markdown_path = write_local_outputs(result, output_path)
        print(f"[prefer-bench] JSON: {json_path}")
        print(f"[prefer-bench] report: {markdown_path}")
        return 1 if any(cell["status"] in {"failed", "error"} for cell in result["cells"]) else 0
    return 2
