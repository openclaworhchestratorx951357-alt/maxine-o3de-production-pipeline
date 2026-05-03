#!/usr/bin/env python3
"""Extract read-only AP job-state proof evidence from manifest row-mapping data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple


PROOF_VERSION = "ap-job-state-proof-1"
SUCCESS_TOKENS = ("complete", "completed", "success", "succeeded", "pass", "passed", "ok", "finished")
FAILURE_TOKENS = ("fail", "failed", "error", "abort", "cancel", "warning", "warn", "timeout")


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
    parser = argparse.ArgumentParser(description="Extract candidate AP job-state proof from manifest evidence.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output", default="", help="Optional output path (defaults to in-place)")
    parser.add_argument("--min-source-confidence", type=float, default=0.70, help="Min source confidence")
    return parser.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def normalize_value(value: Any) -> str:
    return safe_text(value).strip().lower().replace("\\", "/")


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (bool, int, float)) or value is None:
            normalized[str(key)] = value
        else:
            normalized[str(key)] = safe_text(value)
    return normalized


def is_job_table(table: Dict[str, Any]) -> bool:
    role = str(table.get("role", "")).strip().lower()
    name = str(table.get("name", "")).strip().lower()
    return role == "job" or "job" in name


def extract_identifier_values(row_values: Dict[str, Any], match_mode: str) -> Set[str]:
    values: Set[str] = set()
    for key, value in row_values.items():
        name = str(key).lower()
        text = normalize_value(value)
        if not text:
            continue

        if match_mode == "source":
            if "source" in name and ("id" in name or "uuid" in name or "guid" in name):
                values.add(text)
        elif match_mode == "product":
            if ("product" in name and ("id" in name or "subid" in name or "uuid" in name or "guid" in name)) or (
                "source" in name and ("id" in name or "uuid" in name or "guid" in name)
            ):
                values.add(text)
            if "product" in name and any(token in name for token in ("path", "name", "file")):
                values.add(text)
    return values


def extract_status_fields(row_values: Dict[str, Any]) -> Dict[str, str]:
    status_fields: Dict[str, str] = {}
    for key, value in row_values.items():
        name = str(key).lower()
        if any(token in name for token in ("status", "state", "result", "fail", "error", "warning")):
            status_fields[str(key)] = safe_text(value)
    return status_fields


def extract_platform_fields(row_values: Dict[str, Any]) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for key, value in row_values.items():
        if "platform" in str(key).lower():
            fields[str(key)] = safe_text(value)
    return fields


def extract_timestamp_fields(row_values: Dict[str, Any]) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for key, value in row_values.items():
        name = str(key).lower()
        if any(token in name for token in ("time", "date", "utc", "created", "updated", "modified")):
            fields[str(key)] = safe_text(value)
    return fields


def classify_job_state(status_fields: Dict[str, str], row_values: Dict[str, Any]) -> str:
    texts: List[str] = []
    if status_fields:
        texts = [normalize_value(v) for v in status_fields.values() if normalize_value(v)]
    if not texts:
        texts = [normalize_value(v) for v in row_values.values() if normalize_value(v)]
    blob = " | ".join(texts)

    if any(token in blob for token in FAILURE_TOKENS):
        return "failure_like"
    if any(token in blob for token in SUCCESS_TOKENS):
        return "success_like"
    return "unknown"


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

    ap_row_mapping = o3de.get("ap_row_mapping")
    source_identity = o3de.get("ap_source_identity_match")
    product_match = o3de.get("ap_product_candidate_match")

    min_source_conf = max(0.0, min(1.0, float(args.min_source_confidence)))

    has_source_evidence = False
    source_identifier_values: Set[str] = set()
    if isinstance(source_identity, dict):
        status = str(source_identity.get("status", "")).strip().lower()
        best_match = source_identity.get("best_match")
        if isinstance(best_match, dict):
            confidence = float(best_match.get("confidence", 0.0))
            if status == "candidate_match" and confidence >= min_source_conf:
                has_source_evidence = True
            row_values = best_match.get("row_values", {})
            if isinstance(row_values, dict):
                source_identifier_values = extract_identifier_values(row_values, "source")

    has_product_evidence = False
    product_identifier_values: Set[str] = set()
    product_candidates: List[Dict[str, Any]] = []
    if isinstance(product_match, dict):
        status = str(product_match.get("status", "")).strip().lower()
        candidate_products = product_match.get("candidate_products", [])
        if isinstance(candidate_products, list):
            product_candidates = [p for p in candidate_products if isinstance(p, dict)]
        if status == "candidate_products" and len(product_candidates) > 0:
            has_product_evidence = True
        for candidate in product_candidates:
            row_values = candidate.get("row_values", {})
            if isinstance(row_values, dict):
                product_identifier_values.update(extract_identifier_values(row_values, "product"))

    job_rows_considered = 0
    candidate_job_rows: List[Dict[str, Any]] = []

    databases = ap_row_mapping.get("databases", []) if isinstance(ap_row_mapping, dict) else []
    if isinstance(databases, list):
        for db in databases:
            if not isinstance(db, dict):
                continue
            db_path = str(db.get("path", ""))
            tables = db.get("tables", [])
            if not isinstance(tables, list):
                continue
            for table in tables:
                if not isinstance(table, dict):
                    continue
                if not is_job_table(table):
                    continue
                table_name = str(table.get("name", ""))
                sampled_rows = table.get("sampled_rows", [])
                if not isinstance(sampled_rows, list):
                    continue
                for idx, row in enumerate(sampled_rows):
                    if not isinstance(row, dict):
                        continue
                    job_rows_considered += 1
                    normalized_row = normalize_row(row)
                    status_fields = extract_status_fields(normalized_row)
                    platform_fields = extract_platform_fields(normalized_row)
                    timestamp_fields = extract_timestamp_fields(normalized_row)
                    row_source_ids = extract_identifier_values(normalized_row, "source")
                    row_product_ids = extract_identifier_values(normalized_row, "product")

                    source_link_reasons: List[str] = []
                    product_link_reasons: List[str] = []
                    linked_source = False
                    linked_product = False

                    if source_identifier_values and row_source_ids:
                        shared_source = sorted(source_identifier_values.intersection(row_source_ids))
                        if shared_source:
                            linked_source = True
                            source_link_reasons.append("shared_source_identifier")
                            source_link_reasons.append(f"shared_source_values:{','.join(shared_source)}")

                    if product_identifier_values and row_product_ids:
                        shared_product = sorted(product_identifier_values.intersection(row_product_ids))
                        if shared_product:
                            linked_product = True
                            product_link_reasons.append("shared_product_or_source_identifier")
                            product_link_reasons.append(f"shared_product_values:{','.join(shared_product)}")

                    has_status_signal = len(status_fields) > 0
                    if not (has_status_signal or linked_source or linked_product):
                        continue

                    result_classification = classify_job_state(status_fields, normalized_row)

                    candidate_job_rows.append(
                        {
                            "database_path": db_path,
                            "table_name": table_name,
                            "row_index": idx,
                            "linked_source": linked_source,
                            "linked_product": linked_product,
                            "source_link_reason_codes": source_link_reasons,
                            "product_link_reason_codes": product_link_reasons,
                            "status_fields": status_fields,
                            "platform_fields": platform_fields,
                            "timestamp_fields": timestamp_fields,
                            "result_classification": result_classification,
                            "row_values": normalized_row,
                        }
                    )

    success_like_job_count = sum(1 for row in candidate_job_rows if row.get("result_classification") == "success_like")
    failure_like_job_count = sum(1 for row in candidate_job_rows if row.get("result_classification") == "failure_like")
    unknown_job_count = sum(1 for row in candidate_job_rows if row.get("result_classification") == "unknown")

    if not has_source_evidence or not has_product_evidence:
        status = "missing_source_or_product_evidence"
    elif len(candidate_job_rows) > 0:
        status = "candidate_job_state_found"
    else:
        status = "no_candidate_job_state"

    proof_block = {
        "proof_version": PROOF_VERSION,
        "status": status,
        "job_rows_considered": job_rows_considered,
        "candidate_job_rows": candidate_job_rows,
        "summary": {
            "candidate_job_count": len(candidate_job_rows),
            "success_like_job_count": success_like_job_count,
            "failure_like_job_count": failure_like_job_count,
            "unknown_job_count": unknown_job_count,
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
            "job_state_is_resolution": False,
        },
        "updated_utc": utc_now(),
    }

    o3de["ap_job_state_proof"] = proof_block

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
        print(f"FAIL: manifest validation failed after AP job-state proof update: {output_path}")
        return result.returncode

    print(
        "PASS: AP job-state proof extraction recorded. "
        f"status={status} job_rows_considered={job_rows_considered} "
        f"candidate_job_count={len(candidate_job_rows)} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
