#!/usr/bin/env python3
"""Read-only SQLite schema inspection for O3DE Asset Processor candidates."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional


INSPECTION_VERSION = "ap-db-schema-inspection-1"
TRUE_FALSE_CHOICES = {"true", "false"}


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


def quote_ident(identifier: str) -> str:
    return identifier.replace('"', '""')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect AP SQLite schema candidates in read-only mode.")
    parser.add_argument("--manifest", required=True, help="Path to input manifest JSON")
    parser.add_argument(
        "--database",
        action="append",
        default=[],
        help="Database path to inspect (repeatable). If omitted, discovered candidates from manifest are used.",
    )
    parser.add_argument("--project-path", default="", help="Optional project path for resolving relative db paths")
    parser.add_argument("--output", default="", help="Optional output manifest path (defaults to in-place)")
    parser.add_argument("--max-row-count-tables", type=int, default=50, help="Limit row-count queries per database")
    parser.add_argument("--max-indexes-per-table", type=int, default=50, help="Limit indexes collected per table")
    parser.add_argument(
        "--skip-row-counts",
        default="false",
        help="Skip COUNT(*) table scans (true|false).",
    )
    return parser.parse_args()


def infer_roles(table_names: List[str]) -> Dict[str, List[str]]:
    roles = {
        "source_tables": [],
        "product_tables": [],
        "job_tables": [],
        "scanfolder_tables": [],
        "builder_tables": [],
        "dependency_tables": [],
    }
    for name in table_names:
        low = name.lower()
        if "source" in low:
            roles["source_tables"].append(name)
        if "product" in low:
            roles["product_tables"].append(name)
        if "job" in low:
            roles["job_tables"].append(name)
        if "scan" in low or "folder" in low:
            roles["scanfolder_tables"].append(name)
        if "builder" in low:
            roles["builder_tables"].append(name)
        if "depend" in low:
            roles["dependency_tables"].append(name)
    return roles


def to_sqlite_ro_uri(path: Path) -> str:
    path_str = urllib.parse.quote(path.resolve().as_posix(), safe="/:")
    return f"file:{path_str}?mode=ro"


def list_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    ).fetchall()
    return [str(row[0]) for row in rows]


def list_columns(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    escaped = quote_ident(table_name)
    rows = conn.execute(f'PRAGMA table_info("{escaped}")').fetchall()
    columns: List[Dict[str, Any]] = []
    for row in rows:
        # cid, name, type, notnull, dflt_value, pk
        columns.append(
            {
                "name": row[1] if len(row) > 1 else "",
                "type": row[2] if len(row) > 2 else "",
                "notnull": int(row[3]) if len(row) > 3 else 0,
                "pk": int(row[5]) if len(row) > 5 else 0,
                "default": row[4] if len(row) > 4 else None,
            }
        )
    return columns


def list_indexes(conn: sqlite3.Connection, table_name: str, max_indexes: int) -> Dict[str, Any]:
    escaped = quote_ident(table_name)
    rows = conn.execute(f'PRAGMA index_list("{escaped}")').fetchall()
    indexes: List[Dict[str, Any]] = []
    for row in rows[: max(1, max_indexes)]:
        indexes.append(
            {
                "name": row[1] if len(row) > 1 else "",
                "unique": bool(row[2]) if len(row) > 2 else False,
                "origin": row[3] if len(row) > 3 else "",
                "partial": bool(row[4]) if len(row) > 4 else False,
            }
        )
    result: Dict[str, Any] = {"indexes": indexes}
    if len(rows) > max(1, max_indexes):
        result["indexes_truncated"] = True
        result["indexes_total"] = len(rows)
    return result


def resolve_database_candidates(
    manifest: Dict[str, Any],
    explicit_databases: List[str],
    project_path: Optional[Path],
    repo_root: Path,
) -> List[Path]:
    resolved: List[Path] = []

    if explicit_databases:
        for raw in explicit_databases:
            candidate = Path(raw)
            if candidate.is_absolute():
                resolved.append(candidate)
            elif project_path is not None:
                resolved.append((project_path / candidate).resolve())
            else:
                resolved.append((repo_root / candidate).resolve())
        return resolved

    db_candidates = manifest.get("o3de", {}).get("ap_metadata_discovery", {}).get("database_candidates", [])
    if not isinstance(db_candidates, list):
        return resolved

    for item in db_candidates:
        if not isinstance(item, dict):
            continue
        if not item.get("exists", False):
            continue
        raw_path = str(item.get("path", "")).strip() or str(item.get("relative_path", "")).strip()
        if not raw_path:
            continue
        candidate = Path(raw_path)
        if candidate.is_absolute():
            resolved.append(candidate)
        elif project_path is not None:
            resolved.append((project_path / candidate).resolve())
        else:
            resolved.append((repo_root / candidate).resolve())

    return resolved


def inspect_database(
    db_path: Path,
    skip_row_counts: bool,
    max_row_count_tables: int,
    max_indexes_per_table: int,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "path": str(db_path),
        "exists": db_path.exists() and db_path.is_file(),
        "opened_read_only": False,
    }

    if not record["exists"]:
        record["open_error"] = "Database path does not exist or is not a file."
        return record

    record["size_bytes"] = db_path.stat().st_size
    record["modified_utc"] = mtime_utc(db_path)

    uri = to_sqlite_ro_uri(db_path)
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(uri, uri=True)
        record["opened_read_only"] = True
        table_names = list_tables(conn)
        tables: List[Dict[str, Any]] = []
        row_count_limit = max(1, max_row_count_tables)

        for idx, table_name in enumerate(table_names):
            table_record: Dict[str, Any] = {
                "name": table_name,
                "columns": list_columns(conn, table_name),
            }
            idx_info = list_indexes(conn, table_name, max_indexes_per_table)
            table_record["indexes"] = idx_info["indexes"]
            if "indexes_truncated" in idx_info:
                table_record["indexes_truncated"] = True
                table_record["indexes_total"] = idx_info["indexes_total"]

            if not skip_row_counts:
                if idx < row_count_limit:
                    escaped = quote_ident(table_name)
                    try:
                        count = conn.execute(f'SELECT COUNT(*) FROM "{escaped}";').fetchone()
                        table_record["row_count"] = int(count[0]) if count else 0
                    except Exception as exc:  # noqa: BLE001
                        table_record["row_count_error"] = str(exc)
                else:
                    table_record["row_count_skipped"] = True

            tables.append(table_record)

        roles = infer_roles(table_names)
        record["tables"] = tables
        record["candidate_table_roles"] = {
            **roles,
            "heuristic": "name_contains",
        }
    except Exception as exc:  # noqa: BLE001
        record["open_error"] = str(exc)
    finally:
        if conn is not None:
            conn.close()

    return record


def main() -> int:
    args = parse_args()
    skip_row_counts_raw = str(args.skip_row_counts).strip().lower()
    if skip_row_counts_raw not in TRUE_FALSE_CHOICES:
        print("FAIL: --skip-row-counts must be true or false.")
        return 2
    skip_row_counts = skip_row_counts_raw == "true"

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

    project_path: Optional[Path] = None
    if args.project_path:
        project_path = resolve_path(repo_root, args.project_path)

    database_paths = resolve_database_candidates(manifest, args.database, project_path, repo_root)
    if not database_paths:
        print("FAIL: no databases supplied or discovered in manifest.o3de.ap_metadata_discovery.database_candidates.")
        return 2

    db_records: List[Dict[str, Any]] = []
    opened_count = 0
    failed_count = 0
    total_tables = 0
    source_count = 0
    product_count = 0
    job_count = 0
    dependency_count = 0

    for db_path in database_paths:
        record = inspect_database(
            db_path=db_path,
            skip_row_counts=skip_row_counts,
            max_row_count_tables=args.max_row_count_tables,
            max_indexes_per_table=args.max_indexes_per_table,
        )
        db_records.append(record)

        if record.get("opened_read_only"):
            opened_count += 1
            tables = record.get("tables", [])
            if isinstance(tables, list):
                total_tables += len(tables)
            roles = record.get("candidate_table_roles", {})
            if isinstance(roles, dict):
                source_count += len(roles.get("source_tables", []))
                product_count += len(roles.get("product_tables", []))
                job_count += len(roles.get("job_tables", []))
                dependency_count += len(roles.get("dependency_tables", []))
        else:
            failed_count += 1

    if opened_count == 0:
        print("FAIL: all database inspections failed to open read-only.")
        return 2

    inspection: Dict[str, Any] = {
        "inspection_version": INSPECTION_VERSION,
        "status": "inspected",
        "databases": db_records,
        "summary": {
            "inspected_database_count": len(db_records),
            "opened_database_count": opened_count,
            "failed_database_count": failed_count,
            "total_table_count": total_tables,
            "heuristic_source_table_count": source_count,
            "heuristic_product_table_count": product_count,
            "heuristic_job_table_count": job_count,
            "heuristic_dependency_table_count": dependency_count,
        },
        "safety": {
            "read_only": True,
            "opened_sqlite_read_only": True,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": False,
        },
        "updated_utc": utc_now(),
    }
    if failed_count > 0:
        inspection["warnings"] = [
            f"{failed_count} database(s) failed to open read-only. See databases[*].open_error."
        ]

    o3de_obj = manifest.get("o3de")
    if not isinstance(o3de_obj, dict):
        o3de_obj = {}
        manifest["o3de"] = o3de_obj
    o3de_obj["ap_database_inspection"] = inspection

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
        print(f"FAIL: manifest validation failed after DB inspection update: {output_path}")
        return result.returncode

    print(
        "PASS: AP DB schema inspection recorded. "
        f"inspected={len(db_records)} opened={opened_count} failed={failed_count} tables={total_tables} "
        f"heuristic_source={source_count} heuristic_product={product_count} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
