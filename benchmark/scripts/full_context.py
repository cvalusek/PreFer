from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable
import uuid

from prefer_bench.http_client import HTTPResult, request_json


FILLER_UNIT = " neutral synthetic filler."


@dataclass(frozen=True)
class FullContextOptions:
    base_url: str
    model: str | None = None
    context_size: int | None = None
    reserve_tokens: int = 8192
    max_tokens: int = 128
    timeout_seconds: float = 1800.0
    sizing_timeout_seconds: float = 300.0
    token_tolerance: int = 64
    max_request_bytes: int = 16 * 1024 * 1024
    dry_run: bool = False


def normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    if not normalized:
        raise ValueError("base URL must not be empty")
    return normalized


def _response_json(response: HTTPResult, path: str) -> Any:
    try:
        payload = response.json()
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        excerpt = response.body[:512].decode("utf-8", errors="replace")
        raise RuntimeError(f"{path} returned non-JSON HTTP {response.status}: {excerpt!r}") from exc
    if response.status >= 400:
        raise RuntimeError(f"{path} returned HTTP {response.status}: {payload!r}")
    return payload


def _matching_model(models: list[dict[str, Any]], requested: str | None) -> tuple[str, dict[str, Any]]:
    if requested:
        for record in models:
            aliases = record.get("aliases", [])
            if record.get("id") == requested or requested in aliases:
                return requested, record
        raise RuntimeError(f"model {requested!r} is not advertised by /v1/models")

    loaded = [record for record in models if record.get("status", {}).get("value") == "loaded"]
    candidates = loaded or [record for record in models if record.get("id") != "default"]
    if len(candidates) != 1:
        ids = [record.get("id") for record in candidates]
        raise RuntimeError(f"unable to choose one model automatically from {ids!r}; pass --model")
    model_id = candidates[0].get("id")
    if not isinstance(model_id, str) or not model_id:
        raise RuntimeError("selected /v1/models record has no usable id")
    return model_id, candidates[0]


def _context_size_from_record(record: dict[str, Any]) -> int | None:
    args = record.get("status", {}).get("args", [])
    if not isinstance(args, list):
        return None
    for index, value in enumerate(args[:-1]):
        if value == "--ctx-size":
            try:
                return int(args[index + 1])
            except (TypeError, ValueError):
                return None
    return None


def _codes() -> list[str]:
    run_id = uuid.uuid4().hex.upper()
    return [f"START-{run_id[:8]}", f"MIDDLE-{run_id[8:16]}", f"END-{run_id[16:24]}"]


def build_prompt(repetitions: int, codes: list[str]) -> str:
    if repetitions < 0:
        raise ValueError("repetitions must not be negative")
    if len(codes) != 3:
        raise ValueError("exactly three retrieval codes are required")
    first_half = repetitions // 2
    second_half = repetitions - first_half
    return (
        "This is a deterministic long-context retrieval test. Remember the three "
        "needle codes and ignore all neutral filler. Do not answer until the final instruction.\n"
        f"START NEEDLE: {codes[0]}\n"
        + FILLER_UNIT * first_half
        + f"\nMIDDLE NEEDLE: {codes[1]}\n"
        + FILLER_UNIT * second_half
        + f"\nEND NEEDLE: {codes[2]}\n"
        + "Return the start, middle, and end codes in that exact order."
    )


def size_prompt(
    token_counter: Callable[[str], int],
    target_tokens: int,
    tolerance: int,
    codes: list[str],
    progress: Callable[[str], None] | None = None,
) -> tuple[str, int, int]:
    if target_tokens < 1:
        raise ValueError("target token count must be positive")
    if tolerance < 0:
        raise ValueError("token tolerance must not be negative")

    measured: dict[int, tuple[str, int]] = {}

    def measure(repetitions: int) -> tuple[str, int]:
        repetitions = max(0, repetitions)
        if repetitions not in measured:
            prompt = build_prompt(repetitions, codes)
            count = token_counter(prompt)
            measured[repetitions] = (prompt, count)
            if progress:
                progress(f"sizing: repetitions={repetitions} chat_tokens={count}")
        return measured[repetitions]

    _, base_count = measure(0)
    _, sample_count = measure(1024)
    slope = (sample_count - base_count) / 1024
    if slope <= 0:
        raise RuntimeError("token count did not grow with filler repetitions")

    repetitions = max(0, round((target_tokens - base_count) / slope))
    for _ in range(8):
        prompt, count = measure(repetitions)
        if abs(count - target_tokens) <= tolerance:
            return prompt, repetitions, count
        local_slope = (count - base_count) / repetitions if repetitions else slope
        if local_slope <= 0:
            local_slope = slope
        step = round((target_tokens - count) / local_slope)
        if step == 0:
            step = 1 if count < target_tokens else -1
        next_repetitions = max(0, repetitions + step)
        if next_repetitions == repetitions or next_repetitions in measured:
            break
        repetitions = next_repetitions

    best_repetitions, (best_prompt, best_count) = min(
        measured.items(),
        key=lambda item: (abs(item[1][1] - target_tokens), item[1][1] > target_tokens),
    )
    if abs(best_count - target_tokens) > tolerance:
        raise RuntimeError(
            f"could not size prompt within {tolerance} tokens of {target_tokens}; "
            f"closest was {best_count} at {best_repetitions} repetitions"
        )
    return best_prompt, best_repetitions, best_count


def _expected_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["codes"],
        "properties": {
            "codes": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "string"},
            }
        },
        "additionalProperties": False,
    }


def _content_document(content: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(content, str):
        return None, "assistant content is not a string"
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        return None, f"assistant content is not JSON: {exc}"
    if not isinstance(document, dict):
        return None, "assistant JSON is not an object"
    return document, None


def run_full_context(
    options: FullContextOptions,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    root_url = normalize_base_url(options.base_url)
    if options.reserve_tokens <= options.max_tokens:
        raise ValueError("--reserve-tokens must be greater than --max-tokens")

    models_response = request_json(root_url, "GET", "/v1/models", timeout=30.0)
    models_payload = _response_json(models_response, "/v1/models")
    models = models_payload.get("data", []) if isinstance(models_payload, dict) else []
    if not isinstance(models, list):
        raise RuntimeError("/v1/models data is not an array")
    model, model_record = _matching_model(models, options.model)
    context_size = options.context_size or _context_size_from_record(model_record)
    if context_size is None:
        raise RuntimeError("could not discover --ctx-size; pass --context-size explicitly")
    target_tokens = context_size - options.reserve_tokens
    if target_tokens <= 0:
        raise ValueError("context size must be greater than the reserved token count")
    if progress:
        progress(f"model={model} context_size={context_size} target_prompt_tokens={target_tokens}")

    codes = _codes()

    def chat_token_count(prompt: str) -> int:
        template_response = request_json(
            root_url,
            "POST",
            "/apply-template",
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout=options.sizing_timeout_seconds,
        )
        template_payload = _response_json(template_response, "/apply-template")
        rendered = template_payload.get("prompt") if isinstance(template_payload, dict) else None
        if not isinstance(rendered, str):
            raise RuntimeError("/apply-template response has no string prompt")
        tokenize_response = request_json(
            root_url,
            "POST",
            "/tokenize",
            {"model": model, "content": rendered, "add_special": False},
            timeout=options.sizing_timeout_seconds,
        )
        tokenize_payload = _response_json(tokenize_response, "/tokenize")
        tokens = tokenize_payload.get("tokens") if isinstance(tokenize_payload, dict) else None
        if not isinstance(tokens, list):
            raise RuntimeError("/tokenize response has no token array")
        return len(tokens)

    prompt, repetitions, measured_tokens = size_prompt(
        chat_token_count,
        target_tokens,
        options.token_tolerance,
        codes,
        progress=progress,
    )
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": options.max_tokens,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "prefer_full_context_probe",
                "strict": True,
                "schema": _expected_schema(),
            },
        },
    }
    request_bytes = len(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    if request_bytes > options.max_request_bytes:
        raise RuntimeError(
            f"generated request is {request_bytes} bytes, above safety cap {options.max_request_bytes}"
        )

    base_result = {
        "schema_version": "prefer.full-context-probe.v1",
        "status": "sized" if options.dry_run else "pending",
        "endpoint": root_url,
        "model": model,
        "context_size": context_size,
        "reserve_tokens": options.reserve_tokens,
        "target_prompt_tokens": target_tokens,
        "measured_chat_tokens": measured_tokens,
        "filler_repetitions": repetitions,
        "request_bytes": request_bytes,
        "expected_codes": codes,
    }
    if options.dry_run:
        return base_result

    if progress:
        progress(
            f"sending full request: measured_chat_tokens={measured_tokens} "
            f"request_bytes={request_bytes} timeout={options.timeout_seconds:.0f}s"
        )
    started = time.perf_counter()
    response = request_json(
        root_url,
        "POST",
        "/v1/chat/completions",
        body,
        timeout=options.timeout_seconds,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    payload = _response_json(response, "/v1/chat/completions")
    choices = payload.get("choices", []) if isinstance(payload, dict) else []
    first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    message = first_choice.get("message", {}) if isinstance(first_choice, dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    document, content_error = _content_document(content)
    observed_codes = document.get("codes") if isinstance(document, dict) else None
    usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    observed_prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None

    checks = [
        {
            "name": "http_success",
            "pass": response.status == 200,
            "observed": response.status,
        },
        {
            "name": "prompt_tokens_match_sizing",
            "pass": isinstance(observed_prompt_tokens, int)
            and abs(observed_prompt_tokens - measured_tokens) <= options.token_tolerance,
            "expected": measured_tokens,
            "observed": observed_prompt_tokens,
            "tolerance": options.token_tolerance,
        },
        {
            "name": "context_not_exceeded",
            "pass": isinstance(observed_prompt_tokens, int)
            and observed_prompt_tokens + options.max_tokens <= context_size,
            "context_size": context_size,
            "prompt_tokens": observed_prompt_tokens,
            "max_tokens": options.max_tokens,
        },
        {
            "name": "retrieved_start_middle_end",
            "pass": observed_codes == codes,
            "expected": codes,
            "observed": observed_codes,
        },
        {
            "name": "clean_stop",
            "pass": finish_reason == "stop",
            "observed": finish_reason,
        },
    ]
    passed = content_error is None and all(check["pass"] for check in checks)
    base_result.update(
        {
            "status": "passed" if passed else "failed",
            "pass": passed,
            "duration_ms": elapsed_ms,
            "checks": checks,
            "response": {
                "finish_reason": finish_reason,
                "content_error": content_error,
                "content": content[:2048] if isinstance(content, str) else content,
                "usage": usage,
                "timings": payload.get("timings") if isinstance(payload, dict) else None,
            },
        }
    )
    return base_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe a PreFer endpoint near its full context limit")
    parser.add_argument("--base-url", required=True, help="PreFer root URL or URL ending in /v1")
    parser.add_argument("--model", help="Model id or alias; auto-selects when exactly one model is loaded")
    parser.add_argument("--context-size", type=int, help="Override auto-discovered --ctx-size")
    parser.add_argument("--reserve-tokens", type=int, default=8192, help="Leave this much context unused")
    parser.add_argument("--max-tokens", type=int, default=128, help="Maximum retrieval response tokens")
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--sizing-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--token-tolerance", type=int, default=64)
    parser.add_argument("--max-request-mib", type=float, default=16.0)
    parser.add_argument("--dry-run", action="store_true", help="Size and tokenize the request without generating")
    parser.add_argument("--output", type=Path, help="Optional JSON result path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.context_size is not None and args.context_size < 1:
        raise SystemExit("--context-size must be positive")
    if args.reserve_tokens < 1:
        raise SystemExit("--reserve-tokens must be positive")
    if args.max_tokens < 1:
        raise SystemExit("--max-tokens must be positive")
    if args.token_tolerance < 0:
        raise SystemExit("--token-tolerance must not be negative")
    if args.max_request_mib <= 0:
        raise SystemExit("--max-request-mib must be positive")

    result = run_full_context(
        FullContextOptions(
            base_url=args.base_url,
            model=args.model,
            context_size=args.context_size,
            reserve_tokens=args.reserve_tokens,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
            sizing_timeout_seconds=args.sizing_timeout_seconds,
            token_tolerance=args.token_tolerance,
            max_request_bytes=int(args.max_request_mib * 1024 * 1024),
            dry_run=args.dry_run,
        ),
        progress=lambda message: print(f"[prefer-bench] {message}", file=sys.stderr),
    )
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result["status"] in {"passed", "sized"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
