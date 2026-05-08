"""JSON loading and schema validation helpers used by local validators."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from tools.validation.results import ValidationResult


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def schema_validate(payload: Dict[str, Any], schema: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:  # pragma: no cover - jsonschema is present in CI/local today.
        for field in schema.get("required", []):
            if field not in payload:
                result.add_error("MXN_INPUT_MISSING", f"Missing required field: {field}")
        return result

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"{location}: {error.message}")
    return result


def validate_json_file(path: Path, schema_path: Path) -> ValidationResult:
    result = ValidationResult()
    if not path.exists():
        result.add_error("MXN_INPUT_MISSING", f"JSON file not found: {path}")
        return result
    if not schema_path.exists():
        result.add_error("MXN_VALIDATION_TOOL_UNAVAILABLE", f"Schema file not found: {schema_path}")
        return result
    try:
        payload = load_json(path)
        schema = load_json(schema_path)
    except Exception as exc:
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Could not parse JSON: {exc}")
        return result
    result.merge(schema_validate(payload, schema))
    return result


def repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def print_result(label: str, result: ValidationResult) -> None:
    prefix = "PASS" if result.status == "pass" else "WARN" if result.status in {"warn", "pending_manual"} else "FAIL"
    print(f"{prefix}: {label} -> {result.status}")
    for code in result.error_codes:
        print(f"  - {code}")
    for code in result.warning_codes:
        print(f"  - {code}")
    for message in result.messages:
        print(f"  - {message}")
