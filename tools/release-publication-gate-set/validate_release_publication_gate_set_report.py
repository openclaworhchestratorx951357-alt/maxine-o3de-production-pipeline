#!/usr/bin/env python3
"""Validate release-publication gate-set evidence from manifest or report JSON."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "RELEASE_PUBLICATION_GATE_SET_v1_REPORT"
CHECK_ID = "release_publication_gate_set_v1"
CONTRACT_ID = "RELEASE_PUBLICATION_GATE_SET_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"
RELEASE_LANE = "release_character"

ALLOWED_RESULT = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_TIER = {"draft", "npc", "hero", "test", "unknown"}
BLOCKING_GATE_RESULT = {"warn", "fail", "pending_manual"}

REQUIRED_RELEASE_GATES: List[str] = [
    "dcc_conform_v1",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "screenshot_evidence_v1",
    "ci_artifact_retention_v1",
    "release_package_bundle_v1",
    "release_promotion_decision_v1",
    "release_publication_preflight_v1",
    "release_publication_request_approval_v1",
    "release_publication_execution_admission_gate_v1",
    "release_publication_execution_request_ledger_v1",
    "release_publication_ready_for_execution_request_v1",
    "release_publication_execution_handoff_v1",
    "release_publication_execution_admission_request_packet_v1",
    "release_publication_execution_admission_review_v1",
    "release_publication_execution_authorization_record_v1",
    "release_publication_execution_window_ticket_v1",
    "release_publication_execution_window_state_v1",
    "release_publication_execution_receipt_v1",
    "release_publication_rollback_drill_v1",
    "release_publication_evidence_integrity_index_v1",
    "release_publication_chain_audit_bundle_v1",
]

HERO_REQUIRED_GATES: List[str] = ["manual_hero_review_v1"]


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


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate release-publication gate-set report evidence. "
            "Input may be a manifest (qc.gates) or a prebuilt gate-set report."
        )
    )
    parser.add_argument("input_path", help="Path to manifest or gate-set report JSON")
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write structured gate-set report JSON.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero exit code for warn status.",
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


def derive_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")) for item in findings if isinstance(item, dict)}
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


def normalize_tier(raw: Any) -> str:
    tier = str(raw or "").strip().lower()
    if tier in ALLOWED_TIER:
        return tier
    return "unknown"


def has_jsonschema() -> bool:
    try:
        import jsonschema  # noqa: F401
    except Exception:
        return False
    return True


def build_report_from_manifest(manifest: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    observed_gates: List[Dict[str, Any]] = []
    missing_required_gates: List[str] = []
    out_of_order_gates: List[Dict[str, Any]] = []
    blocked_by_status: List[Dict[str, Any]] = []

    job = manifest.get("job", {}) if isinstance(manifest.get("job"), dict) else {}
    identity = manifest.get("identity", {}) if isinstance(manifest.get("identity"), dict) else {}
    qc = manifest.get("qc", {}) if isinstance(manifest.get("qc"), dict) else {}

    job_id = str(job.get("job_id", "")).strip() or "unknown-job"
    lane = str(job.get("lane", "")).strip() or "unknown-lane"
    package_id = (
        str(identity.get("package_id", "")).strip()
        or str(identity.get("character_id", "")).strip()
        or "unknown-package"
    )
    tier = normalize_tier(identity.get("tier", identity.get("package_tier", "unknown")))

    required_gate_order = list(REQUIRED_RELEASE_GATES)
    if tier == "hero":
        required_gate_order.insert(4, HERO_REQUIRED_GATES[0])

    gates_raw = qc.get("gates", [])
    if not isinstance(gates_raw, list):
        add_finding(
            findings,
            "manifest_qc_gates_invalid",
            "error",
            "open",
            "manifest qc.gates must be an array.",
        )
        gates_raw = []

    gate_index_by_check: Dict[str, int] = {}
    gate_result_by_check: Dict[str, str] = {}

    for index, gate in enumerate(gates_raw):
        if not isinstance(gate, dict):
            add_finding(
                findings,
                "gate_entry_invalid",
                "error",
                "open",
                "Each manifest qc.gates entry must be an object.",
                {"index": index},
            )
            continue

        check_id = str(gate.get("check_id", gate.get("check", ""))).strip()
        result = str(gate.get("result", "")).strip()
        if not check_id:
            add_finding(
                findings,
                "gate_check_id_missing",
                "error",
                "open",
                "Each manifest gate must provide check_id (or legacy check).",
                {"index": index},
            )
            continue

        if check_id not in gate_index_by_check:
            gate_index_by_check[check_id] = index
            gate_result_by_check[check_id] = result

        observed_gates.append(
            {
                "check_id": check_id,
                "result": result,
                "index": index,
            }
        )

    if lane != RELEASE_LANE:
        add_finding(
            findings,
            "non_release_lane_manifest",
            "warning",
            "open",
            "Manifest lane is not release_character; release-publication gate-set check is advisory.",
            {"lane": lane},
        )

    previous_index = -1
    for required in required_gate_order:
        index = gate_index_by_check.get(required)
        if index is None:
            missing_required_gates.append(required)
            add_finding(
                findings,
                "missing_required_gate",
                "error",
                "open",
                "Required gate missing from manifest qc.gates[].",
                {"check_id": required},
            )
            continue

        result = gate_result_by_check.get(required, "")
        if result not in ALLOWED_RESULT:
            add_finding(
                findings,
                "invalid_gate_result",
                "error",
                "open",
                "Gate result must be pass|warn|fail|pending_manual.",
                {"check_id": required, "result": result},
            )
        elif result != "pass":
            blocked_by_status.append({"check_id": required, "result": result})
            if result == "warn":
                add_finding(
                    findings,
                    "gate_warn_result",
                    "warning",
                    "open",
                    "Gate result is warn and requires operator review before publication.",
                    {"check_id": required},
                )
            elif result == "pending_manual":
                add_finding(
                    findings,
                    "gate_pending_manual_result",
                    "manual_review",
                    "open",
                    "Gate result is pending_manual and cannot be auto-promoted.",
                    {"check_id": required},
                )
            else:
                add_finding(
                    findings,
                    "gate_fail_result",
                    "error",
                    "open",
                    "Gate result is fail.",
                    {"check_id": required},
                )

        if index < previous_index:
            expected_after = required_gate_order[required_gate_order.index(required) - 1]
            out_of_order_gates.append(
                {
                    "check_id": required,
                    "expected_after": expected_after,
                    "actual_index": index,
                    "expected_min_index": previous_index + 1,
                }
            )
            add_finding(
                findings,
                "gate_order_violation",
                "error",
                "open",
                "Required gate order is not deterministic in manifest qc.gates[].",
                {
                    "check_id": required,
                    "actual_index": index,
                    "expected_min_index": previous_index + 1,
                },
            )
        previous_index = max(previous_index, index)

    status = derive_status(findings)
    qc_severity = status_to_qc_severity(status)

    return {
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "report_type": EXPECTED_REPORT_TYPE,
        "job_id": job_id,
        "package_id": package_id,
        "lane": lane,
        "tier": tier,
        "status": status,
        "target_path": TARGET_PATH,
        "required_gate_order": required_gate_order,
        "observed_gates": observed_gates,
        "missing_required_gates": missing_required_gates,
        "out_of_order_gates": out_of_order_gates,
        "blocked_by_status": blocked_by_status,
        "findings": findings,
        "manifest_attachment": {
            "target_path": TARGET_PATH,
            "future_target_path": FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": status,
                "severity": qc_severity,
                "details": {
                    "contract_id": CONTRACT_ID,
                    "required_gate_count": len(required_gate_order),
                    "observed_gate_count": len(observed_gates),
                    "missing_gate_count": len(missing_required_gates),
                    "out_of_order_gate_count": len(out_of_order_gates),
                    "blocked_by_status_count": len(blocked_by_status),
                    "manifest_path": str(source_path),
                },
            },
        },
        "generated_utc": utc_now(),
    }


def validate_existing_report(report: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    findings: List[Dict[str, Any]]
    if isinstance(report.get("findings"), list):
        findings = [x for x in report["findings"] if isinstance(x, dict)]
    else:
        findings = []
        add_finding(
            findings,
            "findings_field_invalid",
            "error",
            "open",
            "findings must be an array.",
        )

    declared_status = str(report.get("status", "")).strip()
    if declared_status not in ALLOWED_RESULT:
        add_finding(
            findings,
            "status_invalid",
            "error",
            "open",
            "status must be one of pass|warn|fail|pending_manual.",
            {"actual": declared_status},
        )
        declared_status = "fail"

    if str(report.get("schema_version", "")).strip() != EXPECTED_SCHEMA_VERSION:
        add_finding(
            findings,
            "schema_version_mismatch",
            "error",
            "open",
            f"schema_version must be {EXPECTED_SCHEMA_VERSION}.",
            {"actual": report.get("schema_version")},
        )
    if str(report.get("report_type", "")).strip() != EXPECTED_REPORT_TYPE:
        add_finding(
            findings,
            "report_type_mismatch",
            "error",
            "open",
            f"report_type must be {EXPECTED_REPORT_TYPE}.",
            {"actual": report.get("report_type")},
        )

    required_gate_order = report.get("required_gate_order", [])
    if not isinstance(required_gate_order, list) or not required_gate_order:
        add_finding(
            findings,
            "required_gate_order_invalid",
            "error",
            "open",
            "required_gate_order must be a non-empty array.",
        )
        required_gate_order = []

    if str(report.get("target_path", "")).strip() != TARGET_PATH:
        add_finding(
            findings,
            "target_path_invalid",
            "error",
            "open",
            f"target_path must be {TARGET_PATH}.",
            {"actual": report.get("target_path")},
        )

    observed_gates = report.get("observed_gates", [])
    if not isinstance(observed_gates, list):
        add_finding(
            findings,
            "observed_gates_invalid",
            "error",
            "open",
            "observed_gates must be an array.",
        )
        observed_gates = []

    for index, gate in enumerate(observed_gates):
        if not isinstance(gate, dict):
            add_finding(
                findings,
                "observed_gate_entry_invalid",
                "error",
                "open",
                "Each observed gate entry must be an object.",
                {"index": index},
            )
            continue
        check_id = str(gate.get("check_id", "")).strip()
        result = str(gate.get("result", "")).strip()
        if not check_id:
            add_finding(
                findings,
                "observed_gate_check_id_missing",
                "error",
                "open",
                "Each observed gate must provide check_id.",
                {"index": index},
            )
        if result not in ALLOWED_RESULT:
            add_finding(
                findings,
                "observed_gate_result_invalid",
                "error",
                "open",
                "Each observed gate result must be pass|warn|fail|pending_manual.",
                {"index": index, "result": result},
            )

    missing_required_gates = report.get("missing_required_gates", [])
    if not isinstance(missing_required_gates, list):
        add_finding(
            findings,
            "missing_required_gates_invalid",
            "error",
            "open",
            "missing_required_gates must be an array.",
        )
        missing_required_gates = []

    out_of_order_gates = report.get("out_of_order_gates", [])
    if not isinstance(out_of_order_gates, list):
        add_finding(
            findings,
            "out_of_order_gates_invalid",
            "error",
            "open",
            "out_of_order_gates must be an array.",
        )
        out_of_order_gates = []

    blocked_by_status = report.get("blocked_by_status", [])
    if not isinstance(blocked_by_status, list):
        add_finding(
            findings,
            "blocked_by_status_invalid",
            "error",
            "open",
            "blocked_by_status must be an array.",
        )
        blocked_by_status = []

    for index, item in enumerate(blocked_by_status):
        if not isinstance(item, dict):
            add_finding(
                findings,
                "blocked_by_status_entry_invalid",
                "error",
                "open",
                "Each blocked_by_status entry must be an object.",
                {"index": index},
            )
            continue
        result = str(item.get("result", "")).strip()
        if result not in BLOCKING_GATE_RESULT:
            add_finding(
                findings,
                "blocked_by_status_result_invalid",
                "error",
                "open",
                "blocked_by_status result must be warn|fail|pending_manual.",
                {"index": index, "result": result},
            )

    manifest_attachment = report.get("manifest_attachment", {})
    if not isinstance(manifest_attachment, dict):
        manifest_attachment = {}
        add_finding(
            findings,
            "manifest_attachment_invalid",
            "error",
            "open",
            "manifest_attachment must be an object.",
        )
    if str(manifest_attachment.get("target_path", "")).strip() != TARGET_PATH:
        add_finding(
            findings,
            "manifest_attachment_target_invalid",
            "error",
            "open",
            f"manifest_attachment.target_path must be {TARGET_PATH}.",
            {"actual": manifest_attachment.get("target_path")},
        )
    if str(manifest_attachment.get("future_target_path", "")).strip() != FUTURE_TARGET_PATH:
        add_finding(
            findings,
            "manifest_attachment_future_target_invalid",
            "error",
            "open",
            f"manifest_attachment.future_target_path must be {FUTURE_TARGET_PATH}.",
            {"actual": manifest_attachment.get("future_target_path")},
        )

    qc_check = manifest_attachment.get("qc_check", {})
    if not isinstance(qc_check, dict):
        qc_check = {}
        add_finding(
            findings,
            "manifest_attachment_qc_check_invalid",
            "error",
            "open",
            "manifest_attachment.qc_check must be an object.",
        )

    qc_check_id = str(qc_check.get("check_id", "")).strip()
    if qc_check_id != CHECK_ID:
        add_finding(
            findings,
            "manifest_attachment_qc_check_id_invalid",
            "error",
            "open",
            f"manifest_attachment.qc_check.check_id must be {CHECK_ID}.",
            {"actual": qc_check_id},
        )

    qc_check_result = str(qc_check.get("result", "")).strip()
    if qc_check_result and qc_check_result != declared_status:
        add_finding(
            findings,
            "manifest_attachment_qc_result_mismatch",
            "error",
            "open",
            "manifest_attachment.qc_check.result must match report status.",
            {"status": declared_status, "qc_check_result": qc_check_result},
        )

    qc_severity = str(qc_check.get("severity", "")).strip()
    if qc_severity and qc_severity not in ALLOWED_SEVERITY:
        add_finding(
            findings,
            "manifest_attachment_qc_severity_invalid",
            "error",
            "open",
            "manifest_attachment.qc_check.severity must be info|warning|error|manual_review.",
            {"actual": qc_severity},
        )

    if declared_status == "pass":
        if missing_required_gates:
            add_finding(
                findings,
                "pass_with_missing_gates",
                "error",
                "open",
                "status pass is invalid when missing_required_gates is non-empty.",
            )
        if out_of_order_gates:
            add_finding(
                findings,
                "pass_with_out_of_order_gates",
                "error",
                "open",
                "status pass is invalid when out_of_order_gates is non-empty.",
            )
        if blocked_by_status:
            add_finding(
                findings,
                "pass_with_blocked_by_status",
                "error",
                "open",
                "status pass is invalid when blocked_by_status is non-empty.",
            )

    if declared_status == "warn" and not blocked_by_status:
        add_finding(
            findings,
            "warn_without_blocking_gate_status",
            "warning",
            "open",
            "status warn typically expects blocked_by_status evidence.",
        )

    if declared_status == "fail" and not findings:
        add_finding(
            findings,
            "fail_without_findings",
            "error",
            "open",
            "status fail requires at least one finding.",
        )

    derived = derive_status(findings)
    final_status = declared_status
    if derived == "fail":
        final_status = "fail"
    elif derived == "pending_manual" and declared_status == "pass":
        final_status = "pending_manual"
    elif derived == "warn" and declared_status == "pass":
        final_status = "warn"

    report["status"] = final_status
    report["findings"] = findings
    if not isinstance(manifest_attachment, dict):
        manifest_attachment = {}
    if not isinstance(qc_check, dict):
        qc_check = {}
    qc_check["check_id"] = CHECK_ID
    qc_check["result"] = final_status
    qc_check["severity"] = status_to_qc_severity(final_status)
    details = qc_check.get("details", {})
    if not isinstance(details, dict):
        details = {}
    details["contract_id"] = CONTRACT_ID
    details.setdefault("source_path", str(source_path))
    qc_check["details"] = details
    manifest_attachment["target_path"] = TARGET_PATH
    manifest_attachment["future_target_path"] = FUTURE_TARGET_PATH
    manifest_attachment["qc_check"] = qc_check
    report["manifest_attachment"] = manifest_attachment
    report.setdefault("generated_utc", utc_now())
    report["target_path"] = TARGET_PATH

    return report


def is_report_payload(payload: Dict[str, Any]) -> bool:
    return str(payload.get("report_type", "")).strip() == EXPECTED_REPORT_TYPE


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    input_path = resolve_path(repo_root, args.input_path)
    schema_path = repo_root / "schemas" / "maxine_release_publication_gate_set_report.schema.json"

    if not input_path.exists():
        print(f"FAIL: input not found: {input_path}")
        return 2
    if not schema_path.exists():
        print(f"FAIL: schema not found: {schema_path}")
        return 2

    try:
        payload = load_json(input_path)
        schema = load_json(schema_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    if is_report_payload(payload):
        report = validate_existing_report(payload, input_path)
    else:
        report = build_report_from_manifest(payload, input_path)

    if has_jsonschema():
        ok, errors = validate_schema_with_jsonschema(report, schema)
        if not ok:
            report_findings = report.get("findings", [])
            if not isinstance(report_findings, list):
                report_findings = []
                report["findings"] = report_findings
            for error in errors:
                add_finding(
                    report_findings,
                    "report_schema_validation_error",
                    "error",
                    "open",
                    "Generated gate-set report failed schema validation.",
                    {"error": error},
                )
            report["status"] = "fail"
            attachment = report.get("manifest_attachment", {})
            if not isinstance(attachment, dict):
                attachment = {}
                report["manifest_attachment"] = attachment
            qc_check = attachment.get("qc_check", {})
            if not isinstance(qc_check, dict):
                qc_check = {}
                attachment["qc_check"] = qc_check
            qc_check["check_id"] = CHECK_ID
            qc_check["result"] = "fail"
            qc_check["severity"] = "error"
            details = qc_check.get("details", {})
            if not isinstance(details, dict):
                details = {}
            details["contract_id"] = CONTRACT_ID
            qc_check["details"] = details
            attachment["target_path"] = TARGET_PATH
            attachment["future_target_path"] = FUTURE_TARGET_PATH
    else:
        print("INFO: jsonschema not available; skipping report schema validation.")

    rendered = json.dumps(report, indent=2)
    print(rendered)

    if args.output:
        output_path = resolve_path(repo_root, args.output)
        write_json(output_path, report)

    final_status = str(report.get("status", "fail"))
    if final_status == "pass":
        return 0
    if final_status == "warn":
        return 0 if args.allow_warn else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
