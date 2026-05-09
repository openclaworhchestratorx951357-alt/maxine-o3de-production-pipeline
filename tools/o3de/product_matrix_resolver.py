"""Lane-specific expected product matrix validation."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Set

from tools.o3de.product_resolver import ProductRecord, coerce_product_records
from tools.validation.results import ValidationResult


KNOWN_PRODUCT_TYPES: Set[str] = {
    "actor",
    "animgraph",
    "azmaterial",
    "azmodel",
    "motion",
    "motionset",
    "procprefab",
    "pxmesh",
}


def _types(products: Iterable[ProductRecord]) -> Counter[str]:
    return Counter(product.product_type for product in products)


def _require(result: ValidationResult, counts: Counter[str], product_type: str, message: str) -> None:
    if counts[product_type] <= 0:
        result.add_error("MXN_ASSET_PRODUCT_MISSING", message)


def validate_expected_products(
    lane: str,
    product_records: Iterable[Any],
    *,
    strict: bool = True,
    publish_tier: str = "package",
    physics_enabled: bool = False,
    materialized: bool = False,
    collider_waiver: bool = False,
    material_waiver: bool = False,
    external_motion_required: bool = False,
    cache_heuristic_used: bool = False,
) -> ValidationResult:
    result = ValidationResult()
    products = coerce_product_records(product_records)
    counts = _types(products)
    lane = str(lane).strip()
    publish_tier = str(publish_tier or "package").strip()

    unknown = sorted(product_type for product_type in counts if product_type not in KNOWN_PRODUCT_TYPES)
    for product_type in unknown:
        result.add_error("MXN_ASSET_PRODUCT_MISSING", f"unknown product type '{product_type}' is not in the production matrix.")

    pending = [product for product in products if product.status != "ready"]
    if pending:
        code = "MXN_ASSET_PRODUCTS_PENDING"
        message = "Pending Asset Processor products remain for target platform."
        if strict:
            result.add_error(code, message)
        else:
            result.add_warning(code, message)

    heuristic_products = [product for product in products if _uses_cache_heuristic(product)]
    heuristic_used = cache_heuristic_used or bool(heuristic_products)
    if lane in {"release_rigged", "external_rig_import"} and heuristic_used:
        result.add_error(
            "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
            "Release product resolution cannot use cache guessing/newest-file heuristics.",
        )
    elif lane == "draft_mesh" and heuristic_used:
        result.add_warning(
            "MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN",
            "Draft cache heuristic evidence is allowed only as draft-only warning evidence.",
        )

    if lane == "draft_mesh":
        _require(result, counts, "azmodel", "draft_mesh requires azmodel.")
    elif lane == "release_rigged":
        _require(result, counts, "actor", "release_rigged requires actor.")
        _require(result, counts, "motion", "release_rigged requires at least one motion.")
        if publish_tier in {"release", "package"}:
            _require(result, counts, "motionset", "release_rigged release publish tier requires motionset.")
            _require(result, counts, "animgraph", "release_rigged release publish tier requires animgraph.")
        if publish_tier == "package":
            _require(result, counts, "procprefab", "release_rigged package publication requires procprefab.")
    elif lane == "external_rig_import":
        _require(result, counts, "actor", "external_rig_import requires actor.")
        if external_motion_required:
            _require(result, counts, "motion", "external_rig_import manifest marks motion as required.")
        if publish_tier == "package":
            _require(result, counts, "procprefab", "external_rig_import package publication requires procprefab.")
    else:
        result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Unsupported production lane: {lane}")

    if lane in {"release_rigged", "external_rig_import"} and physics_enabled and counts["pxmesh"] <= 0 and not collider_waiver:
        result.add_error("MXN_COLLIDER_INVALID", "Physics-enabled release requires pxmesh or collider waiver.")
    if lane in {"release_rigged", "external_rig_import"} and materialized and counts["azmaterial"] <= 0 and not material_waiver:
        result.add_error("MXN_MATERIAL_MISSING", "Materialized release requires azmaterial or material waiver.")

    result.details["product_type_counts"] = dict(counts)
    return result


def _uses_cache_heuristic(product: ProductRecord) -> bool:
    evidence_source = str(getattr(product, "evidence_source", "")).strip().lower()
    if evidence_source in {"cache_heuristic", "newest_cache_file", "best_looking_cache_file", "fallback_mesh_selection"}:
        return True
    if getattr(product, "produced_by_source_uuid", True) is False and evidence_source not in {"fixture", "local_o3de", "asset_system"}:
        return True
    return False


def validate_product_matrix_payload(payload: Dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    lanes = payload.get("lanes") if isinstance(payload.get("lanes"), dict) else {}
    for lane in ("draft_mesh", "release_rigged", "external_rig_import"):
        if lane not in lanes:
            result.add_error("MXN_SCHEMA_VALIDATION_FAIL", f"Product matrix is missing lane: {lane}")
            continue
        required = lanes[lane].get("required", []) if isinstance(lanes[lane], dict) else []
        for product_type in required:
            if product_type not in KNOWN_PRODUCT_TYPES:
                result.add_error("MXN_ASSET_PRODUCT_MISSING", f"Product matrix lane {lane} references unknown product type {product_type}.")
    return result
