#!/usr/bin/env python3
"""Validate pilot release-lane gate chain completeness against a manifest fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_RESULTS = {"pass", "warn", "fail", "pending_manual"}
CHECK_ID = "pilot_release_chain_v1"
CONTRACT_ID = "PILOT_RELEASE_CHAIN_v1"
ALLOWED_TARGET = "qc.gates[]"
ALLOWED_FUTURE_TARGET = "qc.checks[]"
REQUIRED_IMPLEMENTED_GATE_IDS = {
    "max_biped_v1_skeleton_contract",
    "dcc_conform_v1",
    "source_product_evidence_resolver_v1",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "screenshot_evidence_v1",
    "manual_hero_review_v1",
    "ci_artifact_retention_v1",
    "release_package_bundle_v1",
    "release_publication_rollback_drill_v1",
    "release_publication_ready_for_execution_request_v1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate pilot release-lane gate chain fixture against required ordered gate IDs."
    )
    parser.add_argument(
        "manifest",
        help="Path to manifest JSON that contains qc.gates[] entries.",
    )
    parser.add_argument(
        "--chain",
        default="examples/release-lane-gate-chain/max_biped_v1_release_lane_gate_chain.json",
        help="Path to release-lane gate chain JSON definition.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return exit 0 when overall status is warn.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def finding(fid: str, severity: str, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": fid,
        "severity": severity,
        "status": "open",
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def derive_status(findings: List[Dict[str, Any]], chain_results: List[str]) -> str:
    if any(item.get("severity") == "error" for item in findings):
        return "fail"
    if "fail" in chain_results:
        return "fail"
    if any(item.get("severity") in {"warning", "manual_review"} for item in findings):
        return "warn"
    if any(result in {"warn", "pending_manual"} for result in chain_results):
        return "warn"
    return "pass"


def collect_gate_index(gates: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int], List[str]]:
    gate_map: Dict[str, Dict[str, Any]] = {}
    order_map: Dict[str, int] = {}
    duplicates: List[str] = []

    for idx, gate in enumerate(gates):
        if not isinstance(gate, dict):
            continue
        check_id = str(gate.get("check_id", "")).strip()
        if not check_id:
            continue
        if check_id in gate_map:
            duplicates.append(check_id)
            continue
        gate_map[check_id] = gate
        order_map[check_id] = idx

    return gate_map, order_map, duplicates


def build_manifest_attachment(status: str, findings: List[Dict[str, Any]], details: Dict[str, Any]) -> Dict[str, Any]:
    severity = "info"
    if status == "warn":
        severity = "warning"
    if status == "fail":
        severity = "error"
    return {
        "target_path": ALLOWED_TARGET,
        "future_target_path": ALLOWED_FUTURE_TARGET,
        "qc_check": {
            "check_id": CHECK_ID,
            "result": status,
            "severity": severity,
            "details": details,
        },
    }


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    chain_path = Path(args.chain).resolve()

    findings: List[Dict[str, Any]] = []
    status = "fail"

    if not manifest_path.exists():
        findings.append(finding("manifest_missing", "error", f"Manifest file not found: {manifest_path}"))
    if not chain_path.exists():
        findings.append(finding("chain_missing", "error", f"Chain definition file not found: {chain_path}"))
    if findings:
        payload = {
            "status": "fail",
            "check_id": CHECK_ID,
            "contract_id": CONTRACT_ID,
            "findings": findings,
            "manifest_attachment": build_manifest_attachment(
                "fail",
                findings,
                {
                    "manifest_path": str(manifest_path),
                    "chain_path": str(chain_path),
                },
            ),
        }
        print(json.dumps(payload, indent=2))
        return 1

    try:
        manifest = load_json(manifest_path)
        chain = load_json(chain_path)
    except Exception as exc:
        findings.append(finding("json_parse_error", "error", f"Failed to parse input JSON: {exc}"))
        payload = {
            "status": "fail",
            "check_id": CHECK_ID,
            "contract_id": CONTRACT_ID,
            "findings": findings,
            "manifest_attachment": build_manifest_attachment(
                "fail",
                findings,
                {
                    "manifest_path": str(manifest_path),
                    "chain_path": str(chain_path),
                },
            ),
        }
        print(json.dumps(payload, indent=2))
        return 1

    qc = manifest.get("qc", {})
    gates = qc.get("gates", []) if isinstance(qc, dict) else []
    chain_gates = chain.get("gates", [])
    if not isinstance(gates, list):
        findings.append(finding("manifest_qc_gates_not_array", "error", "Manifest qc.gates must be an array."))
        gates = []
    if not isinstance(chain_gates, list):
        findings.append(finding("chain_gates_not_array", "error", "Chain definition gates must be an array."))
        chain_gates = []

    gate_map, gate_order, duplicates = collect_gate_index(gates)
    if duplicates:
        findings.append(
            finding(
                "duplicate_check_id",
                "error",
                "Duplicate check_id entries detected in manifest qc.gates.",
                {"duplicate_check_ids": sorted(set(duplicates))},
            )
        )

    required_ordered: List[str] = []
    implemented_gate_ids: List[str] = []
    required_gate_ids: List[str] = []
    for item in chain_gates:
        if not isinstance(item, dict):
            findings.append(finding("chain_gate_not_object", "error", "Each chain gate entry must be an object."))
            continue
        check_id = str(item.get("check_id", "")).strip()
        if not check_id:
            findings.append(finding("chain_check_id_missing", "error", "Chain gate entry missing check_id."))
            continue
        required = bool(item.get("required", False))
        implemented = bool(item.get("implemented", False))
        if required:
            required_ordered.append(check_id)
            required_gate_ids.append(check_id)
        if implemented:
            implemented_gate_ids.append(check_id)

    implemented_set = set(implemented_gate_ids)
    missing_implemented_ids = sorted(REQUIRED_IMPLEMENTED_GATE_IDS - implemented_set)
    extra_implemented_ids = sorted(implemented_set - REQUIRED_IMPLEMENTED_GATE_IDS)
    if missing_implemented_ids:
        findings.append(
            finding(
                "chain_missing_required_implemented_gates",
                "error",
                "Chain definition is missing required implemented gate IDs.",
                {"missing_implemented_gate_ids": missing_implemented_ids},
            )
        )
    if extra_implemented_ids:
        findings.append(
            finding(
                "chain_has_unexpected_implemented_gates",
                "warning",
                "Chain definition contains implemented gate IDs outside the current integrated set.",
                {"extra_implemented_gate_ids": extra_implemented_ids},
            )
        )

    chain_results: List[str] = []
    missing_ids: List[str] = []
    out_of_order_ids: List[str] = []

    previous_idx = -1
    for check_id in required_ordered:
        gate = gate_map.get(check_id)
        if gate is None:
            missing_ids.append(check_id)
            continue

        current_idx = gate_order.get(check_id, -1)
        if current_idx < previous_idx:
            out_of_order_ids.append(check_id)
        previous_idx = max(previous_idx, current_idx)

        result = str(gate.get("result", "")).strip()
        if result not in ALLOWED_RESULTS:
            findings.append(
                finding(
                    "invalid_gate_result",
                    "error",
                    f"Gate {check_id} has unsupported result '{result}'.",
                    {"check_id": check_id, "result": result},
                )
            )
            continue

        chain_results.append(result)

        if check_id in implemented_gate_ids and result == "pending_manual":
            findings.append(
                finding(
                    "implemented_gate_pending_manual",
                    "error",
                    f"Implemented gate {check_id} cannot be pending_manual in pilot chain.",
                    {"check_id": check_id},
                )
            )
        if check_id not in implemented_gate_ids and result == "pass":
            findings.append(
                finding(
                    "unimplemented_gate_marked_pass",
                    "error",
                    f"Unimplemented gate {check_id} cannot be marked pass yet.",
                    {"check_id": check_id},
                )
            )
        if check_id not in implemented_gate_ids and result == "warn":
            findings.append(
                finding(
                    "unimplemented_gate_warn",
                    "warning",
                    f"Unimplemented gate {check_id} is warn; pending_manual is preferred until implemented.",
                    {"check_id": check_id},
                )
            )

    if missing_ids:
        findings.append(
            finding(
                "required_gate_missing",
                "error",
                "Manifest is missing one or more required release-lane gates.",
                {"missing_gate_ids": missing_ids},
            )
        )
    if out_of_order_ids:
        findings.append(
            finding(
                "required_gate_out_of_order",
                "error",
                "Required release-lane gates are out of declared chain order.",
                {"out_of_order_gate_ids": out_of_order_ids},
            )
        )

    status = derive_status(findings, chain_results)
    details = {
        "manifest_path": str(manifest_path),
        "chain_path": str(chain_path),
        "required_gate_count": len(required_gate_ids),
        "manifest_gate_count": len(gate_map),
        "implemented_gate_ids": implemented_gate_ids,
        "missing_gate_ids": missing_ids,
        "out_of_order_gate_ids": out_of_order_ids,
        "attachment_target_path": ALLOWED_TARGET,
        "future_attachment_target_path": ALLOWED_FUTURE_TARGET,
    }
    payload = {
        "status": status,
        "check_id": CHECK_ID,
        "contract_id": CONTRACT_ID,
        "findings": findings,
        "manifest_attachment": build_manifest_attachment(status, findings, details),
    }
    print(json.dumps(payload, indent=2))

    if status == "pass":
        return 0
    if status == "warn":
        return 0 if args.allow_warn else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
