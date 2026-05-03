#!/usr/bin/env python3
"""Read-only filesystem probe for MAXINE O3DE asset evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


VALID_MODES = {"contract", "filesystem_probe"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def file_mtime_utc(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON from {path}: {exc}") from exc


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe local O3DE filesystem evidence for an asset manifest.")
    parser.add_argument("--manifest", required=True, help="Input manifest path")
    parser.add_argument("--source-asset", required=True, help="Source asset path (relative or absolute)")
    parser.add_argument("--project-path", default="", help="Optional O3DE project path")
    parser.add_argument("--cache-path", default="", help="Optional O3DE cache path")
    parser.add_argument("--lane", default="", help="Optional lane override")
    parser.add_argument("--output", default="", help="Optional output manifest path (defaults to in-place)")
    parser.add_argument("--max-candidates", type=int, default=25, help="Maximum candidate cache files to record")
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default="filesystem_probe", help="Probe mode")
    return parser.parse_args()


def gather_cache_candidates(cache_root: Path, source_stem: str, limit: int) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if limit < 1:
        return candidates

    source_stem_l = source_stem.lower()
    for path in cache_root.rglob("*"):
        if not path.is_file():
            continue
        name_l = path.name.lower()
        stem_l = path.stem.lower()
        if source_stem_l in name_l or source_stem_l in stem_l:
            candidates.append(
                {
                    "path": str(path),
                    "extension": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                    "modified_utc": file_mtime_utc(path),
                }
            )
            if len(candidates) >= limit:
                break
    return candidates


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    manifest_path = resolve_path(repo_root, args.manifest)
    if not manifest_path.exists():
        print(f"FAIL: manifest file not found: {manifest_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    lane = args.lane.strip() if args.lane else str(manifest.get("job", {}).get("lane", "")).strip()
    if not lane:
        print("FAIL: lane not provided and manifest.job.lane missing.")
        return 2

    source_asset_input = str(args.source_asset)
    source_path = Path(source_asset_input)
    source_asset_name = source_path.name
    source_asset_extension = source_path.suffix.lower()
    source_asset_stem = source_path.stem

    probe: Dict[str, Any] = {
        "mode": args.mode,
        "lane": lane,
        "source_asset_input": source_asset_input,
        "source_asset_name": source_asset_name,
        "source_asset_extension": source_asset_extension,
        "cache_guessing_used": False,
        "real_o3de_query_used": False,
        "authoritative_resolution": False,
        "updated_utc": utc_now(),
        "notes": [],
    }

    # Project/source evidence (filesystem_probe mode only)
    if args.mode == "filesystem_probe" and args.project_path:
        project_path = resolve_path(repo_root, args.project_path)
        project_exists = project_path.exists() and project_path.is_dir()
        project_json = project_path / "project.json"
        project_json_exists = project_json.exists() and project_json.is_file()

        probe["project_path"] = str(project_path)
        probe["project_exists"] = project_exists
        probe["project_json_exists"] = project_json_exists

        if source_path.is_absolute():
            source_full = source_path
        else:
            source_full = project_path / source_path
        probe["source_asset_full_path"] = str(source_full)

        source_exists = source_full.exists() and source_full.is_file()
        probe["source_asset_exists"] = source_exists
        if source_exists:
            probe["size_bytes"] = source_full.stat().st_size
            probe["modified_utc"] = file_mtime_utc(source_full)
            probe["sha256"] = sha256_file(source_full)
    elif args.mode == "filesystem_probe":
        probe["project_probe_skipped"] = True
        probe["notes"].append("Project path not provided; project/source probing skipped.")
    else:
        probe["project_probe_skipped"] = True
        probe["notes"].append("contract mode selected; filesystem project/source probing skipped.")

    # Cache evidence (filesystem_probe mode only)
    if args.mode == "filesystem_probe" and args.cache_path:
        cache_path = resolve_path(repo_root, args.cache_path)
        cache_exists = cache_path.exists() and cache_path.is_dir()
        probe["cache_path"] = str(cache_path)
        probe["cache_exists"] = cache_exists
        if cache_exists:
            probe["candidates"] = gather_cache_candidates(cache_path, source_asset_stem, args.max_candidates)
        else:
            probe["candidates"] = []
    elif args.mode == "filesystem_probe":
        probe["cache_probe_skipped"] = True
    else:
        probe["cache_probe_skipped"] = True
        probe["notes"].append("contract mode selected; cache probing skipped.")

    o3de_obj = manifest.get("o3de")
    if not isinstance(o3de_obj, dict):
        o3de_obj = {}
        manifest["o3de"] = o3de_obj

    o3de_obj["asset_probe"] = probe

    asset_resolution = o3de_obj.get("asset_resolution")
    if isinstance(asset_resolution, dict):
        asset_resolution["probe_available"] = True

    output_path = resolve_path(repo_root, args.output) if args.output else manifest_path
    write_json(output_path, manifest)

    validator_script = repo_root / "tools" / "manifest-validator" / "validate_manifest.py"
    cmd = [sys.executable, str(validator_script), str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        print(f"FAIL: manifest validation failed after probe update: {output_path}")
        return result.returncode

    print(f"PASS: filesystem probe evidence recorded in {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
