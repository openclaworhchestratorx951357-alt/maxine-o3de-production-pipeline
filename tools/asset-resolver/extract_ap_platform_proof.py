#!/usr/bin/env python3
"""Extract read-only AP platform proof evidence from manifest data."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


PROOF_VERSION = "ap-platform-proof-1"


PLATFORM_TOKEN_MAP = {
    "pc": "pc",
    "windows": "pc",
    "win": "pc",
    "linux": "linux",
    "mac": "mac",
    "osx": "mac",
    "ios": "ios",
    "android": "android",
}


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
    parser = argparse.ArgumentParser(description="Extract AP platform proof from manifest evidence only.")
    parser.add_argument("--manifest", required=True, help="Path to manifest JSON")
    parser.add_argument("--output", default="", help="Optional output path (defaults to in-place)")
    parser.add_argument("--target-platform", default="", help="Optional explicit target platform")
    return parser.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def normalize_text(value: Any) -> str:
    return safe_text(value).strip().lower().replace("\\", "/")


def canonicalize_platform(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    for token, canonical in PLATFORM_TOKEN_MAP.items():
        if text == token:
            return canonical
    for token, canonical in PLATFORM_TOKEN_MAP.items():
        if token in text:
            return canonical
    return ""


def detect_platform_tokens(text: Any) -> List[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    found: List[str] = []
    for token, canonical in PLATFORM_TOKEN_MAP.items():
        if token in normalized and canonical not in found:
            found.append(canonical)
    return found


def determine_target_platform(manifest: Dict[str, Any], cli_target: str) -> str:
    if cli_target:
        target = canonicalize_platform(cli_target)
        return target if target else normalize_text(cli_target)

    o3de = manifest.get("o3de", {})
    if isinstance(o3de, dict):
        target = canonicalize_platform(o3de.get("target_platform"))
        if target:
            return target

    job = manifest.get("job", {})
    if isinstance(job, dict):
        target = canonicalize_platform(job.get("platform"))
        if target:
            return target

    return "unknown"


def build_hint(source: str, location: str, value: str, platform: str) -> Dict[str, str]:
    return {
        "source": source,
        "location": location,
        "value": safe_text(value),
        "detected_platform": platform,
    }


def collect_product_candidate_hints(product_match: Dict[str, Any]) -> List[Dict[str, str]]:
    hints: List[Dict[str, str]] = []
    candidate_products = product_match.get("candidate_products", [])
    if not isinstance(candidate_products, list):
        return hints

    for c_idx, candidate in enumerate(candidate_products):
        if not isinstance(candidate, dict):
            continue
        row_values = candidate.get("row_values", {})
        if not isinstance(row_values, dict):
            continue
        for key, value in row_values.items():
            key_name = str(key)
            key_l = key_name.lower()
            maybe_tokens: List[str] = []
            if "platform" in key_l:
                maybe_tokens = detect_platform_tokens(value)
            elif any(token in key_l for token in ("path", "product", "file", "name")):
                maybe_tokens = detect_platform_tokens(value)
            for platform in maybe_tokens:
                hints.append(
                    build_hint(
                        source="ap_product_candidate_match",
                        location=f"candidate_products[{c_idx}].row_values.{key_name}",
                        value=safe_text(value),
                        platform=platform,
                    )
                )
    return hints


def collect_file_validation_hints(file_validation: Dict[str, Any]) -> List[Dict[str, str]]:
    hints: List[Dict[str, str]] = []
    validated_candidates = file_validation.get("validated_candidates", [])
    if not isinstance(validated_candidates, list):
        return hints

    for c_idx, candidate in enumerate(validated_candidates):
        if not isinstance(candidate, dict):
            continue
        path_checks = candidate.get("path_checks", [])
        if not isinstance(path_checks, list):
            continue
        for p_idx, check in enumerate(path_checks):
            if not isinstance(check, dict):
                continue
            for key in ("normalized_path", "resolved_path", "input_path"):
                value = check.get(key)
                for platform in detect_platform_tokens(value):
                    hints.append(
                        build_hint(
                            source="ap_product_file_validation",
                            location=f"validated_candidates[{c_idx}].path_checks[{p_idx}].{key}",
                            value=safe_text(value),
                            platform=platform,
                        )
                    )
            root_val = check.get("root")
            for platform in detect_platform_tokens(root_val):
                hints.append(
                    build_hint(
                        source="ap_product_file_validation",
                        location=f"validated_candidates[{c_idx}].path_checks[{p_idx}].root",
                        value=safe_text(root_val),
                        platform=platform,
                    )
                )
    return hints


def collect_job_state_hints(job_state: Dict[str, Any]) -> List[Dict[str, str]]:
    hints: List[Dict[str, str]] = []
    candidate_rows = job_state.get("candidate_job_rows", [])
    if not isinstance(candidate_rows, list):
        return hints

    for r_idx, row in enumerate(candidate_rows):
        if not isinstance(row, dict):
            continue

        platform_fields = row.get("platform_fields", {})
        if isinstance(platform_fields, dict):
            for key, value in platform_fields.items():
                for platform in detect_platform_tokens(value):
                    hints.append(
                        build_hint(
                            source="ap_job_state_proof",
                            location=f"candidate_job_rows[{r_idx}].platform_fields.{key}",
                            value=safe_text(value),
                            platform=platform,
                        )
                    )

        row_values = row.get("row_values", {})
        if isinstance(row_values, dict):
            for key, value in row_values.items():
                key_l = str(key).lower()
                if "platform" in key_l:
                    for platform in detect_platform_tokens(value):
                        hints.append(
                            build_hint(
                                source="ap_job_state_proof",
                                location=f"candidate_job_rows[{r_idx}].row_values.{key}",
                                value=safe_text(value),
                                platform=platform,
                            )
                        )
    return hints


def split_hints_by_target(hints: Sequence[Dict[str, str]], target_platform: str) -> tuple[list[Dict[str, str]], list[Dict[str, str]]]:
    matching: List[Dict[str, str]] = []
    mismatching: List[Dict[str, str]] = []

    if target_platform == "unknown":
        return matching, mismatching

    for hint in hints:
        platform = str(hint.get("detected_platform", "")).strip().lower()
        if not platform:
            continue
        if platform == target_platform:
            matching.append(hint)
        else:
            mismatching.append(hint)
    return matching, mismatching


def dedupe_hints(hints: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[str] = set()
    out: List[Dict[str, str]] = []
    for hint in hints:
        key = "|".join(
            [
                str(hint.get("source", "")),
                str(hint.get("location", "")),
                str(hint.get("detected_platform", "")),
                str(hint.get("value", "")),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(hint)
    return out


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

    target_platform = determine_target_platform(manifest, args.target_platform)

    product_match = o3de.get("ap_product_candidate_match")
    file_validation = o3de.get("ap_product_file_validation")
    job_state = o3de.get("ap_job_state_proof")

    hints: List[Dict[str, str]] = []
    if isinstance(product_match, dict):
        hints.extend(collect_product_candidate_hints(product_match))
    if isinstance(file_validation, dict):
        hints.extend(collect_file_validation_hints(file_validation))
    if isinstance(job_state, dict):
        hints.extend(collect_job_state_hints(job_state))

    platform_hints = dedupe_hints(hints)
    matching_hints, mismatching_hints = split_hints_by_target(platform_hints, target_platform)

    if len(platform_hints) == 0:
        status = "no_platform_evidence"
    elif target_platform == "unknown":
        status = "target_platform_unknown"
    elif len(matching_hints) > 0:
        status = "candidate_platform_found"
    else:
        status = "platform_mismatch"

    proof_block = {
        "proof_version": PROOF_VERSION,
        "status": status,
        "target_platform": target_platform,
        "platform_hints": platform_hints,
        "matching_hints": matching_hints,
        "mismatching_hints": mismatching_hints,
        "summary": {
            "platform_hint_count": len(platform_hints),
            "matching_hint_count": len(matching_hints),
            "mismatching_hint_count": len(mismatching_hints),
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
            "platform_proof_is_resolution": False,
        },
        "updated_utc": utc_now(),
    }

    o3de["ap_platform_proof"] = proof_block

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
        print(f"FAIL: manifest validation failed after AP platform proof update: {output_path}")
        return result.returncode

    print(
        "PASS: AP platform proof extraction recorded. "
        f"status={status} target_platform={target_platform} "
        f"hint_count={len(platform_hints)} matching={len(matching_hints)} mismatching={len(mismatching_hints)} "
        f"output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
