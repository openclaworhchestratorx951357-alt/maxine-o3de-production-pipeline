#!/usr/bin/env python3
"""Create a read-only dry-run plan for future authoritative product resolution."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


VALID_PLAN_STATUSES = {"dry_run_ready", "dry_run_blocked", "dry_run_incomplete"}
REQUIRED_TOP_LEVEL = [
    "schema_version",
    "plan_id",
    "status",
    "source_manifest",
    "required_proofs",
    "available_evidence",
    "missing_proofs",
    "proposed_actions",
    "forbidden_actions",
    "safety",
]
REQUIRED_PROOF_IDS = [
    "source_identity_proof",
    "expected_product_type_proof",
    "product_file_existence_proof",
    "asset_processor_job_success_proof",
    "platform_proof",
    "product_freshness_proof",
    "product_identity_proof",
    "safety_compliance_proof",
]


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
    parser = argparse.ArgumentParser(description="Plan future authoritative resolver requirements in dry-run mode.")
    parser.add_argument("--manifest", required=True, help="Path to input manifest JSON")
    parser.add_argument("--output", required=True, help="Path to output dry-run plan JSON")
    parser.add_argument(
        "--plan-schema",
        default="schemas/maxine_authoritative_resolver_plan.schema.json",
        help="Plan schema path for optional jsonschema validation",
    )
    return parser.parse_args()


def as_list_of_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def as_bool(value: Any) -> bool:
    return bool(value is True)


def minimal_validate_plan(plan: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for field in REQUIRED_TOP_LEVEL:
        if field not in plan:
            errors.append(f"Missing required field: {field}")

    status = plan.get("status")
    if status not in VALID_PLAN_STATUSES:
        errors.append(f"Invalid status: {status!r}")

    required_proofs = plan.get("required_proofs")
    if not isinstance(required_proofs, list):
        errors.append("required_proofs must be an array")
    else:
        seen: List[str] = []
        for idx, item in enumerate(required_proofs):
            if not isinstance(item, dict):
                errors.append(f"required_proofs[{idx}] must be an object")
                continue
            for field in ("id", "description", "required", "satisfied", "evidence_ref"):
                if field not in item:
                    errors.append(f"required_proofs[{idx}] missing field: {field}")
            proof_id = str(item.get("id", "")).strip()
            if proof_id:
                seen.append(proof_id)
        for proof_id in REQUIRED_PROOF_IDS:
            if proof_id not in seen:
                errors.append(f"required_proofs missing id: {proof_id}")

    safety = plan.get("safety")
    if not isinstance(safety, dict):
        errors.append("safety must be an object")
    else:
        required_safety = [
            "read_only",
            "writes_resolved_products",
            "runs_o3de_editor",
            "runs_asset_processor",
            "opens_database",
            "modifies_database",
            "spawns_entities",
            "publishes_prefabs",
            "claims_asset_ids",
        ]
        for field in required_safety:
            if field not in safety:
                errors.append(f"safety missing field: {field}")
        if safety.get("read_only") is not True:
            errors.append("safety.read_only must be true")
        false_fields = [
            "writes_resolved_products",
            "runs_o3de_editor",
            "runs_asset_processor",
            "opens_database",
            "modifies_database",
            "spawns_entities",
            "publishes_prefabs",
            "claims_asset_ids",
        ]
        for field in false_fields:
            if safety.get(field) is not False:
                errors.append(f"safety.{field} must be false")

    return errors


def jsonschema_validate(plan: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        return False, [f"jsonschema import failed: {exc}"]

    validator = Draft202012Validator(schema)
    all_errors = sorted(validator.iter_errors(plan), key=lambda err: list(err.path))
    if not all_errors:
        return True, []
    messages: List[str] = []
    for err in all_errors:
        loc = ".".join(str(part) for part in err.absolute_path) or "<root>"
        messages.append(f"{loc}: {err.message}")
    return False, messages


def build_proof(
    proof_id: str,
    description: str,
    satisfied: bool,
    evidence_ref: str,
) -> Dict[str, Any]:
    return {
        "id": proof_id,
        "description": description,
        "required": True,
        "satisfied": bool(satisfied),
        "evidence_ref": evidence_ref,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    manifest_path = resolve_path(repo_root, args.manifest)
    output_path = resolve_path(repo_root, args.output)
    schema_path = resolve_path(repo_root, args.plan_schema)

    if not manifest_path.exists():
        print(f"FAIL: manifest not found: {manifest_path}")
        return 2
    if not schema_path.exists():
        print(f"FAIL: plan schema not found: {schema_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    try:
        _schema = load_json(schema_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    o3de = manifest.get("o3de")
    if not isinstance(o3de, dict):
        print("FAIL: manifest.o3de is missing.")
        return 2

    readiness = o3de.get("ap_resolver_readiness")
    asset_resolution = o3de.get("asset_resolution")
    source_match = o3de.get("ap_source_identity_match")
    product_match = o3de.get("ap_product_candidate_match")
    file_validation = o3de.get("ap_product_file_validation")

    readiness_status = str(readiness.get("status", "missing")) if isinstance(readiness, dict) else "missing"
    readiness_dims = readiness.get("dimensions", {}) if isinstance(readiness, dict) else {}
    if not isinstance(readiness_dims, dict):
        readiness_dims = {}

    dim_source = readiness_dims.get("source_identity_evidence", {})
    dim_product = readiness_dims.get("product_candidate_evidence", {})
    dim_files = readiness_dims.get("file_existence_evidence", {})
    dim_coverage = readiness_dims.get("required_contract_coverage", {})
    dim_safety = readiness_dims.get("safety_compliance", {})
    if not isinstance(dim_source, dict):
        dim_source = {}
    if not isinstance(dim_product, dict):
        dim_product = {}
    if not isinstance(dim_files, dict):
        dim_files = {}
    if not isinstance(dim_coverage, dict):
        dim_coverage = {}
    if not isinstance(dim_safety, dict):
        dim_safety = {}

    source_identity_satisfied = as_bool(dim_source.get("passes"))
    expected_product_type_satisfied = as_bool(dim_product.get("passes")) and len(
        as_list_of_strings(dim_coverage.get("missing_required_product_types", []))
    ) == 0
    product_file_existence_satisfied = as_bool(dim_files.get("passes"))
    safety_compliance_satisfied = as_bool(dim_safety.get("passes"))

    required_proofs = [
        build_proof(
            "source_identity_proof",
            "Source identity is matched with confidence and readiness pass criteria.",
            source_identity_satisfied,
            "manifest.o3de.ap_resolver_readiness.dimensions.source_identity_evidence",
        ),
        build_proof(
            "expected_product_type_proof",
            "Expected product contract types have candidate support and no missing required types.",
            expected_product_type_satisfied,
            "manifest.o3de.ap_resolver_readiness.dimensions.product_candidate_evidence + required_contract_coverage",
        ),
        build_proof(
            "product_file_existence_proof",
            "Candidate product files exist according to readiness file evidence.",
            product_file_existence_satisfied,
            "manifest.o3de.ap_resolver_readiness.dimensions.file_existence_evidence",
        ),
        build_proof(
            "asset_processor_job_success_proof",
            "Asset Processor job status is proven successful for current source/product records.",
            False,
            "not_implemented_yet",
        ),
        build_proof(
            "platform_proof",
            "Platform targeting for candidate products is explicitly verified.",
            False,
            "not_implemented_yet",
        ),
        build_proof(
            "product_freshness_proof",
            "Candidate products are verified current and not stale.",
            False,
            "not_implemented_yet",
        ),
        build_proof(
            "product_identity_proof",
            "Product identity contract is verified without ambiguity.",
            False,
            "not_implemented_yet",
        ),
        build_proof(
            "safety_compliance_proof",
            "No safety violations exist in readiness evidence chain.",
            safety_compliance_satisfied,
            "manifest.o3de.ap_resolver_readiness.dimensions.safety_compliance",
        ),
    ]

    missing_proofs = [proof["id"] for proof in required_proofs if not bool(proof.get("satisfied"))]
    all_required_satisfied = len(missing_proofs) == 0

    blocked_statuses = {
        "blocked_safety_violation",
        "blocked_missing_source_identity",
        "blocked_missing_product_candidates",
        "blocked_missing_required_product_files",
    }
    if all_required_satisfied:
        status = "dry_run_ready"
    elif readiness_status in blocked_statuses:
        status = "dry_run_blocked"
    else:
        status = "dry_run_incomplete"

    job = manifest.get("job")
    job_id = ""
    if isinstance(job, dict):
        job_id = str(job.get("job_id", "")).strip()
    plan_id = f"authoritative-plan-{job_id}" if job_id else "authoritative-plan-unknown-job"

    available_evidence = {
        "readiness": {
            "present": isinstance(readiness, dict),
            "status": readiness_status,
        },
        "asset_resolution": {
            "present": isinstance(asset_resolution, dict),
            "required_products": as_list_of_strings(asset_resolution.get("required_products", []))
            if isinstance(asset_resolution, dict)
            else [],
        },
        "ap_source_identity_match": {
            "present": isinstance(source_match, dict),
            "status": str(source_match.get("status", "missing")) if isinstance(source_match, dict) else "missing",
        },
        "ap_product_candidate_match": {
            "present": isinstance(product_match, dict),
            "status": str(product_match.get("status", "missing")) if isinstance(product_match, dict) else "missing",
        },
        "ap_product_file_validation": {
            "present": isinstance(file_validation, dict),
            "status": str(file_validation.get("status", "missing")) if isinstance(file_validation, dict) else "missing",
        },
    }

    proposed_actions = [
        "Define Asset Processor job-state proof contract from read-only evidence.",
        "Define platform proof contract for product candidate targeting.",
        "Define product freshness proof contract to reject stale outputs.",
        "Define product identity proof contract for authoritative matching.",
    ]

    forbidden_actions = [
        "write resolved products",
        "claim Asset IDs",
        "spawn entity",
        "publish prefab",
        "run O3DE Editor",
        "run Asset Processor",
        "modify AP database",
    ]

    plan = {
        "schema_version": "1.0.0",
        "plan_id": plan_id,
        "status": status,
        "source_manifest": str(manifest_path),
        "required_proofs": required_proofs,
        "available_evidence": available_evidence,
        "missing_proofs": missing_proofs,
        "proposed_actions": proposed_actions,
        "forbidden_actions": forbidden_actions,
        "safety": {
            "read_only": True,
            "writes_resolved_products": False,
            "runs_o3de_editor": False,
            "runs_asset_processor": False,
            "opens_database": False,
            "modifies_database": False,
            "spawns_entities": False,
            "publishes_prefabs": False,
            "claims_asset_ids": False,
        },
        "updated_utc": utc_now(),
    }

    try:
        write_json(output_path, plan)
    except Exception as exc:
        print(f"FAIL: unable to write plan output: {exc}")
        return 2

    errors = minimal_validate_plan(plan)
    if errors:
        print("FAIL: minimal plan validation failed.")
        for error in errors:
            print(f"  - {error}")
        return 1

    has_jsonschema = False
    try:
        import jsonschema  # noqa: F401

        has_jsonschema = True
    except Exception:
        has_jsonschema = False

    if has_jsonschema:
        ok, schema_errors = jsonschema_validate(plan, _schema)
        if not ok:
            print("FAIL: schema validation failed for authoritative resolution plan.")
            for error in schema_errors:
                print(f"  - {error}")
            return 1
    else:
        print("INFO: jsonschema not available; schema validation skipped (minimal validation passed).")

    print(
        "PASS: authoritative resolver dry-run plan created. "
        f"status={status} missing_proof_count={len(missing_proofs)} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
