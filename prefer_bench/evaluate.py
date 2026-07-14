from __future__ import annotations

from datetime import date
import json
from typing import Any

from .schema import validate


MISSING = object()


def json_pointer(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    current = document
    for raw_part in pointer.lstrip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return MISSING
    return current


def _normalized(value: Any) -> Any:
    return " ".join(value.casefold().split()) if isinstance(value, str) else value


def _valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def classify_semantics(document: Any, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for rule in rules:
        kind = rule["kind"]
        pointer = rule["path"]
        value = json_pointer(document, pointer)
        if kind == "non_empty":
            if value is MISSING or value is None or (hasattr(value, "__len__") and len(value) == 0):
                anomalies.append({"code": "missing_required_content", "path": pointer})
        elif kind == "exact":
            if value is MISSING:
                anomalies.append({"code": "missing_required_content", "path": pointer})
            elif _normalized(value) != _normalized(rule["value"]):
                anomalies.append({"code": "fact_mismatch", "path": pointer, "expected": rule["value"], "actual": value})
        elif kind == "valid_date":
            if value is MISSING:
                anomalies.append({"code": "missing_required_content", "path": pointer})
            elif not _valid_iso_date(value):
                anomalies.append({"code": "impossible_date", "path": pointer, "actual": value})
        elif kind == "array_min_items":
            if not isinstance(value, list) or len(value) < rule["value"]:
                anomalies.append({
                    "code": "missing_required_planning_content",
                    "path": pointer,
                    "expected_min_items": rule["value"],
                    "actual_items": len(value) if isinstance(value, list) else None,
                })
        elif kind == "contains_object":
            if not isinstance(value, list):
                anomalies.append({"code": "missing_required_planning_content", "path": pointer, "expected": rule["match"]})
            else:
                match = rule["match"]
                contains = rule.get("contains", {})
                found = any(
                    isinstance(item, dict)
                    and all(_normalized(item.get(key, MISSING)) == _normalized(expected) for key, expected in match.items())
                    and all(
                        isinstance(item.get(key), str)
                        and all(_normalized(term) in _normalized(item[key]) for term in terms)
                        for key, terms in contains.items()
                    )
                    for item in value
                )
                if not found:
                    anomalies.append({
                        "code": "missing_required_planning_content",
                        "path": pointer,
                        "expected": {"match": match, "contains": contains},
                    })
        elif kind == "all_valid_dates":
            if not isinstance(value, list):
                anomalies.append({"code": "missing_required_planning_content", "path": pointer})
            else:
                for index, item in enumerate(value):
                    actual = item.get(rule["field"], MISSING) if isinstance(item, dict) else MISSING
                    if actual is MISSING:
                        anomalies.append({"code": "missing_required_content", "path": f"{pointer}/{index}/{rule['field']}"})
                    elif not _valid_iso_date(actual):
                        anomalies.append({"code": "impossible_date", "path": f"{pointer}/{index}/{rule['field']}", "actual": actual})
        else:
            raise ValueError(f"unsupported semantic rule: {kind}")
    return anomalies


def evaluate_content(content: Any, output_schema: dict[str, Any], semantic_rules: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(content, str):
        return {
            "json_valid": False,
            "schema_valid": False,
            "schema_errors": [{"path": "$", "message": "assistant content is not a string"}],
            "semantic_anomalies": [{"code": "missing_required_content", "path": "$"}],
            "document": None,
        }
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        return {
            "json_valid": False,
            "schema_valid": False,
            "schema_errors": [{"path": "$", "message": f"invalid JSON: {exc.msg}"}],
            "semantic_anomalies": [{"code": "unparseable_structured_content", "path": "$"}],
            "document": None,
        }
    schema_errors = validate(document, output_schema)
    anomalies = classify_semantics(document, semantic_rules)
    return {
        "json_valid": True,
        "schema_valid": not schema_errors,
        "schema_errors": schema_errors,
        "semantic_anomalies": anomalies,
        "document": document,
    }
