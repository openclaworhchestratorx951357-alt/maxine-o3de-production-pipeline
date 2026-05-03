#!/usr/bin/env python3
"""Evaluate non-authoritative AP resolver readiness from existing manifest evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


READINESS_VERSION = "ap-resolver-readiness-1"
TRUE_FALSE = {"true", "false"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON from {path}: {exc}") from exc


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_path(base: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


def parse_bool_arg(raw: str, flag: str) -> bool:
    value = str(raw).strip().lower()
    if value not in TRUE_FALSE:
        raise ValueError(f"{flag} must be true or false.")
    return value == "true"


def parse_float_01(value: float, flag: str) -> float:
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValueError(f"{flag} must be a number.") from exc
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"{flag} must be between 0.0 and 1.0.")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate non-authoritative AP resolver readiness from source/product/file evidence."
    )
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output", default="", help="Optional output manifest path (defaults to in-place)")
    parser.add_argument("--min-source-confidence", type=float, default=0.70, help="Min source confidence")
    parser.add_argument("--min-product-confidence", type=float, default=0.40, help="Min product confidence")
    parser.add_argument(
        "--require-existing-required",
        default="true",
        help="Require existing files for required product types (true|false)",
    )
    return parser.parse_args()


def as_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip().lower() for v in value if str(v).strip()]


def first_float(*values: Any) -> float:
    for value in values:
        try:
            if value is None:
                continue
            return float(value)
        except Exception:  # noqa: BLE001
            continue
    return 0.0


def gather_hazard_violations(block_name: str, safety_block: Dict[str, Any]) -> List[str]:
    hazards: List[Tuple[str, str]] = [
        ("authoritative_resolution", "authoritative_resolution"),
        ("claimed_asset_ids", "claimed_asset_ids"),
        ("claimed_products_resolved", "claimed_products_resolved"),
        ("product_candidate_is_resolution", "product_candidate_is_resolution"),
        ("file_existence_is_resolution", "file_existence_is_resolution"),
        ("published_or_spawned", "published_or_spawned"),
        ("ran_o3de_editor", "ran_o3de_editor"),
        ("ran_asset_processor", "ran_asset_processor"),
        ("opened_database", "opened_database"),
    ]
    violations: List[str] = []
    for field, label in hazards:
        if bool(safety_block.get(field, False)):
            violations.append(f"{block_name}.{label}=true")
    return violations


def recommended_action_for_status(status: str) -> str:
    if status == "ready_for_authoritative_resolution_attempt":
        return "Proceed to a future authoritative resolver dry-run contract step."
    if status == "blocked_safety_violation":
        return "Fix safety violations in upstream evidence before any resolver attempt."
    if status == "blocked_missing_source_identity":
        return "Run source identity matching and provide a confidence-qualified candidate source match."
    if status == "blocked_missing_product_candidates":
        return "Run candidate product matching with source-linked product evidence."
    if status == "blocked_missing_required_product_files":
        return "Provide required product candidate coverage and required file existence evidence."
    return "Complete missing source/product/file evidence blocks and rerun readiness evaluation."


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        min_source_confidence = parse_float_01(args.min_source_confidence, "--min-source-confidence")
        min_product_confidence = parse_float_01(args.min_product_confidence, "--min-product-confidence")
        require_existing_required = parse_bool_arg(args.require_existing_required, "--require-existing-required")
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    manifest_path = resolve_path(repo_root, args.manifest)
    if not manifest_path.exists():
        print(f"FAIL: manifest file not found: {manifest_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    o3de = manifest.get("o3de")
    if not isinstance(o3de, dict):
        print("FAIL: manifest.o3de is missing.")
        return 2

    asset_resolution = o3de.get("asset_resolution")
    source_match = o3de.get("ap_source_identity_match")
    product_match = o3de.get("ap_product_candidate_match")
    file_validation = o3de.get("ap_product_file_validation")

    required_products: List[str] = []
    if isinstance(asset_resolution, dict):
        required_products = as_string_list(asset_resolution.get("required_products", []))

    source_present = isinstance(source_match, dict)
    source_status = str(source_match.get("status", "missing")) if source_present else "missing"
    source_best_match = source_match.get("best_match", {}) if source_present else {}
    if not isinstance(source_best_match, dict):
        source_best_match = {}
    source_best_confidence = first_float(
        source_best_match.get("confidence"),
        source_match.get("summary", {}).get("best_confidence") if source_present else None,
    )
    source_passes = source_status == "candidate_match" and source_best_confidence >= min_source_confidence

    product_present = isinstance(product_match, dict)
    product_status = str(product_match.get("status", "missing")) if product_present else "missing"
    product_summary = product_match.get("summary", {}) if product_present else {}
    if not isinstance(product_summary, dict):
        product_summary = {}
    product_candidate_count = int(first_float(product_summary.get("candidate_product_count", 0)))
    product_best_confidence = first_float(product_summary.get("best_product_confidence", 0.0))
    product_meets_min_confidence = product_best_confidence >= min_product_confidence
    product_passes = product_status == "candidate_products" and product_candidate_count > 0

    file_present = isinstance(file_validation, dict)
    file_status = str(file_validation.get("status", "missing")) if file_present else "missing"
    file_summary = file_validation.get("summary", {}) if file_present else {}
    if not isinstance(file_summary, dict):
        file_summary = {}
    candidates_with_existing_file = int(first_float(file_summary.get("candidates_with_existing_file", 0)))
    required_product_existing_file_count = int(first_float(file_summary.get("required_product_existing_file_count", 0)))
    file_passes = candidates_with_existing_file > 0

    missing_required_product_types = as_string_list(product_summary.get("missing_required_product_types", []))
    required_product_types_without_existing_file = as_string_list(
        file_summary.get("required_product_types_without_existing_file", [])
    )

    required_coverage_passes = len(missing_required_product_types) == 0
    if require_existing_required and file_present:
        if len(required_product_types_without_existing_file) > 0:
            required_coverage_passes = False

    source_safety = source_match.get("safety", {}) if source_present else {}
    product_safety = product_match.get("safety", {}) if product_present else {}
    file_safety = file_validation.get("safety", {}) if file_present else {}
    if not isinstance(source_safety, dict):
        source_safety = {}
    if not isinstance(product_safety, dict):
        product_safety = {}
    if not isinstance(file_safety, dict):
        file_safety = {}

    safety_violations: List[str] = []
    safety_violations.extend(gather_hazard_violations("ap_source_identity_match", source_safety))
    safety_violations.extend(gather_hazard_violations("ap_product_candidate_match", product_safety))
    safety_violations.extend(gather_hazard_violations("ap_product_file_validation", file_safety))
    safety_passes = len(safety_violations) == 0

    blockers: List[str] = []
    warnings: List[str] = []

    if not product_meets_min_confidence and product_present and product_candidate_count > 0:
        warnings.append(
            "Product candidate evidence exists but best_product_confidence is below min_product_confidence threshold."
        )

    if not file_present:
        warnings.append("ap_product_file_validation is missing; file existence evidence is incomplete.")

    if not isinstance(asset_resolution, dict):
        warnings.append("asset_resolution block is missing; required contract checks may be incomplete.")

    if not safety_passes:
        status = "blocked_safety_violation"
        blockers.extend(safety_violations)
    elif not source_passes:
        status = "blocked_missing_source_identity"
        blockers.append(
            f"source_identity_evidence_failed(status={source_status}, best_confidence={source_best_confidence:.2f})"
        )
    elif not product_passes:
        status = "blocked_missing_product_candidates"
        blockers.append(
            f"product_candidate_evidence_failed(status={product_status}, candidate_product_count={product_candidate_count})"
        )
    elif not required_coverage_passes:
        status = "blocked_missing_required_product_files"
        if missing_required_product_types:
            blockers.append(f"missing_required_product_types={','.join(missing_required_product_types)}")
        if require_existing_required and required_product_types_without_existing_file:
            blockers.append(
                "required_product_types_without_existing_file="
                + ",".join(required_product_types_without_existing_file)
            )
    elif not file_present or not file_passes:
        status = "incomplete_evidence"
        blockers.append(
            f"file_existence_evidence_incomplete(status={file_status}, candidates_with_existing_file={candidates_with_existing_file})"
        )
    else:
        status = "ready_for_authoritative_resolution_attempt"

    readiness_block: Dict[str, Any] = {
        "readiness_version": READINESS_VERSION,
        "status": status,
        "dimensions": {
            "source_identity_evidence": {
                "present": source_present,
                "status": source_status,
                "best_confidence": source_best_confidence,
                "min_source_confidence": min_source_confidence,
                "passes": source_passes,
            },
            "product_candidate_evidence": {
                "present": product_present,
                "status": product_status,
                "candidate_product_count": product_candidate_count,
                "best_product_confidence": product_best_confidence,
                "min_product_confidence": min_product_confidence,
                "meets_min_confidence": product_meets_min_confidence,
                "passes": product_passes,
            },
            "file_existence_evidence": {
                "present": file_present,
                "status": file_status,
                "candidates_with_existing_file": candidates_with_existing_file,
                "required_product_existing_file_count": required_product_existing_file_count,
                "passes": file_passes,
            },
            "required_contract_coverage": {
                "required_products": required_products,
                "missing_required_product_types": missing_required_product_types,
                "required_product_types_without_existing_file": required_product_types_without_existing_file,
                "require_existing_required": require_existing_required,
                "passes": required_coverage_passes,
            },
            "safety_compliance": {
                "passes": safety_passes,
                "violations": safety_violations,
            },
        },
        "blockers": blockers,
        "warnings": warnings,
        "recommended_next_action": recommended_action_for_status(status),
        "safety": {
            "read_only": True,
            "opened_database": False,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": False,
            "readiness_is_resolution": False,
            "published_or_spawned": False,
        },
        "updated_utc": utc_now(),
    }

    o3de["ap_resolver_readiness"] = readiness_block

    output_path = resolve_path(repo_root, args.output) if args.output else manifest_path
    write_json(output_path, manifest)

    validator_script = repo_root / "tools" / "manifest-validator" / "validate_manifest.py"
    cmd = [sys.executable, str(validator_script), str(output_path)]
    vr = subprocess.run(cmd, capture_output=True, text=True)
    if vr.stdout:
        print(vr.stdout.strip())
    if vr.stderr:
        print(vr.stderr.strip())
    if vr.returncode != 0:
        print(f"FAIL: manifest validation failed after readiness evaluation: {output_path}")
        return vr.returncode

    print(
        "PASS: AP resolver readiness evaluated. "
        f"status={status} source_pass={source_passes} product_pass={product_passes} "
        f"file_pass={file_passes} required_coverage_pass={required_coverage_passes} "
        f"safety_pass={safety_passes} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
