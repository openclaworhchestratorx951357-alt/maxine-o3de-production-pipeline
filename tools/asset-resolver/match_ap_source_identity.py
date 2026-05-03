#!/usr/bin/env python3
"""Read-only candidate source identity matching from AP row-mapping evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


MATCHING_VERSION = "ap-source-identity-match-1"
HIGH_CONFIDENCE_THRESHOLD = 0.80


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


def normalize_path(value: str) -> str:
    out = str(value).strip().replace("\\", "/").lower()
    out = re.sub(r"/+", "/", out)
    while out.startswith("./"):
        out = out[2:]
    return out.strip()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def path_basename(path_text: str) -> str:
    if not path_text:
        return ""
    return path_text.rsplit("/", 1)[-1]


def path_stem(path_text: str) -> str:
    base = path_basename(path_text)
    if "." not in base:
        return base
    return base.rsplit(".", 1)[0]


def infer_source_input(manifest: Dict[str, Any], explicit: str) -> str:
    if explicit:
        return str(explicit)

    inputs = manifest.get("inputs", {})
    if isinstance(inputs, dict):
        maybe = str(inputs.get("input_path", "")).strip()
        if maybe:
            return maybe

    probe = manifest.get("o3de", {}).get("asset_probe", {})
    if isinstance(probe, dict):
        maybe = str(probe.get("source_asset_input", "")).strip()
        if maybe:
            return maybe

    resolution = manifest.get("o3de", {}).get("asset_resolution", {})
    if isinstance(resolution, dict):
        maybe = str(resolution.get("source_asset_input", "")).strip()
        if maybe:
            return maybe

    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match candidate source identity from AP row mapping evidence.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--source-asset", default="", help="Optional source asset override")
    parser.add_argument("--output", default="", help="Optional output path (defaults to in-place)")
    parser.add_argument("--min-confidence", type=float, default=0.50, help="Minimum confidence for candidate matches")
    return parser.parse_args()


def table_is_source(table: Dict[str, Any], source_table_names: Sequence[str]) -> bool:
    role = str(table.get("role", "")).strip().lower()
    name = str(table.get("name", "")).strip()
    if role == "source":
        return True
    names_l = {n.lower() for n in source_table_names}
    if name.lower() in names_l:
        return True
    if "source" in name.lower():
        return True
    return False


def infer_column_lists(table: Dict[str, Any], sampled_rows: Sequence[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    col_names: List[str] = []
    for c in table.get("columns", []):
        if isinstance(c, dict):
            name = str(c.get("name", "")).strip()
            if name:
                col_names.append(name)
    if not col_names and sampled_rows:
        first = sampled_rows[0]
        if isinstance(first, dict):
            col_names = [str(k) for k in first.keys()]

    path_cols: List[str] = []
    uuid_cols: List[str] = []
    for col in col_names:
        low = col.lower()
        if any(token in low for token in ("source", "path", "name", "file")):
            path_cols.append(col)
        if "uuid" in low or "guid" in low:
            uuid_cols.append(col)
    return path_cols, uuid_cols


def score_row(
    row: Dict[str, Any],
    path_cols: Sequence[str],
    uuid_cols: Sequence[str],
    normalized_source: str,
    source_name: str,
    source_stem: str,
) -> Dict[str, Any]:
    row_text = {str(k): safe_text(v) for k, v in row.items()}
    row_path_info: List[Tuple[str, str, str]] = []
    for col in path_cols:
        raw = row_text.get(col, "")
        if not raw:
            continue
        norm = normalize_path(raw)
        row_path_info.append((col, raw, norm))

    reason_codes: List[str] = []
    matched_fields: List[Dict[str, str]] = []
    score = 0.0

    def add_reason(code: str, weight: float, col: str, raw_value: str, normalized_value: str) -> None:
        nonlocal score
        if code not in reason_codes:
            reason_codes.append(code)
            score += weight
            matched_fields.append(
                {
                    "column": col,
                    "value": raw_value,
                    "normalized_value": normalized_value,
                    "weight": f"{weight:.2f}",
                }
            )

    if normalized_source:
        for col, raw, norm in row_path_info:
            if norm == normalized_source:
                add_reason("exact_normalized_path_match", 0.70, col, raw, norm)
                break

        for col, raw, norm in row_path_info:
            if norm and normalized_source and norm.endswith(normalized_source):
                add_reason("path_suffix_match", 0.60, col, raw, norm)
                break

    for col, raw, norm in row_path_info:
        if source_name and path_basename(norm) == source_name:
            add_reason("filename_exact_match", 0.35, col, raw, norm)
            break

    for col, raw, norm in row_path_info:
        if source_stem and path_stem(norm) == source_stem:
            add_reason("stem_exact_match", 0.20, col, raw, norm)
            break

    uuid_values: List[Dict[str, str]] = []
    for col in uuid_cols:
        val = row_text.get(col, "").strip()
        if val:
            uuid_values.append({"column": col, "value": val})
    if uuid_values:
        reason_codes.append("uuid_like_field_present")
        score += 0.10

    return {
        "confidence": min(1.0, round(score, 4)),
        "reason_codes": reason_codes,
        "matched_fields": matched_fields,
        "uuid_like_fields": uuid_values,
        "row_values": row_text,
    }


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

    min_conf = float(args.min_confidence)
    if min_conf < 0.0:
        min_conf = 0.0
    if min_conf > 1.0:
        min_conf = 1.0

    source_asset_input = infer_source_input(manifest, args.source_asset)
    if not source_asset_input:
        print("FAIL: no source asset could be determined from args or manifest fallback fields.")
        return 2

    normalized_source = normalize_path(source_asset_input)
    source_name = path_basename(normalized_source)
    source_stem = path_stem(normalized_source)
    source_extension = ""
    if "." in source_name:
        source_extension = "." + source_name.rsplit(".", 1)[1]

    ap_row_mapping = manifest.get("o3de", {}).get("ap_row_mapping")
    if not isinstance(ap_row_mapping, dict):
        print("FAIL: manifest.o3de.ap_row_mapping is missing.")
        return 2
    databases = ap_row_mapping.get("databases", [])
    if not isinstance(databases, list):
        print("FAIL: manifest.o3de.ap_row_mapping.databases is missing or invalid.")
        return 2

    candidates: List[Dict[str, Any]] = []
    source_rows_considered = 0

    for db in databases:
        if not isinstance(db, dict):
            continue
        db_path = str(db.get("path", ""))
        source_table_names = []
        candidate_tables = db.get("candidate_tables", {})
        if isinstance(candidate_tables, dict):
            source_table_names = [str(x) for x in candidate_tables.get("source_tables", [])]

        tables = db.get("tables", [])
        if not isinstance(tables, list):
            continue

        for table in tables:
            if not isinstance(table, dict):
                continue
            if not table_is_source(table, source_table_names):
                continue
            table_name = str(table.get("name", ""))
            sampled_rows = table.get("sampled_rows", [])
            if not isinstance(sampled_rows, list):
                continue

            typed_rows: List[Dict[str, Any]] = [r for r in sampled_rows if isinstance(r, dict)]
            source_rows_considered += len(typed_rows)
            path_cols, uuid_cols = infer_column_lists(table, typed_rows)

            for idx, row in enumerate(typed_rows):
                scored = score_row(
                    row=row,
                    path_cols=path_cols,
                    uuid_cols=uuid_cols,
                    normalized_source=normalized_source,
                    source_name=source_name,
                    source_stem=source_stem,
                )
                confidence = float(scored.get("confidence", 0.0))
                if confidence < min_conf:
                    continue
                reason_codes = scored.get("reason_codes", [])
                if not reason_codes:
                    continue

                candidates.append(
                    {
                        "database_path": db_path,
                        "table_name": table_name,
                        "row_index": idx,
                        "confidence": confidence,
                        "reason_codes": reason_codes,
                        "matched_fields": scored.get("matched_fields", []),
                        "uuid_like_fields": scored.get("uuid_like_fields", []),
                        "row_values": scored.get("row_values", {}),
                    }
                )

    candidates.sort(
        key=lambda c: (
            -float(c.get("confidence", 0.0)),
            str(c.get("database_path", "")),
            str(c.get("table_name", "")),
            int(c.get("row_index", 0)),
        )
    )

    best_match = candidates[0] if candidates else None
    best_conf = float(best_match.get("confidence", 0.0)) if best_match else 0.0
    high_conf_count = sum(1 for c in candidates if float(c.get("confidence", 0.0)) >= HIGH_CONFIDENCE_THRESHOLD)
    status = "candidate_match" if candidates else "no_match"

    match_block: Dict[str, Any] = {
        "matching_version": MATCHING_VERSION,
        "status": status,
        "source_asset_input": source_asset_input,
        "normalized_source_asset": normalized_source,
        "source_asset_name": source_name,
        "source_asset_stem": source_stem,
        "source_asset_extension": source_extension,
        "min_confidence": min_conf,
        "candidate_matches": candidates,
        "best_match": best_match,
        "summary": {
            "source_rows_considered": source_rows_considered,
            "candidate_match_count": len(candidates),
            "high_confidence_match_count": high_conf_count,
            "best_confidence": best_conf,
        },
        "safety": {
            "read_only": True,
            "opened_database": False,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_source_uuid": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": False,
            "source_identity_is_product_resolution": False,
        },
        "updated_utc": utc_now(),
    }

    o3de_obj = manifest.get("o3de")
    if not isinstance(o3de_obj, dict):
        o3de_obj = {}
        manifest["o3de"] = o3de_obj
    o3de_obj["ap_source_identity_match"] = match_block

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
        print(f"FAIL: manifest validation failed after source identity match update: {output_path}")
        return result.returncode

    print(
        "PASS: AP source identity matching recorded. "
        f"status={status} source_rows={source_rows_considered} "
        f"candidate_matches={len(candidates)} best_confidence={best_conf:.2f} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
