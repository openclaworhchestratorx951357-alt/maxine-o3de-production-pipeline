"""Composable QC gates for manifest-driven production-readiness checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from tools.qc.publication_contract import validate_publication_contract
from tools.qc.skeleton_contract import validate_skeleton_contract
from tools.validation.results import ValidationResult, combine_statuses


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else REPO_ROOT / path


def _gate(check_id: str, result: ValidationResult) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "result": result.status,
        "error_codes": result.error_codes,
        "warning_codes": result.warning_codes,
        "messages": result.messages,
    }


def input_integrity(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    inputs = manifest.get("inputs") if isinstance(manifest.get("inputs"), dict) else {}
    sources = inputs.get("sources", [])
    if not isinstance(sources, list) or not sources:
        result.add_error("MXN_INPUT_MISSING", "Manifest inputs.sources must include source records.")
        return result
    for source in sources:
        if not isinstance(source, dict) or not source.get("sha256"):
            result.add_error("MXN_INPUT_HASH_MISMATCH", "Each input source requires a sha256 hash.")
    return result


def scan_safe_packaging(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    publication = manifest.get("publication") if isinstance(manifest.get("publication"), dict) else {}
    package = publication.get("package") if isinstance(publication.get("package"), dict) else {}
    package_root = str(package.get("package_root", "")).replace("\\", "/")
    if package_root and (".." in package_root.split("/") or package_root.startswith("/")):
        result.add_error("MXN_PATH_UNSAFE", "Publication package root must be repo-relative and traversal-free.")
    return result


def asset_processing_completion(manifest: Dict[str, Any]) -> ValidationResult:
    return validate_publication_contract(manifest, strict=True)


def scale_origin_facing(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    dcc = manifest.get("dcc_conform") if isinstance(manifest.get("dcc_conform"), dict) else {}
    transform = dcc.get("transform") if isinstance(dcc.get("transform"), dict) else {}
    if float(transform.get("meters_per_unit", 0)) != 1.0:
        result.add_error("MXN_SCALE_INVALID", "1 meter must equal 1 O3DE world unit.")
    if transform.get("origin_centered") is not True:
        result.add_error("MXN_ORIGIN_INVALID", "Release export must be origin-centered.")
    if str(transform.get("forward", "")).strip() not in {"Y", "+Y", "-Y"}:
        result.add_error("MXN_FACING_INVALID", "Manifest must declare a valid forward direction.")
    return result


def geometry_sanity(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    geometry = manifest.get("dcc_conform", {}).get("geometry", {}) if isinstance(manifest.get("dcc_conform"), dict) else {}
    if geometry.get("valid") is not True:
        result.add_error("MXN_GEOMETRY_INVALID", "Geometry sanity fixture must be valid.")
    return result


def uv_material_sanity(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    dcc = manifest.get("dcc_conform") if isinstance(manifest.get("dcc_conform"), dict) else {}
    uv = dcc.get("uv") if isinstance(dcc.get("uv"), dict) else {}
    materials = dcc.get("materials") if isinstance(dcc.get("materials"), dict) else {}
    if uv.get("present") is not True:
        result.add_error("MXN_UV_MISSING", "UV inventory is required.")
    if materials.get("present") is not True and materials.get("waiver", {}).get("approved") is not True:
        result.add_error("MXN_MATERIAL_MISSING", "Material inventory or waiver is required.")
    return result


def skeleton_gate(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    dcc = manifest.get("dcc_conform") if isinstance(manifest.get("dcc_conform"), dict) else {}
    skeleton_ref = str(dcc.get("skeleton_ref", "")).strip()
    if not skeleton_ref:
        result.add_error("MXN_SKELETON_MISSING", "Manifest dcc_conform.skeleton_ref is required.")
        return result
    path = _resolve(skeleton_ref)
    if not path.exists():
        result.add_error("MXN_SKELETON_MISSING", f"Skeleton ref not found: {skeleton_ref}")
        return result
    skeleton = json.loads(path.read_text(encoding="utf-8-sig"))
    tier = str(manifest.get("identity", {}).get("character_tier", "hero"))
    result.merge(validate_skeleton_contract(skeleton, character_tier=tier))
    return result


def skinning_quality(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    skinning = manifest.get("dcc_conform", {}).get("skinning", {}) if isinstance(manifest.get("dcc_conform"), dict) else {}
    if skinning.get("valid") is not True:
        result.add_error("MXN_SKINNING_INVALID", "Skinning weights must pass fixture checks.")
    return result


def facial_capability(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    tier = str(manifest.get("identity", {}).get("character_tier", "hero")).lower()
    facial = manifest.get("dcc_conform", {}).get("facial", {}) if isinstance(manifest.get("dcc_conform"), dict) else {}
    morphs = facial.get("morphs", [])
    if isinstance(morphs, list) and morphs:
        return result
    waiver = facial.get("waiver") if isinstance(facial.get("waiver"), dict) else {}
    if tier == "npc" and waiver.get("approved") is True:
        result.add_warning("MXN_FACIAL_MORPH_MISSING", "NPC facial morph waiver accepted with warning.")
    else:
        result.add_error("MXN_FACIAL_MORPH_MISSING", "Hero/release facial morph inventory is required.")
    return result


def collision_legality(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    collision = manifest.get("dcc_conform", {}).get("collision", {}) if isinstance(manifest.get("dcc_conform"), dict) else {}
    if collision.get("valid") is not True and collision.get("waiver", {}).get("approved") is not True:
        result.add_error("MXN_COLLIDER_INVALID", "Collision setup requires primitive/convex policy pass or waiver.")
    return result


def animation_sanity(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    lane = manifest.get("job", {}).get("lane")
    if lane == "draft_mesh":
        return result
    products = manifest.get("o3de", {}).get("actual_products", []) if isinstance(manifest.get("o3de"), dict) else []
    if not any(isinstance(product, dict) and product.get("product_type") == "motion" for product in products):
        result.add_error("MXN_ANIMATION_LOAD_FAIL", "Release animation sanity requires at least one motion product.")
    return result


def runtime_smoke(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    smoke = manifest.get("runtime_validation", {}).get("smoke", {}) if isinstance(manifest.get("runtime_validation"), dict) else {}
    if smoke.get("result") not in {"pass", "pass_fixture"}:
        result.add_error("MXN_RUNTIME_SMOKE_FAIL", "Runtime smoke evidence is missing or failed.")
    if smoke.get("live_runtime_executed") is True:
        result.add_error("MXN_RUNTIME_SMOKE_FAIL", "Local validator does not admit live runtime smoke execution.")
    return result


def cleanup_undo(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    undo = manifest.get("undo") if isinstance(manifest.get("undo"), dict) else {}
    cleanup = manifest.get("cleanup") if isinstance(manifest.get("cleanup"), dict) else {}
    if not undo.get("plan_ref") and not undo.get("steps"):
        result.add_error("MXN_UNDO_PLAN_MISSING", "Undo plan is required.")
    if not cleanup.get("plan_ref") and not cleanup.get("steps"):
        result.add_error("MXN_UNDO_PLAN_MISSING", "Cleanup instructions are required.")
    return result


def provenance_completeness(manifest: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    provenance = manifest.get("provenance") if isinstance(manifest.get("provenance"), dict) else {}
    if not provenance.get("source_hashes") or not provenance.get("tool_versions"):
        result.add_error("MXN_PROVENANCE_INCOMPLETE", "Provenance requires source_hashes and tool_versions.")
    return result


GATES = [
    ("input_integrity", input_integrity),
    ("scan_safe_packaging", scan_safe_packaging),
    ("asset_processing_completion", asset_processing_completion),
    ("scale_origin_facing", scale_origin_facing),
    ("geometry_sanity", geometry_sanity),
    ("uv_material_sanity", uv_material_sanity),
    ("skeleton_contract", skeleton_gate),
    ("skinning_quality", skinning_quality),
    ("facial_capability", facial_capability),
    ("collision_legality", collision_legality),
    ("animation_sanity", animation_sanity),
    ("runtime_smoke", runtime_smoke),
    ("cleanup_undo", cleanup_undo),
    ("provenance_completeness", provenance_completeness),
]


def run_qc_gates(manifest: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    statuses: List[str] = []
    error_codes: List[str] = []
    warning_codes: List[str] = []
    for check_id, fn in GATES:
        result = fn(manifest)
        checks.append(_gate(check_id, result))
        statuses.append(result.status)
        for code in result.error_codes:
            if code not in error_codes:
                error_codes.append(code)
        for code in result.warning_codes:
            if code not in warning_codes:
                warning_codes.append(code)
    status = combine_statuses(statuses)
    return {
        "schema_version": "1.0.0",
        "report_id": f"qc-{manifest.get('job', {}).get('job_id', 'unknown')}",
        "status": status,
        "checks": checks,
        "error_codes": error_codes,
        "warning_codes": warning_codes,
    }
