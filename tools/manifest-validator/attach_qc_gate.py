#!/usr/bin/env python3
"""Attach manifest-attachable QC payloads to MAXINE Manifest v1 qc.gates[] safely."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List


VALID_GATE_RESULTS = {"pass", "warn", "fail", "pending_manual"}
VALID_QC_OVERALL = {"pass", "warn", "fail"}
EXPECTED_TARGET_PATH = "qc.gates[]"
EXPECTED_FUTURE_TARGET_PATH = "qc.checks[]"


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attach validator manifest payload to manifest qc.gates[]."
    )
    parser.add_argument("manifest_path", help="Path to manifest JSON.")
    parser.add_argument(
        "validator_output_path",
        help="Path to validator output JSON/text containing a JSON payload.",
    )
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Persist updates back to manifest_path. Without this flag, only prints updated manifest JSON.",
    )
    return parser.parse_args()


def _extract_json_payload(text: str) -> Dict[str, Any]:
    start = text.find("{")
    if start < 0:
        raise ValueError("validator output did not include a JSON payload")
    return json.loads(text[start:])


def load_validator_payload(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        raw = _extract_json_payload(text)
    if not isinstance(raw, dict):
        raise ValueError("validator payload must be a JSON object")
    return raw


def ensure_object(parent: Dict[str, Any], key: str) -> Dict[str, Any]:
    child = parent.get(key)
    if not isinstance(child, dict):
        child = {}
        parent[key] = child
    return child


def _normalize_qc_overall(value: str) -> str:
    if value in VALID_QC_OVERALL:
        return value
    return "warn"


def _gate_result_to_overall(gate_result: str) -> str:
    if gate_result == "fail":
        return "fail"
    if gate_result in {"warn", "pending_manual"}:
        return "warn"
    return "pass"


def _combine_overall(current: str, new_value: str) -> str:
    rank = {"pass": 0, "warn": 1, "fail": 2}
    return new_value if rank[new_value] > rank[current] else current


def attach_gate(manifest: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    attachment = payload.get("manifest_attachment")
    if not isinstance(attachment, dict):
        raise ValueError("validator payload is missing manifest_attachment object")

    target_path = str(attachment.get("target_path", "")).strip()
    future_target_path = str(attachment.get("future_target_path", "")).strip()
    if target_path != EXPECTED_TARGET_PATH:
        raise ValueError(
            f"unsupported manifest target path: {target_path!r}; expected {EXPECTED_TARGET_PATH!r}"
        )
    if future_target_path != EXPECTED_FUTURE_TARGET_PATH:
        raise ValueError(
            "unsupported future target path: "
            f"{future_target_path!r}; expected {EXPECTED_FUTURE_TARGET_PATH!r}"
        )

    qc_check = attachment.get("qc_check")
    if not isinstance(qc_check, dict):
        raise ValueError("validator payload is missing manifest_attachment.qc_check object")

    check_id = str(qc_check.get("check_id", "")).strip()
    result = str(qc_check.get("result", "")).strip()
    if not check_id:
        raise ValueError("manifest_attachment.qc_check.check_id is required")
    if result not in VALID_GATE_RESULTS:
        raise ValueError(f"manifest_attachment.qc_check.result must be one of {sorted(VALID_GATE_RESULTS)}")

    qc = ensure_object(manifest, "qc")
    gates = qc.get("gates")
    if not isinstance(gates, list):
        gates = []
        qc["gates"] = gates

    replaced = False
    for idx, gate in enumerate(gates):
        if isinstance(gate, dict) and str(gate.get("check_id", "")).strip() == check_id:
            gates[idx] = qc_check
            replaced = True
            break
    if not replaced:
        gates.append(qc_check)

    current_overall = _normalize_qc_overall(str(qc.get("overall", "")).strip())
    qc["overall"] = _combine_overall(current_overall, _gate_result_to_overall(result))
    return manifest


def write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    target_dir = path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp = target_dir / f".{path.name}.tmp-{os.getpid()}"
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest_path).resolve()
    payload_path = Path(args.validator_output_path).resolve()

    if not manifest_path.exists():
        print(f"FAIL: manifest not found: {manifest_path}")
        return 2
    if not payload_path.exists():
        print(f"FAIL: validator output not found: {payload_path}")
        return 2

    try:
        manifest = load_json(manifest_path)
        payload = load_validator_payload(payload_path)
        updated = attach_gate(manifest, payload)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.write_back:
        write_json_atomic(manifest_path, updated)
        print(f"PASS: attached qc gate to manifest: {manifest_path}")
    else:
        print(json.dumps(updated, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
