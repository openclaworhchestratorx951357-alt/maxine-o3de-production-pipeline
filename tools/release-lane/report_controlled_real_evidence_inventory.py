#!/usr/bin/env python3
"""Report controlled real evidence inventory from approved local inputs only."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


ATTACHMENT_TARGET_PATH = "qc.gates[]"
ATTACHMENT_FUTURE_TARGET_PATH = "qc.checks[]"
REPORT_TYPE = "CONTROLLED_REAL_EVIDENCE_INVENTORY_v1_REPORT"
DEFAULT_PROJECT_INVENTORY = (
    "examples/sandbox/project-inventory/max_biped_v1_project_inventory.fixture.json"
)
DEFAULT_ASSET_CANDIDATE_INVENTORY = (
    "examples/sandbox/asset-candidates/max_biped_v1_asset_candidate_inventory.fixture.json"
)
DEFAULT_OUTPUT = (
    "examples/sandbox/manifests/reports/pilot-release-chain-proof/"
    "controlled-real-evidence-inventory.json"
)
DEFAULT_APPROVED_EVIDENCE_ROOTS = [
    "examples/sandbox/receipts",
    "examples/sandbox/review-packets",
    "examples/sandbox/review-decisions",
    "examples/sandbox/workflow-runs",
    "examples/sandbox/evidence-bundles",
]
BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
BLOCKED_SURFACES = [
    "o3de_editor_execution",
    "asset_processor_execution",
    "blender_or_dcc_execution",
    "spawn_or_publish_execution",
    "cache_read",
    "live_asset_database_read",
    "authoritative_source_uuid_claims",
    "authoritative_asset_id_claims",
    "authoritative_product_id_claims",
    "production_path_write",
    "engine_path_write",
]
REQUIRED_EXPLICIT_NON_ADMISSIONS = {
    "product_resolution",
    "asset_id_claims",
    "spawning",
    "publishing",
    "o3de_editor_execution",
    "asset_processor_execution",
    "o3de_cli_execution",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize approved-local-input evidence inventory using existing read-only "
            "project and asset-candidate inventory records."
        )
    )
    parser.add_argument(
        "--project-inventory",
        default=DEFAULT_PROJECT_INVENTORY,
        help="Path to project inventory JSON.",
    )
    parser.add_argument(
        "--asset-candidate-inventory",
        default=DEFAULT_ASSET_CANDIDATE_INVENTORY,
        help="Path to asset candidate inventory JSON.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Optional output report path.",
    )
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Return exit 0 when status is warn.",
    )
    return parser.parse_args()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result: List[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        text = item.strip().replace("\\", "/")
        if text:
            result.append(text)
    return result


def _is_relative_safe(path_value: str) -> bool:
    value = path_value.strip().replace("\\", "/")
    if not value:
        return False
    if value.startswith("/") or value.startswith("\\"):
        return False
    if Path(value).is_absolute():
        return False
    parts = [part for part in value.split("/") if part]
    return ".." not in parts


def _contains_blocked_token(path_value: str) -> bool:
    parts = [part.lower() for part in path_value.replace("\\", "/").split("/") if part]
    return any(part in BLOCKED_PATH_TOKENS for part in parts)


def _dedupe_sorted(values: Iterable[str]) -> List[str]:
    return sorted({value for value in values if value})


def _path_in_roots(candidate: str, approved_roots: List[str]) -> bool:
    value = candidate.strip().replace("\\", "/")
    if not value:
        return False
    for root in approved_roots:
        root_norm = root.strip().replace("\\", "/").strip("/")
        value_norm = value.strip("/")
        if not root_norm:
            continue
        if value_norm == root_norm:
            return True
        if value_norm.startswith(root_norm + "/"):
            return True
    return False


def _finding(fid: str, severity: str, message: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": fid,
        "severity": severity,
        "status": "open",
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _evidence_counts(linked: Dict[str, Any]) -> Dict[str, int]:
    return {
        "receipt_ids": len(_as_str_list(linked.get("receipt_ids"))),
        "review_packet_ids": len(_as_str_list(linked.get("review_packet_ids"))),
        "decision_ids": len(_as_str_list(linked.get("decision_ids"))),
        "workflow_run_ids": len(_as_str_list(linked.get("workflow_run_ids"))),
        "evidence_bundle_ids": len(_as_str_list(linked.get("evidence_bundle_ids"))),
    }


def _sum_counts(counts: Dict[str, int]) -> int:
    return sum(int(value) for value in counts.values())


def _normalize_path_for_report(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
        return str(rel).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def build_report(
    project_inventory: Dict[str, Any],
    asset_inventory: Dict[str, Any],
    project_inventory_path: Path,
    asset_inventory_path: Path,
    repo_root: Path,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    project_inventory_id = str(project_inventory.get("inventory_id", "")).strip()
    asset_inventory_id = str(asset_inventory.get("inventory_id", "")).strip()
    if not project_inventory_id:
        findings.append(_finding("project_inventory_id_missing", "error", "Project inventory is missing inventory_id."))
    if not asset_inventory_id:
        findings.append(_finding("asset_inventory_id_missing", "error", "Asset candidate inventory is missing inventory_id."))

    approved_input_roots = _dedupe_sorted(
        _as_str_list(project_inventory.get("known_asset_folders"))
        + _as_str_list(project_inventory.get("generated_asset_candidate_folders"))
    )
    approved_evidence_roots = _dedupe_sorted(
        _as_str_list(project_inventory.get("sandbox_evidence_folders"))
        + list(DEFAULT_APPROVED_EVIDENCE_ROOTS)
    )

    if not approved_input_roots:
        findings.append(_finding("approved_input_roots_missing", "error", "No approved input roots were found in project inventory."))

    blocked_roots = [root for root in approved_input_roots if _contains_blocked_token(root)]
    if blocked_roots:
        findings.append(
            _finding(
                "approved_input_roots_blocked_token",
                "error",
                "Approved input roots include blocked path tokens.",
                {"roots": blocked_roots},
            )
        )

    source_asset_candidates = asset_inventory.get("source_asset_candidates")
    if not isinstance(source_asset_candidates, list):
        findings.append(_finding("source_asset_candidates_not_array", "error", "Asset candidate inventory source_asset_candidates must be an array."))
        source_asset_candidates = []

    outside_approved_roots: List[str] = []
    blocked_candidate_paths: List[str] = []
    invalid_candidate_paths: List[str] = []
    category_counts: Dict[str, int] = {}

    for candidate in source_asset_candidates:
        if not isinstance(candidate, dict):
            findings.append(_finding("candidate_not_object", "error", "Each source candidate must be an object."))
            continue
        rel_path = str(candidate.get("relative_path", "")).strip().replace("\\", "/")
        category = str(candidate.get("category", "unknown_source")).strip() or "unknown_source"
        category_counts[category] = category_counts.get(category, 0) + 1

        if not _is_relative_safe(rel_path):
            invalid_candidate_paths.append(rel_path)
            continue
        if _contains_blocked_token(rel_path):
            blocked_candidate_paths.append(rel_path)
            continue
        if not _path_in_roots(rel_path, approved_input_roots):
            outside_approved_roots.append(rel_path)

    if invalid_candidate_paths:
        findings.append(
            _finding(
                "candidate_invalid_relative_path",
                "error",
                "One or more candidate paths are absolute or contain traversal.",
                {"paths": invalid_candidate_paths},
            )
        )
    if blocked_candidate_paths:
        findings.append(
            _finding(
                "candidate_blocked_token_path",
                "error",
                "One or more candidate paths include blocked path tokens.",
                {"paths": blocked_candidate_paths},
            )
        )
    if outside_approved_roots:
        findings.append(
            _finding(
                "candidate_outside_approved_roots",
                "error",
                "One or more candidate paths are outside approved input roots.",
                {"paths": outside_approved_roots},
            )
        )

    linked_sandbox_evidence = (
        asset_inventory.get("linked_sandbox_evidence")
        if isinstance(asset_inventory.get("linked_sandbox_evidence"), dict)
        else {}
    )
    linked_counts = _evidence_counts(linked_sandbox_evidence)
    total_linked_ids = _sum_counts(linked_counts)

    explicit_non_admissions = set(_as_str_list(asset_inventory.get("explicit_non_admissions")))
    missing_non_admissions = sorted(REQUIRED_EXPLICIT_NON_ADMISSIONS - explicit_non_admissions)
    if missing_non_admissions:
        findings.append(
            _finding(
                "missing_required_non_admissions",
                "error",
                "Asset candidate inventory is missing required explicit_non_admissions entries.",
                {"missing": missing_non_admissions},
            )
        )

    errors = [item for item in findings if item.get("severity") == "error"]
    warnings: List[Dict[str, Any]] = []

    candidate_count = len([item for item in source_asset_candidates if isinstance(item, dict)])
    if candidate_count == 0:
        warnings.append(
            _finding(
                "candidate_count_zero",
                "warning",
                "No source candidates are currently inventoried.",
            )
        )
    if total_linked_ids == 0:
        warnings.append(
            _finding(
                "linked_evidence_ids_zero",
                "warning",
                "No linked sandbox evidence ids were found.",
            )
        )
    findings.extend(warnings)

    if errors:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    controlled_real_inventory_ready = status == "pass"
    missing_for_promotion: List[str] = []
    if candidate_count == 0:
        missing_for_promotion.append("add approved local input candidates to controlled evidence inventory")
    if total_linked_ids == 0:
        missing_for_promotion.append("link approved sandbox evidence ids to inventoried candidates")
    if status == "fail":
        missing_for_promotion.append("resolve inventory policy violations (path safety and non-admission completeness)")
    missing_for_promotion.append(
        "execution admission remains blocked until explicit approval phrase: APPROVE EXECUTION ADMISSION <candidate_id>"
    )

    report = {
        "schema_version": "1.0.0",
        "report_type": REPORT_TYPE,
        "status": status,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_attachment_target_path": ATTACHMENT_TARGET_PATH,
        "future_manifest_attachment_target_path": ATTACHMENT_FUTURE_TARGET_PATH,
        "inventory_mode": "approved_local_inputs_and_evidence_sources_only",
        "source_project_inventory_path": _normalize_path_for_report(project_inventory_path, repo_root),
        "source_asset_candidate_inventory_path": _normalize_path_for_report(asset_inventory_path, repo_root),
        "source_project_inventory_id": project_inventory_id,
        "source_asset_candidate_inventory_id": asset_inventory_id,
        "approved_input_roots": approved_input_roots,
        "approved_evidence_roots": approved_evidence_roots,
        "discovered_asset_candidate_count": candidate_count,
        "discovered_candidate_categories": category_counts,
        "linked_evidence_counts": linked_counts,
        "candidate_path_policy": {
            "outside_approved_roots_count": len(outside_approved_roots),
            "blocked_token_path_count": len(blocked_candidate_paths),
            "outside_approved_roots_paths": sorted(outside_approved_roots),
            "blocked_token_paths": sorted(blocked_candidate_paths),
            "invalid_relative_paths": sorted(invalid_candidate_paths),
        },
        "controlled_real_inventory_ready": controlled_real_inventory_ready,
        "execution_admitted": False,
        "blocked_surfaces": BLOCKED_SURFACES,
        "missing_for_promotion": missing_for_promotion,
        "findings": findings,
    }
    return report


def _resolve_repo_path(repo_root: Path, raw_path: str, label: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must remain inside repository root.") from exc
    return resolved


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        project_inventory_path = _resolve_repo_path(repo_root, args.project_inventory, "project_inventory")
        asset_inventory_path = _resolve_repo_path(repo_root, args.asset_candidate_inventory, "asset_candidate_inventory")
        output_path = _resolve_repo_path(repo_root, args.output, "output")
    except ValueError as exc:
        payload = {
            "schema_version": "1.0.0",
            "report_type": REPORT_TYPE,
            "status": "fail",
            "error": str(exc),
        }
        print(json.dumps(payload, indent=2))
        return 2

    if not project_inventory_path.exists():
        payload = {
            "schema_version": "1.0.0",
            "report_type": REPORT_TYPE,
            "status": "fail",
            "error": f"project_inventory_not_found: {project_inventory_path}",
        }
        print(json.dumps(payload, indent=2))
        return 1
    if not asset_inventory_path.exists():
        payload = {
            "schema_version": "1.0.0",
            "report_type": REPORT_TYPE,
            "status": "fail",
            "error": f"asset_candidate_inventory_not_found: {asset_inventory_path}",
        }
        print(json.dumps(payload, indent=2))
        return 1

    try:
        project_inventory = _read_json(project_inventory_path)
        asset_inventory = _read_json(asset_inventory_path)
    except Exception as exc:
        payload = {
            "schema_version": "1.0.0",
            "report_type": REPORT_TYPE,
            "status": "fail",
            "error": f"inventory_parse_failed: {exc}",
        }
        print(json.dumps(payload, indent=2))
        return 1

    report = build_report(
        project_inventory=project_inventory,
        asset_inventory=asset_inventory,
        project_inventory_path=project_inventory_path,
        asset_inventory_path=asset_inventory_path,
        repo_root=repo_root,
    )
    _write_json(output_path, report)
    report["output_path"] = _normalize_path_for_report(output_path, repo_root)
    print(json.dumps(report, indent=2))

    if report["status"] == "pass":
        return 0
    if report["status"] == "warn":
        return 0 if args.allow_warn else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
