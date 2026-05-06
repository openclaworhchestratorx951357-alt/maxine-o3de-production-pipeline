#!/usr/bin/env python3
"""Generate and validate production-readiness report v1 from a pilot release-lane manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


EXPECTED_SCHEMA_VERSION = "1.0.0"
EXPECTED_REPORT_TYPE = "PRODUCTION_READINESS_REPORT_v1_REPORT"
CHECK_ID = "production_readiness_report_v1"
CONTRACT_ID = "PRODUCTION_READINESS_REPORT_v1"
TARGET_PATH = "qc.gates[]"
FUTURE_TARGET_PATH = "qc.checks[]"

ALLOWED_GATE_RESULTS = {"pass", "warn", "fail", "pending_manual"}
ALLOWED_FINDING_SEVERITY = {"info", "warning", "error", "manual_review"}
ALLOWED_EVIDENCE_CLASS = {"fixture", "imported", "controlled_real", "manual", "future"}
ALLOWED_PILOT_CHAIN_STATUS = {"pass", "warn", "fail", "pending_manual", "missing", "unknown"}

REQUIRED_GATE_REFS: List[str] = [
    "max_biped_v1_skeleton_contract",
    "dcc_conform_v1",
    "source_product_evidence_resolver_v1",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "screenshot_evidence_v1",
    "manual_hero_review_v1",
    "aaa_performance_budget_v1",
    "ci_artifact_retention_v1",
    "release_package_bundle_v1",
    "release_promotion_decision_v1",
    "release_publication_preflight_v1",
    "release_publication_request_approval_v1",
    "release_publication_execution_admission_gate_v1",
    "release_publication_execution_request_ledger_v1",
    "release_publication_execution_receipt_v1",
    "release_publication_rollback_drill_v1",
    "release_publication_evidence_integrity_index_v1",
    "release_publication_chain_audit_bundle_v1",
    "release_publication_ready_for_execution_request_v1",
    "release_publication_execution_handoff_v1",
    "release_publication_execution_admission_request_packet_v1",
    "release_publication_gate_set_v1",
    "pilot_release_chain_v1",
    "real_pilot_release_candidate_package_v1",
]

CORE_AAA_GATE_REFS: List[str] = [
    "source_product_evidence_resolver_v1",
    "dcc_conform_v1",
    "max_biped_v1_skeleton_contract",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "screenshot_evidence_v1",
    "manual_hero_review_v1",
    "aaa_performance_budget_v1",
]

EVIDENCE_CLASS_FALLBACK: Dict[str, str] = {
    "max_biped_v1_skeleton_contract": "controlled_real",
    "dcc_conform_v1": "controlled_real",
    "source_product_evidence_resolver_v1": "imported",
    "material_uv_qc_v1": "controlled_real",
    "animation_smoke_v1": "controlled_real",
    "screenshot_evidence_v1": "controlled_real",
    "manual_hero_review_v1": "manual",
    "aaa_performance_budget_v1": "controlled_real",
    "ci_artifact_retention_v1": "fixture",
    "release_package_bundle_v1": "manual",
    "release_promotion_decision_v1": "manual",
    "release_publication_preflight_v1": "manual",
    "release_publication_request_approval_v1": "manual",
    "release_publication_execution_admission_gate_v1": "manual",
    "release_publication_execution_request_ledger_v1": "manual",
    "release_publication_execution_receipt_v1": "manual",
    "release_publication_rollback_drill_v1": "fixture",
    "release_publication_evidence_integrity_index_v1": "manual",
    "release_publication_chain_audit_bundle_v1": "manual",
    "release_publication_ready_for_execution_request_v1": "fixture",
    "release_publication_execution_handoff_v1": "manual",
    "release_publication_execution_admission_request_packet_v1": "manual",
    "release_publication_gate_set_v1": "manual",
    "pilot_release_chain_v1": "manual",
    "real_pilot_release_candidate_package_v1": "manual",
    "production_readiness_report_v1": "manual",
}

EXECUTION_ADMISSION_BOOL_KEYS = {
    "execution_admitted",
    "o3de_execution_admitted",
    "editor_execution_admitted",
    "runtime_execution_admitted",
    "asset_processor_execution_admitted",
    "dcc_execution_admitted",
    "blender_execution_admitted",
    "benchmark_execution_admitted",
    "profiler_execution_admitted",
}
PUBLICATION_ADMISSION_BOOL_KEYS = {
    "publication_admitted",
    "publish_admitted",
    "package_publication_admitted",
    "spawn_publish_admitted",
}
ADMISSION_STATUS_VALUES = {"admitted", "allowed", "executed", "published", "true", "yes"}
BLOCKED_EXPECTED_VALUES = {"blocked", "false", "no", "not_admitted"}
SOURCE_AUTHORITY_ALLOWED = {"evidence_only", "not_authoritative", "not_claimed", "blocked", "false"}
SOURCE_AUTHORITY_DISALLOWED = {"authoritative", "admitted_authoritative", "claimed", "true"}

SAFE_STATUS_FIELDS = [
    "o3de_execution_status",
    "editor_execution_status",
    "runtime_execution_status",
    "asset_processor_execution_status",
    "dcc_execution_status",
    "blender_execution_status",
    "profiler_execution_status",
    "screenshot_capture_status",
    "spawn_publish_status",
    "production_write_status",
]

NOOP_RECEIPT_CANDIDATE_ID = "release_candidate_package_receipt_noop_v1"
NOOP_RECEIPT_APPROVAL_PHRASE = (
    "APPROVE EXECUTION ADMISSION release_candidate_package_receipt_noop_v1"
)
NOOP_RECEIPT_DECISION_RECORD_REL = Path(
    "examples/execution-admission/release_candidate_package_receipt_noop_execution_admission_decision_approved.json"
)
NOOP_RECEIPT_PASS_REPORT_REL = Path(
    "examples/execution-admission/release_candidate_package_receipt_noop_report_pass.json"
)

REAL_EXECUTION_ADMISSION_STATUS_VALUES = {"admitted", "allowed", "executed", "true", "yes"}
PUBLICATION_ADMISSION_STATUS_VALUES = {"admitted", "allowed", "published", "true", "yes"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a production-readiness report from the release-lane pilot manifest while "
            "keeping execution/publication posture evidence-only."
        )
    )
    parser.add_argument("manifest_path", help="Path to release-lane manifest JSON.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for structured report JSON.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return zero exit code when report status is warn.",
    )
    return parser.parse_args()


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
        "severity": severity if severity in ALLOWED_FINDING_SEVERITY else "error",
        "status": status,
        "message": message,
    }
    if details:
        item["details"] = details
    findings.append(item)


def status_to_qc_severity(status: str) -> str:
    if status == "pass":
        return "info"
    if status == "warn":
        return "warning"
    return "error"


def derive_status(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")).strip() for item in findings}
    if "error" in severities:
        return "fail"
    if "manual_review" in severities or "warning" in severities:
        return "warn"
    return "pass"


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


def _normalize_gate_map(manifest: Dict[str, Any], findings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    qc = manifest.get("qc") if isinstance(manifest.get("qc"), dict) else {}
    gates = qc.get("gates", [])
    if not isinstance(gates, list):
        add_finding(
            findings,
            "manifest_qc_gates_invalid",
            "error",
            "open",
            "Manifest qc.gates must be an array.",
        )
        return {}

    gate_map: Dict[str, Dict[str, Any]] = {}
    for idx, gate in enumerate(gates):
        if not isinstance(gate, dict):
            add_finding(
                findings,
                "manifest_qc_gate_entry_invalid",
                "error",
                "open",
                "Each manifest qc.gates entry must be an object.",
                {"index": idx},
            )
            continue
        check_id = str(gate.get("check_id", gate.get("check", ""))).strip()
        if not check_id:
            add_finding(
                findings,
                "manifest_qc_gate_check_id_missing",
                "error",
                "open",
                "Each manifest qc.gates entry must include check_id (or legacy check).",
                {"index": idx},
            )
            continue
        if check_id not in gate_map:
            gate_map[check_id] = gate
    return gate_map


def _is_truthy(value: Any) -> bool:
    if value is True:
        return True
    text = str(value).strip().lower()
    return text in ADMISSION_STATUS_VALUES


def _normalized_result(value: Any) -> str:
    result = str(value).strip()
    if result in ALLOWED_GATE_RESULTS:
        return result
    if result:
        return "unknown"
    return "missing"


def _gate_to_readiness(value: Any) -> str:
    normalized = _normalized_result(value)
    if normalized == "pass":
        return "pass"
    if normalized in {"warn", "pending_manual"}:
        return "warn"
    if normalized == "missing":
        return "missing"
    return "fail"


def _normalize_evidence_class(check_id: str, gate: Dict[str, Any]) -> str:
    details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
    details_class = str(details.get("evidence_class", "")).strip()
    if details_class in ALLOWED_EVIDENCE_CLASS:
        return details_class
    fallback = EVIDENCE_CLASS_FALLBACK.get(check_id, "future")
    if fallback in ALLOWED_EVIDENCE_CLASS:
        return fallback
    return "future"


def _composite_gate_status(gate_ids: List[str], gate_map: Dict[str, Dict[str, Any]]) -> str:
    statuses = [_gate_to_readiness(gate_map.get(gate_id, {}).get("result")) for gate_id in gate_ids]
    if any(status == "fail" for status in statuses):
        return "fail"
    if any(status == "missing" for status in statuses):
        return "missing"
    if any(status == "warn" for status in statuses):
        return "warn"
    return "pass"


def _collect_result_counts(gate_map: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "pending_manual": 0, "unknown": 0}
    for gate in gate_map.values():
        result = _normalized_result(gate.get("result"))
        if result in counts:
            counts[result] += 1
        elif result == "missing":
            counts["unknown"] += 1
        else:
            counts["unknown"] += 1
    return counts


def _git_head_commit(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            value = proc.stdout.strip()
            if value:
                return value
    except Exception:
        pass
    return "unknown"


def _scan_claim_surfaces(
    gate_map: Dict[str, Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    real_execution_admission_claimed = False
    publication_admission_claimed = False
    execution_refs: List[str] = []
    publication_refs: List[str] = []
    admitted_noop_receipt_candidate_ids: List[str] = []
    admitted_real_execution_candidate_ids: List[str] = []
    admitted_publication_candidate_ids: List[str] = []
    receipt_backed_candidate_ids: List[str] = []
    source_authority_claimed = False
    cache_live_db_admitted = False
    production_write_admitted = False
    production_ready_claim_gates: List[str] = []

    for check_id, gate in gate_map.items():
        details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
        for key, raw_value in details.items():
            key_norm = str(key).strip().lower()
            value_norm = str(raw_value).strip().lower()

            if key_norm in {"execution_admission_reference", "execution_admission_ref"} and value_norm:
                execution_refs.append(str(raw_value).strip())
            if key_norm in {"publication_admission_reference", "publication_admission_ref"} and value_norm:
                publication_refs.append(str(raw_value).strip())

            if key_norm == "admitted_noop_receipt_candidate_ids":
                values = raw_value if isinstance(raw_value, list) else [raw_value]
                for value in values:
                    candidate_id = str(value).strip()
                    if candidate_id:
                        admitted_noop_receipt_candidate_ids.append(candidate_id)
            if key_norm == "receipt_backed_candidate_ids":
                values = raw_value if isinstance(raw_value, list) else [raw_value]
                for value in values:
                    candidate_id = str(value).strip()
                    if candidate_id:
                        receipt_backed_candidate_ids.append(candidate_id)
            if key_norm == "admitted_real_execution_candidate_ids":
                values = raw_value if isinstance(raw_value, list) else [raw_value]
                for value in values:
                    candidate_id = str(value).strip()
                    if candidate_id:
                        admitted_real_execution_candidate_ids.append(candidate_id)
            if key_norm == "admitted_publication_candidate_ids":
                values = raw_value if isinstance(raw_value, list) else [raw_value]
                for value in values:
                    candidate_id = str(value).strip()
                    if candidate_id:
                        admitted_publication_candidate_ids.append(candidate_id)

            if key_norm in EXECUTION_ADMISSION_BOOL_KEYS and _is_truthy(raw_value):
                real_execution_admission_claimed = True
            if key_norm in PUBLICATION_ADMISSION_BOOL_KEYS and _is_truthy(raw_value):
                publication_admission_claimed = True

            if key_norm in {"execution_admission_status", "real_execution_admission_status"}:
                if value_norm in REAL_EXECUTION_ADMISSION_STATUS_VALUES:
                    real_execution_admission_claimed = True
            if key_norm.endswith("execution_status") and value_norm in REAL_EXECUTION_ADMISSION_STATUS_VALUES:
                real_execution_admission_claimed = True
            if key_norm in {"publication_status", "package_publication_status", "spawn_publish_status", "publication_admission_status"}:
                if value_norm in PUBLICATION_ADMISSION_STATUS_VALUES:
                    publication_admission_claimed = True

            if key_norm in {
                "source_uuid_claim_status",
                "asset_id_claim_status",
                "product_id_claim_status",
                "source_product_authority_status",
            }:
                if value_norm in SOURCE_AUTHORITY_DISALLOWED:
                    source_authority_claimed = True
                    add_finding(
                        findings,
                        "source_product_authority_false_claim",
                        "error",
                        "open",
                        "Source/product authority claim must remain evidence-only in this slice.",
                        {"check_id": check_id, "field": key, "actual": raw_value},
                    )
                elif value_norm and value_norm not in SOURCE_AUTHORITY_ALLOWED:
                    source_authority_claimed = True
                    add_finding(
                        findings,
                        "source_product_authority_unexpected_claim",
                        "error",
                        "open",
                        "Unexpected source/product authority status detected.",
                        {"check_id": check_id, "field": key, "actual": raw_value},
                    )

            if key_norm in {"cache_access_status", "live_db_access_status", "cache_live_db_status"}:
                if value_norm in ADMISSION_STATUS_VALUES:
                    cache_live_db_admitted = True
                    add_finding(
                        findings,
                        "cache_live_db_false_admission",
                        "error",
                        "open",
                        "Cache/live DB access must remain blocked in this slice.",
                        {"check_id": check_id, "field": key, "actual": raw_value},
                    )

            if key_norm == "production_write_status" and value_norm in ADMISSION_STATUS_VALUES:
                production_write_admitted = True
                add_finding(
                    findings,
                    "production_write_false_admission",
                    "error",
                    "open",
                    "Production path writes must remain blocked in this slice.",
                    {"check_id": check_id, "field": key, "actual": raw_value},
                )

            if key_norm == "production_readiness_level" and value_norm == "production_ready":
                production_ready_claim_gates.append(check_id)

    if NOOP_RECEIPT_CANDIDATE_ID in admitted_real_execution_candidate_ids:
        add_finding(
            findings,
            "noop_candidate_misclassified_as_real_execution",
            "error",
            "open",
            "No-op receipt candidate cannot be classified as a real execution-admitted candidate.",
            {"candidate_id": NOOP_RECEIPT_CANDIDATE_ID},
        )
    if NOOP_RECEIPT_CANDIDATE_ID in admitted_publication_candidate_ids:
        add_finding(
            findings,
            "noop_candidate_misclassified_as_publication",
            "error",
            "open",
            "No-op receipt candidate cannot be classified as a publication-admitted candidate.",
            {"candidate_id": NOOP_RECEIPT_CANDIDATE_ID},
        )
    if real_execution_admission_claimed and not admitted_real_execution_candidate_ids:
        add_finding(
            findings,
            "real_execution_admission_without_candidate_reference",
            "error",
            "open",
            "Real execution admission claims require explicit admitted_real_execution_candidate_ids references.",
        )
    if publication_admission_claimed and not admitted_publication_candidate_ids:
        add_finding(
            findings,
            "publication_admission_without_candidate_reference",
            "error",
            "open",
            "Publication admission claims require explicit admitted_publication_candidate_ids references.",
        )
    if admitted_real_execution_candidate_ids and not execution_refs:
        add_finding(
            findings,
            "execution_admission_without_reference",
            "error",
            "open",
            "Execution admission cannot be true without an execution admission reference.",
        )
    if admitted_publication_candidate_ids and not publication_refs:
        add_finding(
            findings,
            "publication_admission_without_reference",
            "error",
            "open",
            "Publication admission cannot be true without a publication admission reference.",
        )

    return {
        "real_execution_admission_claimed": real_execution_admission_claimed,
        "publication_admission_claimed": publication_admission_claimed,
        "execution_references": sorted(set(execution_refs)),
        "publication_references": sorted(set(publication_refs)),
        "admitted_noop_receipt_candidate_ids": sorted(set(admitted_noop_receipt_candidate_ids)),
        "admitted_real_execution_candidate_ids": sorted(set(admitted_real_execution_candidate_ids)),
        "admitted_publication_candidate_ids": sorted(set(admitted_publication_candidate_ids)),
        "receipt_backed_candidate_ids": sorted(set(receipt_backed_candidate_ids)),
        "source_authority_claimed": source_authority_claimed,
        "cache_live_db_admitted": cache_live_db_admitted,
        "production_write_admitted": production_write_admitted,
        "production_ready_claim_gates": sorted(set(production_ready_claim_gates)),
    }


def _collect_noop_receipt_admission(repo_root: Path, findings: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    admitted_noop_receipt_candidate_ids: List[str] = []
    receipt_backed_candidate_ids: List[str] = []

    decision_record_path = repo_root / NOOP_RECEIPT_DECISION_RECORD_REL
    if not decision_record_path.exists():
        add_finding(
            findings,
            "noop_receipt_decision_record_missing",
            "error",
            "open",
            "Expected admitted no-op receipt decision record is missing.",
            {"path": str(NOOP_RECEIPT_DECISION_RECORD_REL)},
        )
        return {
            "admitted_noop_receipt_candidate_ids": admitted_noop_receipt_candidate_ids,
            "receipt_backed_candidate_ids": receipt_backed_candidate_ids,
        }

    decision_record = load_json(decision_record_path)
    decision_candidate_id = str(decision_record.get("candidate_id", "")).strip()
    decision_state = str(decision_record.get("decision_state", "")).strip().lower()
    surface_id = str(
        (
            decision_record.get("requested_execution", {})
            if isinstance(decision_record.get("requested_execution"), dict)
            else {}
        ).get("surface_id", "")
    ).strip()
    approval = decision_record.get("approval", {}) if isinstance(decision_record.get("approval"), dict) else {}
    approval_received = approval.get("approval_received")
    approval_phrase = str(approval.get("approval_phrase_received", "")).strip()
    admission_outcome = (
        decision_record.get("admission_outcome", {})
        if isinstance(decision_record.get("admission_outcome"), dict)
        else {}
    )
    execution_admitted = admission_outcome.get("execution_admitted")

    decision_is_valid = (
        decision_candidate_id == NOOP_RECEIPT_CANDIDATE_ID
        and decision_state == "approved"
        and surface_id == "release_candidate_package_receipt_noop_execution"
        and approval_received is True
        and approval_phrase == NOOP_RECEIPT_APPROVAL_PHRASE
        and execution_admitted is True
    )
    if decision_is_valid:
        admitted_noop_receipt_candidate_ids.append(NOOP_RECEIPT_CANDIDATE_ID)
    else:
        add_finding(
            findings,
            "noop_receipt_decision_record_invalid",
            "error",
            "open",
            "No-op receipt decision record does not satisfy admitted candidate requirements.",
            {"path": str(NOOP_RECEIPT_DECISION_RECORD_REL)},
        )

    receipt_report_path = repo_root / NOOP_RECEIPT_PASS_REPORT_REL
    if not receipt_report_path.exists():
        add_finding(
            findings,
            "noop_receipt_report_fixture_missing",
            "error",
            "open",
            "Expected no-op receipt pass fixture is missing.",
            {"path": str(NOOP_RECEIPT_PASS_REPORT_REL)},
        )
        return {
            "admitted_noop_receipt_candidate_ids": sorted(set(admitted_noop_receipt_candidate_ids)),
            "receipt_backed_candidate_ids": sorted(set(receipt_backed_candidate_ids)),
        }

    receipt_report = load_json(receipt_report_path)
    report_candidate_id = str(receipt_report.get("candidate_id", "")).strip()
    report_status = str(receipt_report.get("status", "")).strip().lower()
    command_mode = str(receipt_report.get("command_mode", "")).strip().lower()
    external_execution_performed = receipt_report.get("external_execution_performed")
    publication_performed = receipt_report.get("publication_performed")
    receipt_report_valid = (
        report_candidate_id == NOOP_RECEIPT_CANDIDATE_ID
        and report_status == "pass"
        and command_mode == "noop"
        and external_execution_performed is False
        and publication_performed is False
    )
    if receipt_report_valid:
        receipt_backed_candidate_ids.append(NOOP_RECEIPT_CANDIDATE_ID)
    else:
        add_finding(
            findings,
            "noop_receipt_report_fixture_invalid",
            "error",
            "open",
            "No-op receipt pass fixture must stay non-executing and non-publishing.",
            {"path": str(NOOP_RECEIPT_PASS_REPORT_REL)},
        )

    return {
        "admitted_noop_receipt_candidate_ids": sorted(set(admitted_noop_receipt_candidate_ids)),
        "receipt_backed_candidate_ids": sorted(set(receipt_backed_candidate_ids)),
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = resolve_path(repo_root, args.manifest_path)
    schema_path = repo_root / "schemas" / "maxine_production_readiness_report.schema.json"

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
    gate_map = _normalize_gate_map(manifest, findings)

    missing_required_gate_ids: List[str] = []
    required_gate_results: Dict[str, str] = {}
    for check_id in REQUIRED_GATE_REFS:
        gate = gate_map.get(check_id)
        if gate is None:
            missing_required_gate_ids.append(check_id)
            add_finding(
                findings,
                "missing_required_gate_chain_summary",
                "error",
                "open",
                "Required gate is missing from manifest gate chain summary.",
                {"check_id": check_id},
            )
            continue

        raw_result = _normalized_result(gate.get("result"))
        required_gate_results[check_id] = raw_result
        if raw_result not in ALLOWED_GATE_RESULTS:
            add_finding(
                findings,
                "invalid_gate_result_value",
                "error",
                "open",
                "Gate result must be pass|warn|fail|pending_manual.",
                {"check_id": check_id, "result": gate.get("result")},
            )

    claim_scan = _scan_claim_surfaces(gate_map, findings)

    noop_receipt_scan = _collect_noop_receipt_admission(repo_root, findings)
    admitted_noop_receipt_candidate_ids = sorted(
        set(claim_scan["admitted_noop_receipt_candidate_ids"])
        | set(noop_receipt_scan["admitted_noop_receipt_candidate_ids"])
    )
    admitted_real_execution_candidate_ids = sorted(set(claim_scan["admitted_real_execution_candidate_ids"]))
    admitted_publication_candidate_ids = sorted(set(claim_scan["admitted_publication_candidate_ids"]))
    receipt_backed_candidate_ids = sorted(
        set(claim_scan["receipt_backed_candidate_ids"]) | set(noop_receipt_scan["receipt_backed_candidate_ids"])
    )

    if set(receipt_backed_candidate_ids) - set(admitted_noop_receipt_candidate_ids):
        add_finding(
            findings,
            "receipt_backed_candidate_without_noop_admission",
            "error",
            "open",
            "Receipt-backed candidates must also be admitted no-op receipt candidates.",
            {
                "candidate_ids": sorted(
                    set(receipt_backed_candidate_ids) - set(admitted_noop_receipt_candidate_ids)
                )
            },
        )
    if NOOP_RECEIPT_CANDIDATE_ID in admitted_noop_receipt_candidate_ids and NOOP_RECEIPT_CANDIDATE_ID not in receipt_backed_candidate_ids:
        add_finding(
            findings,
            "admitted_noop_candidate_missing_receipt_backing",
            "error",
            "open",
            "Admitted no-op receipt candidate must be receipt-backed.",
            {"candidate_id": NOOP_RECEIPT_CANDIDATE_ID},
        )

    real_execution_admission_status = "admitted" if admitted_real_execution_candidate_ids else "blocked"
    execution_admission_status = real_execution_admission_status
    publication_admission_status = "admitted" if admitted_publication_candidate_ids else "blocked"
    source_product_authority_status = (
        "admitted_authoritative" if claim_scan["source_authority_claimed"] else "not_authoritative"
    )
    cache_live_db_status = "admitted" if claim_scan["cache_live_db_admitted"] else "blocked"
    production_write_status = "admitted" if claim_scan["production_write_admitted"] else "blocked"

    if claim_scan["production_ready_claim_gates"] and (
        real_execution_admission_status != "admitted" or publication_admission_status != "admitted"
    ):
        add_finding(
            findings,
            "production_ready_claim_while_blocked",
            "error",
            "open",
            "Production-ready claim is invalid while execution/publication admission remains blocked.",
            {"check_ids": claim_scan["production_ready_claim_gates"]},
        )

    pilot_chain_status_raw = _normalized_result(required_gate_results.get("pilot_release_chain_v1", "missing"))
    if pilot_chain_status_raw == "unknown":
        pilot_chain_status = "unknown"
    elif pilot_chain_status_raw == "missing":
        pilot_chain_status = "missing"
    elif pilot_chain_status_raw in ALLOWED_PILOT_CHAIN_STATUS:
        pilot_chain_status = pilot_chain_status_raw
    else:
        pilot_chain_status = "unknown"

    release_candidate_package_status = _gate_to_readiness(
        required_gate_results.get("real_pilot_release_candidate_package_v1", "missing")
    )
    manual_hero_review_status = _gate_to_readiness(
        required_gate_results.get("manual_hero_review_v1", "missing")
    )
    performance_budget_status = _gate_to_readiness(
        required_gate_results.get("aaa_performance_budget_v1", "missing")
    )
    rollback_readiness_status = _gate_to_readiness(
        required_gate_results.get("release_publication_rollback_drill_v1", "missing")
    )
    evidence_integrity_status = _gate_to_readiness(
        required_gate_results.get("release_publication_evidence_integrity_index_v1", "missing")
    )
    aaa_quality_gate_status = _composite_gate_status(CORE_AAA_GATE_REFS, gate_map)

    has_required_fail = any(
        result in {"fail", "unknown", "missing"} for result in required_gate_results.values()
    ) or bool(missing_required_gate_ids)
    has_required_warn = any(
        result in {"warn", "pending_manual"} for result in required_gate_results.values()
    )

    evidence_ready = (
        not has_required_fail
        and pilot_chain_status == "pass"
        and release_candidate_package_status == "pass"
    )
    review_ready = (
        evidence_ready
        and manual_hero_review_status == "pass"
        and performance_budget_status == "pass"
        and aaa_quality_gate_status == "pass"
    )

    if has_required_fail:
        production_readiness_level = "blocked"
        readiness_decision = "fail"
    elif review_ready and real_execution_admission_status != "admitted":
        production_readiness_level = "review_ready"
        readiness_decision = "blocked_for_execution"
    elif review_ready and publication_admission_status != "admitted":
        production_readiness_level = "execution_ready"
        readiness_decision = "blocked_for_publication"
    elif review_ready:
        production_readiness_level = "production_ready"
        readiness_decision = "pass_evidence_only"
    elif evidence_ready and has_required_warn:
        production_readiness_level = "evidence_ready"
        readiness_decision = "warn_evidence_only"
    elif evidence_ready:
        production_readiness_level = "evidence_ready"
        readiness_decision = "pass_evidence_only"
    else:
        production_readiness_level = "blocked"
        readiness_decision = "fail"

    controlled_real_gate_ids: List[str] = []
    imported_gate_ids: List[str] = []
    manual_gate_ids: List[str] = []
    fixture_only_gate_ids: List[str] = []
    for check_id in REQUIRED_GATE_REFS:
        gate = gate_map.get(check_id)
        if gate is None:
            continue
        evidence_class = _normalize_evidence_class(check_id, gate)
        if evidence_class == "controlled_real":
            controlled_real_gate_ids.append(check_id)
        elif evidence_class == "imported":
            imported_gate_ids.append(check_id)
        elif evidence_class == "manual":
            manual_gate_ids.append(check_id)
        elif evidence_class == "fixture":
            fixture_only_gate_ids.append(check_id)

    result_counts = _collect_result_counts(gate_map)
    required_pass_count = sum(1 for result in required_gate_results.values() if result == "pass")

    remaining_required_actions: List[str] = []
    if missing_required_gate_ids:
        remaining_required_actions.append(
            "fill missing required gate outputs before readiness claims can proceed"
        )
    if real_execution_admission_status != "admitted":
        remaining_required_actions.append(
            "record explicit approved execution admission before execution-ready/production-ready claims"
        )
    if publication_admission_status != "admitted":
        remaining_required_actions.append(
            "record explicit approved publication admission before publication claims"
        )
    if source_product_authority_status != "not_authoritative":
        remaining_required_actions.append(
            "revert source/product authority posture to evidence-only unless explicit admitted authority exists"
        )
    if cache_live_db_status != "blocked":
        remaining_required_actions.append("restore Cache/live DB status to blocked for this evidence-only lane")
    if production_write_status != "blocked":
        remaining_required_actions.append("restore production write status to blocked for this evidence-only lane")
    if not review_ready:
        remaining_required_actions.append(
            "close remaining manual hero review/performance/AAA quality gaps for review-ready state"
        )
    if admitted_noop_receipt_candidate_ids and real_execution_admission_status != "admitted":
        remaining_required_actions.append(
            "treat no-op receipt admission as receipt-only; real execution admission remains separately blocked"
        )
    remaining_required_actions = sorted(set(remaining_required_actions))

    blocking_findings = sorted(
        {str(item.get("id", "")).strip() for item in findings if str(item.get("severity")) == "error"}
    )
    warning_findings = sorted(
        {
            str(item.get("id", "")).strip()
            for item in findings
            if str(item.get("severity")) in {"warning", "manual_review"}
        }
    )

    status = derive_status(findings)

    job = manifest.get("job") if isinstance(manifest.get("job"), dict) else {}
    job_id = str(job.get("job_id", "")).strip() or "unknown-job"
    report_id = f"production-readiness-{job_id}"
    report_version = "v1"

    evaluated_release_candidate_package_ref = ""
    release_package_gate = gate_map.get("real_pilot_release_candidate_package_v1")
    if isinstance(release_package_gate, dict):
        details = release_package_gate.get("details")
        if isinstance(details, dict):
            evaluated_release_candidate_package_ref = str(
                details.get("report_path", details.get("evidence_bundle_ref", ""))
            ).strip()
    if not evaluated_release_candidate_package_ref:
        evaluated_release_candidate_package_ref = "real_pilot_release_candidate_package_v1"

    payload: Dict[str, Any] = {
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "report_type": EXPECTED_REPORT_TYPE,
        "status": status,
        "generated_utc": utc_now(),
        "report_id": report_id,
        "report_version": report_version,
        "generated_for_branch_or_commit": _git_head_commit(repo_root),
        "evaluated_manifest_ref": str(manifest_path),
        "evaluated_release_candidate_package_ref": evaluated_release_candidate_package_ref,
        "evaluated_gate_chain_ref": "examples/release-lane-gate-chain/max_biped_v1_release_lane_gate_chain.json",
        "pilot_chain_status": pilot_chain_status,
        "final_gate_count": len(gate_map),
        "evidence_summary": {
            "total_gate_count": len(gate_map),
            "required_gate_count": len(REQUIRED_GATE_REFS),
            "required_pass_count": required_pass_count,
            "pass_count": result_counts["pass"],
            "warn_count": result_counts["warn"],
            "fail_count": result_counts["fail"],
            "pending_manual_count": result_counts["pending_manual"],
            "evidence_ready": evidence_ready,
            "review_ready": review_ready,
        },
        "controlled_real_gate_ids": sorted(set(controlled_real_gate_ids)),
        "imported_gate_ids": sorted(set(imported_gate_ids)),
        "manual_gate_ids": sorted(set(manual_gate_ids)),
        "fixture_only_gate_ids": sorted(set(fixture_only_gate_ids)),
        "missing_required_gate_ids": sorted(set(missing_required_gate_ids)),
        "release_candidate_package_status": release_candidate_package_status,
        "aaa_quality_gate_status": aaa_quality_gate_status,
        "performance_budget_status": performance_budget_status,
        "manual_hero_review_status": manual_hero_review_status,
        "rollback_readiness_status": rollback_readiness_status,
        "evidence_integrity_status": evidence_integrity_status,
        "admitted_noop_receipt_candidate_ids": admitted_noop_receipt_candidate_ids,
        "receipt_backed_candidate_ids": receipt_backed_candidate_ids,
        "admitted_real_execution_candidate_ids": admitted_real_execution_candidate_ids,
        "admitted_publication_candidate_ids": admitted_publication_candidate_ids,
        "execution_admission_status": execution_admission_status,
        "real_execution_admission_status": real_execution_admission_status,
        "publication_admission_status": publication_admission_status,
        "source_product_authority_status": source_product_authority_status,
        "cache_live_db_status": cache_live_db_status,
        "production_write_status": production_write_status,
        "production_readiness_level": production_readiness_level,
        "readiness_decision": readiness_decision,
        "blocking_findings": blocking_findings,
        "warning_findings": warning_findings,
        "remaining_required_actions": remaining_required_actions,
        "recommended_next_milestone": "execution_publication_admission_planning_v1",
        "claim_status": "evidence_only",
        "safety": {
            "o3de_execution_status": "blocked",
            "editor_execution_status": "blocked",
            "runtime_execution_status": "blocked",
            "asset_processor_execution_status": "blocked",
            "dcc_execution_status": "blocked",
            "blender_execution_status": "blocked",
            "profiler_execution_status": "blocked",
            "screenshot_capture_status": "blocked",
            "spawn_publish_status": "blocked",
            "production_write_status": "blocked",
        },
        "findings": findings,
        "manifest_attachment": {
            "target_path": TARGET_PATH,
            "future_target_path": FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": status,
                "severity": status_to_qc_severity(status),
                "details": {
                    "contract_id": CONTRACT_ID,
                    "report_id": report_id,
                    "report_version": report_version,
                    "evidence_class": "manual",
                    "pilot_chain_status": pilot_chain_status,
                    "final_gate_count": len(gate_map),
                    "production_readiness_level": production_readiness_level,
                    "readiness_decision": readiness_decision,
                    "admitted_noop_receipt_candidate_ids": admitted_noop_receipt_candidate_ids,
                    "receipt_backed_candidate_ids": receipt_backed_candidate_ids,
                    "admitted_real_execution_candidate_ids": admitted_real_execution_candidate_ids,
                    "admitted_publication_candidate_ids": admitted_publication_candidate_ids,
                    "execution_admission_status": execution_admission_status,
                    "real_execution_admission_status": real_execution_admission_status,
                    "publication_admission_status": publication_admission_status,
                    "claim_status": "evidence_only",
                    "validated_at_utc": utc_now(),
                    "safety": {field: "blocked" for field in SAFE_STATUS_FIELDS},
                },
            },
        },
    }

    # Enforce schema alignment for generated payload.
    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, errors = validate_schema_with_jsonschema(payload, schema)
        if not ok:
            for err in errors:
                add_finding(
                    payload["findings"],
                    "schema_validation_error",
                    "error",
                    "open",
                    "Generated production readiness payload failed schema validation.",
                    {"error": err},
                )
            payload["status"] = "fail"
            payload["manifest_attachment"]["qc_check"]["result"] = "fail"
            payload["manifest_attachment"]["qc_check"]["severity"] = "error"
            payload["blocking_findings"] = sorted(
                {
                    str(item.get("id", "")).strip()
                    for item in payload["findings"]
                    if str(item.get("severity")) == "error"
                }
            )

    if args.output:
        output_path = resolve_path(repo_root, args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))

    final_status = str(payload.get("status", "fail")).strip()
    if final_status == "pass":
        return 0
    if final_status == "warn" and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
