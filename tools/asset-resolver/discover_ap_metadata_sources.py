#!/usr/bin/env python3
"""Read-only discovery of candidate O3DE Asset Processor metadata sources."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


DISCOVERY_VERSION = "ap-metadata-discovery-1"
INCLUDE_HASH_CHOICES = {"true", "false"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def mtime_utc(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat()


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


def rel_to_project(path: Path, project_path: Path) -> str:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return path.as_posix()


def file_info(path: Path) -> Dict[str, Any]:
    return {
        "size_bytes": path.stat().st_size,
        "modified_utc": mtime_utc(path),
    }


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover read-only O3DE AP metadata source candidates.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--project-path", required=True, help="Path to O3DE project root")
    parser.add_argument("--output", default="", help="Optional output manifest path (defaults to in-place)")
    parser.add_argument(
        "--candidate-file",
        default="",
        help="Optional path to candidate config JSON (defaults to tools/asset-resolver/ap_metadata_candidates.json)",
    )
    parser.add_argument("--max-files-per-glob", type=int, default=100, help="Max matched files to keep per glob")
    parser.add_argument(
        "--include-hashes",
        default="false",
        help="Whether to include sha256 hashes for discovered database files (true|false)",
    )
    return parser.parse_args()


def normalized_path_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def first_candidate_path(project_path: Path, candidates: List[str], fallback: str) -> Path:
    if not candidates:
        return project_path / fallback
    for rel in candidates:
        candidate = project_path / Path(rel)
        if candidate.exists():
            return candidate
    return project_path / Path(candidates[0])


def discover_settings_registry_files(project_path: Path, patterns: List[str], max_per_glob: int) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    max_limit = max(1, max_per_glob)

    if not project_path.exists():
        return records

    for pattern in patterns:
        matches = sorted((p for p in project_path.glob(pattern) if p.is_file()), key=lambda p: p.as_posix().lower())
        for file_path in matches[:max_limit]:
            key = str(file_path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            info = file_info(file_path)
            records.append(
                {
                    "path": str(file_path),
                    "relative_path": rel_to_project(file_path, project_path),
                    "extension": file_path.suffix.lower(),
                    "size_bytes": info["size_bytes"],
                    "modified_utc": info["modified_utc"],
                }
            )
    return records


def discover_logs(project_path: Path, log_candidates: List[str]) -> List[Dict[str, Any]]:
    logs: List[Dict[str, Any]] = []
    for rel in log_candidates:
        path = project_path / Path(rel)
        record: Dict[str, Any] = {
            "path": str(path),
            "relative_path": rel.replace("\\", "/"),
            "exists": path.exists() and path.is_file(),
        }
        if record["exists"]:
            info = file_info(path)
            record["size_bytes"] = info["size_bytes"]
            record["modified_utc"] = info["modified_utc"]
        logs.append(record)
    return logs


def discover_cache_dirs(project_path: Path, cache_candidates: List[str]) -> List[Dict[str, Any]]:
    cache_dirs: List[Dict[str, Any]] = []
    for rel in cache_candidates:
        path = project_path / Path(rel)
        cache_dirs.append(
            {
                "path": str(path),
                "relative_path": rel.replace("\\", "/"),
                "exists": path.exists() and path.is_dir(),
            }
        )
    return cache_dirs


def add_db_candidate(
    path: Path,
    project_path: Path,
    include_hashes: bool,
    seen: Set[str],
    out: List[Dict[str, Any]],
) -> None:
    key = str(path.resolve()).lower() if path.exists() else str(path).lower()
    if key in seen:
        return
    seen.add(key)

    exists = path.exists() and path.is_file()
    record: Dict[str, Any] = {
        "path": str(path),
        "relative_path": rel_to_project(path, project_path),
        "exists": exists,
    }
    if exists:
        info = file_info(path)
        record["size_bytes"] = info["size_bytes"]
        record["modified_utc"] = info["modified_utc"]
        if include_hashes:
            record["sha256"] = sha256_of_file(path)
    out.append(record)


def discover_database_candidates(
    project_path: Path,
    cache_candidates: List[str],
    db_names: List[str],
    include_hashes: bool,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    db_name_set = {name.lower() for name in db_names}

    for cache_rel in cache_candidates:
        cache_path = project_path / Path(cache_rel)

        for db_name in db_names:
            add_db_candidate(cache_path / db_name, project_path, include_hashes, seen, out)

        if cache_path.exists() and cache_path.is_dir():
            for candidate in cache_path.rglob("*"):
                if not candidate.is_file():
                    continue
                if candidate.name.lower() in db_name_set:
                    add_db_candidate(candidate, project_path, include_hashes, seen, out)

    return out


def main() -> int:
    args = parse_args()
    include_hashes_raw = str(args.include_hashes).strip().lower()
    if include_hashes_raw not in INCLUDE_HASH_CHOICES:
        print("FAIL: --include-hashes must be true or false.")
        return 2
    include_hashes = include_hashes_raw == "true"

    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = resolve_path(repo_root, args.manifest)
    if not manifest_path.exists():
        print(f"FAIL: manifest file not found: {manifest_path}")
        return 2

    candidate_path = (
        resolve_path(repo_root, args.candidate_file)
        if args.candidate_file
        else (repo_root / "tools" / "asset-resolver" / "ap_metadata_candidates.json")
    )
    if not candidate_path.exists():
        print(f"FAIL: candidate config not found: {candidate_path}")
        return 2

    project_path = resolve_path(repo_root, args.project_path)

    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    try:
        candidates = load_json(candidate_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    project_manifest_candidates = normalized_path_list(candidates.get("project_manifest_candidates"))
    user_project_candidates = normalized_path_list(candidates.get("user_project_candidates"))
    registry_globs = normalized_path_list(candidates.get("settings_registry_globs"))
    log_candidates = normalized_path_list(candidates.get("log_candidates"))
    cache_dir_candidates = normalized_path_list(candidates.get("cache_dir_candidates"))
    database_name_candidates = normalized_path_list(candidates.get("database_name_candidates"))
    candidate_notes = normalized_path_list(candidates.get("notes"))

    project_exists = project_path.exists() and project_path.is_dir()

    project_json_path = first_candidate_path(project_path, project_manifest_candidates, "project.json")
    project_json_exists = project_json_path.exists() and project_json_path.is_file()
    project_json_record: Dict[str, Any] = {
        "path": str(project_json_path),
        "exists": project_json_exists,
    }
    if project_json_exists:
        project_json_record.update(file_info(project_json_path))
        try:
            project_data = load_json(project_json_path)
            if isinstance(project_data, dict):
                if "project_name" in project_data:
                    project_json_record["parsed_project_name"] = project_data.get("project_name")
                if "engine" in project_data:
                    project_json_record["parsed_engine"] = project_data.get("engine")
                if isinstance(project_data.get("external_subdirectories"), list):
                    project_json_record["parsed_external_subdirectories_count"] = len(
                        project_data.get("external_subdirectories")
                    )
        except ValueError as exc:
            project_json_record["parse_error"] = str(exc)

    user_project_path = first_candidate_path(project_path, user_project_candidates, "user/project.json")
    user_project_exists = user_project_path.exists() and user_project_path.is_file()
    user_project_record: Dict[str, Any] = {
        "path": str(user_project_path),
        "exists": user_project_exists,
    }
    if user_project_exists:
        user_project_record.update(file_info(user_project_path))

    settings_registry_files = discover_settings_registry_files(project_path, registry_globs, args.max_files_per_glob)
    logs = discover_logs(project_path, log_candidates)
    cache_dirs = discover_cache_dirs(project_path, cache_dir_candidates)
    database_candidates = discover_database_candidates(
        project_path, cache_dir_candidates, database_name_candidates, include_hashes
    )

    summary = {
        "registry_file_count": len(settings_registry_files),
        "log_candidate_count": len(logs),
        "existing_log_count": sum(1 for item in logs if item.get("exists")),
        "cache_dir_candidate_count": len(cache_dirs),
        "existing_cache_dir_count": sum(1 for item in cache_dirs if item.get("exists")),
        "database_candidate_count": len(database_candidates),
        "existing_database_candidate_count": sum(1 for item in database_candidates if item.get("exists")),
    }

    ap_metadata_discovery: Dict[str, Any] = {
        "discovery_version": DISCOVERY_VERSION,
        "project_path": str(project_path),
        "project_exists": project_exists,
        "project_json": project_json_record,
        "user_project_json": user_project_record,
        "settings_registry_files": settings_registry_files,
        "logs": logs,
        "cache_dirs": cache_dirs,
        "database_candidates": database_candidates,
        "summary": summary,
        "safety": {
            "read_only": True,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "modified_project": False,
            "authoritative_resolution": False,
            "real_o3de_query_used": False,
            "cache_guessing_used_as_success": False,
        },
        "updated_utc": utc_now(),
    }
    if candidate_notes:
        ap_metadata_discovery["notes"] = candidate_notes

    o3de_obj = manifest.get("o3de")
    if not isinstance(o3de_obj, dict):
        o3de_obj = {}
        manifest["o3de"] = o3de_obj
    o3de_obj["ap_metadata_discovery"] = ap_metadata_discovery

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
        print(f"FAIL: manifest validation failed after AP metadata discovery update: {output_path}")
        return result.returncode

    print(
        "PASS: AP metadata discovery recorded. "
        f"registry_files={summary['registry_file_count']} "
        f"existing_logs={summary['existing_log_count']} "
        f"existing_db_candidates={summary['existing_database_candidate_count']} "
        f"output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
