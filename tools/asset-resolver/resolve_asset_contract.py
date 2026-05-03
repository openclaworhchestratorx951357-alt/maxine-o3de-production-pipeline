#!/usr/bin/env python3
"""Record asset-resolution product contracts into a MAXINE manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


VALID_STATUSES = {"planned", "unresolved", "resolved"}
RESOLVER_VERSION = "asset-resolver-poc-1"


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


def dedupe(items: List[str]) -> List[str]:
    out: List[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve MAXINE asset product contract into manifest.")
    parser.add_argument("--manifest", required=True, help="Path to input manifest JSON")
    parser.add_argument("--source-asset", required=True, help="Source asset path string")
    parser.add_argument("--lane", default="", help="Optional lane override")
    parser.add_argument("--output", default="", help="Optional output manifest path (defaults to in-place)")
    parser.add_argument(
        "--contract-file",
        default="",
        help="Optional path to product contract file (defaults to tools/asset-resolver/product_contracts.json)",
    )
    parser.add_argument(
        "--status",
        default="planned",
        choices=sorted(VALID_STATUSES),
        help="Resolution status to record",
    )
    parser.add_argument(
        "--allow-poc-resolved",
        action="store_true",
        help="Allow 'resolved' status in POC mode when explicitly requested.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (repo_root / manifest_path).resolve()
    if not manifest_path.exists():
        print(f"FAIL: manifest file not found: {manifest_path}")
        return 2

    contract_path = Path(args.contract_file) if args.contract_file else (repo_root / "tools" / "asset-resolver" / "product_contracts.json")
    if not contract_path.is_absolute():
        contract_path = (repo_root / contract_path).resolve()
    if not contract_path.exists():
        print(f"FAIL: contract file not found: {contract_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    try:
        contracts = load_json(contract_path)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    lane = args.lane or str(manifest.get("job", {}).get("lane", "")).strip()
    if not lane:
        print("FAIL: lane not provided and manifest.job.lane missing.")
        return 2
    if lane not in contracts:
        print(f"FAIL: lane '{lane}' not found in contract file {contract_path}")
        return 2

    if args.status == "resolved" and not args.allow_poc_resolved:
        print("FAIL: status 'resolved' is blocked in this POC without --allow-poc-resolved.")
        return 2

    contract = contracts[lane]
    required_products = [str(x) for x in contract.get("required_products", [])]
    optional_products = [str(x) for x in contract.get("optional_products", [])]
    planned_products = [str(x) for x in contract.get("planned_products", [])]
    notes = [str(x) for x in contract.get("notes", [])]

    source_asset_input = str(args.source_asset)
    source_path_obj = Path(source_asset_input)
    source_asset_name = source_path_obj.name
    source_asset_extension = source_path_obj.suffix.lower()

    unresolved_products: List[str]
    if args.status in {"planned", "unresolved"}:
        unresolved_products = dedupe(required_products + planned_products)
    else:
        existing_resolved = []
        existing_ar = manifest.get("o3de", {}).get("asset_resolution", {})
        if isinstance(existing_ar, dict):
            maybe_resolved = existing_ar.get("resolved_products")
            if isinstance(maybe_resolved, list):
                existing_resolved = [str(x) for x in maybe_resolved]

        if existing_resolved:
            unresolved_products = []
        else:
            unresolved_products = dedupe(required_products + planned_products)
            notes = notes + [
                "POC resolved mode requested but explicit resolved_products were not supplied; unresolved_products retained."
            ]

    o3de_obj = manifest.get("o3de")
    if not isinstance(o3de_obj, dict):
        o3de_obj = {}
        manifest["o3de"] = o3de_obj

    existing_probe = o3de_obj.get("asset_probe")
    probe_available = isinstance(existing_probe, dict)

    o3de_obj["asset_resolution"] = {
        "resolver_version": RESOLVER_VERSION,
        "status": args.status,
        "lane": lane,
        "source_asset_input": source_asset_input,
        "source_asset_name": source_asset_name,
        "source_asset_extension": source_asset_extension,
        "required_products": required_products,
        "optional_products": optional_products,
        "planned_products": planned_products,
        "unresolved_products": unresolved_products,
        "notes": notes,
        "cache_guessing_used": False,
        "real_o3de_query_used": False,
        "probe_available": probe_available,
        "updated_utc": utc_now(),
    }

    output_path = Path(args.output) if args.output else manifest_path
    if not output_path.is_absolute():
        output_path = (repo_root / output_path).resolve()

    write_json(output_path, manifest)

    validator = repo_root / "tools" / "manifest-validator" / "validate_manifest.py"
    cmd = [sys.executable, str(validator), str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode != 0:
        print(f"FAIL: manifest validation failed after resolver update: {output_path}")
        return result.returncode

    print(f"PASS: asset contract recorded for lane '{lane}' in {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
