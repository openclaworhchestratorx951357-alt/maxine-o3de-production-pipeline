#!/usr/bin/env python3
"""Validate release_candidate_package_receipt_noop_v1 receipt reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
APPROVAL_PHRASE = "APPROVE EXECUTION ADMISSION release_candidate_package_receipt_noop_v1"
ALLOWED_OUTPUT_PREFIX = (
    "examples/sandbox/execution-receipts/release-candidate-package-receipt-noop/"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate no-op release-candidate package receipt admission report."
    )
    parser.add_argument("report_path", help="Path to no-op receipt report JSON.")
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero when status is warn.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_schema(report: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        return False, [f"jsonschema import failed: {exc}"]

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda err: list(err.path))
    if not errors:
        return True, []

    messages: List[str] = []
    for err in errors:
        location = ".".join(str(p) for p in err.absolute_path) or "<root>"
        messages.append(f"{location}: {err.message}")
    return False, messages


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    payload: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "message": message,
    }
    if details:
        payload["details"] = details
    findings.append(payload)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = (repo_root / args.report_path).resolve() if not Path(args.report_path).is_absolute() else Path(args.report_path).resolve()
    schema_path = repo_root / "schemas" / "maxine_release_candidate_package_receipt_noop_report.schema.json"

    if not report_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"report not found: {report_path}",
                },
                indent=2,
            )
        )
        return 2
    if not schema_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": f"schema not found: {schema_path}",
                },
                indent=2,
            )
        )
        return 2

    report = load_json(report_path)
    schema = load_json(schema_path)
    findings: List[Dict[str, Any]] = []

    ok, schema_errors = validate_schema(report, schema)
    if not ok:
        for message in schema_errors:
            add_finding(
                findings,
                "schema_validation_error",
                "error",
                "Report failed schema validation.",
                {"error": message},
            )

    if str(report.get("candidate_id", "")).strip() != CANDIDATE_ID:
        add_finding(
            findings,
            "candidate_id_invalid",
            "error",
            "candidate_id must match release_candidate_package_receipt_noop_v1.",
            {"actual": report.get("candidate_id")},
        )

    if str(report.get("approval_phrase", "")).strip() != APPROVAL_PHRASE:
        add_finding(
            findings,
            "approval_phrase_invalid",
            "error",
            "approval_phrase must exactly match approved candidate phrase.",
            {"actual": report.get("approval_phrase")},
        )

    if bool(report.get("external_execution_performed")):
        add_finding(
            findings,
            "external_execution_not_allowed",
            "error",
            "external_execution_performed must remain false.",
        )
    if bool(report.get("publication_performed")):
        add_finding(
            findings,
            "publication_not_allowed",
            "error",
            "publication_performed must remain false.",
        )

    for field in (
        "o3de_execution_status",
        "editor_execution_status",
        "runtime_execution_status",
        "asset_processor_execution_status",
        "blender_dcc_execution_status",
        "cache_live_db_access_status",
        "spawn_publish_status",
        "production_write_status",
    ):
        if str(report.get(field, "")).strip() != "blocked":
            add_finding(
                findings,
                "blocked_surface_widened",
                "error",
                f"{field} must remain blocked.",
                {"field": field, "actual": report.get(field)},
            )

    for field in (
        "source_uuid_claim_status",
        "asset_id_claim_status",
        "product_id_claim_status",
    ):
        if str(report.get(field, "")).strip() != "not_authoritative":
            add_finding(
                findings,
                "authoritative_claim_not_allowed",
                "error",
                f"{field} must remain not_authoritative.",
                {"field": field, "actual": report.get(field)},
            )

    output_refs = report.get("output_refs", [])
    if not isinstance(output_refs, list) or not output_refs:
        add_finding(
            findings,
            "output_refs_missing",
            "error",
            "output_refs must be a non-empty array.",
        )
    else:
        for output_ref in output_refs:
            normalized = str(output_ref).replace("\\", "/").strip()
            if not normalized.startswith(ALLOWED_OUTPUT_PREFIX):
                add_finding(
                    findings,
                    "output_ref_outside_allowed_root",
                    "error",
                    "output_refs must remain under approved sandbox receipt path.",
                    {"output_ref": output_ref, "allowed_prefix": ALLOWED_OUTPUT_PREFIX},
                )

    severity_set = {str(item.get("severity", "")).strip() for item in findings}
    if "error" in severity_set:
        status = "fail"
    elif "warning" in severity_set:
        status = "warn"
    else:
        status = "pass"

    payload = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_VALIDATION_v1_REPORT",
        "status": status,
        "candidate_id": CANDIDATE_ID,
        "validated_report_path": str(report_path),
        "findings": findings,
    }
    print(json.dumps(payload, indent=2))

    if status == "pass":
        return 0
    if status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
