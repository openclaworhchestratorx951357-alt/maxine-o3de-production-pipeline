#!/usr/bin/env python3
"""Read-only candidate product matching from AP row/source identity evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


MATCHING_VERSION = "ap-product-candidate-match-1"


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
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def normalize_text(value: str) -> str:
    text = safe_text(value).strip().replace("\\", "/").lower()
    text = re.sub(r"/+", "/", text)
    return text


def normalize_row_values(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in row.items():
        key = str(k)
        if isinstance(v, (bool, int, float)) or v is None:
            out[key] = v
        else:
            out[key] = safe_text(v)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match candidate AP product rows from manifest evidence only.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output", default="", help="Optional output manifest path (defaults to in-place)")
    parser.add_argument("--min-source-confidence", type=float, default=0.70, help="Min source match confidence")
    parser.add_argument("--min-product-confidence", type=float, default=0.40, help="Min product candidate confidence")
    return parser.parse_args()


def collect_expected_contract(asset_resolution: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    required = [str(x).strip().lower() for x in asset_resolution.get("required_products", []) if str(x).strip()]
    optional = [str(x).strip().lower() for x in asset_resolution.get("optional_products", []) if str(x).strip()]
    planned = [str(x).strip().lower() for x in asset_resolution.get("planned_products", []) if str(x).strip()]
    return required, optional, planned


def row_values_as_strings(row: Dict[str, Any]) -> Dict[str, str]:
    return {str(k): safe_text(v) for k, v in row.items()}


def extract_source_identifier_values(row_values: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in row_values.items():
        lk = k.lower()
        if "source" in lk and ("id" in lk or "uuid" in lk or "guid" in lk):
            val = normalize_text(v)
            if val:
                out[k] = val
    return out


def extract_product_identifier_values(row_values: Dict[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in row_values.items():
        lk = k.lower()
        if "source" in lk and ("id" in lk or "uuid" in lk or "guid" in lk):
            val = normalize_text(v)
            if val:
                out[k] = val
    return out


def extract_source_name_stem(source_identity: Dict[str, Any], best_source_row: Dict[str, str]) -> Tuple[str, str]:
    name = normalize_text(str(source_identity.get("source_asset_name", "")))
    stem = normalize_text(str(source_identity.get("source_asset_stem", "")))
    if not name:
        for key in ("SourceName", "source_name", "SourcePath", "source_path", "path", "file"):
            if key in best_source_row:
                val = normalize_text(best_source_row[key])
                if "/" in val:
                    name = val.rsplit("/", 1)[-1]
                else:
                    name = val
                break
    if not stem and name:
        stem = name.rsplit(".", 1)[0] if "." in name else name
    return name, stem


def classify_product_types(row_values: Dict[str, str]) -> Tuple[List[str], List[str], Set[str]]:
    type_rules = [
        ("azmodel", [".azmodel", "azmodel"]),
        ("actor", [".actor", "actor"]),
        ("motionset", [".motionset", "motionset"]),
        ("animgraph", [".animgraph", "animgraph"]),
        ("motion", [".motion", "motion"]),
        ("procprefab", [".procprefab", "procprefab", "prefab"]),
        ("azmaterial", [".azmaterial", "azmaterial", "material"]),
        ("collider", [".pxmesh", "pxmesh", "collider"]),
    ]

    evidence_texts: List[str] = []
    for col, val in row_values.items():
        lk = col.lower()
        if any(token in lk for token in ("product", "path", "name", "file")):
            evidence_texts.append(normalize_text(val))
    if not evidence_texts:
        evidence_texts = [normalize_text(v) for v in row_values.values()]
    combined = " | ".join(evidence_texts)

    found_types: List[str] = []
    reasons: List[str] = []
    extension_matches: Set[str] = set()
    for ptype, tokens in type_rules:
        token_hit = False
        ext_hit = False
        for t in tokens:
            if t.startswith("."):
                if t in combined:
                    ext_hit = True
                    token_hit = True
            else:
                if t in combined:
                    token_hit = True
        if token_hit:
            found_types.append(ptype)
            reasons.append(f"type_token_match:{ptype}")
        if ext_hit:
            extension_matches.add(ptype)
            reasons.append(f"extension_match:{ptype}")

    # stable unique
    dedup_types: List[str] = []
    for t in found_types:
        if t not in dedup_types:
            dedup_types.append(t)
    dedup_reasons: List[str] = []
    for r in reasons:
        if r not in dedup_reasons:
            dedup_reasons.append(r)
    return dedup_types, dedup_reasons, extension_matches


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
        print("FAIL: manifest.o3de is missing.")
        return 2

    ap_row_mapping = o3de.get("ap_row_mapping")
    if not isinstance(ap_row_mapping, dict):
        print("FAIL: manifest.o3de.ap_row_mapping is missing.")
        return 2

    source_identity = o3de.get("ap_source_identity_match")
    if not isinstance(source_identity, dict):
        print("FAIL: manifest.o3de.ap_source_identity_match is missing.")
        return 2

    warnings: List[str] = []

    asset_resolution = o3de.get("asset_resolution")
    required_products: List[str] = []
    optional_products: List[str] = []
    planned_products: List[str] = []
    if isinstance(asset_resolution, dict):
        required_products, optional_products, planned_products = collect_expected_contract(asset_resolution)
    else:
        warnings.append("asset_resolution missing; expected product contract is empty in this run.")

    expected_all = sorted(set(required_products + optional_products + planned_products))

    min_source_conf = max(0.0, min(1.0, float(args.min_source_confidence)))
    min_product_conf = max(0.0, min(1.0, float(args.min_product_confidence)))

    best_match = source_identity.get("best_match")
    has_source_match = isinstance(best_match, dict) and float(best_match.get("confidence", 0.0)) >= min_source_conf
    source_confidence = float(best_match.get("confidence", 0.0)) if isinstance(best_match, dict) else 0.0

    best_source_row_values: Dict[str, str] = {}
    source_match_table = ""
    source_match_row_index: Optional[int] = None
    source_name = ""
    source_stem = ""
    source_id_values: Dict[str, str] = {}

    if has_source_match and isinstance(best_match, dict):
        source_match_table = str(best_match.get("table_name", ""))
        if "row_index" in best_match:
            try:
                source_match_row_index = int(best_match.get("row_index"))
            except Exception:  # noqa: BLE001
                source_match_row_index = None
        row_vals = best_match.get("row_values", {})
        if isinstance(row_vals, dict):
            best_source_row_values = row_values_as_strings(row_vals)
        source_id_values = extract_source_identifier_values(best_source_row_values)
        source_name, source_stem = extract_source_name_stem(source_identity, best_source_row_values)

    product_rows_considered = 0
    linked_product_row_count = 0
    candidate_products: List[Dict[str, Any]] = []

    databases = ap_row_mapping.get("databases", [])
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
                table_name = str(table.get("name", ""))
                role = str(table.get("role", "")).lower()
                if role != "product" and "product" not in table_name.lower():
                    continue

                sampled_rows = table.get("sampled_rows", [])
                if not isinstance(sampled_rows, list):
                    continue

                for idx, row in enumerate(sampled_rows):
                    if not isinstance(row, dict):
                        continue
                    product_rows_considered += 1
                    row_str = row_values_as_strings(row)
                    row_norm = {k: normalize_text(v) for k, v in row_str.items()}

                    link_reason_codes: List[str] = []
                    link_by_id = False
                    weak_link = False

                    if has_source_match:
                        product_id_values = extract_product_identifier_values(row_str)
                        for p_col, p_val in product_id_values.items():
                            for s_col, s_val in source_id_values.items():
                                if p_val and s_val and p_val == s_val:
                                    link_by_id = True
                                    code = f"source_identifier_match:{p_col}:{s_col}"
                                    if code not in link_reason_codes:
                                        link_reason_codes.append(code)

                        values_joined = " | ".join(row_norm.values())
                        if source_name and source_name in values_joined:
                            weak_link = True
                            link_reason_codes.append("source_filename_weak_link")
                        elif source_stem and source_stem in values_joined:
                            weak_link = True
                            link_reason_codes.append("source_stem_weak_link")

                    linked = link_by_id or weak_link
                    if linked:
                        linked_product_row_count += 1

                    candidate_product_types, type_reason_codes, extension_matches = classify_product_types(row_str)

                    expected_product_match = [t for t in candidate_product_types if t in expected_all]
                    required_match = [t for t in candidate_product_types if t in required_products]
                    optional_match = [t for t in candidate_product_types if t in optional_products]
                    planned_match = [t for t in candidate_product_types if t in planned_products]

                    confidence = 0.0
                    # contract-aware confidence
                    if expected_product_match:
                        confidence += 0.50
                    # extension-aware confidence
                    if extension_matches:
                        confidence += 0.40
                    # source-link confidence
                    if link_by_id:
                        confidence += 0.30
                    elif weak_link:
                        confidence += 0.10
                    confidence = min(1.0, round(confidence, 4))

                    # candidate rows require source evidence + product contract typing
                    if not has_source_match:
                        continue
                    if not linked:
                        continue
                    if not candidate_product_types:
                        continue
                    if confidence < min_product_conf:
                        continue

                    candidate_products.append(
                        {
                            "database_path": db_path,
                            "table_name": table_name,
                            "row_index": idx,
                            "confidence": confidence,
                            "candidate_product_types": candidate_product_types,
                            "expected_product_match": expected_product_match,
                            "required_product_match": required_match,
                            "optional_product_match": optional_match,
                            "planned_product_match": planned_match,
                            "link_reason_codes": link_reason_codes,
                            "type_reason_codes": type_reason_codes,
                            "row_values": normalize_row_values(row),
                        }
                    )

    candidate_products.sort(
        key=lambda c: (
            -float(c.get("confidence", 0.0)),
            str(c.get("database_path", "")),
            str(c.get("table_name", "")),
            int(c.get("row_index", 0)),
        )
    )

    required_candidate_count = sum(1 for c in candidate_products if c.get("required_product_match"))
    optional_candidate_count = sum(1 for c in candidate_products if c.get("optional_product_match"))
    planned_candidate_count = sum(1 for c in candidate_products if c.get("planned_product_match"))
    best_product_confidence = max([float(c.get("confidence", 0.0)) for c in candidate_products], default=0.0)

    matched_required_types: Set[str] = set()
    for c in candidate_products:
        for t in c.get("required_product_match", []):
            matched_required_types.add(str(t))
    missing_required = sorted([t for t in required_products if t not in matched_required_types])

    if not has_source_match:
        status = "no_source_match"
    elif not candidate_products:
        status = "no_product_candidates"
    else:
        status = "candidate_products"

    result_block: Dict[str, Any] = {
        "matching_version": MATCHING_VERSION,
        "status": status,
        "expected_contract": {
            "required_products": required_products,
            "optional_products": optional_products,
            "planned_products": planned_products,
        },
        "source_match_summary": {
            "has_source_match": has_source_match,
            "source_confidence": source_confidence,
            "source_match_table": source_match_table,
            "source_match_row_index": source_match_row_index,
        },
        "candidate_products": candidate_products,
        "summary": {
            "product_rows_considered": product_rows_considered,
            "linked_product_row_count": linked_product_row_count,
            "candidate_product_count": len(candidate_products),
            "required_product_candidate_count": required_candidate_count,
            "optional_product_candidate_count": optional_candidate_count,
            "planned_product_candidate_count": planned_candidate_count,
            "missing_required_product_types": missing_required,
            "best_product_confidence": best_product_confidence,
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
            "product_candidate_is_resolution": False,
            "published_or_spawned": False,
        },
        "updated_utc": utc_now(),
    }
    if warnings:
        result_block["warnings"] = warnings

    o3de["ap_product_candidate_match"] = result_block

    output_path = resolve_path(repo_root, args.output) if args.output else manifest_path
    write_json(output_path, manifest)

    validator_script = repo_root / "tools" / "manifest-validator" / "validate_manifest.py"
    cmd = [sys.executable, str(validator_script), str(output_path)]
    vr = subprocess.run(cmd, capture_output=True, text=True)
    if vr.stdout:
        print(vr.stdout.strip())
    if vr.stderr:
        print(vr.stderr.strip())
    if vr.returncode != 0:
        print(f"FAIL: manifest validation failed after product candidate matching: {output_path}")
        return vr.returncode

    print(
        "PASS: AP product candidate matching recorded. "
        f"status={status} rows_considered={product_rows_considered} "
        f"candidate_products={len(candidate_products)} best_confidence={best_product_confidence:.2f} "
        f"output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
