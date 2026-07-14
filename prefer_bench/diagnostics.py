from __future__ import annotations

from typing import Any


STRUCTURED_SKIP_CODES = {
    "not_selected",
    "operator_disabled",
    "second_model_not_selected",
    "wait_not_selected",
    "wait_below_configured_threshold",
    "preset_has_no_idle_sleep",
    "harness_size_cap",
    "model_did_not_emit_tool_call",
}

CONTRACT_FAILURE_CODES = {
    "client_timeout",
    "concurrency_error",
    "http_rejection",
    "idle_probe_error",
    "models_request_error",
    "stream_error",
    "tool_request_rejected",
    "transport_error",
}

ENVIRONMENT_CODES = {
    "benchmark_image_missing",
    "cache_volume_missing",
    "cached_model_file_missing",
    "cleanup_invariant_failed",
    "image_build_failed",
    "image_build_timeout",
    "image_manifest_check_failed",
    "image_manifest_digest_mismatch",
    "invalid_cache_volume",
    "no_benchmark_port",
    "readiness_timeout",
    "readiness_unavailable",
    "unsafe_shared_volume",
}


def reason_category(code: str) -> str:
    if code == "image_manifest_unavailable":
        return "image_manifest_unavailable"
    if code in {"model_load_failed", "model_load_failure"}:
        return "model_load_failure"
    if code in {"gpu_memory_exhausted", "resource_limit"}:
        return "resource_limit"
    if code.startswith("unsupported_") or code == "llama_cpp_e4b_mtp_pascal_fattn_tile":
        return "unsupported_combination"
    if code in STRUCTURED_SKIP_CODES:
        return "structured_skip"
    if code in CONTRACT_FAILURE_CODES:
        return "contract_failure"
    if code in ENVIRONMENT_CODES or code.endswith("_failed"):
        return "environment_unavailable"
    return "runtime_failure"


def manifest_failure_code(output: str) -> str:
    lowered = output.casefold()
    unavailable_markers = (
        "manifest unknown",
        "no such manifest",
        "manifest not found",
        "name unknown",
    )
    return "image_manifest_unavailable" if any(marker in lowered for marker in unavailable_markers) else "image_manifest_check_failed"


def linux_amd64_manifest_digests(payload: Any) -> set[str]:
    records = payload if isinstance(payload, list) else [payload]
    digests: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        descriptor = record.get("Descriptor")
        if not isinstance(descriptor, dict):
            continue
        platform = descriptor.get("platform")
        if not isinstance(platform, dict):
            continue
        digest = descriptor.get("digest")
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64" and isinstance(digest, str):
            digests.add(digest)
    return digests


def classify_runtime_failure(
    log_text: str,
    *,
    error_detail: str = "",
    preset: str = "",
    backend_revision: str = "",
) -> dict[str, Any] | None:
    combined = f"{log_text}\n{error_detail}"
    lowered = combined.casefold()

    if "fattn-tile.cuh:1321" in lowered and ("li512eli512" in lowered or "512" in lowered):
        return {
            "category": "unsupported_combination",
            "code": "llama_cpp_e4b_mtp_pascal_fattn_tile",
            "detail": (
                "The b9843 CUDA tile path lacks the 512-wide GQA-ratio-2 specialization used by the Gemma E4B MTP draft on Pascal."
            ),
            "action": (
                "Use the explicit 12gb-pascal.ini preset on b9843 (E4B MTP disabled), or compare an immutable newer llama.cpp image containing upstream PR #25148."
            ),
            "facts": {
                "preset": preset,
                "backend_revision": backend_revision,
                "attention_shape": "DKQ=512,DV=512",
                "draft_gqa_ratio": 2,
            },
        }

    if "v cache quantization requires flash_attn" in lowered or (
        "quantized v cache" in lowered and "requires flash attention" in lowered
    ):
        return {
            "category": "unsupported_combination",
            "code": "unsupported_quantized_v_cache_without_flash_attention",
            "detail": "A quantized V cache was requested while the selected backend could not enable Flash Attention.",
            "action": "Keep Flash Attention enabled, use an unquantized V cache, or select a source-backed compatibility preset.",
            "facts": {"preset": preset, "backend_revision": backend_revision},
        }

    memory_markers = ("out of memory", "cuda_error_out_of_memory", "cudamalloc failed", "failed to allocate")
    if any(marker in lowered for marker in memory_markers):
        return {
            "category": "resource_limit",
            "code": "gpu_memory_exhausted",
            "detail": "The runtime reported a GPU allocation failure; this is distinct from an unsupported kernel/cache combination.",
            "facts": {"preset": preset, "backend_revision": backend_revision},
        }

    if "failed to load" in lowered or "model_load_failed" in lowered:
        return {
            "category": "model_load_failure",
            "code": "model_load_failure",
            "detail": "The selected model failed to load without matching a more specific supported diagnostic.",
            "facts": {"preset": preset, "backend_revision": backend_revision},
        }

    return None
