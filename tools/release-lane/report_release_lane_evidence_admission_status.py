#!/usr/bin/env python3
"""Report release-lane evidence classification and execution-admission status."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ATTACHMENT_TARGET_PATH = "qc.gates[]"
ATTACHMENT_FUTURE_TARGET_PATH = "qc.checks[]"
DEFAULT_MANIFEST = "examples/manifests/example-release-character-pilot-chain.manifest.json"
REQUIRED_CHAIN_GATE_IDS = [
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
    "real_pilot_release_candidate_package_v1",
]
EVIDENCE_CLASS_BY_CHECK_ID = {
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
    "real_pilot_release_candidate_package_v1": "manual",
}
BLOCKED_EXECUTION_SURFACES = [
    "o3de_editor_execution",
    "asset_processor_execution",
    "blender_or_dcc_execution",
    "spawn_or_publish_execution",
    "cache_read",
    "live_asset_database_read",
    "authoritative_source_uuid_claims",
    "authoritative_asset_id_claims",
    "authoritative_product_id_claims",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize pilot release-lane evidence classes and execution-admission posture "
            "from a manifest."
        )
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help="Path to pilot manifest JSON (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        help="Optional output path for JSON report. The report is always printed to stdout.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _collect_gates(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    qc = manifest.get("qc")
    if not isinstance(qc, dict):
        return []
    gates = qc.get("gates")
    if not isinstance(gates, list):
        return []
    return [item for item in gates if isinstance(item, dict)]


def _result_counts(gates: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "pending_manual": 0, "unknown": 0}
    for gate in gates:
        result = str(gate.get("result", "")).strip()
        if result in counts:
            counts[result] += 1
        else:
            counts["unknown"] += 1
    return counts


def _gate_result_map(gates: List[Dict[str, Any]]) -> Dict[str, str]:
    result_map: Dict[str, str] = {}
    for gate in gates:
        check_id = str(gate.get("check_id", "")).strip()
        if not check_id or check_id in result_map:
            continue
        result_map[check_id] = str(gate.get("result", "")).strip()
    return result_map


def _classify_gates(gates: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    classes = {
        "fixture": [],
        "manual": [],
        "imported": [],
        "controlled_real": [],
        "future": [],
    }
    for gate in gates:
        check_id = str(gate.get("check_id", "")).strip()
        if not check_id:
            continue
        details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
        details_class = str(details.get("evidence_class", "")).strip()
        if details_class in classes:
            evidence_class = details_class
        else:
            evidence_class = EVIDENCE_CLASS_BY_CHECK_ID.get(check_id, "future")
        classes.setdefault(evidence_class, []).append(check_id)
    for key in classes:
        classes[key] = sorted(set(classes[key]))
    return classes


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": "manifest_not_found",
                    "manifest_path": str(manifest_path),
                },
                indent=2,
            )
        )
        return 1

    try:
        manifest = _read_json(manifest_path)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "fail",
                    "error": "manifest_parse_failed",
                    "manifest_path": str(manifest_path),
                    "reason": str(exc),
                },
                indent=2,
            )
        )
        return 1

    gates = _collect_gates(manifest)
    gate_result_map = _gate_result_map(gates)
    required_missing = sorted(
        [check_id for check_id in REQUIRED_CHAIN_GATE_IDS if check_id not in gate_result_map]
    )
    required_non_pass = sorted(
        [
            check_id
            for check_id in REQUIRED_CHAIN_GATE_IDS
            if gate_result_map.get(check_id) != "pass"
        ]
    )
    chain_pass = not required_missing and not required_non_pass

    observed_gate_ids = sorted(gate_result_map.keys())
    evidence_classes = _classify_gates(gates)
    controlled_real_evidence_available = bool(evidence_classes["controlled_real"])
    execution_admitted = False

    missing_for_operational: List[str] = []
    if not chain_pass:
        missing_for_operational.append(
            "pilot package must pass full required release-lane chain with pass results"
        )
    if not controlled_real_evidence_available:
        missing_for_operational.append(
            "promote fixture/manual/imported evidence to controlled real evidence for required chain gates"
        )
    if not execution_admitted:
        missing_for_operational.append(
            "record explicit approved execution-admission decision and bounded admitted execution receipt"
        )

    overall_release_lane_state = "evidence_only_pre_production"
    if chain_pass and controlled_real_evidence_available and not execution_admitted:
        overall_release_lane_state = "controlled_evidence_ready_execution_blocked"
    if execution_admitted:
        overall_release_lane_state = "execution_admitted"

    report = {
        "schema_version": "1.0.0",
        "report_type": "RELEASE_LANE_EVIDENCE_ADMISSION_STATUS_v1_REPORT",
        "status": "pass",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_attachment_target_path": ATTACHMENT_TARGET_PATH,
        "future_manifest_attachment_target_path": ATTACHMENT_FUTURE_TARGET_PATH,
        "overall_release_lane_state": overall_release_lane_state,
        "pilot_chain": {
            "required_gate_count": len(REQUIRED_CHAIN_GATE_IDS),
            "observed_gate_count": len(observed_gate_ids),
            "required_missing_gate_ids": required_missing,
            "required_non_pass_gate_ids": required_non_pass,
            "chain_pass": chain_pass,
        },
        "qc_result_counts": _result_counts(gates),
        "evidence_classification": {
            "fixture_check_ids": evidence_classes["fixture"],
            "manual_check_ids": evidence_classes["manual"],
            "imported_check_ids": evidence_classes["imported"],
            "controlled_real_check_ids": evidence_classes["controlled_real"],
            "future_check_ids": evidence_classes["future"],
        },
        "execution_admission_status": {
            "execution_admitted": execution_admitted,
            "admitted_surfaces": [],
            "blocked_surfaces": BLOCKED_EXECUTION_SURFACES,
        },
        "missing_for_operational": missing_for_operational,
    }

    if args.output:
        _write_json(Path(args.output).resolve(), report)

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
