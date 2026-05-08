"""Prefab/package-first publication contract validation."""

from __future__ import annotations

from typing import Any, Dict

from tools.o3de.product_matrix_resolver import validate_expected_products
from tools.qc.mixamo_policy import validate_mixamo_policy
from tools.validation.results import ValidationResult


def _has_value(payload: Dict[str, Any], key: str) -> bool:
    return bool(str(payload.get(key, "")).strip())


def validate_publication_contract(manifest: Dict[str, Any], *, strict: bool = True) -> ValidationResult:
    result = ValidationResult()
    job = manifest.get("job") if isinstance(manifest.get("job"), dict) else {}
    lane = str(job.get("lane", "")).strip()
    o3de = manifest.get("o3de") if isinstance(manifest.get("o3de"), dict) else {}
    products = o3de.get("actual_products", []) if isinstance(o3de.get("actual_products"), list) else []
    publication = manifest.get("publication") if isinstance(manifest.get("publication"), dict) else {}
    package = publication.get("package") if isinstance(publication.get("package"), dict) else {}
    product_resolution = o3de.get("product_resolution") if isinstance(o3de.get("product_resolution"), dict) else {}

    if lane in {"draft_mesh", "release_rigged", "external_rig_import"}:
        result.merge(
            validate_expected_products(
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
        )

    evidence = manifest.get("evidence") if isinstance(manifest.get("evidence"), dict) else {}
    if not _has_value(evidence, "bundle_ref"):
        result.add_error("MXN_PROVENANCE_INCOMPLETE", "Release publication requires an evidence bundle reference.")

    undo = manifest.get("undo") if isinstance(manifest.get("undo"), dict) else {}
    if not _has_value(undo, "plan_ref") and not undo.get("steps"):
        result.add_error("MXN_UNDO_PLAN_MISSING", "Publication package requires undo instructions.")

    if lane in {"release_rigged", "external_rig_import"}:
        prefab_ref = str(package.get("prefab_ref", "")).strip()
        if not prefab_ref:
            result.add_error("MXN_ASSET_PRODUCT_MISSING", "Release package requires explicit prefab/procprefab publication ref.")
        refs = evidence.get("refs", []) if isinstance(evidence.get("refs"), list) else []
        if refs and all(str(ref.get("kind", "")).strip() == "spawn" for ref in refs if isinstance(ref, dict)):
            result.add_error("MXN_RUNTIME_SMOKE_FAIL", "Release package cannot pass with spawn-only evidence.")

    runtime = manifest.get("runtime_validation") if isinstance(manifest.get("runtime_validation"), dict) else {}
    smoke = runtime.get("smoke") if isinstance(runtime.get("smoke"), dict) else {}
    if lane == "draft_mesh" and smoke.get("result") not in {"pass", "pass_fixture"}:
        result.add_error("MXN_RUNTIME_SMOKE_FAIL", "Draft package requires smoke evidence.")

    mixamo = validate_mixamo_policy(manifest, offline=True)
    if lane in {"release_rigged", "external_rig_import"} and mixamo.status == "pending_manual":
        result.add_error("MXN_MIXAMO_PENDING_MANUAL", "Unresolved Mixamo handoff cannot pass release publication.")
    elif mixamo.status == "fail":
        result.merge(mixamo)
    return result
