from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .paths import RESULT_SCHEMA_PATH
from .schema import assert_valid


def empty_cell(cell_id: str, kind: str, status: str = "passed", model: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": cell_id,
        "kind": kind,
        "status": status,
        "model": model,
        "context": None,
        "measurements": {},
        "contract": {"pass": None, "checks": []},
        "quality": {"schema_valid": None, "semantic_evaluated": False, "semantic_anomalies": []},
    }


def skip_cell(cell_id: str, kind: str, code: str, detail: str, model: dict[str, Any] | None = None) -> dict[str, Any]:
    cell = empty_cell(cell_id, kind, "skipped", model)
    cell["skip"] = {"code": code, "detail": detail}
    return cell


def error_cell(cell_id: str, kind: str, code: str, detail: str, model: dict[str, Any] | None = None) -> dict[str, Any]:
    cell = empty_cell(cell_id, kind, "error", model)
    cell["error"] = {"code": code, "detail": detail}
    cell["contract"]["pass"] = False
    return cell


def summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(cell["status"] for cell in cells)
    schema_cells = [cell for cell in cells if cell["quality"]["schema_valid"] is not None]
    semantic_cells = [cell for cell in cells if cell["quality"]["semantic_evaluated"]]
    schema_rate = (
        sum(1 for cell in schema_cells if cell["quality"]["schema_valid"]) / len(schema_cells)
        if schema_cells
        else None
    )
    anomaly_rate = (
        sum(1 for cell in semantic_cells if cell["quality"]["semantic_anomalies"]) / len(semantic_cells)
        if semantic_cells
        else None
    )
    return {
        "cell_counts": dict(sorted(counts.items())),
        "schema_contract_attempts": len(schema_cells),
        "schema_contract_pass_rate": schema_rate,
        "semantic_evaluations": len(semantic_cells),
        "semantic_anomaly_rate": anomaly_rate,
    }


def finish_result(result: dict[str, Any], started_monotonic: float, now_monotonic: float) -> dict[str, Any]:
    result["run"]["duration_ms"] = round((now_monotonic - started_monotonic) * 1000, 3)
    result["summary"] = summarize(result["cells"])
    return result


def validate_result(result: dict[str, Any]) -> None:
    with RESULT_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    assert_valid(result, schema, "benchmark result")


def write_json(result: dict[str, Any], path: Path) -> None:
    validate_result(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
