#!/usr/bin/env python3
"""Audit release-rigged golden corpus source prerequisites without running O3DE."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "examples" / "golden-corpus"
DEFAULT_PROJECT = Path.home() / "O3DE" / "Projects" / "MAXINE_GoldenCorpus"
RELEASE_CASE = "release_rigged"
RELEASE_SOURCE_ROOT = Path("Assets") / "Characters" / "MAXINE" / "release"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _repo_or_local_ref(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _project_relative(path: Path, project: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve())).replace("\\", "/")
    except ValueError:
        return _repo_or_local_ref(path)


def _fixture_release_report(corpus: Path) -> Dict[str, Any]:
    return _load_json(corpus / RELEASE_CASE / "asset_processor_batch.fixture.json")


def _source_paths_from_fixture(report: Dict[str, Any]) -> List[str]:
    paths: List[str] = []
    for source in report.get("source_assets", []):
        if isinstance(source, dict):
            value = str(source.get("path", "")).strip()
            if value:
                paths.append(value.replace("\\", "/"))
    return paths


def _find_files(root: Path, patterns: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    if not root.exists():
        return files
    for pattern in patterns:
        files.extend(path for path in root.rglob(pattern) if path.is_file())
    return sorted(set(files), key=lambda item: str(item).lower())


def _first_assetinfo_with(root: Path, marker: str) -> Path | None:
    for path in _find_files(root, ["*.assetinfo", "*.assetinfo.generated"]):
        if marker.lower() in _read_text(path).lower():
            return path
    return None


def _first_assetinfo_with_any(root: Path, markers: Iterable[str]) -> Path | None:
    normalized = [marker.lower() for marker in markers]
    for path in _find_files(root, ["*.assetinfo", "*.assetinfo.generated"]):
        text = _read_text(path).lower()
        if any(marker in text for marker in normalized):
            return path
    return None


def _first_file(root: Path, patterns: Iterable[str]) -> Path | None:
    files = _find_files(root, patterns)
    return files[0] if files else None


def _capability(path: Path | None, project: Path) -> Dict[str, Any]:
    return {"present": path is not None, "path": _project_relative(path, project) if path else ""}


def _status_for_source_file(path: Path | None) -> str:
    return "source-provided" if path else "missing"


def _load_project(project: Path) -> Dict[str, Any]:
    project_json = project / "project.json"
    if not project_json.exists():
        return {}
    try:
        return _load_json(project_json)
    except json.JSONDecodeError:
        return {}


def _gem_enabled(gems: Iterable[str], *names: str) -> bool:
    normalized = {str(gem).lower() for gem in gems}
    return any(name.lower() in normalized for name in names)


def _apb_report_summary(path: Path | None) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = _load_json(path)
    except json.JSONDecodeError:
        return {"path": _repo_or_local_ref(path), "status": "invalid_json"}
    return {
        "path": _repo_or_local_ref(path),
        "status": payload.get("status", ""),
        "produced_products": payload.get("produced_products", []),
        "missing_products": payload.get("missing_products", []),
        "pending_products": payload.get("pending_assets", []),
        "errors": payload.get("errors", []),
        "cache_heuristic_used": bool(payload.get("cache_heuristic_used", False)),
    }


def audit_golden_corpus_sources(
    corpus: Path = DEFAULT_CORPUS,
    project: Path = DEFAULT_PROJECT,
    *,
    apb_report: Path | None = None,
) -> Dict[str, Any]:
    corpus = Path(corpus)
    project = Path(project)
    release_report = _fixture_release_report(corpus)
    project_data = _load_project(project)
    gems = project_data.get("gem_names", []) if isinstance(project_data.get("gem_names", []), list) else []
    release_root = project / RELEASE_SOURCE_ROOT

    expected_source_paths = _source_paths_from_fixture(release_report)
    expected_products = list(release_report.get("expected_products", []))
    actor_assetinfo = _first_assetinfo_with(release_root, "actorgroup")
    motion_assetinfo = _first_assetinfo_with(release_root, "motiongroup")
    physics_assetinfo = _first_assetinfo_with_any(
        release_root,
        [
            "physicsmaterialslots",
            "primitiveassetparams",
            "trianglemeshassetparams",
            "convexassetparams",
        ],
    )
    motionset = _first_file(release_root, ["*.motionset"])
    animgraph = _first_file(release_root, ["*.animgraph"])
    release_sources = _find_files(
        release_root,
        ["*.fbx", "*.gltf", "*.glb", "*.assetinfo", "*.assetinfo.generated", "*.motionset", "*.animgraph", "*.prefab", "*.material"],
    )

    gem_enablement = {
        "SceneProcessing": True,
        "EMotionFX": _gem_enabled(gems, "EMotionFX"),
        "PhysX_or_PhysX5": _gem_enabled(gems, "PhysX", "PhysX5"),
        "PrefabBuilder": _gem_enabled(gems, "PrefabBuilder"),
        "PythonAssetBuilder": _gem_enabled(gems, "PythonAssetBuilder"),
        "Atom_or_EMotionFX_Atom": _gem_enabled(gems, "Atom", "EMotionFX_Atom", "Atom_Feature_Common"),
    }

    errors: List[str] = []
    warnings: List[str] = []
    if not release_sources:
        errors.append("MXN_RELEASE_RIGGED_SOURCE_MISSING")
    if actor_assetinfo is None:
        errors.append("MXN_RELEASE_RIGGED_ACTOR_SOURCE_MISSING")
    if motion_assetinfo is None:
        errors.append("MXN_RELEASE_RIGGED_MOTION_SOURCE_MISSING")
    if motionset is None:
        errors.append("MXN_RELEASE_RIGGED_MOTIONSET_SOURCE_MISSING")
    if animgraph is None:
        errors.append("MXN_RELEASE_RIGGED_ANIMGRAPH_SOURCE_MISSING")
    if physics_assetinfo is None:
        errors.append("MXN_RELEASE_RIGGED_PXMESH_SETTINGS_MISSING")
    for gem_name, enabled in gem_enablement.items():
        if gem_name in {"PythonAssetBuilder", "Atom_or_EMotionFX_Atom"}:
            continue
        if not enabled:
            errors.append(f"MXN_RELEASE_RIGGED_GEM_MISSING_{gem_name.upper()}")
    if not gem_enablement["PythonAssetBuilder"]:
        warnings.append("PythonAssetBuilder is not enabled; this is acceptable unless release scene settings depend on Python builders.")

    return {
        "schema_version": "1.0.0",
        "report_type": "maxine_golden_corpus_source_audit",
        "generated_at": _utc_now(),
        "status": "pass" if not errors else "fail",
        "lane": RELEASE_CASE,
        "project_name": project_data.get("project_name", ""),
        "project_path": _repo_or_local_ref(project),
        "release_source_root": _repo_or_local_ref(release_root),
        "expected_source_paths": expected_source_paths,
        "expected_products": expected_products,
        "release_rigged_source_asset_found": bool(release_sources),
        "source_files": [_project_relative(path, project) for path in release_sources],
        "actor_capable_source": _capability(actor_assetinfo, project),
        "motion_capable_source": _capability(motion_assetinfo, project),
        "scene_settings_present": bool(actor_assetinfo or motion_assetinfo or physics_assetinfo),
        "motionset": {"status": _status_for_source_file(motionset), "path": _project_relative(motionset, project) if motionset else ""},
        "animgraph": {"status": _status_for_source_file(animgraph), "path": _project_relative(animgraph, project) if animgraph else ""},
        "pxmesh": {
            "status": "source-settings-present" if physics_assetinfo else "missing",
            "path": _project_relative(physics_assetinfo, project) if physics_assetinfo else "",
        },
        "gem_enablement": gem_enablement,
        "apb_report": _apb_report_summary(apb_report),
        "live_asset_processor_batch_execution": False,
        "live_editor_execution": False,
        "live_publication": False,
        "cache_heuristic_used": False,
        "errors": errors,
        "warnings": warnings,
        "next_steps": [
            "Stage release-rigged source assets under Assets/Characters/MAXINE/release in the controlled project.",
            "Run bounded APB-only processing and verify actor, motion, motionset, animgraph, and pxmesh product evidence.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit MAXINE golden corpus release-rigged source prerequisites.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--apb-report", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = audit_golden_corpus_sources(args.corpus, args.project, apb_report=args.apb_report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Golden corpus source audit: {report['status']}")
        print(f"project: {report['project_name']} ({report['project_path']})")
        print(f"release source root: {report['release_source_root']}")
        print(f"release_rigged_source_asset_found: {str(report['release_rigged_source_asset_found']).lower()}")
        print(f"actor_capable_source: {report['actor_capable_source']['path'] or 'missing'}")
        print(f"motion_capable_source: {report['motion_capable_source']['path'] or 'missing'}")
        print(f"motionset: {report['motionset']['status']}")
        print(f"animgraph: {report['animgraph']['status']}")
        print(f"pxmesh: {report['pxmesh']['status']}")
        for error in report["errors"]:
            print(f"  error: {error}")
        for warning in report["warnings"]:
            print(f"  warning: {warning}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
