#!/usr/bin/env python3
"""Validate release-publication gate completeness/order from a manifest."""

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
        description="Validate release-publication gate-set completeness/order from manifest qc.gates[]."
    )
    parser.add_argument("manifest_path", help="Path to manifest JSON")
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write structured report JSON.",
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


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = resolve_path(repo_root, args.manifest_path)
    schema_path = repo_root / "schemas" / "maxine_release_publication_gate_set_report.schema.json"

    if not manifest_path.exists():
        print(f"FAIL: manifest not found: {manifest_path}")
        return 2
    if not schema_path.exists():
        print(f"FAIL: schema not found: {schema_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
        schema = load_json(schema_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

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

    report: Dict[str, Any] = {
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
                    "manifest_path": str(manifest_path),
                },
            },
        },
        "generated_utc": utc_now(),
    }

    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, errors = validate_schema_with_jsonschema(report, schema)
        if not ok:
            for error in errors:
                add_finding(
                    report["findings"],
                    "report_schema_validation_error",
                    "error",
                    "open",
                    "Generated gate-set report failed schema validation.",
                    {"error": error},
                )
            report["status"] = derive_status(report["findings"])
            report["manifest_attachment"]["qc_check"]["result"] = report["status"]
            report["manifest_attachment"]["qc_check"]["severity"] = status_to_qc_severity(report["status"])
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
