#!/usr/bin/env python3
"""Extract source/product evidence resolver report from admitted evidence sources only."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPORT_TYPE = "SOURCE_PRODUCT_EVIDENCE_RESOLVER_v1_REPORT"
SCHEMA_VERSION = "1.0.0"
ATTACHMENT_TARGET_PATH = "qc.gates[]"
ATTACHMENT_FUTURE_TARGET_PATH = "qc.checks[]"
CHECK_ID = "source_product_evidence_resolver_v1"

DEFAULT_PROJECT_INVENTORY = (
    "examples/sandbox/project-inventory/max_biped_v1_project_inventory.fixture.json"
)
DEFAULT_ASSET_CANDIDATE_INVENTORY = (
    "examples/sandbox/asset-candidates/max_biped_v1_asset_candidate_inventory.fixture.json"
)
DEFAULT_CONTROLLED_INVENTORY_REPORT = (
    "examples/controlled-real-evidence-inventory/"
    "max_biped_v1_controlled_real_evidence_inventory_pass.json"
)
DEFAULT_FIXTURE_REPORT = (
    "examples/source-product-evidence-resolver/max_biped_v1_source_product_resolver_pass.json"
)
DEFAULT_AP_EVIDENCE_IMPORT_ROOT = "examples/sandbox/ap-evidence-imports/pilot-candidates"
DEFAULT_OUTPUT = (
    "examples/sandbox/manifests/reports/pilot-release-chain-proof/"
    "source-product-evidence-resolver-extracted.json"
)

BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
EXPECTED_PRODUCT_TYPES = [
    "actor",
    "motion",
    "procprefab",
    "azmodel",
    "material",
    "texture",
    "pxmesh",
]
REQUIRED_IMPORTED_PRODUCT_TYPES = EXPECTED_PRODUCT_TYPES
NON_ADMISSIONS = [
    "no live cache read",
    "no live db read",
    "no source uuid claim",
    "no asset id claim",
    "no product id claim",
    "no asset processor execution",
    "no o3de execution",
    "no spawn",
    "no publish",
]
QUALITY_TO_CONFIDENCE = {
    "strong_snapshot_only": 0.92,
    "partial": 0.86,
    "weak": 0.78,
    "none": 0.72,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build SOURCE_PRODUCT_EVIDENCE_RESOLVER_v1_REPORT from admitted evidence "
            "sources only (controlled inventory + approved local inputs + optional AP "
            "evidence imports + fixture-backed fallback). Pass status requires imported AP "
            "evidence coverage for required product types."
        )
    )
    parser.add_argument("--project-inventory", default=DEFAULT_PROJECT_INVENTORY)
    parser.add_argument("--asset-candidate-inventory", default=DEFAULT_ASSET_CANDIDATE_INVENTORY)
    parser.add_argument(
        "--controlled-inventory-report",
        default=DEFAULT_CONTROLLED_INVENTORY_REPORT,
    )
    parser.add_argument("--fixture-report", default=DEFAULT_FIXTURE_REPORT)
    parser.add_argument(
        "--ap-evidence-import",
        action="append",
        default=[],
        help=(
            "Path to AP evidence import JSON. May be passed multiple times. "
            "If omitted, JSON files under --ap-evidence-import-root are used."
        ),
    )
    parser.add_argument(
        "--ap-evidence-import-root",
        default=DEFAULT_AP_EVIDENCE_IMPORT_ROOT,
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-warn", action="store_true")
    return parser.parse_args()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _resolve_repo_path(repo_root: Path, raw_path: str, label: str) -> Path:
    candidate = Path(raw_path)
    resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} must remain inside repository root.") from exc
    return resolved


def _normalize(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    output: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            output.append(item.strip().replace("\\", "/"))
    return output


def _contains_blocked_token(path_text: str) -> bool:
    parts = [part.lower() for part in path_text.replace("\\", "/").split("/") if part]
    if ".." in parts:
        return True
    return any(part in BLOCKED_PATH_TOKENS for part in parts)


def _is_safe_relative_path(path_text: str) -> bool:
    text = path_text.strip().replace("\\", "/")
    if not text or text.startswith("/") or text.startswith("\\"):
        return False
    if Path(text).is_absolute():
        return False
    parts = [part for part in text.split("/") if part]
    return ".." not in parts


def _path_in_roots(candidate: str, approved_roots: Iterable[str]) -> bool:
    cand = candidate.strip().replace("\\", "/").strip("/")
    for root in approved_roots:
        normalized_root = root.strip().replace("\\", "/").strip("/")
        if not normalized_root:
            continue
        if cand == normalized_root or cand.startswith(normalized_root + "/"):
            return True
    return False


def _finding(
    finding_id: str,
    severity: str,
    message: str,
    details: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": finding_id,
        "severity": severity,
        "status": "open",
        "message": message,
    }
    if details:
        payload["details"] = details
    return payload


def _status_from_findings(findings: List[Dict[str, Any]]) -> str:
    severities = {str(item.get("severity", "")).strip() for item in findings}
    if "error" in severities:
        return "fail"
    if "warning" in severities:
        return "warn"
    return "pass"


def _qc_severity(status: str) -> str:
    if status == "pass":
        return "info"
    if status == "warn":
        return "warning"
    return "error"


def _product_type_for_mention(mention: str) -> str | None:
    lowered = mention.lower()
    if lowered.endswith(".actor"):
        return "actor"
    if lowered.endswith(".motion") or lowered.endswith(".motionset"):
        return "motion"
    if lowered.endswith(".procprefab") or lowered.endswith(".prefab"):
        return "procprefab"
    if lowered.endswith(".azmodel"):
        return "azmodel"
    if lowered.endswith(".material") or lowered.endswith(".azmaterial"):
        return "material"
    if (
        lowered.endswith(".streamingimage")
        or lowered.endswith(".dds")
        or lowered.endswith(".png")
        or lowered.endswith(".jpg")
        or lowered.endswith(".jpeg")
        or lowered.endswith(".tif")
        or lowered.endswith(".tiff")
        or lowered.endswith(".exr")
    ):
        return "texture"
    if lowered.endswith(".pxmesh"):
        return "pxmesh"
    return None


def _collect_ap_import_paths(
    explicit_paths: List[str],
    ap_import_root: Path,
    repo_root: Path,
) -> List[Path]:
    if explicit_paths:
        paths: List[Path] = []
        for idx, raw in enumerate(explicit_paths):
            paths.append(_resolve_repo_path(repo_root, raw, f"ap_evidence_import[{idx}]"))
        return paths

    if not ap_import_root.exists():
        return []
    return sorted(path for path in ap_import_root.glob("*.json") if path.is_file())


def _load_fixture_observed(fixture_report: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    observed_map: Dict[str, Dict[str, Any]] = {}
    for item in fixture_report.get("observed_products", []):
        if not isinstance(item, dict):
            continue
        product_type = str(item.get("product_type", "")).strip()
        if product_type not in EXPECTED_PRODUCT_TYPES:
            continue
        if product_type in observed_map:
            continue
        observed_map[product_type] = item
    return observed_map


def _build_expected_products() -> List[Dict[str, Any]]:
    return [
        {"product_type": "actor", "required": True},
        {"product_type": "motion", "required": True},
        {"product_type": "procprefab", "required": True},
        {"product_type": "azmodel", "required": True},
        {"product_type": "material", "required": False},
        {"product_type": "texture", "required": False},
        {"product_type": "pxmesh", "required": False},
    ]


def _collect_imported_observed(
    ap_import_payloads: List[Tuple[Path, Dict[str, Any]]],
    findings: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    observed: Dict[str, Dict[str, Any]] = {}

    for path, payload in ap_import_payloads:
        if payload.get("read_only") is not True:
            findings.append(
                _finding(
                    "ap_import_not_read_only",
                    "error",
                    "AP evidence import payload must remain read_only=true.",
                    {"path": str(path)},
                )
            )
            continue

        for key in (
            "asset_processor_execution_admitted",
            "o3de_execution_admitted",
            "cache_access_admitted",
            "live_database_access_admitted",
            "product_ids_claimed",
            "asset_ids_claimed",
            "source_uuids_claimed",
            "product_resolution_claimed",
            "spawn_admitted",
            "publish_admitted",
        ):
            if payload.get(key) is not False:
                findings.append(
                    _finding(
                        "ap_import_safety_mismatch",
                        "error",
                        "AP evidence import payload contains non-admitted execution or ID-claim flag.",
                        {"path": str(path), "field": key, "value": payload.get(key)},
                    )
                )

        confidence = QUALITY_TO_CONFIDENCE.get(
            str(payload.get("evidence_quality", "")).strip(),
            0.75,
        )
        mentions = _as_str_list(payload.get("observed_product_like_mentions"))
        for mention in mentions:
            product_type = _product_type_for_mention(mention)
            if product_type is None:
                continue
            if product_type in observed:
                continue
            observed[product_type] = {
                "product_type": product_type,
                "product_path_or_hint": mention,
                "evidence_status": "observed",
                "evidence_source": "imported_ap_evidence",
                "confidence": confidence,
            }

    return observed


def _build_observed_products(
    expected_products: List[Dict[str, Any]],
    imported_observed: Dict[str, Dict[str, Any]],
    fixture_observed: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    observed_products: List[Dict[str, Any]] = []
    for expected in expected_products:
        product_type = str(expected["product_type"])
        if product_type in imported_observed:
            observed_products.append(imported_observed[product_type])
            continue

        fixture_item = fixture_observed.get(product_type)
        if fixture_item:
            observed_products.append(
                {
                    "product_type": product_type,
                    "product_path_or_hint": str(fixture_item.get("product_path_or_hint", "")).strip()
                    or f"fixture-hint://{product_type}",
                    "evidence_status": "observed",
                    "evidence_source": "fixture",
                    "confidence": 0.8,
                }
            )
            continue

        observed_products.append(
            {
                "product_type": product_type,
                "product_path_or_hint": f"missing://{product_type}",
                "evidence_status": "missing",
                "evidence_source": "fixture",
                "confidence": 0.0,
            }
        )
    return observed_products


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        project_inventory_path = _resolve_repo_path(repo_root, args.project_inventory, "project_inventory")
        asset_inventory_path = _resolve_repo_path(
            repo_root, args.asset_candidate_inventory, "asset_candidate_inventory"
        )
        controlled_inventory_path = _resolve_repo_path(
            repo_root, args.controlled_inventory_report, "controlled_inventory_report"
        )
        fixture_report_path = _resolve_repo_path(repo_root, args.fixture_report, "fixture_report")
        ap_import_root = _resolve_repo_path(repo_root, args.ap_evidence_import_root, "ap_evidence_import_root")
        output_path = _resolve_repo_path(repo_root, args.output, "output")
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "report_type": REPORT_TYPE,
                    "status": "fail",
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 2

    required_paths = [
        ("project_inventory", project_inventory_path),
        ("asset_candidate_inventory", asset_inventory_path),
        ("controlled_inventory_report", controlled_inventory_path),
        ("fixture_report", fixture_report_path),
    ]
    missing = [label for label, path in required_paths if not path.exists()]
    if missing:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "report_type": REPORT_TYPE,
                    "status": "fail",
                    "error": "missing_required_input",
                    "missing": missing,
                },
                indent=2,
            )
        )
        return 1

    try:
        project_inventory = _read_json(project_inventory_path)
        asset_inventory = _read_json(asset_inventory_path)
        controlled_inventory = _read_json(controlled_inventory_path)
        fixture_report = _read_json(fixture_report_path)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "report_type": REPORT_TYPE,
                    "status": "fail",
                    "error": f"input_parse_failed: {exc}",
                },
                indent=2,
            )
        )
        return 1

    findings: List[Dict[str, Any]] = []

    if controlled_inventory.get("status") == "fail":
        findings.append(
            _finding(
                "controlled_inventory_report_fail",
                "error",
                "Controlled real evidence inventory report is fail.",
                {"path": _normalize(controlled_inventory_path, repo_root)},
            )
        )
    if controlled_inventory.get("execution_admitted") is not False:
        findings.append(
            _finding(
                "controlled_inventory_execution_admitted_not_allowed",
                "error",
                "Controlled inventory report must keep execution_admitted=false.",
                {"path": _normalize(controlled_inventory_path, repo_root)},
            )
        )
    if controlled_inventory.get("controlled_real_inventory_ready") is not True:
        findings.append(
            _finding(
                "controlled_inventory_not_ready",
                "warning",
                "Controlled inventory readiness is not true.",
                {"path": _normalize(controlled_inventory_path, repo_root)},
            )
        )

    project_inventory_id = str(project_inventory.get("inventory_id", "")).strip()
    asset_inventory_id = str(asset_inventory.get("inventory_id", "")).strip()
    if not project_inventory_id:
        findings.append(_finding("project_inventory_id_missing", "error", "Project inventory_id is required."))
    if not asset_inventory_id:
        findings.append(
            _finding("asset_candidate_inventory_id_missing", "error", "Asset candidate inventory_id is required.")
        )

    approved_input_roots = sorted(
        set(
            _as_str_list(project_inventory.get("known_asset_folders"))
            + _as_str_list(project_inventory.get("generated_asset_candidate_folders"))
        )
    )
    if not approved_input_roots:
        findings.append(_finding("approved_input_roots_missing", "error", "No approved input roots found."))

    candidates = asset_inventory.get("source_asset_candidates")
    if not isinstance(candidates, list):
        findings.append(
            _finding(
                "source_asset_candidates_not_array",
                "error",
                "source_asset_candidates must be an array.",
            )
        )
        candidates = []

    selected_candidate: Dict[str, Any] | None = None
    for candidate in candidates:
        if isinstance(candidate, dict):
            selected_candidate = candidate
            break
    if selected_candidate is None:
        findings.append(
            _finding(
                "source_candidate_missing",
                "error",
                "No source asset candidate is available for resolver extraction.",
            )
        )
        selected_candidate = {}

    candidate_id = str(selected_candidate.get("candidate_id", "")).strip() or "unknown-candidate"
    source_asset_path = str(selected_candidate.get("relative_path", "")).strip().replace("\\", "/")
    if not source_asset_path:
        findings.append(_finding("source_asset_path_missing", "error", "Selected source candidate missing relative_path."))
    elif not _is_safe_relative_path(source_asset_path):
        findings.append(
            _finding(
                "source_asset_path_invalid",
                "error",
                "Selected source candidate path must be safe and relative.",
                {"relative_path": source_asset_path},
            )
        )
    elif _contains_blocked_token(source_asset_path):
        findings.append(
            _finding(
                "source_asset_path_blocked",
                "error",
                "Selected source candidate path contains blocked tokens.",
                {"relative_path": source_asset_path},
            )
        )
    elif approved_input_roots and not _path_in_roots(source_asset_path, approved_input_roots):
        findings.append(
            _finding(
                "source_asset_path_outside_approved_roots",
                "error",
                "Selected source candidate path is outside approved input roots.",
                {"relative_path": source_asset_path, "approved_input_roots": approved_input_roots},
            )
        )

    ap_import_paths = _collect_ap_import_paths(args.ap_evidence_import, ap_import_root, repo_root)
    ap_import_payloads: List[Tuple[Path, Dict[str, Any]]] = []
    for path in ap_import_paths:
        normalized = _normalize(path, repo_root)
        if not normalized.startswith("examples/sandbox/ap-evidence-imports/"):
            findings.append(
                _finding(
                    "ap_evidence_import_path_outside_admitted_root",
                    "error",
                    "AP evidence imports must be located under examples/sandbox/ap-evidence-imports.",
                    {"path": normalized},
                )
            )
            continue
        try:
            payload = _read_json(path)
        except Exception as exc:
            findings.append(
                _finding(
                    "ap_evidence_import_parse_failed",
                    "error",
                    "AP evidence import JSON could not be parsed.",
                    {"path": normalized, "reason": str(exc)},
                )
            )
            continue
        ap_import_payloads.append((path, payload))

    imported_observed = _collect_imported_observed(ap_import_payloads, findings)
    fixture_observed = _load_fixture_observed(fixture_report)
    expected_products = _build_expected_products()
    observed_products = _build_observed_products(expected_products, imported_observed, fixture_observed)
    imported_product_types = sorted(imported_observed.keys())
    required_imported_types = list(REQUIRED_IMPORTED_PRODUCT_TYPES)
    missing_required_imported_types = sorted(
        set(required_imported_types) - set(imported_product_types)
    )
    fixture_fallback_product_types = sorted(
        str(item.get("product_type", "")).strip()
        for item in observed_products
        if str(item.get("evidence_source", "")).strip() == "fixture"
    )
    required_types_using_fixture_fallback = sorted(
        set(required_imported_types).intersection(fixture_fallback_product_types)
    )

    if not ap_import_payloads:
        findings.append(
            _finding(
                "required_ap_evidence_imports_missing_for_pass",
                "error",
                "Pass status requires bounded AP evidence import fixtures for pilot candidates.",
                {
                    "required_imported_product_types": required_imported_types,
                    "ap_import_root": _normalize(ap_import_root, repo_root),
                },
            )
        )

    if missing_required_imported_types:
        findings.append(
            _finding(
                "required_imported_product_coverage_missing",
                "error",
                "Imported AP evidence does not cover all required product types for pass status.",
                {
                    "required_imported_product_types": required_imported_types,
                    "imported_product_types": imported_product_types,
                    "missing_required_imported_product_types": missing_required_imported_types,
                },
            )
        )

    if required_types_using_fixture_fallback:
        findings.append(
            _finding(
                "required_types_using_fixture_fallback",
                "error",
                "Required product types cannot rely on fixture fallback when reporting pass.",
                {
                    "required_types_using_fixture_fallback": required_types_using_fixture_fallback,
                },
            )
        )

    status = _status_from_findings(findings)
    evidence_source_type = "imported_ap_evidence" if imported_observed else "fixture"
    job_suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    report: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "job_id": f"job-release-source-product-extract-{job_suffix}",
        "package_id": "maxine-release-pilot-bounded-resolver",
        "lane": "release_character",
        "status": status,
        "source_asset_reference": candidate_id,
        "source_asset_path": source_asset_path or "unknown-source-path",
        "evidence_source_type": evidence_source_type,
        "expected_products": expected_products,
        "observed_products": observed_products,
        "source_uuid_claim_status": "not_claimed",
        "asset_id_claim_status": "not_claimed",
        "product_id_claim_status": "not_claimed",
        "cache_access_status": "blocked",
        "live_db_access_status": "blocked",
        "findings": findings,
        "manifest_attachment": {
            "target_path": ATTACHMENT_TARGET_PATH,
            "future_target_path": ATTACHMENT_FUTURE_TARGET_PATH,
            "qc_check": {
                "check_id": CHECK_ID,
                "result": status,
                "severity": _qc_severity(status),
                "details": {
                    "extraction_mode": "admitted_evidence_sources_only",
                    "source_project_inventory_path": _normalize(project_inventory_path, repo_root),
                    "source_asset_candidate_inventory_path": _normalize(asset_inventory_path, repo_root),
                    "source_controlled_inventory_report_path": _normalize(controlled_inventory_path, repo_root),
                    "source_fixture_report_path": _normalize(fixture_report_path, repo_root),
                    "ap_evidence_import_paths": [_normalize(path, repo_root) for path, _ in ap_import_payloads],
                    "candidate_id": candidate_id,
                    "required_imported_product_types": required_imported_types,
                    "imported_product_types": imported_product_types,
                    "missing_required_imported_product_types": missing_required_imported_types,
                    "required_types_using_fixture_fallback": required_types_using_fixture_fallback,
                },
            },
        },
        "safety_summary": (
            "Bounded source/product evidence extraction used admitted controlled inventory records, "
            "approved local inputs, imported AP evidence fixtures for required product coverage, "
            "sandbox evidence links, and fixture-backed hints only where allowed."
        ),
        "explicit_non_admissions": NON_ADMISSIONS,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "extraction_inputs": {
            "project_inventory_id": project_inventory_id,
            "asset_candidate_inventory_id": asset_inventory_id,
            "controlled_inventory_report_status": str(controlled_inventory.get("status", "")),
            "controlled_inventory_ready": controlled_inventory.get("controlled_real_inventory_ready"),
            "ap_evidence_import_count": len(ap_import_payloads),
            "ap_import_root": _normalize(ap_import_root, repo_root),
            "required_imported_product_types": required_imported_types,
            "imported_product_types": imported_product_types,
            "missing_required_imported_product_types": missing_required_imported_types,
            "required_imported_coverage_complete": not missing_required_imported_types,
            "fixture_fallback_product_types": fixture_fallback_product_types,
            "required_types_using_fixture_fallback": required_types_using_fixture_fallback,
        },
    }

    _write_json(output_path, report)
    report["output_path"] = _normalize(output_path, repo_root)
    print(json.dumps(report, indent=2))

    if status == "pass":
        return 0
    if status == "warn":
        return 0 if args.allow_warn else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
