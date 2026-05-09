#!/usr/bin/env python3
"""Audit live APB product evidence without using cache heuristics as proof."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT = Path.home() / "O3DE" / "Projects" / "MAXINE_GoldenCorpus"
DEFAULT_SOURCE_FILTER = "assets/characters/maxine/release/maxine_physx_final_spherebot.fbx"
DEFAULT_EXPECTED_PRODUCT = "pxmesh"
PXMESH_DIAGNOSTIC_MARKERS = ("pxmesh", "physx", "physics", "collider", "collision", "pxc")
PHYSX_EDITOR_MODULE_MARKERS = ("physx5.editor.gem.dll", "physx.editor.gem.dll")
SCENE_PROCESSING_MARKERS = ("sceneprocessing", "scenebuilder")
MAX_DIAGNOSTIC_PRODUCTS = 25


def audit_apb_product_evidence(
    *,
    project: Path | str = DEFAULT_PROJECT,
    apb_report: Path | str | None = None,
    apb_executable: Path | str | None = None,
    expected_product: str = DEFAULT_EXPECTED_PRODUCT,
    source_filter: str = DEFAULT_SOURCE_FILTER,
) -> Dict[str, Any]:
    project_path = Path(project)
    expected = expected_product.lower().lstrip(".")
    asset_db_path = project_path / "Cache" / "assetdb.sqlite"
    report_path = Path(apb_report) if apb_report else None
    apb_path = _resolve_apb_executable(apb_executable)

    apb_report_payload = _load_json(report_path) if report_path else {}
    report_products = _products_from_report(apb_report_payload)
    db_payload = _products_from_asset_db(asset_db_path, source_filter=source_filter)

    report_exact = _release_report_products(report_products, expected)
    db_exact = _exact_products(db_payload["source_products"], expected)
    diagnostic_like_products = _diagnostic_like_products(db_payload["products"], expected)
    found_exact = bool(report_exact or db_exact)
    builder_audit = _physx_builder_audit(apb_path)

    errors: List[str] = []
    warnings: List[str] = []
    if db_payload["error"]:
        errors.append(db_payload["error"])
    if not found_exact:
        errors.append("MXN_ASSET_PRODUCT_MISSING")
        if builder_audit["physx_editor_module_available"] and not builder_audit["physx_editor_module_listed_in_dependency_registry"]:
            warnings.append(
                "PhysX editor module exists beside APB but is not listed in the AssetBuilder/APB dependency registry."
            )
    if diagnostic_like_products and not found_exact:
        warnings.append("Physics-like products were found for diagnostics only; they are not accepted as pxmesh release evidence.")
    if bool(apb_report_payload.get("cache_heuristic_used", False)):
        errors.append("MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN")

    status = "pass" if found_exact and not errors else "fail"
    return {
        "schema_version": "1.0.0",
        "report_type": "maxine_apb_product_evidence_audit",
        "generated_at": _utc_now(),
        "status": status,
        "mode": "pxmesh_product_evidence_audit",
        "lane": "release_rigged",
        "project_name": _project_name(project_path),
        "project_path": _path_ref(project_path),
        "asset_database_path": _path_ref(asset_db_path),
        "apb_report_path": _path_ref(report_path) if report_path else "",
        "apb_executable": _path_ref(apb_path) if apb_path else "",
        "expected_product_type": expected,
        "source_filter": source_filter.replace("\\", "/").lower(),
        "apb_report_status": str(apb_report_payload.get("status", "")),
        "apb_process_exit_code": _apb_exit_code(apb_report_payload),
        "apb_report_errors": _string_list(apb_report_payload.get("errors", [])),
        "apb_report_warnings": _string_list(apb_report_payload.get("warnings", [])),
        "apb_report_messages": _string_list(apb_report_payload.get("messages", [])),
        "pxmesh_found_in_apb_report": bool(report_exact),
        "pxmesh_found_in_ap_db": bool(db_exact),
        "pxmesh_like_product_found_under_different_classification": bool(diagnostic_like_products and not found_exact),
        "pxmesh_evidence": _summarize_products(report_exact + db_exact),
        "diagnostic_pxmesh_like_products": _summarize_products(diagnostic_like_products, limit=MAX_DIAGNOSTIC_PRODUCTS),
        "diagnostic_pxmesh_like_product_count": len(diagnostic_like_products),
        "source_products": _summarize_products(db_payload["source_products"]),
        "source_jobs": db_payload["source_jobs"],
        "failed_jobs": db_payload["failed_jobs"],
        "pending_jobs": db_payload["pending_jobs"],
        "apb_report_missing_products": _string_list(apb_report_payload.get("missing_products", [])),
        "apb_report_produced_products": _summarize_products(report_products),
        "physx_builder_audit": builder_audit,
        "product_matrix_status": "pass" if found_exact else "fail",
        "cache_heuristic_used": bool(apb_report_payload.get("cache_heuristic_used", False)),
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "evidence_source": {
            "asset_processor_database": asset_db_path.exists(),
            "apb_report": bool(apb_report_payload),
            "cache_heuristic": False,
        },
        "errors": _unique(errors),
        "warnings": _unique(warnings),
        "next_steps": _next_steps(found_exact=found_exact, builder_audit=builder_audit),
    }


def _products_from_asset_db(asset_db_path: Path, *, source_filter: str) -> Dict[str, Any]:
    empty = {
        "products": [],
        "source_products": [],
        "source_jobs": [],
        "failed_jobs": [],
        "pending_jobs": [],
        "error": "",
    }
    if not asset_db_path.exists():
        empty["error"] = "MXN_VALIDATION_TOOL_UNAVAILABLE"
        return empty

    normalized_source_filter = source_filter.replace("\\", "/").lower()
    source_like = f"%{normalized_source_filter}%"
    try:
        with sqlite3.connect(asset_db_path) as conn:
            conn.row_factory = sqlite3.Row
            products = [
                _product_from_row(row, evidence_source="asset_processor_database")
                for row in conn.execute(
                    """
                    select p.ProductName, p.SubID, s.SourceName, s.SourceGuid, j.Platform, j.Status, j.JobKey
                    from Products p
                    join Jobs j on p.JobPK = j.JobID
                    join Sources s on j.SourcePK = s.SourceID
                    order by lower(p.ProductName)
                    """
                ).fetchall()
            ]
            source_products = [
                product
                for product in products
                if normalized_source_filter in product["source_path"].lower().replace("\\", "/")
            ]
            source_jobs = [
                _job_from_row(row)
                for row in conn.execute(
                    """
                    select s.SourceName, s.SourceGuid, j.JobKey, j.Platform, j.Status,
                           coalesce(j.ErrorCount, 0) as ErrorCount,
                           coalesce(j.WarningCount, 0) as WarningCount
                    from Jobs j
                    join Sources s on j.SourcePK = s.SourceID
                    where lower(replace(s.SourceName, '\\', '/')) like ?
                    order by j.JobKey, j.Platform
                    """,
                    (source_like,),
                ).fetchall()
            ]
    except sqlite3.Error:
        empty["error"] = "MXN_VALIDATION_TOOL_UNAVAILABLE"
        return empty

    failed_jobs = [job for job in source_jobs if int(job.get("status_code", -1)) not in {4, 5}]
    pending_jobs = [job for job in source_jobs if int(job.get("status_code", -1)) in {0, 1, 2, 3}]
    return {
        "products": products,
        "source_products": source_products,
        "source_jobs": source_jobs,
        "failed_jobs": failed_jobs,
        "pending_jobs": pending_jobs,
        "error": "",
    }


def _products_from_report(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    for item in payload.get("produced_products", []):
        if isinstance(item, dict):
            product_path = str(item.get("product_path", "") or item.get("path", "")).replace("\\", "/")
            product_type = str(item.get("product_type", "")).lower().lstrip(".")
            if not product_type and "." in product_path:
                product_type = product_path.rsplit(".", 1)[-1].lower()
            products.append(
                {
                    "product_type": product_type,
                    "product_path": product_path,
                    "source_path": str(item.get("source_path", "")).replace("\\", "/"),
                    "source_uuid": str(item.get("source_uuid", "")),
                    "platform": str(item.get("platform", "")),
                    "sub_id": item.get("sub_id", ""),
                    "job_key": str(item.get("job_key", "")),
                    "evidence_source": "apb_report",
                }
            )
        elif isinstance(item, str):
            product_path = item.replace("\\", "/")
            products.append(
                {
                    "product_type": product_path.rsplit(".", 1)[-1].lower() if "." in product_path else "",
                    "product_path": product_path,
                    "source_path": "",
                    "source_uuid": "",
                    "platform": "",
                    "sub_id": "",
                    "job_key": "",
                    "evidence_source": "apb_report",
                }
            )
    return products


def _product_from_row(row: sqlite3.Row, *, evidence_source: str) -> Dict[str, Any]:
    product_name = str(row["ProductName"]).replace("\\", "/")
    return {
        "product_type": product_name.rsplit(".", 1)[-1].lower() if "." in product_name else "",
        "product_path": product_name,
        "source_path": str(row["SourceName"]).replace("\\", "/"),
        "source_uuid": _blob_to_hex(row["SourceGuid"]),
        "platform": str(row["Platform"]),
        "sub_id": row["SubID"],
        "job_key": str(row["JobKey"]),
        "status_code": row["Status"],
        "evidence_source": evidence_source,
    }


def _job_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "source_path": str(row["SourceName"]).replace("\\", "/"),
        "source_uuid": _blob_to_hex(row["SourceGuid"]),
        "job_key": str(row["JobKey"]),
        "platform": str(row["Platform"]),
        "status_code": row["Status"],
        "errors": row["ErrorCount"],
        "warnings": row["WarningCount"],
    }


def _exact_products(products: Iterable[Dict[str, Any]], expected: str) -> List[Dict[str, Any]]:
    suffix = f".{expected.lower().lstrip('.')}"
    return [
        product
        for product in products
        if str(product.get("product_type", "")).lower().lstrip(".") == expected
        or str(product.get("product_path", "")).lower().replace("\\", "/").endswith(suffix)
    ]


def _release_report_products(products: Iterable[Dict[str, Any]], expected: str) -> List[Dict[str, Any]]:
    release_prefix = "pc/assets/characters/maxine/release/"
    return [
        product
        for product in _exact_products(products, expected)
        if str(product.get("product_path", "")).lower().replace("\\", "/").startswith(release_prefix)
        or str(product.get("source_path", "")).lower().replace("\\", "/").startswith("assets/characters/maxine/release/")
    ]


def _diagnostic_like_products(products: Iterable[Dict[str, Any]], expected: str) -> List[Dict[str, Any]]:
    exact = {_product_key(product) for product in _exact_products(products, expected)}
    result: List[Dict[str, Any]] = []
    for product in products:
        if _product_key(product) in exact:
            continue
        text = " ".join(
            str(product.get(key, "")).lower()
            for key in ("product_path", "source_path", "product_type", "job_key")
        )
        if any(marker in text for marker in PXMESH_DIAGNOSTIC_MARKERS):
            result.append(product)
    return result


def _physx_builder_audit(apb_executable: Path | None) -> Dict[str, Any]:
    if apb_executable is None:
        return {
            "apb_bin_directory": "",
            "physx_editor_module_available": False,
            "physx_editor_module_listed_in_dependency_registry": False,
            "scene_processing_listed_in_dependency_registry": False,
            "dependency_registry_files": [],
            "physx_registry_refs": [],
            "scene_processing_registry_refs": [],
        }
    bin_dir = apb_executable.parent
    registry_dir = bin_dir / "Registry"
    dependency_files = sorted(registry_dir.glob("cmake_dependencies*.setreg")) if registry_dir.exists() else []
    physx_available = any((bin_dir / marker).exists() for marker in ("PhysX5.Editor.Gem.dll", "PhysX.Editor.Gem.dll"))
    physx_refs: List[str] = []
    scene_refs: List[str] = []
    for path in dependency_files:
        text = _read_text(path).lower()
        if any(marker in text for marker in PHYSX_EDITOR_MODULE_MARKERS):
            physx_refs.append(_path_ref(path))
        if any(marker in text for marker in SCENE_PROCESSING_MARKERS):
            scene_refs.append(_path_ref(path))
    return {
        "apb_bin_directory": _path_ref(bin_dir),
        "physx_editor_module_available": physx_available,
        "physx_editor_module_listed_in_dependency_registry": bool(physx_refs),
        "scene_processing_listed_in_dependency_registry": bool(scene_refs),
        "dependency_registry_files": [_path_ref(path) for path in dependency_files],
        "physx_registry_refs": physx_refs,
        "scene_processing_registry_refs": scene_refs,
    }


def _summarize_products(products: Iterable[Dict[str, Any]], *, limit: int | None = None) -> List[Dict[str, Any]]:
    summarized: List[Dict[str, Any]] = []
    for index, product in enumerate(products):
        if limit is not None and index >= limit:
            break
        summarized.append(
            {
                "product_type": str(product.get("product_type", "")),
                "product_path": str(product.get("product_path", "")).replace("\\", "/"),
                "source_path": str(product.get("source_path", "")).replace("\\", "/"),
                "source_uuid": str(product.get("source_uuid", "")),
                "platform": str(product.get("platform", "")),
                "sub_id": product.get("sub_id", ""),
                "job_key": str(product.get("job_key", "")),
                "evidence_source": str(product.get("evidence_source", "")),
            }
        )
    return summarized


def _resolve_apb_executable(path: Path | str | None) -> Path | None:
    value = str(path or os.environ.get("ASSET_PROCESSOR_BATCH_EXECUTABLE", "")).strip()
    return Path(value) if value else None


def _load_json(path: Path | None) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _project_name(project: Path) -> str:
    payload = _load_json(project / "project.json")
    return str(payload.get("project_name", ""))


def _path_ref(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except (OSError, ValueError):
        return str(path).replace("\\", "/")


def _product_key(product: Dict[str, Any]) -> tuple[str, str]:
    return (str(product.get("evidence_source", "")), str(product.get("product_path", "")))


def _blob_to_hex(value: Any) -> str:
    if isinstance(value, bytes):
        return value.hex()
    return str(value or "").strip()


def _unique(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _apb_exit_code(payload: Dict[str, Any]) -> int | None:
    value = payload.get("exit_code")
    if value is None and isinstance(payload.get("command"), dict):
        value = payload["command"].get("exit_code")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _next_steps(*, found_exact: bool, builder_audit: Dict[str, Any]) -> List[str]:
    if found_exact:
        return [
            "Use the pxmesh AP DB/APB report evidence in the APB wrapper and product matrix validation.",
            "Keep cache heuristic release proof disabled.",
        ]
    if builder_audit["physx_editor_module_available"] and not builder_audit["physx_editor_module_listed_in_dependency_registry"]:
        return [
            "Generate or configure the project-paired AssetBuilder/APB dependency registry so PhysX5.Editor.Gem.dll is loaded.",
            "Rerun bounded APB-only processing and require a trusted .pxmesh AP DB/APB report product.",
        ]
    return [
        "Inspect PhysX scene settings, collider source geometry, and PhysX builder activation.",
        "Do not waive pxmesh unless an explicit collider waiver policy is added, tested, and documented.",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit APB product evidence for release-rigged pxmesh output.")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--apb-report", type=Path)
    parser.add_argument("--apb-executable", type=Path)
    parser.add_argument("--expected-product", default=DEFAULT_EXPECTED_PRODUCT)
    parser.add_argument("--source", default=DEFAULT_SOURCE_FILTER)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = audit_apb_product_evidence(
        project=args.project,
        apb_report=args.apb_report,
        apb_executable=args.apb_executable,
        expected_product=args.expected_product,
        source_filter=args.source,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"APB product evidence audit: {report['status']}")
        print(f"project: {report['project_name']} ({report['project_path']})")
        print(f"expected product: {report['expected_product_type']}")
        print(f"pxmesh found in APB report: {str(report['pxmesh_found_in_apb_report']).lower()}")
        print(f"pxmesh found in AP DB: {str(report['pxmesh_found_in_ap_db']).lower()}")
        print(
            "pxmesh-like diagnostic products: "
            f"{str(report['pxmesh_like_product_found_under_different_classification']).lower()}"
        )
        for error in report["errors"]:
            print(f"  error: {error}")
        for warning in report["warnings"]:
            print(f"  warning: {warning}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
