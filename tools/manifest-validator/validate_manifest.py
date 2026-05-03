#!/usr/bin/env python3
"""Validate a MAXINE job manifest against schema or built-in minimal checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


VALID_STATUSES = {"pass", "warn", "fail", "pending_manual", "running", "queued"}
VALID_LANES = {
    "draft_mesh",
    "text_mesh",
    "photo_rig_prep",
    "text_full_rig",
    "external_rig_import",
    "release_character",
}
VALID_QC_OVERALL = {"pass", "warn", "fail"}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def minimal_validate(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if not data.get("schema_version"):
        errors.append("Missing required field: schema_version")

    job = data.get("job")
    if not isinstance(job, dict):
        errors.append("Missing required object: job")
    else:
        job_id = job.get("job_id")
        lane = job.get("lane")
        status = job.get("status")
        if not job_id:
            errors.append("Missing required field: job.job_id")
        if lane not in VALID_LANES:
            errors.append(f"Invalid job.lane: {lane!r}")
        if status not in VALID_STATUSES:
            errors.append(f"Invalid job.status: {status!r}")

    identity = data.get("identity")
    if not isinstance(identity, dict):
        errors.append("Missing required object: identity")
    elif not identity.get("character_id"):
        errors.append("Missing required field: identity.character_id")

    if "inputs" not in data:
        errors.append("Missing required field: inputs")

    qc = data.get("qc")
    if not isinstance(qc, dict):
        errors.append("Missing required object: qc")
    else:
        overall = qc.get("overall")
        if overall not in VALID_QC_OVERALL:
            errors.append(f"Invalid qc.overall: {overall!r}")

    return errors


def validate_with_jsonschema(
    manifest_data: Dict[str, Any], schema_data: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:  # pragma: no cover
        return False, [f"jsonschema import failed: {exc}"]

    validator = Draft202012Validator(schema_data)
    schema_errors = sorted(validator.iter_errors(manifest_data), key=lambda e: list(e.path))
    if not schema_errors:
        return True, []

    messages: List[str] = []
    for err in schema_errors:
        loc = ".".join(str(part) for part in err.absolute_path) or "<root>"
        messages.append(f"{loc}: {err.message}")
    return False, messages


def main() -> int:
    if len(sys.argv) < 2:
        print("FAIL: manifest path argument is required.")
        print("Usage: python tools/manifest-validator/validate_manifest.py <manifest_path>")
        return 2

    manifest_path = Path(sys.argv[1]).resolve()
    if not manifest_path.exists():
        print(f"FAIL: manifest file not found: {manifest_path}")
        return 2

    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "schemas" / "maxine_job_manifest.schema.json"
    if not schema_path.exists():
        print(f"FAIL: schema file not found: {schema_path}")
        return 2

    try:
        manifest_data = load_json(manifest_path)
    except Exception as exc:
        print(f"FAIL: could not parse manifest JSON: {exc}")
        return 1

    try:
        schema_data = load_json(schema_path)
    except Exception as exc:
        print(f"FAIL: could not parse schema JSON: {exc}")
        return 2

    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, errors = validate_with_jsonschema(manifest_data, schema_data)
        if ok:
            print(f"PASS: schema validation succeeded for {manifest_path}")
            return 0
        print(f"FAIL: schema validation failed for {manifest_path}")
        for msg in errors:
            print(f"  - {msg}")
        return 1

    print("INFO: jsonschema not available; running built-in minimal validation.")
    errors = minimal_validate(manifest_data)
    if errors:
        print(f"FAIL: minimal validation failed for {manifest_path}")
        for msg in errors:
            print(f"  - {msg}")
        return 1

    print(f"PASS: minimal validation succeeded for {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
