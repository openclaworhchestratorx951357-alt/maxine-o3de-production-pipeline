#!/usr/bin/env python3
"""Extract read-only AP product identity proof evidence from manifest data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


PROOF_VERSION = "ap-product-identity-proof-1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_path(base: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON from {path}: {exc}") from exc


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract AP product identity proof from manifest evidence only.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output", default="", help="Optional output path (defaults to in-place)")
    parser.add_argument("--min-source-confidence", type=float, default=0.70, help="Min source confidence")
    parser.add_argument("--min-product-confidence", type=float, default=0.40, help="Min product confidence")
    return parser.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def as_string_list(value: Any) -> List[str]:
    return [safe_text(v).strip().lower() for v in as_list(value) if safe_text(v).strip()]


def as_bool(value: Any) -> bool:
    return bool(value)


def first_float(*values: Any) -> float:
    for value in values:
        try:
            if value is None:
                continue
            return float(value)
        except Exception:  # noqa: BLE001
            continue
    return 0.0


def float_01(value: float, label: str) -> float:
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if parsed < 0.0 or parsed > 1.0:
        raise ValueError(f"{label} must be between 0.0 and 1.0.")
    return parsed


def gather_safety_violations(block_name: str, safety: Dict[str, Any]) -> List[str]:
    hazard_fields = [
        "authoritative_resolution",
        "claimed_asset_ids",
        "claimed_products_resolved",
        "product_identity_is_resolution",
        "product_candidate_is_resolution",
        "file_existence_is_resolution",
        "freshness_proof_is_resolution",
        "platform_proof_is_resolution",
        "source_identity_is_product_resolution",
        "job_state_is_resolution",
        "readiness_is_resolution",
        "published_or_spawned",
        "ran_o3de_editor",
        "ran_asset_processor",
        "opened_database",
        "modified_database",
    ]
    violations: List[str] = []
    for field in hazard_fields:
        if as_bool(safety.get(field, False)):
            violations.append(f"{block_name}.{field}=true")
    return violations


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        min_source_confidence = float_01(args.min_source_confidence, "--min-source-confidence")
        min_product_confidence = float_01(args.min_product_confidence, "--min-product-confidence")
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
    source_identity = o3de.get("ap_source_identity_match")
    product_candidates = o3de.get("ap_product_candidate_match")
    file_validation = o3de.get("ap_product_file_validation")
    job_state = o3de.get("ap_job_state_proof")
    platform_proof = o3de.get("ap_platform_proof")
    freshness_proof = o3de.get("ap_product_freshness_proof")

    warnings: List[str] = []
    blockers: List[str] = []

    required_products = as_string_list(asset_resolution.get("required_products")) if isinstance(asset_resolution, dict) else []
    optional_products = as_string_list(asset_resolution.get("optional_products")) if isinstance(asset_resolution, dict) else []
    planned_products = as_string_list(asset_resolution.get("planned_products")) if isinstance(asset_resolution, dict) else []

    if not isinstance(asset_resolution, dict):
        warnings.append("asset_resolution is missing; expected product contract support is reduced.")

    source_status = safe_text(source_identity.get("status")) if isinstance(source_identity, dict) else "missing"
    source_best_match = source_identity.get("best_match", {}) if isinstance(source_identity, dict) else {}
    if not isinstance(source_best_match, dict):
        source_best_match = {}
    source_confidence = first_float(
        source_best_match.get("confidence"),
        source_identity.get("summary", {}).get("best_confidence") if isinstance(source_identity, dict) else None,
    )
    source_supported = source_status == "candidate_match" and source_confidence >= min_source_confidence

    product_status = safe_text(product_candidates.get("status")) if isinstance(product_candidates, dict) else "missing"
    product_summary = product_candidates.get("summary", {}) if isinstance(product_candidates, dict) else {}
    if not isinstance(product_summary, dict):
        product_summary = {}
    product_candidate_list = as_list(product_candidates.get("candidate_products")) if isinstance(product_candidates, dict) else []
    candidate_product_count = int(first_float(product_summary.get("candidate_product_count"), len(product_candidate_list)))
    best_product_confidence = first_float(product_summary.get("best_product_confidence"), 0.0)
    product_supported = (
        product_status == "candidate_products"
        and candidate_product_count > 0
        and best_product_confidence >= min_product_confidence
    )

    missing_required_types = as_string_list(product_summary.get("missing_required_product_types"))
    expected_product_type_supported = product_supported and len(missing_required_types) == 0

    file_status = safe_text(file_validation.get("status")) if isinstance(file_validation, dict) else "missing"
    file_summary = file_validation.get("summary", {}) if isinstance(file_validation, dict) else {}
    if not isinstance(file_summary, dict):
        file_summary = {}
    candidates_with_existing_file = int(first_float(file_summary.get("candidates_with_existing_file"), 0))
    required_types_without_files = as_string_list(file_summary.get("required_product_types_without_existing_file"))
    product_file_supported = candidates_with_existing_file > 0 and len(required_types_without_files) == 0

    job_status = safe_text(job_state.get("status")) if isinstance(job_state, dict) else "missing"
    job_summary = job_state.get("summary", {}) if isinstance(job_state, dict) else {}
    if not isinstance(job_summary, dict):
        job_summary = {}
    candidate_job_count = int(first_float(job_summary.get("candidate_job_count"), len(as_list(job_state.get("candidate_job_rows")) if isinstance(job_state, dict) else [])))
    job_state_supported = job_status == "candidate_job_state_found" and candidate_job_count > 0

    platform_status = safe_text(platform_proof.get("status")) if isinstance(platform_proof, dict) else "missing"
    platform_summary = platform_proof.get("summary", {}) if isinstance(platform_proof, dict) else {}
    if not isinstance(platform_summary, dict):
        platform_summary = {}
    matching_hint_count = int(first_float(platform_summary.get("matching_hint_count"), len(as_list(platform_proof.get("matching_hints")) if isinstance(platform_proof, dict) else [])))
    platform_supported = platform_status == "candidate_platform_found" and matching_hint_count > 0

    freshness_status = safe_text(freshness_proof.get("status")) if isinstance(freshness_proof, dict) else "missing"
    freshness_summary = freshness_proof.get("summary", {}) if isinstance(freshness_proof, dict) else {}
    if not isinstance(freshness_summary, dict):
        freshness_summary = {}
    freshness_support_count = int(first_float(freshness_summary.get("product_newer_or_equal_source_count"), 0))
    freshness_supported = freshness_status == "candidate_freshness_supported" and freshness_support_count > 0

    safety_violations: List[str] = []
    if isinstance(source_identity, dict):
        safety_violations.extend(gather_safety_violations("ap_source_identity_match", source_identity.get("safety", {})))
    if isinstance(product_candidates, dict):
        safety_violations.extend(
            gather_safety_violations("ap_product_candidate_match", product_candidates.get("safety", {}))
        )
    if isinstance(file_validation, dict):
        safety_violations.extend(gather_safety_violations("ap_product_file_validation", file_validation.get("safety", {})))
    if isinstance(job_state, dict):
        safety_violations.extend(gather_safety_violations("ap_job_state_proof", job_state.get("safety", {})))
    if isinstance(platform_proof, dict):
        safety_violations.extend(gather_safety_violations("ap_platform_proof", platform_proof.get("safety", {})))
    if isinstance(freshness_proof, dict):
        safety_violations.extend(
            gather_safety_violations("ap_product_freshness_proof", freshness_proof.get("safety", {}))
        )

    if safety_violations:
        blockers.extend(safety_violations)

    dimensions = {
        "source_identity_supported": {
            "passes": source_supported,
            "status": source_status,
            "best_confidence": source_confidence,
            "min_confidence": min_source_confidence,
        },
        "expected_product_type_supported": {
            "passes": expected_product_type_supported,
            "required_products": required_products,
            "optional_products": optional_products,
            "planned_products": planned_products,
            "missing_required_product_types": missing_required_types,
        },
        "product_candidate_supported": {
            "passes": product_supported,
            "status": product_status,
            "candidate_product_count": candidate_product_count,
            "best_product_confidence": best_product_confidence,
            "min_confidence": min_product_confidence,
        },
        "product_file_supported": {
            "passes": product_file_supported,
            "status": file_status,
            "candidates_with_existing_file": candidates_with_existing_file,
            "required_product_types_without_existing_file": required_types_without_files,
        },
        "job_state_supported": {
            "passes": job_state_supported,
            "status": job_status,
            "candidate_job_count": candidate_job_count,
        },
        "platform_supported": {
            "passes": platform_supported,
            "status": platform_status,
            "matching_hint_count": matching_hint_count,
        },
        "freshness_supported": {
            "passes": freshness_supported,
            "status": freshness_status,
            "product_newer_or_equal_source_count": freshness_support_count,
        },
    }

    for name, block in dimensions.items():
        if not as_bool(block.get("passes", False)):
            blockers.append(f"{name}=false")

    identity_candidates: List[Dict[str, Any]] = []
    for idx, candidate in enumerate(product_candidate_list):
        if not isinstance(candidate, dict):
            continue
        confidence = first_float(candidate.get("confidence"), 0.0)
        if confidence < min_product_confidence:
            continue
        identity_candidates.append(
            {
                "candidate_index": idx,
                "database_path": safe_text(candidate.get("database_path")),
                "table_name": safe_text(candidate.get("table_name")),
                "row_index": candidate.get("row_index"),
                "confidence": confidence,
                "candidate_product_types": as_string_list(candidate.get("candidate_product_types")),
                "expected_product_match": as_string_list(candidate.get("expected_product_match")),
                "required_product_match": as_string_list(candidate.get("required_product_match")),
                "optional_product_match": as_string_list(candidate.get("optional_product_match")),
                "planned_product_match": as_string_list(candidate.get("planned_product_match")),
                "link_reason_codes": [safe_text(x) for x in as_list(candidate.get("link_reason_codes")) if safe_text(x)],
                "type_reason_codes": [safe_text(x) for x in as_list(candidate.get("type_reason_codes")) if safe_text(x)],
                "evidence_support": {
                    "source_identity_supported": source_supported,
                    "job_state_supported": job_state_supported,
                    "platform_supported": platform_supported,
                    "freshness_supported": freshness_supported,
                    "product_file_supported": product_file_supported,
                },
            }
        )

    all_dimensions_pass = all(as_bool(block.get("passes", False)) for block in dimensions.values())
    if safety_violations:
        status = "blocked_safety_violation"
    elif all_dimensions_pass:
        status = "candidate_product_identity_supported"
    else:
        status = "incomplete_product_identity"

    if not identity_candidates:
        warnings.append("No identity_candidates met min product confidence from product candidate evidence.")

    summary = {
        "dimension_count": len(dimensions),
        "passing_dimension_count": sum(1 for block in dimensions.values() if as_bool(block.get("passes", False))),
        "all_dimensions_pass": all_dimensions_pass,
        "identity_candidate_count": len(identity_candidates),
        "product_candidates_considered": len(product_candidate_list),
        "required_product_count": len(required_products),
        "missing_required_product_types_count": len(missing_required_types),
        "best_identity_candidate_confidence": max((first_float(c.get("confidence")) for c in identity_candidates), default=0.0),
    }

    result_block = {
        "proof_version": PROOF_VERSION,
        "status": status,
        "dimensions": dimensions,
        "blockers": blockers,
        "warnings": warnings,
        "identity_candidates": identity_candidates,
        "summary": summary,
        "safety": {
            "read_only": True,
            "opened_database": False,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": False,
            "product_identity_is_resolution": False,
        },
        "updated_utc": utc_now(),
    }

    o3de["ap_product_identity_proof"] = result_block

    output_path = resolve_path(repo_root, args.output) if args.output else manifest_path
    try:
        write_json(output_path, manifest)
    except Exception as exc:
        print(f"FAIL: unable to write output manifest: {exc}")
        return 2

    validator_script = repo_root / "tools" / "manifest-validator" / "validate_manifest.py"
    cmd = [sys.executable, str(validator_script), str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        print(f"FAIL: manifest validation failed after AP product identity proof update: {output_path}")
        return result.returncode

    print(
        "PASS: AP product identity proof extraction recorded. "
        f"status={status} passing_dimensions={summary['passing_dimension_count']}/{summary['dimension_count']} "
        f"identity_candidates={len(identity_candidates)} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
