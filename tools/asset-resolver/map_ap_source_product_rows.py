#!/usr/bin/env python3
"""Read-only candidate source/product row mapping for AP-like SQLite databases."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


MAPPING_VERSION = "ap-row-mapping-1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


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
    parser = argparse.ArgumentParser(description="Read-only AP source/product row mapping.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--database", action="append", default=[], help="Database path (repeatable)")
    parser.add_argument("--project-path", default="", help="Optional project path for relative DB resolution")
    parser.add_argument("--source-asset", default="", help="Optional source asset hint for candidate matching")
    parser.add_argument("--output", default="", help="Optional output manifest path (defaults to in-place)")
    parser.add_argument("--max-rows-per-table", type=int, default=25, help="Max rows to sample per table")
    parser.add_argument("--source-table", action="append", default=[], help="Explicit source table name")
    parser.add_argument("--product-table", action="append", default=[], help="Explicit product table name")
    parser.add_argument("--job-table", action="append", default=[], help="Explicit job table name")
    parser.add_argument("--dependency-table", action="append", default=[], help="Explicit dependency table name")
    return parser.parse_args()


def normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def to_sqlite_ro_uri(path: Path) -> str:
    path_str = urllib.parse.quote(path.resolve().as_posix(), safe="/:")
    return f"file:{path_str}?mode=ro"


def gather_databases(
    manifest: Dict[str, Any],
    explicit_databases: Sequence[str],
    project_path: Optional[Path],
    repo_root: Path,
) -> List[Path]:
    result: List[Path] = []
    if explicit_databases:
        for raw in explicit_databases:
            p = Path(raw)
            if p.is_absolute():
                result.append(p)
            elif project_path is not None:
                result.append((project_path / p).resolve())
            else:
                result.append((repo_root / p).resolve())
        return result

    db_records = manifest.get("o3de", {}).get("ap_database_inspection", {}).get("databases", [])
    if not isinstance(db_records, list):
        return result

    for item in db_records:
        if not isinstance(item, dict):
            continue
        if not item.get("opened_read_only", False):
            continue
        raw_path = str(item.get("path", "")).strip()
        if not raw_path:
            continue
        p = Path(raw_path)
        if p.is_absolute():
            result.append(p)
        elif project_path is not None:
            result.append((project_path / p).resolve())
        else:
            result.append((repo_root / p).resolve())

    return result


def find_db_record_for_path(manifest: Dict[str, Any], db_path: Path) -> Optional[Dict[str, Any]]:
    db_records = manifest.get("o3de", {}).get("ap_database_inspection", {}).get("databases", [])
    if not isinstance(db_records, list):
        return None
    target = str(db_path.resolve()).lower()
    for item in db_records:
        if not isinstance(item, dict):
            continue
        raw_path = str(item.get("path", "")).strip()
        if not raw_path:
            continue
        try:
            item_resolved = str(Path(raw_path).resolve()).lower()
        except Exception:  # noqa: BLE001
            item_resolved = raw_path.lower()
        if item_resolved == target:
            return item
    return None


def unique_preserve(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def infer_table_roles_from_names(table_names: Sequence[str]) -> Dict[str, List[str]]:
    source: List[str] = []
    product: List[str] = []
    job: List[str] = []
    dependency: List[str] = []
    for name in table_names:
        low = name.lower()
        if "source" in low:
            source.append(name)
        if "product" in low:
            product.append(name)
        if "job" in low:
            job.append(name)
        if "depend" in low:
            dependency.append(name)
    return {
        "source_tables": unique_preserve(source),
        "product_tables": unique_preserve(product),
        "job_tables": unique_preserve(job),
        "dependency_tables": unique_preserve(dependency),
    }


def choose_candidate_tables(
    all_tables: Sequence[str],
    db_record: Optional[Dict[str, Any]],
    explicit_source: Sequence[str],
    explicit_product: Sequence[str],
    explicit_job: Sequence[str],
    explicit_dependency: Sequence[str],
) -> Dict[str, List[str]]:
    if explicit_source or explicit_product or explicit_job or explicit_dependency:
        return {
            "source_tables": unique_preserve(list(explicit_source)),
            "product_tables": unique_preserve(list(explicit_product)),
            "job_tables": unique_preserve(list(explicit_job)),
            "dependency_tables": unique_preserve(list(explicit_dependency)),
        }

    if db_record and isinstance(db_record.get("candidate_table_roles"), dict):
        roles = db_record.get("candidate_table_roles", {})
        return {
            "source_tables": unique_preserve([str(x) for x in roles.get("source_tables", [])]),
            "product_tables": unique_preserve([str(x) for x in roles.get("product_tables", [])]),
            "job_tables": unique_preserve([str(x) for x in roles.get("job_tables", [])]),
            "dependency_tables": unique_preserve([str(x) for x in roles.get("dependency_tables", [])]),
        }

    return infer_table_roles_from_names(all_tables)


def list_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    ).fetchall()
    return [str(row[0]) for row in rows]


def list_columns(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    escaped = quote_ident(table_name)
    rows = conn.execute(f'PRAGMA table_info("{escaped}")').fetchall()
    cols: List[Dict[str, Any]] = []
    for row in rows:
        cols.append(
            {
                "name": row[1] if len(row) > 1 else "",
                "type": row[2] if len(row) > 2 else "",
                "notnull": int(row[3]) if len(row) > 3 else 0,
                "pk": int(row[5]) if len(row) > 5 else 0,
                "default": normalize_value(row[4] if len(row) > 4 else None),
            }
        )
    return cols


def sample_rows(conn: sqlite3.Connection, table_name: str, limit: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    escaped = quote_ident(table_name)
    query = f'SELECT * FROM "{escaped}" LIMIT {max(1, limit)};'
    try:
        cursor = conn.execute(query)
        names = [d[0] for d in (cursor.description or [])]
        out: List[Dict[str, Any]] = []
        for raw_row in cursor.fetchall():
            row_obj: Dict[str, Any] = {}
            for idx, value in enumerate(raw_row):
                key = names[idx] if idx < len(names) else f"col_{idx}"
                row_obj[str(key)] = normalize_value(value)
            out.append(row_obj)
        return out, None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def infer_column_role_hints(columns: Sequence[str]) -> Dict[str, List[str]]:
    hints = {
        "source_path_columns": [],
        "source_uuid_columns": [],
        "product_path_columns": [],
        "product_subid_columns": [],
        "job_status_columns": [],
    }
    for col in columns:
        low = col.lower()
        if any(token in low for token in ("source", "path", "name", "file")):
            hints["source_path_columns"].append(col)
        if "uuid" in low or "guid" in low:
            hints["source_uuid_columns"].append(col)
        if any(token in low for token in ("product", "path", "name", "file")):
            hints["product_path_columns"].append(col)
        if "subid" in low or "sub_id" in low:
            hints["product_subid_columns"].append(col)
        if any(token in low for token in ("status", "state", "result")):
            hints["job_status_columns"].append(col)
    for key, vals in hints.items():
        hints[key] = unique_preserve(vals)
    return hints


def row_matches_source(row_obj: Dict[str, Any], source_name: str, source_stem: str) -> bool:
    target_name = source_name.lower()
    target_stem = source_stem.lower()
    if not target_name and not target_stem:
        return False
    for value in row_obj.values():
        if value is None:
            continue
        low = str(value).lower()
        if target_name and target_name in low:
            return True
        if target_stem and target_stem in low:
            return True
    return False


def inspect_database_rows(
    db_path: Path,
    manifest: Dict[str, Any],
    max_rows_per_table: int,
    explicit_source_tables: Sequence[str],
    explicit_product_tables: Sequence[str],
    explicit_job_tables: Sequence[str],
    explicit_dependency_tables: Sequence[str],
    source_asset_name: str,
    source_asset_stem: str,
) -> Tuple[Dict[str, Any], int]:
    record: Dict[str, Any] = {
        "path": str(db_path),
        "exists": db_path.exists() and db_path.is_file(),
        "opened_read_only": False,
    }
    if not record["exists"]:
        record["open_error"] = "Database path does not exist or is not a file."
        return record, 0

    conn: Optional[sqlite3.Connection] = None
    candidate_source_match_count = 0
    try:
        conn = sqlite3.connect(to_sqlite_ro_uri(db_path), uri=True)
        record["opened_read_only"] = True
        all_tables = list_tables(conn)
        db_record = find_db_record_for_path(manifest, db_path)
        roles = choose_candidate_tables(
            all_tables=all_tables,
            db_record=db_record,
            explicit_source=explicit_source_tables,
            explicit_product=explicit_product_tables,
            explicit_job=explicit_job_tables,
            explicit_dependency=explicit_dependency_tables,
        )
        record["candidate_tables"] = roles

        table_names_by_role: List[Tuple[str, str]] = []
        for role_key, role_label in (
            ("source_tables", "source"),
            ("product_tables", "product"),
            ("job_tables", "job"),
            ("dependency_tables", "dependency"),
        ):
            for name in roles.get(role_key, []):
                table_names_by_role.append((name, role_label))

        sampled_tables: List[Dict[str, Any]] = []
        existing_set = {t.lower(): t for t in all_tables}
        for table_name, role_label in table_names_by_role:
            table_record: Dict[str, Any] = {
                "name": table_name,
                "role": role_label,
            }
            resolved_table_name = existing_set.get(table_name.lower())
            if resolved_table_name is None:
                table_record["table_exists"] = False
                table_record["columns"] = []
                table_record["sampled_rows"] = []
                table_record["row_count_sampled"] = 0
                sampled_tables.append(table_record)
                continue

            table_record["table_exists"] = True
            cols = list_columns(conn, resolved_table_name)
            col_names = [str(c.get("name", "")) for c in cols]
            table_record["columns"] = cols
            table_record["column_role_hints"] = infer_column_role_hints(col_names)
            rows, sample_error = sample_rows(conn, resolved_table_name, max_rows_per_table)
            table_record["sampled_rows"] = rows
            table_record["row_count_sampled"] = len(rows)
            if sample_error:
                table_record["sample_error"] = sample_error

            if source_asset_name or source_asset_stem:
                match_count = 0
                for row_obj in rows:
                    if row_matches_source(row_obj, source_asset_name, source_asset_stem):
                        match_count += 1
                if match_count > 0:
                    table_record["candidate_source_matches"] = {
                        "matched": True,
                        "matched_row_count": match_count,
                        "heuristic": "source_name_or_stem_contains",
                    }
                    candidate_source_match_count += match_count
                else:
                    table_record["candidate_source_matches"] = {
                        "matched": False,
                        "matched_row_count": 0,
                        "heuristic": "source_name_or_stem_contains",
                    }

            sampled_tables.append(table_record)

        record["tables"] = sampled_tables
    except Exception as exc:  # noqa: BLE001
        record["open_error"] = str(exc)
    finally:
        if conn is not None:
            conn.close()

    return record, candidate_source_match_count


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

    project_path: Optional[Path] = None
    if args.project_path:
        project_path = resolve_path(repo_root, args.project_path)

    database_paths = gather_databases(manifest, args.database, project_path, repo_root)
    if not database_paths:
        print("FAIL: no databases supplied or discovered from manifest.o3de.ap_database_inspection.databases.")
        return 2

    source_asset_name = ""
    source_asset_stem = ""
    if args.source_asset:
        p = Path(str(args.source_asset))
        source_asset_name = p.name
        source_asset_stem = p.stem

    db_results: List[Dict[str, Any]] = []
    opened_count = 0
    source_table_count = 0
    product_table_count = 0
    job_table_count = 0
    dependency_table_count = 0
    sampled_row_count = 0
    candidate_source_match_count = 0

    for db_path in database_paths:
        record, matches = inspect_database_rows(
            db_path=db_path,
            manifest=manifest,
            max_rows_per_table=max(1, args.max_rows_per_table),
            explicit_source_tables=args.source_table,
            explicit_product_tables=args.product_table,
            explicit_job_tables=args.job_table,
            explicit_dependency_tables=args.dependency_table,
            source_asset_name=source_asset_name,
            source_asset_stem=source_asset_stem,
        )
        db_results.append(record)
        if record.get("opened_read_only"):
            opened_count += 1
            candidate_tables = record.get("candidate_tables", {})
            if isinstance(candidate_tables, dict):
                source_table_count += len(candidate_tables.get("source_tables", []))
                product_table_count += len(candidate_tables.get("product_tables", []))
                job_table_count += len(candidate_tables.get("job_tables", []))
                dependency_table_count += len(candidate_tables.get("dependency_tables", []))

            for table in record.get("tables", []):
                if isinstance(table, dict):
                    sampled_row_count += int(table.get("row_count_sampled", 0))
            candidate_source_match_count += matches

    if opened_count == 0:
        print("FAIL: all database opens failed in read-only mode.")
        return 2

    mapping: Dict[str, Any] = {
        "mapping_version": MAPPING_VERSION,
        "status": "mapped_candidate_rows",
        "source_asset_input": args.source_asset if args.source_asset else "",
        "databases": db_results,
        "summary": {
            "inspected_database_count": len(db_results),
            "opened_database_count": opened_count,
            "source_table_count": source_table_count,
            "product_table_count": product_table_count,
            "job_table_count": job_table_count,
            "dependency_table_count": dependency_table_count,
            "sampled_row_count": sampled_row_count,
            "candidate_source_match_count": candidate_source_match_count,
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
            "row_presence_is_resolution": False,
        },
        "updated_utc": utc_now(),
    }

    if opened_count < len(db_results):
        failed = len(db_results) - opened_count
        mapping["warnings"] = [f"{failed} database(s) failed to open. See databases[*].open_error."]

    o3de_obj = manifest.get("o3de")
    if not isinstance(o3de_obj, dict):
        o3de_obj = {}
        manifest["o3de"] = o3de_obj
    o3de_obj["ap_row_mapping"] = mapping

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
        print(f"FAIL: manifest validation failed after row mapping update: {output_path}")
        return result.returncode

    print(
        "PASS: AP row mapping recorded. "
        f"inspected={len(db_results)} opened={opened_count} sampled_rows={sampled_row_count} "
        f"candidate_source_matches={candidate_source_match_count} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
