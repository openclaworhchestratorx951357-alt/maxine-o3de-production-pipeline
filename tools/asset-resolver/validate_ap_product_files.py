#!/usr/bin/env python3
"""Read-only candidate product file existence validation under explicit safe roots."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


VALIDATION_VERSION = "ap-product-file-validation-1"
TRUE_FALSE = {"true", "false"}
MAX_HASH_BYTES = 10 * 1024 * 1024


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


def normalize_path_text(value: str) -> str:
    text = str(value).strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def path_has_parent_segments(path_text: str) -> bool:
    parts = [p for p in path_text.split("/") if p]
    return any(p == ".." for p in parts)


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:  # noqa: BLE001
        return False


def parse_bool_arg(raw: str, flag: str) -> bool:
    val = str(raw).strip().lower()
    if val not in TRUE_FALSE:
        raise ValueError(f"{flag} must be true or false.")
    return val == "true"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate candidate product file existence under safe roots.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--project-root", default="", help="Optional project root")
    parser.add_argument("--cache-root", default="", help="Optional cache root")
    parser.add_argument("--root", action="append", default=[], help="Additional safe root (repeatable)")
    parser.add_argument("--output", default="", help="Optional output path (defaults to in-place)")
    parser.add_argument(
        "--require-existing-required",
        default="false",
        help="Fail if required candidate product types do not have existing files (true|false)",
    )
    return parser.parse_args()


def collect_safe_roots(repo_root: Path, args: argparse.Namespace) -> List[Path]:
    roots: List[Path] = []
    if args.project_root:
        roots.append(resolve_path(repo_root, args.project_root))
    if args.cache_root:
        roots.append(resolve_path(repo_root, args.cache_root))
    for raw in args.root:
        if raw:
            roots.append(resolve_path(repo_root, raw))

    dedup: List[Path] = []
    seen: Set[str] = set()
    for r in roots:
        key = str(r.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r.resolve())
    return dedup


def extract_product_paths(row_values: Dict[str, Any]) -> List[Dict[str, str]]:
    paths: List[Dict[str, str]] = []
    for key, value in row_values.items():
        name = str(key)
        lname = name.lower()
        if not any(token in lname for token in ("product", "path", "file", "name")):
            continue
        raw = str(value).strip() if value is not None else ""
        if not raw:
            continue
        norm = normalize_path_text(raw)
        if not norm:
            continue
        paths.append({"column": name, "value": raw, "normalized_value": norm})
    return paths


def validate_candidate_paths(
    candidate_paths: List[Dict[str, str]],
    safe_roots: List[Path],
) -> Tuple[List[Dict[str, Any]], int, int]:
    path_checks: List[Dict[str, Any]] = []
    existing_count = 0
    rejected_count = 0

    for entry in candidate_paths:
        norm = entry["normalized_value"]
        raw = entry["value"]
        column = entry["column"]

        if path_has_parent_segments(norm):
            path_checks.append(
                {
                    "column": column,
                    "input_path": raw,
                    "normalized_path": norm,
                    "rejected": True,
                    "reject_reason": "parent_path_segment_not_allowed",
                }
            )
            rejected_count += 1
            continue

        candidate_path = Path(norm)
        if candidate_path.is_absolute():
            inside_any = False
            for root in safe_roots:
                if is_within_root(candidate_path, root):
                    inside_any = True
                    break
            if not inside_any:
                path_checks.append(
                    {
                        "column": column,
                        "input_path": raw,
                        "normalized_path": norm,
                        "rejected": True,
                        "reject_reason": "absolute_path_outside_safe_roots",
                    }
                )
                rejected_count += 1
                continue

            exists = candidate_path.exists() and candidate_path.is_file()
            check: Dict[str, Any] = {
                "column": column,
                "input_path": raw,
                "normalized_path": norm,
                "resolved_path": str(candidate_path.resolve()),
                "exists": exists,
            }
            if exists:
                existing_count += 1
                stat = candidate_path.stat()
                check["size_bytes"] = stat.st_size
                check["modified_utc"] = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat()
                if stat.st_size <= MAX_HASH_BYTES:
                    check["sha256"] = compute_sha256(candidate_path)
            path_checks.append(check)
            continue

        # relative candidate path: resolve against every safe root
        rel_posix = PurePosixPath(norm)
        for root in safe_roots:
            resolved = (root / Path(*rel_posix.parts)).resolve()
            if not is_within_root(resolved, root):
                path_checks.append(
                    {
                        "column": column,
                        "input_path": raw,
                        "normalized_path": norm,
                        "root": str(root),
                        "rejected": True,
                        "reject_reason": "resolved_path_outside_safe_root",
                    }
                )
                rejected_count += 1
                continue

            exists = resolved.exists() and resolved.is_file()
            check = {
                "column": column,
                "input_path": raw,
                "normalized_path": norm,
                "root": str(root),
                "resolved_path": str(resolved),
                "exists": exists,
            }
            if exists:
                existing_count += 1
                stat = resolved.stat()
                check["size_bytes"] = stat.st_size
                check["modified_utc"] = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc).isoformat()
                if stat.st_size <= MAX_HASH_BYTES:
                    check["sha256"] = compute_sha256(resolved)
            path_checks.append(check)

    return path_checks, existing_count, rejected_count


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        require_existing_required = parse_bool_arg(args.require_existing_required, "--require-existing-required")
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    manifest_path = resolve_path(repo_root, args.manifest)
    if not manifest_path.exists():
        print(f"FAIL: manifest file not found: {manifest_path}")
        return 2

    safe_roots = collect_safe_roots(repo_root, args)
    if not safe_roots:
        print("FAIL: no safe roots provided. Use --project-root, --cache-root, or --root.")
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

    candidate_block = o3de.get("ap_product_candidate_match")
    if not isinstance(candidate_block, dict):
        print("FAIL: manifest.o3de.ap_product_candidate_match is missing.")
        return 2

    expected_contract = candidate_block.get("expected_contract", {})
    required_types = []
    if isinstance(expected_contract, dict):
        required_types = [str(x).lower() for x in expected_contract.get("required_products", []) if str(x).strip()]

    candidate_products = candidate_block.get("candidate_products", [])
    if not isinstance(candidate_products, list):
        candidate_products = []

    validated_candidates: List[Dict[str, Any]] = []
    candidates_with_existing_file = 0
    rejected_path_count_total = 0
    required_product_candidate_count = 0
    required_product_existing_file_count = 0
    required_types_with_existing_file: Set[str] = set()
    required_types_with_candidate: Set[str] = set()

    for idx, candidate in enumerate(candidate_products):
        if not isinstance(candidate, dict):
            continue
        row_values = candidate.get("row_values", {})
        if not isinstance(row_values, dict):
            row_values = {}
        path_fields = extract_product_paths(row_values)
        path_checks, existing_file_count, rejected_count = validate_candidate_paths(path_fields, safe_roots)
        any_existing = existing_file_count > 0
        if any_existing:
            candidates_with_existing_file += 1
        rejected_path_count_total += rejected_count

        required_match = [str(x).lower() for x in candidate.get("required_product_match", []) if str(x).strip()]
        if required_match:
            required_product_candidate_count += 1
            for t in required_match:
                required_types_with_candidate.add(t)
            if any_existing:
                required_product_existing_file_count += 1
                for t in required_match:
                    required_types_with_existing_file.add(t)

        validated_candidates.append(
            {
                "candidate_index": idx,
                "candidate_product_types": candidate.get("candidate_product_types", []),
                "expected_product_match": candidate.get("expected_product_match", []),
                "required_product_match": candidate.get("required_product_match", []),
                "source_link_reason_codes": candidate.get("link_reason_codes", []),
                "product_path_fields": path_fields,
                "path_checks": path_checks,
                "any_existing_file": any_existing,
                "existing_file_count": existing_file_count,
                "rejected_path_count": rejected_count,
            }
        )

    candidate_product_count = len(validated_candidates)
    candidates_without_existing = max(0, candidate_product_count - candidates_with_existing_file)
    missing_required_product_types = sorted([t for t in required_types if t not in required_types_with_candidate])
    required_types_without_existing_file = sorted([t for t in required_types if t not in required_types_with_existing_file])

    if candidate_product_count == 0:
        status = "no_candidate_products"
    elif candidates_with_existing_file > 0:
        status = "file_candidates_found"
    else:
        status = "no_existing_files"

    should_fail_required = require_existing_required and len(required_types_without_existing_file) > 0
    if should_fail_required:
        status = "required_missing_files"

    result_block: Dict[str, Any] = {
        "validation_version": VALIDATION_VERSION,
        "status": status,
        "safe_roots": [str(r) for r in safe_roots],
        "validated_candidates": validated_candidates,
        "summary": {
            "candidate_product_count": candidate_product_count,
            "candidates_with_existing_file": candidates_with_existing_file,
            "candidates_without_existing_file": candidates_without_existing,
            "rejected_path_count": rejected_path_count_total,
            "required_product_candidate_count": required_product_candidate_count,
            "required_product_existing_file_count": required_product_existing_file_count,
            "missing_required_product_types": missing_required_product_types,
            "required_product_types_without_existing_file": required_types_without_existing_file,
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
            "file_existence_is_resolution": False,
            "published_or_spawned": False,
        },
        "updated_utc": utc_now(),
    }

    o3de["ap_product_file_validation"] = result_block

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
        print(f"FAIL: manifest validation failed after product file validation: {output_path}")
        return vr.returncode

    print(
        "PASS: AP product file validation recorded. "
        f"status={status} candidates={candidate_product_count} "
        f"with_existing={candidates_with_existing_file} rejected_paths={rejected_path_count_total} "
        f"output={output_path}"
    )

    if should_fail_required:
        print("FAIL: required product types missing existing files under provided roots.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
