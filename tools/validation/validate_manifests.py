#!/usr/bin/env python3
"""Validate MAXINE production-readiness manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.o3de.product_matrix_resolver import validate_expected_products
from tools.qc.mixamo_policy import validate_mixamo_policy
from tools.validation.maxine_paths import MXN_INPUT_MISSING
from tools.validation.results import ValidationResult, combine_statuses
from tools.validation.schema_utils import load_json, print_result, schema_validate


DEFAULT_MANIFESTS = [
    REPO_ROOT / "examples" / "manifests" / "draft_mesh.pass.example.json",
    REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json",
    REPO_ROOT / "examples" / "manifests" / "external_rig_import.pending_manual.example.json",
    REPO_ROOT / "examples" / "manifests" / "failure.example.json",
]
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.job-manifest.schema.json"
EVIDENCE_BUNDLE_SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine.evidence-bundle.schema.json"
REQUIRED_TOP_LEVEL = [
    "schema_version",
    "job",
    "identity",
    "inputs",
    "generation",
    "dcc_conform",
    "o3de",
    "qc",
    "runtime_validation",
    "evidence",
    "provenance",
    "undo",
    "cleanup",
]
VALID_LANES = {"draft_mesh", "release_rigged", "external_rig_import"}
VALID_STATUSES = {"pass", "warn", "fail", "pending_manual"}


def _resolve(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (REPO_ROOT / path)


def _validate_evidence_refs(manifest: Dict[str, Any], strict: bool) -> ValidationResult:
    result = ValidationResult()
    evidence = manifest.get("evidence") if isinstance(manifest.get("evidence"), dict) else {}
    refs = evidence.get("refs", [])
    if strict and not refs:
        result.add_error(MXN_INPUT_MISSING, "Strict manifest validation requires evidence.refs entries.")
    if not isinstance(refs, list):
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", "evidence.refs must be an array.")
        return result
    if not strict:
        return result
    for ref in refs:
        if not isinstance(ref, dict):
            result.add_error("MXN_SCHEMA_VALIDATION_FAIL", "Each evidence ref must be an object.")
            continue
        ref_path = str(ref.get("path", "")).strip()
        if not ref_path:
            result.add_error(MXN_INPUT_MISSING, "Evidence ref is missing path.")
            continue
        resolved = _resolve(ref_path)
        if not resolved.exists():
            result.add_error(MXN_INPUT_MISSING, f"Evidence ref path not found: {ref_path}")
    bundle_ref = str(evidence.get("bundle_ref", "")).strip()
    if strict and bundle_ref and not _resolve(bundle_ref).exists():
        result.add_error(MXN_INPUT_MISSING, f"Evidence bundle ref not found: {bundle_ref}")
    elif strict and bundle_ref:
        try:
            result.merge(schema_validate(load_json(_resolve(bundle_ref)), load_json(EVIDENCE_BUNDLE_SCHEMA_PATH)))
        except Exception as exc:
            result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Evidence bundle validation failed: {exc}")
    return result


def validate_manifest(path: Path, *, strict: bool = False) -> ValidationResult:
    result = ValidationResult()
    if not path.exists():
        result.add_error(MXN_INPUT_MISSING, f"Manifest not found: {path}")
        return result
    if not SCHEMA_PATH.exists():
        result.add_error("MXN_VALIDATION_TOOL_UNAVAILABLE", f"Schema not found: {SCHEMA_PATH}")
        return result

    try:
        manifest = load_json(path)
        schema = load_json(SCHEMA_PATH)
    except Exception as exc:
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Could not parse manifest or schema: {exc}")
        return result

    result.merge(schema_validate(manifest, schema))
    for field in REQUIRED_TOP_LEVEL:
        if field not in manifest:
            result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Missing required manifest field: {field}")
    result.merge(_validate_evidence_refs(manifest, strict))

    job = manifest.get("job") if isinstance(manifest.get("job"), dict) else {}
    lane = str(job.get("lane", "")).strip()
    if lane not in VALID_LANES:
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Invalid job.lane: {lane!r}")
    if str(job.get("status", "")).strip() not in VALID_STATUSES:
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Invalid job.status: {job.get('status')!r}")
    qc = manifest.get("qc") if isinstance(manifest.get("qc"), dict) else {}
    if str(qc.get("overall", "")).strip() not in VALID_STATUSES:
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Invalid qc.overall: {qc.get('overall')!r}")
    o3de = manifest.get("o3de") if isinstance(manifest.get("o3de"), dict) else {}
    product_resolution = o3de.get("product_resolution") if isinstance(o3de.get("product_resolution"), dict) else {}
    if lane in {"release_rigged", "external_rig_import"} and product_resolution.get("cache_heuristic_used") is True:
        result.add_error(
            "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
            "Release manifests cannot use newest/best-looking cache-file heuristics as product resolution.",
        )

    products = o3de.get("actual_products", [])
    if (
        job.get("status") != "fail"
        and isinstance(products, list)
        and lane in {"draft_mesh", "release_rigged", "external_rig_import"}
    ):
        product_result = validate_expected_products(
            lane,
            products,
            strict=strict,
            publish_tier=str(product_resolution.get("publish_tier", "package")),
            physics_enabled=bool(product_resolution.get("physics_enabled", False)),
            materialized=bool(product_resolution.get("materialized", False)),
            collider_waiver=bool(product_resolution.get("collider_waiver", False)),
            material_waiver=bool(product_resolution.get("material_waiver", False)),
            external_motion_required=bool(product_resolution.get("motion_required", False)),
            cache_heuristic_used=bool(product_resolution.get("cache_heuristic_used", False)),
        )
        result.merge(product_result)

    mixamo_result = validate_mixamo_policy(manifest, offline=True)
    if mixamo_result.status == "fail":
        result.merge(mixamo_result)
    elif mixamo_result.status == "pending_manual" and job.get("status") == "pending_manual":
        result.warning_codes.extend(code for code in mixamo_result.warning_codes if code not in result.warning_codes)
        result.messages.extend(mixamo_result.messages)

    result.status = combine_statuses([result.status])
    result.details["manifest_path"] = str(path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MAXINE production-readiness manifests.")
    parser.add_argument("manifest", nargs="*", help="Manifest paths. Defaults to production-readiness examples.")
    parser.add_argument("--strict", action="store_true", help="Require referenced evidence files and release checks.")
    parser.add_argument("--allow-warn", action="store_true", help="Return zero when validation produces warnings.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = [_resolve(raw) for raw in args.manifest] if args.manifest else DEFAULT_MANIFESTS
    statuses: List[str] = []
    for path in paths:
        result = validate_manifest(path, strict=args.strict)
        print_result(str(path), result)
        statuses.append(result.status)
    overall = combine_statuses(statuses)
    print(f"Overall manifest validation: {overall}")
    if overall == "pass":
        return 0
    if overall in {"warn", "pending_manual"} and args.allow_warn:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
