#!/usr/bin/env python3
"""Extract read-only AP product freshness proof evidence from manifest data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


PROOF_VERSION = "ap-product-freshness-proof-1"
TIME_FIELD_TOKENS = ("time", "date", "created", "updated", "modified", "utc")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def resolve_path(base: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Failed to parse JSON from {path}: {exc}") from exc


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract AP product freshness proof from manifest evidence only.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output", default="", help="Optional output path (defaults to in-place)")
    parser.add_argument("--max-stale-seconds", type=int, default=0, help="Allowed product staleness tolerance seconds")
    return parser.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def parse_timestamp(value: Any) -> Optional[dt.datetime]:
    text = safe_text(value).strip()
    if not text:
        return None

    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except Exception:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    else:
        parsed = parsed.astimezone(dt.timezone.utc)
    return parsed


def maybe_collect_timestamp(entries: List[Dict[str, str]], source: str, location: str, raw_value: Any) -> None:
    parsed = parse_timestamp(raw_value)
    if parsed is None:
        return
    entries.append(
        {
            "source": source,
            "location": location,
            "raw_value": safe_text(raw_value),
            "parsed_utc": parsed.isoformat(),
        }
    )


def has_time_token(field_name: str) -> bool:
    lower = str(field_name).lower()
    return any(token in lower for token in TIME_FIELD_TOKENS)


def is_table_role(table: Dict[str, Any], role_name: str) -> bool:
    role = str(table.get("role", "")).strip().lower()
    name = str(table.get("name", "")).strip().lower()
    return role == role_name or role_name in name


def dedupe_timestamp_entries(entries: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[str] = set()
    out: List[Dict[str, str]] = []
    for entry in entries:
        key = "|".join(
            [
                str(entry.get("source", "")),
                str(entry.get("location", "")),
                str(entry.get("parsed_utc", "")),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def collect_source_timestamps(o3de: Dict[str, Any]) -> List[Dict[str, str]]:
    timestamps: List[Dict[str, str]] = []

    asset_probe = o3de.get("asset_probe")
    if isinstance(asset_probe, dict):
        maybe_collect_timestamp(timestamps, "asset_probe", "modified_utc", asset_probe.get("modified_utc"))
        maybe_collect_timestamp(timestamps, "asset_probe", "updated_utc", asset_probe.get("updated_utc"))

    row_mapping = o3de.get("ap_row_mapping")
    databases = row_mapping.get("databases", []) if isinstance(row_mapping, dict) else []
    if isinstance(databases, list):
        for d_idx, database in enumerate(databases):
            if not isinstance(database, dict):
                continue
            tables = database.get("tables", [])
            if not isinstance(tables, list):
                continue
            for t_idx, table in enumerate(tables):
                if not isinstance(table, dict) or not is_table_role(table, "source"):
                    continue
                rows = table.get("sampled_rows", [])
                if not isinstance(rows, list):
                    continue
                for r_idx, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    for key, value in row.items():
                        if has_time_token(str(key)):
                            maybe_collect_timestamp(
                                timestamps,
                                "ap_row_mapping",
                                f"databases[{d_idx}].tables[{t_idx}].sampled_rows[{r_idx}].{key}",
                                value,
                            )

    return dedupe_timestamp_entries(timestamps)


def collect_product_timestamps(o3de: Dict[str, Any]) -> tuple[List[Dict[str, str]], int]:
    timestamps: List[Dict[str, str]] = []
    product_file_timestamp_count = 0

    file_validation = o3de.get("ap_product_file_validation")
    validated_candidates = file_validation.get("validated_candidates", []) if isinstance(file_validation, dict) else []
    if isinstance(validated_candidates, list):
        for c_idx, candidate in enumerate(validated_candidates):
            if not isinstance(candidate, dict):
                continue
            path_checks = candidate.get("path_checks", [])
            if not isinstance(path_checks, list):
                continue
            for p_idx, check in enumerate(path_checks):
                if not isinstance(check, dict):
                    continue
                modified_utc = check.get("modified_utc")
                parsed = parse_timestamp(modified_utc)
                if parsed is not None:
                    product_file_timestamp_count += 1
                    timestamps.append(
                        {
                            "source": "ap_product_file_validation",
                            "location": f"validated_candidates[{c_idx}].path_checks[{p_idx}].modified_utc",
                            "raw_value": safe_text(modified_utc),
                            "parsed_utc": parsed.isoformat(),
                        }
                    )

    product_match = o3de.get("ap_product_candidate_match")
    candidates = product_match.get("candidate_products", []) if isinstance(product_match, dict) else []
    if isinstance(candidates, list):
        for c_idx, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue
            row_values = candidate.get("row_values", {})
            if not isinstance(row_values, dict):
                continue
            for key, value in row_values.items():
                if has_time_token(str(key)):
                    maybe_collect_timestamp(
                        timestamps,
                        "ap_product_candidate_match",
                        f"candidate_products[{c_idx}].row_values.{key}",
                        value,
                    )

    row_mapping = o3de.get("ap_row_mapping")
    databases = row_mapping.get("databases", []) if isinstance(row_mapping, dict) else []
    if isinstance(databases, list):
        for d_idx, database in enumerate(databases):
            if not isinstance(database, dict):
                continue
            tables = database.get("tables", [])
            if not isinstance(tables, list):
                continue
            for t_idx, table in enumerate(tables):
                if not isinstance(table, dict) or not is_table_role(table, "product"):
                    continue
                rows = table.get("sampled_rows", [])
                if not isinstance(rows, list):
                    continue
                for r_idx, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    for key, value in row.items():
                        if has_time_token(str(key)):
                            maybe_collect_timestamp(
                                timestamps,
                                "ap_row_mapping",
                                f"databases[{d_idx}].tables[{t_idx}].sampled_rows[{r_idx}].{key}",
                                value,
                            )

    return dedupe_timestamp_entries(timestamps), product_file_timestamp_count


def collect_job_timestamps(o3de: Dict[str, Any]) -> List[Dict[str, str]]:
    timestamps: List[Dict[str, str]] = []
    job_state = o3de.get("ap_job_state_proof")
    candidate_rows = job_state.get("candidate_job_rows", []) if isinstance(job_state, dict) else []
    if not isinstance(candidate_rows, list):
        return timestamps

    for j_idx, row in enumerate(candidate_rows):
        if not isinstance(row, dict):
            continue

        ts_fields = row.get("timestamp_fields", {})
        if isinstance(ts_fields, dict):
            for key, value in ts_fields.items():
                maybe_collect_timestamp(
                    timestamps,
                    "ap_job_state_proof",
                    f"candidate_job_rows[{j_idx}].timestamp_fields.{key}",
                    value,
                )

        row_values = row.get("row_values", {})
        if isinstance(row_values, dict):
            for key, value in row_values.items():
                if has_time_token(str(key)):
                    maybe_collect_timestamp(
                        timestamps,
                        "ap_job_state_proof",
                        f"candidate_job_rows[{j_idx}].row_values.{key}",
                        value,
                    )

    return dedupe_timestamp_entries(timestamps)


def build_comparisons(
    source_timestamps: Sequence[Dict[str, str]],
    product_timestamps: Sequence[Dict[str, str]],
    max_stale_seconds: int,
) -> List[Dict[str, Any]]:
    comparisons: List[Dict[str, Any]] = []
    for s_idx, source_entry in enumerate(source_timestamps):
        source_dt = parse_timestamp(source_entry.get("parsed_utc"))
        if source_dt is None:
            continue
        for p_idx, product_entry in enumerate(product_timestamps):
            product_dt = parse_timestamp(product_entry.get("parsed_utc"))
            if product_dt is None:
                continue
            delta_seconds = (product_dt - source_dt).total_seconds()
            if delta_seconds >= (0 - max_stale_seconds):
                classification = "product_newer_or_equal_source"
            else:
                classification = "product_older_than_source"

            comparisons.append(
                {
                    "source_index": s_idx,
                    "product_index": p_idx,
                    "source_timestamp_utc": source_dt.isoformat(),
                    "product_timestamp_utc": product_dt.isoformat(),
                    "delta_seconds": delta_seconds,
                    "classification": classification,
                }
            )
    return comparisons


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

    o3de = manifest.get("o3de")
    if not isinstance(o3de, dict):
        o3de = {}
        manifest["o3de"] = o3de

    max_stale_seconds = int(args.max_stale_seconds)
    if max_stale_seconds < 0:
        max_stale_seconds = 0

    source_timestamps = collect_source_timestamps(o3de)
    product_timestamps, product_file_timestamp_count = collect_product_timestamps(o3de)
    job_timestamps = collect_job_timestamps(o3de)

    comparisons = build_comparisons(source_timestamps, product_timestamps, max_stale_seconds)

    newer_or_equal_count = sum(1 for c in comparisons if c.get("classification") == "product_newer_or_equal_source")
    older_count = sum(1 for c in comparisons if c.get("classification") == "product_older_than_source")

    source_count = len(source_timestamps)
    product_count = len(product_timestamps)

    if source_count == 0:
        status = "no_source_timestamp"
    elif product_file_timestamp_count == 0 and product_count == 0:
        status = "no_product_file_timestamp"
    elif len(comparisons) == 0:
        status = "insufficient_timestamp_evidence"
    elif older_count > 0:
        status = "product_older_than_source"
    elif newer_or_equal_count > 0:
        status = "candidate_freshness_supported"
    else:
        status = "insufficient_timestamp_evidence"

    proof_block = {
        "proof_version": PROOF_VERSION,
        "status": status,
        "max_stale_seconds": max_stale_seconds,
        "source_timestamps": source_timestamps,
        "product_timestamps": product_timestamps,
        "job_timestamps": job_timestamps,
        "comparisons": comparisons,
        "summary": {
            "source_timestamp_count": source_count,
            "product_timestamp_count": product_count,
            "job_timestamp_count": len(job_timestamps),
            "product_newer_or_equal_source_count": newer_or_equal_count,
            "product_older_than_source_count": older_count,
        },
        "safety": {
            "read_only": True,
            "opened_database": False,
            "modified_database": False,
            "ran_o3de_editor": False,
            "ran_asset_processor": False,
            "authoritative_resolution": False,
            "claimed_asset_ids": False,
            "claimed_products_resolved": False,
            "freshness_proof_is_resolution": False,
        },
        "updated_utc": utc_now(),
    }

    o3de["ap_product_freshness_proof"] = proof_block

    output_path = resolve_path(repo_root, args.output) if args.output else manifest_path
    try:
        write_json(output_path, manifest)
    except Exception as exc:
        print(f"FAIL: unable to write output manifest: {exc}")
        return 2

    validator_script = repo_root / "tools" / "manifest-validator" / "validate_manifest.py"
    cmd = [sys.executable, str(validator_script), str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        print(f"FAIL: manifest validation failed after AP product freshness proof update: {output_path}")
        return result.returncode

    print(
        "PASS: AP product freshness proof extraction recorded. "
        f"status={status} source_timestamps={source_count} "
        f"product_timestamps={product_count} comparisons={len(comparisons)} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
