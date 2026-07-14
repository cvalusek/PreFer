"""Small, dependency-free validator for the JSON Schema subset used here.

The live API contract is intentionally narrow. Pulling a large validation
stack into a GPU benchmark image would make the harness less portable, so the
repository uses only the keywords below and tests this validator directly.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": _is_number(value),
        "boolean": isinstance(value, bool),
    }.get(expected, False)


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(instance, item) for item in expected_types):
            errors.append({"path": path, "message": f"expected type {expected_types}, got {type(instance).__name__}"})
            return errors

    if "const" in schema and instance != schema["const"]:
        errors.append({"path": path, "message": f"expected constant {schema['const']!r}"})

    if "enum" in schema and instance not in schema["enum"]:
        errors.append({"path": path, "message": f"value is not in enum {schema['enum']!r}"})

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append({"path": path, "message": f"missing required property {key!r}"})

        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(validate(value, properties[key], child_path))
            elif schema.get("additionalProperties") is False:
                errors.append({"path": child_path, "message": "additional property is not allowed"})

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append({"path": path, "message": f"expected at least {schema['minItems']} items"})
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append({"path": path, "message": f"expected at most {schema['maxItems']} items"})
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, value in enumerate(instance):
                errors.extend(validate(value, item_schema, f"{path}[{index}]"))

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append({"path": path, "message": f"expected at least {schema['minLength']} characters"})
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, instance) is None:
            errors.append({"path": path, "message": f"string does not match {pattern!r}"})
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
            except ValueError:
                errors.append({"path": path, "message": "invalid date-time"})

    if _is_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append({"path": path, "message": f"value is below minimum {schema['minimum']}"})
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append({"path": path, "message": f"value is above maximum {schema['maximum']}"})

    return errors


def assert_valid(instance: Any, schema: dict[str, Any], label: str = "document") -> None:
    errors = validate(instance, schema)
    if errors:
        detail = "; ".join(f"{error['path']}: {error['message']}" for error in errors)
        raise ValueError(f"{label} failed schema validation: {detail}")
