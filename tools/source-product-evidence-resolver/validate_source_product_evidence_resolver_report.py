#!/usr/bin/env python3
"""Validate evidence-only source->product resolver reports for release-lane integration."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_STATUS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_CLAIM_STATUS = {"blocked", "not_claimed", "evidence_only", "future_admitted"}
ALLOWED_OBSERVED_STATUS = {"observed", "partial", "missing"}
ALLOWED_EVIDENCE_SOURCE_TYPES = {
    "fixture",
    "imported_ap_evidence",
    "future_asset_system_query",
}
ALLOWED_PRODUCT_TYPES = {
    "actor",
    "motion",
    "procprefab",
    "azmodel",
    "material",
    "texture",
    "pxmesh",
}
ADMITTED_EVIDENCE_SOURCES = {"fixture", "imported_ap_evidence"}
EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "SOURCE_PRODUCT_EVIDENCE_RESOLVER_v1_REPORT"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "source_product_evidence_resolver_v1"
CONTRACT_ID = "SOURCE_PRODUCT_EVIDENCE_RESOLVER_v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON: {path} ({exc})") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate MAXINE source product evidence resolver report JSON."
    )
    parser.add_argument("report_path", help="Path to source product evidence resolver report JSON")
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero exit code for warn status",
    )
    return parser.parse_args()


def add_finding(
    findings: List[Dict[str, Any]],
    finding_id: str,
    severity: str,
    status: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> None:
    item: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "status": status,
        "message": message,
    }
    if details:
        item["details"] = details
    findings.append(item)


def validate_schema_with_jsonschema(report: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
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


def derive_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")) for item in findings}
    if "error" in severities:
        return "fail"
    if "manual_review" in severities:
        return "pending_manual"
    if "warning" in severities:
        return "warn"
    return "pass"


def status_to_qc_severity(status: str) -> str:
    if status == "pass":
        return "info"
    if status == "warn":
        return "warning"
    if status == "pending_manual":
        return "manual_review"
    return "error"


def _contains_unsafe_path_tokens(path_text: str) -> bool:
    blocked = ("..", "|", ";", ">", "<", "&", "`")
    lowered = path_text.lower()
    return any(token in lowered for token in blocked)


def _string_list_or_empty(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    clean: List[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            clean.append(item.strip())
    return clean


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    report_path = resolve_path(repo_root, args.report_path)
    schema_path = repo_root / "schemas" / "maxine_source_product_evidence_resolver_report.schema.json"

    if not report_path.exists():
        print(f"FAIL: report not found: {report_path}")
        return 2
    if not schema_path.exists():
        print(f"FAIL: schema not found: {schema_path}")
        return 2

    try:
        report = load_json(report_path)
        schema = load_json(schema_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    findings: List[Dict[str, Any]] = []

    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, errors = validate_schema_with_jsonschema(report, schema)
        if not ok:
            for err in errors:
                add_finding(
                    findings,
                    "schema_validation_error",
                    "error",
                    "open",
                    "Report failed JSON schema validation.",
                    {"error": err},
                )
    else:
        print("INFO: jsonschema not available; using rule-based validation.")

    schema_version = str(report.get("schema_version", "")).strip()
    if schema_version != EXPECTED_SCHEMA_VERSION:
        add_finding(
            findings,
            "schema_version_mismatch",
            "error",
            "open",
            f"schema_version must be {EXPECTED_SCHEMA_VERSION}.",
            {"actual": schema_version},
        )

    report_type = str(report.get("report_type", "")).strip()
    if report_type != EXPECTED_REPORT_TYPE:
        add_finding(
            findings,
            "report_type_mismatch",
            "error",
            "open",
            f"report_type must be {EXPECTED_REPORT_TYPE}.",
            {"actual": report_type},
        )

    declared_status = str(report.get("status", "")).strip()
    if declared_status not in ALLOWED_STATUS:
        add_finding(
            findings,
            "status_invalid",
            "error",
            "open",
            "status must be one of pass|warn|fail|pending_manual.",
            {"actual": declared_status},
        )

    for required in ("job_id", "package_id", "lane", "source_asset_reference", "source_asset_path"):
        value = str(report.get(required, "")).strip()
        if not value:
            add_finding(
                findings,
                f"{required}_missing",
                "error",
                "open",
                f"{required} is required.",
            )
        elif required.endswith("_path") and _contains_unsafe_path_tokens(value):
            add_finding(
                findings,
                f"{required}_unsafe",
                "error",
                "open",
                f"{required} contains unsafe traversal or shell tokens.",
                {"value": value},
            )

    evidence_source_type = str(report.get("evidence_source_type", "")).strip()
    if evidence_source_type not in ALLOWED_EVIDENCE_SOURCE_TYPES:
        add_finding(
            findings,
            "evidence_source_type_invalid",
            "error",
            "open",
            "evidence_source_type must be fixture|imported_ap_evidence|future_asset_system_query.",
            {"actual": evidence_source_type},
        )
    elif evidence_source_type not in ADMITTED_EVIDENCE_SOURCES:
        add_finding(
            findings,
            "evidence_source_not_admitted",
            "warning",
            "open",
            "Evidence source is future-oriented and not an admitted deterministic source in v1.",
            {"evidence_source_type": evidence_source_type},
        )

    expected_products = report.get("expected_products", [])
    if not isinstance(expected_products, list) or not expected_products:
        add_finding(
            findings,
            "expected_products_invalid",
            "error",
            "open",
            "expected_products must be a non-empty array.",
        )
        expected_products = []

    expected_required: Dict[str, bool] = {}
    for idx, item in enumerate(expected_products):
        if not isinstance(item, dict):
            add_finding(
                findings,
                "expected_product_invalid",
                "error",
                "open",
                f"expected_products[{idx}] must be an object.",
            )
            continue
        ptype = str(item.get("product_type", "")).strip()
        prequired = item.get("required")
        if ptype not in ALLOWED_PRODUCT_TYPES:
            add_finding(
                findings,
                "expected_product_type_invalid",
                "error",
                "open",
                f"expected_products[{idx}].product_type is invalid.",
                {"actual": ptype},
            )
            continue
        if not isinstance(prequired, bool):
            add_finding(
                findings,
                "expected_product_required_invalid",
                "error",
                "open",
                f"expected_products[{idx}].required must be boolean.",
            )
            continue
        expected_required[ptype] = prequired

    observed_products = report.get("observed_products", [])
    if not isinstance(observed_products, list):
        add_finding(
            findings,
            "observed_products_invalid",
            "error",
            "open",
            "observed_products must be an array.",
        )
        observed_products = []

    observed_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for idx, item in enumerate(observed_products):
        if not isinstance(item, dict):
            add_finding(
                findings,
                "observed_product_invalid",
                "error",
                "open",
                f"observed_products[{idx}] must be an object.",
            )
            continue
        ptype = str(item.get("product_type", "")).strip()
        path_or_hint = str(item.get("product_path_or_hint", "")).strip()
        ev_status = str(item.get("evidence_status", "")).strip()
        ev_source = str(item.get("evidence_source", "")).strip()
        confidence = item.get("confidence")

        if ptype not in ALLOWED_PRODUCT_TYPES:
            add_finding(
                findings,
                "observed_product_type_invalid",
                "error",
                "open",
                f"observed_products[{idx}].product_type is invalid.",
                {"actual": ptype},
            )
            continue
        if not path_or_hint:
            add_finding(
                findings,
                "observed_product_path_missing",
                "error",
                "open",
                f"observed_products[{idx}].product_path_or_hint is required.",
            )
        elif _contains_unsafe_path_tokens(path_or_hint):
            add_finding(
                findings,
                "observed_product_path_unsafe",
                "error",
                "open",
                "observed product path/hint contains unsafe traversal or shell tokens.",
                {"product_path_or_hint": path_or_hint},
            )
        if ev_status not in ALLOWED_OBSERVED_STATUS:
            add_finding(
                findings,
                "observed_product_status_invalid",
                "error",
                "open",
                f"observed_products[{idx}].evidence_status must be observed|partial|missing.",
                {"actual": ev_status},
            )
        if not ev_source:
            add_finding(
                findings,
                "observed_product_source_missing",
                "error",
                "open",
                f"observed_products[{idx}].evidence_source is required.",
            )
        if not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
            add_finding(
                findings,
                "observed_product_confidence_invalid",
                "error",
                "open",
                f"observed_products[{idx}].confidence must be within [0.0, 1.0].",
                {"actual": confidence},
            )
        elif confidence < 0.7:
            add_finding(
                findings,
                "observed_product_confidence_low",
                "warning",
                "open",
                "Observed product confidence is below preferred deterministic threshold.",
                {"product_type": ptype, "confidence": confidence},
            )

        observed_by_type.setdefault(ptype, []).append(item)

    for ptype, required in expected_required.items():
        observed_items = observed_by_type.get(ptype, [])
        has_observed = any(
            str(item.get("evidence_status", "")).strip() == "observed" for item in observed_items
        )
        if required and not has_observed:
            add_finding(
                findings,
                "required_expected_product_missing",
                "error",
                "open",
                "Required expected product evidence is missing.",
                {"product_type": ptype},
            )
        elif not required and not has_observed:
            add_finding(
                findings,
                "optional_expected_product_missing",
                "warning",
                "open",
                "Optional expected product evidence was not observed.",
                {"product_type": ptype},
            )

    source_uuid_claim_status = str(report.get("source_uuid_claim_status", "")).strip()
    asset_id_claim_status = str(report.get("asset_id_claim_status", "")).strip()
    product_id_claim_status = str(report.get("product_id_claim_status", "")).strip()

    for field_name, field_value in (
        ("source_uuid_claim_status", source_uuid_claim_status),
        ("asset_id_claim_status", asset_id_claim_status),
        ("product_id_claim_status", product_id_claim_status),
    ):
        if field_value not in ALLOWED_CLAIM_STATUS:
            add_finding(
                findings,
                f"{field_name}_invalid",
                "error",
                "open",
                f"{field_name} must be blocked|not_claimed|evidence_only|future_admitted.",
                {"actual": field_value},
            )
        elif field_value == "future_admitted":
            add_finding(
                findings,
                f"{field_name}_not_admitted",
                "error",
                "open",
                f"{field_name} cannot claim future admission in this evidence-only slice.",
                {"actual": field_value},
            )

    cache_access_status = str(report.get("cache_access_status", "")).strip()
    if cache_access_status != "blocked":
        add_finding(
            findings,
            "cache_access_not_blocked",
            "error",
            "open",
            "cache_access_status must remain blocked.",
            {"actual": cache_access_status},
        )

    live_db_access_status = str(report.get("live_db_access_status", "")).strip()
    if live_db_access_status != "blocked":
        add_finding(
            findings,
            "live_db_access_not_blocked",
            "error",
            "open",
            "live_db_access_status must remain blocked.",
            {"actual": live_db_access_status},
        )

    input_findings = report.get("findings", [])
    if not isinstance(input_findings, list):
        add_finding(findings, "findings_not_array", "error", "open", "findings must be an array.")
        input_findings = []
    else:
        for idx, item in enumerate(input_findings):
            if not isinstance(item, dict):
                add_finding(findings, "finding_invalid", "error", "open", f"findings[{idx}] must be an object.")
                continue
            fid = str(item.get("id", "")).strip()
            sev = str(item.get("severity", "")).strip()
            fstatus = str(item.get("status", "")).strip()
            msg = str(item.get("message", "")).strip()
            if not fid:
                add_finding(findings, "finding_id_missing", "error", "open", f"findings[{idx}].id is required.")
            if sev not in ALLOWED_FINDING_SEVERITY:
                add_finding(
                    findings,
                    "finding_severity_invalid",
                    "error",
                    "open",
                    "findings severity must be info|warning|error|manual_review.",
                    {"actual": sev},
                )
            if not fstatus:
                add_finding(findings, "finding_status_missing", "error", "open", f"findings[{idx}].status is required.")
            if not msg:
                add_finding(findings, "finding_message_missing", "error", "open", f"findings[{idx}].message is required.")

    attachment = report.get("manifest_attachment", {}) if isinstance(report.get("manifest_attachment"), dict) else {}
    target_path = str(attachment.get("target_path", "")).strip()
    future_target_path = str(attachment.get("future_target_path", "")).strip()
    if target_path != TARGET_PATH:
        add_finding(
            findings,
            "manifest_target_path_invalid",
            "error",
            "open",
            f"manifest_attachment.target_path must be {TARGET_PATH}.",
            {"actual": target_path},
        )
    if future_target_path != FUTURE_TARGET_PATH:
        add_finding(
            findings,
            "manifest_future_target_path_invalid",
            "error",
            "open",
            f"manifest_attachment.future_target_path must be {FUTURE_TARGET_PATH}.",
            {"actual": future_target_path},
        )

    explicit_non_admissions = _string_list_or_empty(report.get("explicit_non_admissions"))
    required_non_admissions = {
        "no live cache read",
        "no live db read",
        "no source uuid claim",
        "no asset id claim",
        "no product id claim",
        "no asset processor execution",
        "no o3de execution",
        "no spawn",
        "no publish",
    }
    if not explicit_non_admissions:
        add_finding(
            findings,
            "explicit_non_admissions_missing",
            "error",
            "open",
            "explicit_non_admissions must include safety non-admission statements.",
        )
    else:
        missing_non_admissions = sorted(required_non_admissions - set(explicit_non_admissions))
        if missing_non_admissions:
            add_finding(
                findings,
                "explicit_non_admissions_incomplete",
                "warning",
                "open",
                "explicit_non_admissions is missing expected safety statements.",
                {"missing": missing_non_admissions},
            )

    combined_findings = findings + input_findings
    computed_status = derive_status(combined_findings)
    if declared_status in ALLOWED_STATUS and declared_status != computed_status:
        add_finding(
            findings,
            "status_mismatch",
            "error",
            "open",
            "report.status does not match computed findings severity.",
            {"declared": declared_status, "computed": computed_status},
        )
        combined_findings = findings + input_findings
        computed_status = derive_status(combined_findings)

    qc_severity = status_to_qc_severity(computed_status)
    output_payload: Dict[str, Any] = {
        "status": computed_status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "findings": combined_findings,
        "manifest_attachment": {
            "target_path": TARGET_PATH,
            "future_target_path": FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": computed_status,
                "severity": qc_severity,
                "details": {
                    "report_path": str(report_path),
                    "report_status": declared_status,
                    "evidence_source_type": evidence_source_type,
                    "validated_at_utc": utc_now(),
                },
            },
        },
    }

    print(json.dumps(output_payload, indent=2))

    if computed_status == "pass":
        return 0
    if computed_status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
