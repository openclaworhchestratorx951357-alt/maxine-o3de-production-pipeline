#!/usr/bin/env python3
"""Run a deterministic local/CI proof for the pilot release-lane chain."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
PROOF_SCRIPT_ID = "prove_pilot_release_chain.py"
ATTACHMENT_TARGET_PATH = "qc.gates[]"
ATTACHMENT_FUTURE_TARGET_PATH = "qc.checks[]"
DEFAULT_OUTPUT_ROOT = "examples/sandbox/manifests/reports/pilot-release-chain-proof"
RUNNER_REL = "tools/release-lane/run_pilot_release_chain_validation.py"
EVIDENCE_ADMISSION_STATUS_REL = "tools/release-lane/report_release_lane_evidence_admission_status.py"
EXECUTION_ADMISSION_RECEIPT_DRY_RUN_REL = (
    "tools/release-lane/generate_execution_admission_receipt_dry_run.py"
)
DECISION_RECORD_REL = (
    "examples/execution-admission/max_biped_v1_execution_admission_decision_approved.json"
)
BASE_MANIFEST_REL = "examples/manifests/example-release-character-pilot-chain-base.manifest.json"
CHAIN_REL = "examples/release-lane-gate-chain/max_biped_v1_release_lane_gate_chain.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prove pilot release-lane chain integration by running normal and strict "
            "validation passes with deterministic expectations."
        )
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Output root directory for proof run artifacts.",
    )
    return parser.parse_args()


def _path_within(candidate: Path, parent: Path) -> bool:
    candidate_abs = candidate.resolve()
    parent_abs = parent.resolve()
    try:
        candidate_abs.relative_to(parent_abs)
        return True
    except ValueError:
        return False


def resolve_safe_path(repo_root: Path, raw_path: str, label: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if not _path_within(candidate, repo_root):
        raise ValueError(f"{label} must remain inside repository root.")

    lower_parts = {part.lower() for part in candidate.parts}
    blocked = lower_parts & BLOCKED_PATH_TOKENS
    if blocked:
        blocked_tokens = ", ".join(sorted(blocked))
        raise ValueError(f"{label} resolves to blocked path token(s): {blocked_tokens}.")

    return candidate


def parse_payload_from_stdout(stdout: str) -> Dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise ValueError("runner output did not include JSON payload")
    return json.loads(stdout[start:])


def run_runner(
    repo_root: Path,
    output_root: Path,
    run_name: str,
    strict: bool,
) -> Tuple[int, Dict[str, Any]]:
    run_root = output_root / run_name
    run_root.mkdir(parents=True, exist_ok=True)
    output_manifest = run_root / "generated.manifest.json"
    output_dir = run_root / "reports"

    cmd: List[str] = [
        sys.executable,
        str((repo_root / RUNNER_REL).resolve()),
        "--base-manifest",
        str((repo_root / BASE_MANIFEST_REL).resolve()),
        "--output-manifest",
        str(output_manifest),
        "--output-dir",
        str(output_dir),
        "--chain-path",
        str((repo_root / CHAIN_REL).resolve()),
    ]
    if strict:
        cmd.append("--strict-chain")

    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["output_manifest"] = str(output_manifest)
    payload["output_dir"] = str(output_dir)
    payload["runner_return_code"] = proc.returncode
    return proc.returncode, payload


def run_evidence_admission_status(
    repo_root: Path,
    output_root: Path,
    manifest_path: Path,
) -> Tuple[int, Dict[str, Any]]:
    output_path = output_root / "release-lane-evidence-admission-status.json"
    cmd: List[str] = [
        sys.executable,
        str((repo_root / EVIDENCE_ADMISSION_STATUS_REL).resolve()),
        "--manifest",
        str(manifest_path),
        "--output",
        str(output_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["output_path"] = str(output_path)
    payload["reporter_return_code"] = proc.returncode
    return proc.returncode, payload


def run_execution_admission_receipt_dry_run(
    repo_root: Path,
    output_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    output_path = output_root / "execution-admission-receipt-dry-run.json"
    cmd: List[str] = [
        sys.executable,
        str((repo_root / EXECUTION_ADMISSION_RECEIPT_DRY_RUN_REL).resolve()),
        "--decision-record",
        str((repo_root / DECISION_RECORD_REL).resolve()),
        "--output",
        str(output_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["output_path"] = str(output_path)
    payload["reporter_return_code"] = proc.returncode
    return proc.returncode, payload


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + os.linesep, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        output_root = resolve_safe_path(repo_root, args.output_root, "output_root")
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    try:
        normal_code, normal_payload = run_runner(
            repo_root=repo_root,
            output_root=output_root,
            run_name="normal",
            strict=False,
        )
        strict_code, strict_payload = run_runner(
            repo_root=repo_root,
            output_root=output_root,
            run_name="strict",
            strict=True,
        )
        evidence_code, evidence_payload = run_evidence_admission_status(
            repo_root=repo_root,
            output_root=output_root,
            manifest_path=Path(strict_payload["output_manifest"]),
        )
        receipt_code, receipt_payload = run_execution_admission_receipt_dry_run(
            repo_root=repo_root,
            output_root=output_root,
        )
    except Exception as exc:
        print(f"FAIL: pilot chain proof runner execution failed: {exc}")
        return 1

    failures: List[str] = []
    if normal_code != 0:
        failures.append("normal run must return 0.")
    if normal_payload.get("pilot_chain_status") != "pass":
        failures.append("normal run must produce pilot_chain_status=pass for current fixture chain.")
    if strict_code != 0:
        failures.append("strict run must return 0 when chain is pass.")
    if strict_payload.get("pilot_chain_status") != "pass":
        failures.append("strict run must produce pilot_chain_status=pass for current fixture chain.")
    if evidence_code != 0:
        failures.append("evidence admission status report command must return 0.")
    if evidence_payload.get("report_type") != "RELEASE_LANE_EVIDENCE_ADMISSION_STATUS_v1_REPORT":
        failures.append(
            "evidence admission status report must emit RELEASE_LANE_EVIDENCE_ADMISSION_STATUS_v1_REPORT."
        )
    if evidence_payload.get("status") != "pass":
        failures.append("evidence admission status report status must be pass.")
    if receipt_code != 0:
        failures.append("execution-admission receipt dry-run report command must return 0.")
    if receipt_payload.get("report_type") != "EXECUTION_ADMISSION_RECEIPT_DRY_RUN_v1_REPORT":
        failures.append(
            "execution-admission receipt dry-run report must emit EXECUTION_ADMISSION_RECEIPT_DRY_RUN_v1_REPORT."
        )
    if receipt_payload.get("status") != "pass":
        failures.append("execution-admission receipt dry-run report status must be pass.")
    if receipt_payload.get("execution_performed") is not False:
        failures.append("execution-admission receipt dry-run report must keep execution_performed=false.")

    summary: Dict[str, Any] = {
        "status": "pass" if not failures else "fail",
        "check_id": "pilot_release_chain_ci_proof_v1",
        "script_id": PROOF_SCRIPT_ID,
        "current_attachment_target_path": ATTACHMENT_TARGET_PATH,
        "future_attachment_target_path": ATTACHMENT_FUTURE_TARGET_PATH,
        "details": {
            "normal_run": normal_payload,
            "strict_run": strict_payload,
            "evidence_admission_report": evidence_payload,
            "execution_admission_receipt_dry_run_report": receipt_payload,
            "failures": failures,
        },
    }

    summary_path = output_root / "proof-summary.json"
    write_json(summary_path, summary)
    summary["summary_path"] = str(summary_path)
    print(json.dumps(summary, indent=2))

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
