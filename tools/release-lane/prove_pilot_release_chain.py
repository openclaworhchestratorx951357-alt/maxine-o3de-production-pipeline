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
PRODUCTION_READINESS_REPORT_REL = (
    "tools/production-readiness-report/validate_production_readiness_report.py"
)
RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_REL = (
    "tools/execution-admission/generate_release_candidate_package_receipt_noop.py"
)
CONTROLLED_REAL_EVIDENCE_INVENTORY_REL = (
    "tools/release-lane/report_controlled_real_evidence_inventory.py"
)
EXECUTION_ADMISSION_CANDIDATE_MATRIX_VALIDATOR_REL = (
    "tools/execution-admission/validate_execution_admission_candidate_matrix.py"
)
EXECUTION_ADMISSION_CANDIDATE_MATRIX_EXAMPLE_REL = (
    "examples/execution-admission/execution_admission_candidate_matrix_v1.json"
)
EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_VALIDATOR_REL = (
    "tools/execution-admission/validate_execution_admission_preflight_contracts.py"
)
EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_EXAMPLE_REL = (
    "examples/execution-admission/execution_admission_preflight_contracts_v1.json"
)
EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_VALIDATOR_REL = (
    "tools/execution-admission/validate_execution_admission_preflight_proof_packages.py"
)
EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_EXAMPLE_REL = (
    "examples/execution-admission/execution_admission_preflight_proof_packages_v1.json"
)
EXECUTION_ADMISSION_READINESS_ROLLUP_VALIDATOR_REL = (
    "tools/execution-admission/validate_execution_admission_readiness_rollup.py"
)
EXECUTION_ADMISSION_READINESS_ROLLUP_EXAMPLE_REL = (
    "examples/execution-admission/execution_admission_readiness_rollup_v1.json"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_VALIDATOR_REL = (
    "tools/execution-admission/validate_release_candidate_publication_dry_run_plan.py"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_EXAMPLE_REL = (
    "examples/execution-admission/release_candidate_package_publish_dry_run_plan_v1.json"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_VALIDATOR_REL = (
    "tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py"
)
RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_EXAMPLE_REL = (
    "examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json"
)
PROJECT_INVENTORY_FIXTURE_REL = (
    "examples/sandbox/project-inventory/max_biped_v1_project_inventory.fixture.json"
)
ASSET_CANDIDATE_INVENTORY_FIXTURE_REL = (
    "examples/sandbox/asset-candidates/max_biped_v1_asset_candidate_inventory.fixture.json"
)
NOOP_DECISION_RECORD_REL = (
    "examples/execution-admission/"
    "release_candidate_package_receipt_noop_execution_admission_decision_approved.json"
)
NOOP_RECEIPT_OUTPUT_ROOT_REL = (
    "examples/sandbox/execution-receipts/release-candidate-package-receipt-noop"
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


def run_production_readiness_report(
    repo_root: Path,
    output_root: Path,
    manifest_path: Path,
) -> Tuple[int, Dict[str, Any]]:
    output_path = output_root / "production-readiness-report.json"
    cmd: List[str] = [
        sys.executable,
        str((repo_root / PRODUCTION_READINESS_REPORT_REL).resolve()),
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


def run_release_candidate_package_receipt_noop(
    repo_root: Path,
    output_root: Path,
    release_candidate_package_report: Path,
) -> Tuple[int, Dict[str, Any]]:
    output_path = (
        repo_root
        / NOOP_RECEIPT_OUTPUT_ROOT_REL
        / f"proof-{output_root.name}-release-candidate-package-receipt-noop.json"
    )
    cmd: List[str] = [
        sys.executable,
        str((repo_root / RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_REL).resolve()),
        "--decision-record",
        str((repo_root / NOOP_DECISION_RECORD_REL).resolve()),
        "--release-candidate-package-report",
        str(release_candidate_package_report.resolve()),
        "--output",
        str(output_path.resolve()),
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


def run_controlled_real_evidence_inventory(
    repo_root: Path,
    output_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    output_path = output_root / "controlled-real-evidence-inventory.json"
    cmd: List[str] = [
        sys.executable,
        str((repo_root / CONTROLLED_REAL_EVIDENCE_INVENTORY_REL).resolve()),
        "--project-inventory",
        str((repo_root / PROJECT_INVENTORY_FIXTURE_REL).resolve()),
        "--asset-candidate-inventory",
        str((repo_root / ASSET_CANDIDATE_INVENTORY_FIXTURE_REL).resolve()),
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


def run_execution_admission_candidate_matrix(
    repo_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    cmd: List[str] = [
        sys.executable,
        str((repo_root / EXECUTION_ADMISSION_CANDIDATE_MATRIX_VALIDATOR_REL).resolve()),
        str((repo_root / EXECUTION_ADMISSION_CANDIDATE_MATRIX_EXAMPLE_REL).resolve()),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["reporter_return_code"] = proc.returncode
    return proc.returncode, payload


def run_execution_admission_preflight_contracts(
    repo_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    cmd: List[str] = [
        sys.executable,
        str((repo_root / EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_VALIDATOR_REL).resolve()),
        str((repo_root / EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_EXAMPLE_REL).resolve()),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["reporter_return_code"] = proc.returncode
    return proc.returncode, payload


def run_execution_admission_preflight_proof_packages(
    repo_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    cmd: List[str] = [
        sys.executable,
        str(
            (
                repo_root
                / EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_VALIDATOR_REL
            ).resolve()
        ),
        str(
            (
                repo_root
                / EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_EXAMPLE_REL
            ).resolve()
        ),
        "--matrix-path",
        str((repo_root / EXECUTION_ADMISSION_CANDIDATE_MATRIX_EXAMPLE_REL).resolve()),
        "--preflight-path",
        str(
            (repo_root / EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_EXAMPLE_REL).resolve()
        ),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["reporter_return_code"] = proc.returncode
    return proc.returncode, payload


def run_execution_admission_readiness_rollup(
    repo_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    cmd: List[str] = [
        sys.executable,
        str((repo_root / EXECUTION_ADMISSION_READINESS_ROLLUP_VALIDATOR_REL).resolve()),
        str((repo_root / EXECUTION_ADMISSION_READINESS_ROLLUP_EXAMPLE_REL).resolve()),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["reporter_return_code"] = proc.returncode
    return proc.returncode, payload


def run_release_candidate_publication_dry_run_plan(
    repo_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    cmd: List[str] = [
        sys.executable,
        str(
            (
                repo_root
                / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_VALIDATOR_REL
            ).resolve()
        ),
        str(
            (
                repo_root
                / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_EXAMPLE_REL
            ).resolve()
        ),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
    payload["reporter_return_code"] = proc.returncode
    return proc.returncode, payload


def run_release_candidate_publication_dry_run_receipt_contract(
    repo_root: Path,
) -> Tuple[int, Dict[str, Any]]:
    cmd: List[str] = [
        sys.executable,
        str(
            (
                repo_root
                / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_VALIDATOR_REL
            ).resolve()
        ),
        str(
            (
                repo_root
                / RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_EXAMPLE_REL
            ).resolve()
        ),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    payload = parse_payload_from_stdout(proc.stdout)
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
        production_readiness_code, production_readiness_payload = run_production_readiness_report(
            repo_root=repo_root,
            output_root=output_root,
            manifest_path=Path(strict_payload["output_manifest"]),
        )
        strict_step_map = {
            str(step.get("step", "")).strip(): step
            for step in strict_payload.get("validator_steps", [])
            if isinstance(step, dict)
        }
        real_pilot_step = strict_step_map.get("real_pilot_release_candidate_package")
        if not isinstance(real_pilot_step, dict):
            raise ValueError("strict run missing real_pilot_release_candidate_package validator step")
        real_pilot_payload_path = real_pilot_step.get("payload_path")
        if not isinstance(real_pilot_payload_path, str) or not real_pilot_payload_path.strip():
            raise ValueError("strict run real_pilot_release_candidate_package payload_path is missing")
        receipt_code, receipt_payload = run_release_candidate_package_receipt_noop(
            repo_root=repo_root,
            output_root=output_root,
            release_candidate_package_report=Path(real_pilot_payload_path),
        )
        controlled_inventory_code, controlled_inventory_payload = run_controlled_real_evidence_inventory(
            repo_root=repo_root,
            output_root=output_root,
        )
        candidate_matrix_code, candidate_matrix_payload = run_execution_admission_candidate_matrix(
            repo_root=repo_root,
        )
        (
            preflight_contracts_code,
            preflight_contracts_payload,
        ) = run_execution_admission_preflight_contracts(
            repo_root=repo_root,
        )
        (
            preflight_proof_packages_code,
            preflight_proof_packages_payload,
        ) = run_execution_admission_preflight_proof_packages(
            repo_root=repo_root,
        )
        (
            readiness_rollup_code,
            readiness_rollup_payload,
        ) = run_execution_admission_readiness_rollup(
            repo_root=repo_root,
        )
        (
            dry_run_plan_code,
            dry_run_plan_payload,
        ) = run_release_candidate_publication_dry_run_plan(
            repo_root=repo_root,
        )
        (
            dry_run_receipt_contract_code,
            dry_run_receipt_contract_payload,
        ) = run_release_candidate_publication_dry_run_receipt_contract(
            repo_root=repo_root,
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
    if production_readiness_code != 0:
        failures.append("production readiness report command must return 0.")
    if production_readiness_payload.get("report_type") != "PRODUCTION_READINESS_REPORT_v1_REPORT":
        failures.append(
            "production readiness report must emit PRODUCTION_READINESS_REPORT_v1_REPORT."
        )
    if production_readiness_payload.get("status") != "pass":
        failures.append("production readiness report status must be pass.")
    if production_readiness_payload.get("readiness_decision") not in {
        "blocked_for_execution",
        "blocked_for_publication",
        "pass_evidence_only",
        "warn_evidence_only",
    }:
        failures.append(
            "production readiness report must classify evidence-only readiness without claiming full production readiness."
        )
    if receipt_code != 0:
        failures.append("release-candidate package no-op receipt report command must return 0.")
    if receipt_payload.get("report_type") != "RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_v1_REPORT":
        failures.append(
            "release-candidate package no-op receipt report must emit RELEASE_CANDIDATE_PACKAGE_RECEIPT_NOOP_v1_REPORT."
        )
    if receipt_payload.get("status") != "pass":
        failures.append("release-candidate package no-op receipt report status must be pass.")
    if receipt_payload.get("command_mode") != "noop":
        failures.append("release-candidate package no-op receipt report must keep command_mode=noop.")
    if receipt_payload.get("external_execution_performed") is not False:
        failures.append("release-candidate package no-op receipt report must keep external_execution_performed=false.")
    if receipt_payload.get("publication_performed") is not False:
        failures.append("release-candidate package no-op receipt report must keep publication_performed=false.")
    if receipt_payload.get("candidate_id") != "release_candidate_package_receipt_noop_v1":
        failures.append("release-candidate package no-op receipt report candidate_id must match admitted candidate.")
    if controlled_inventory_code != 0:
        failures.append("controlled real evidence inventory report command must return 0.")
    if controlled_inventory_payload.get("report_type") != "CONTROLLED_REAL_EVIDENCE_INVENTORY_v1_REPORT":
        failures.append(
            "controlled real evidence inventory report must emit CONTROLLED_REAL_EVIDENCE_INVENTORY_v1_REPORT."
        )
    if controlled_inventory_payload.get("status") != "pass":
        failures.append("controlled real evidence inventory report status must be pass.")
    if controlled_inventory_payload.get("execution_admitted") is not False:
        failures.append("controlled real evidence inventory report must keep execution_admitted=false.")
    if candidate_matrix_code != 0:
        failures.append("execution-admission candidate matrix validator must return 0.")
    if candidate_matrix_payload.get("report_type") != "EXECUTION_ADMISSION_CANDIDATE_MATRIX_VALIDATION_v1_REPORT":
        failures.append(
            "execution-admission candidate matrix validator must emit EXECUTION_ADMISSION_CANDIDATE_MATRIX_VALIDATION_v1_REPORT."
        )
    if candidate_matrix_payload.get("status") != "pass":
        failures.append("execution-admission candidate matrix validator status must be pass.")
    if candidate_matrix_payload.get("candidate_matrix_present") is not True:
        failures.append("execution-admission candidate matrix report must confirm candidate_matrix_present=true.")
    if candidate_matrix_payload.get("admitted_noop_receipt_candidate_ids") != ["release_candidate_package_receipt_noop_v1"]:
        failures.append(
            "execution-admission candidate matrix report must keep admitted_noop_receipt_candidate_ids limited to release_candidate_package_receipt_noop_v1."
        )
    if candidate_matrix_payload.get("admitted_real_execution_candidate_ids") not in ([], None):
        failures.append("execution-admission candidate matrix report must keep admitted_real_execution_candidate_ids empty.")
    if candidate_matrix_payload.get("admitted_publication_candidate_ids") not in ([], None):
        failures.append("execution-admission candidate matrix report must keep admitted_publication_candidate_ids empty.")
    if candidate_matrix_payload.get("real_execution_admission_status") != "blocked":
        failures.append("execution-admission candidate matrix report must keep real_execution_admission_status=blocked.")
    if candidate_matrix_payload.get("publication_admission_status") != "blocked":
        failures.append("execution-admission candidate matrix report must keep publication_admission_status=blocked.")
    if preflight_contracts_code != 0:
        failures.append("execution-admission preflight contracts validator must return 0.")
    if preflight_contracts_payload.get("report_type") != "EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_VALIDATION_v1_REPORT":
        failures.append(
            "execution-admission preflight contracts validator must emit EXECUTION_ADMISSION_PREFLIGHT_CONTRACTS_VALIDATION_v1_REPORT."
        )
    if preflight_contracts_payload.get("status") != "pass":
        failures.append("execution-admission preflight contracts validator status must be pass.")
    if preflight_contracts_payload.get("preflight_contracts_present") is not True:
        failures.append(
            "execution-admission preflight contracts report must confirm preflight_contracts_present=true."
        )
    if preflight_contracts_payload.get("admitted_noop_receipt_candidate_ids") != ["release_candidate_package_receipt_noop_v1"]:
        failures.append(
            "execution-admission preflight contracts report must keep admitted_noop_receipt_candidate_ids limited to release_candidate_package_receipt_noop_v1."
        )
    if preflight_contracts_payload.get("admitted_real_execution_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight contracts report must keep admitted_real_execution_candidate_ids empty.")
    if preflight_contracts_payload.get("admitted_publication_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight contracts report must keep admitted_publication_candidate_ids empty.")
    if preflight_contracts_payload.get("real_execution_preflight_passed_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight contracts report must keep real_execution_preflight_passed_candidate_ids empty.")
    if preflight_contracts_payload.get("publication_preflight_passed_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight contracts report must keep publication_preflight_passed_candidate_ids empty.")
    if preflight_contracts_payload.get("real_execution_admission_status") != "blocked":
        failures.append("execution-admission preflight contracts report must keep real_execution_admission_status=blocked.")
    if preflight_contracts_payload.get("publication_admission_status") != "blocked":
        failures.append("execution-admission preflight contracts report must keep publication_admission_status=blocked.")
    if preflight_contracts_payload.get("production_ready_claimed") is not False:
        failures.append("execution-admission preflight contracts report must keep production_ready_claimed=false.")
    if preflight_proof_packages_code != 0:
        failures.append("execution-admission preflight proof packages validator must return 0.")
    if preflight_proof_packages_payload.get("report_type") != "EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_VALIDATION_v1_REPORT":
        failures.append(
            "execution-admission preflight proof packages validator must emit EXECUTION_ADMISSION_PREFLIGHT_PROOF_PACKAGES_VALIDATION_v1_REPORT."
        )
    if preflight_proof_packages_payload.get("status") != "pass":
        failures.append("execution-admission preflight proof packages validator status must be pass.")
    if preflight_proof_packages_payload.get("preflight_proof_packages_present") is not True:
        failures.append(
            "execution-admission preflight proof packages report must confirm preflight_proof_packages_present=true."
        )
    if preflight_proof_packages_payload.get("admitted_noop_receipt_candidate_ids") != ["release_candidate_package_receipt_noop_v1"]:
        failures.append(
            "execution-admission preflight proof packages report must keep admitted_noop_receipt_candidate_ids limited to release_candidate_package_receipt_noop_v1."
        )
    if preflight_proof_packages_payload.get("admitted_real_execution_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight proof packages report must keep admitted_real_execution_candidate_ids empty.")
    if preflight_proof_packages_payload.get("admitted_publication_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight proof packages report must keep admitted_publication_candidate_ids empty.")
    if preflight_proof_packages_payload.get("real_execution_preflight_passed_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight proof packages report must keep real_execution_preflight_passed_candidate_ids empty.")
    if preflight_proof_packages_payload.get("publication_preflight_passed_candidate_ids") not in ([], None):
        failures.append("execution-admission preflight proof packages report must keep publication_preflight_passed_candidate_ids empty.")
    if preflight_proof_packages_payload.get("real_execution_admission_status") != "blocked":
        failures.append("execution-admission preflight proof packages report must keep real_execution_admission_status=blocked.")
    if preflight_proof_packages_payload.get("publication_admission_status") != "blocked":
        failures.append("execution-admission preflight proof packages report must keep publication_admission_status=blocked.")
    if preflight_proof_packages_payload.get("production_ready_claimed") is not False:
        failures.append("execution-admission preflight proof packages report must keep production_ready_claimed=false.")
    if readiness_rollup_code != 0:
        failures.append("execution-admission readiness rollup validator must return 0.")
    if readiness_rollup_payload.get("report_type") != "EXECUTION_ADMISSION_READINESS_ROLLUP_VALIDATION_v1_REPORT":
        failures.append(
            "execution-admission readiness rollup validator must emit EXECUTION_ADMISSION_READINESS_ROLLUP_VALIDATION_v1_REPORT."
        )
    if readiness_rollup_payload.get("status") != "pass":
        failures.append("execution-admission readiness rollup validator status must be pass.")
    if readiness_rollup_payload.get("execution_admission_readiness_rollup_present") is not True:
        failures.append(
            "execution-admission readiness rollup report must confirm execution_admission_readiness_rollup_present=true."
        )
    if readiness_rollup_payload.get("overall_readiness_rollup_status") != "static_rollup_valid_blocked":
        failures.append(
            "execution-admission readiness rollup report must keep overall_readiness_rollup_status=static_rollup_valid_blocked."
        )
    if readiness_rollup_payload.get("admitted_noop_receipt_candidate_ids") != ["release_candidate_package_receipt_noop_v1"]:
        failures.append(
            "execution-admission readiness rollup report must keep admitted_noop_receipt_candidate_ids limited to release_candidate_package_receipt_noop_v1."
        )
    if readiness_rollup_payload.get("admitted_real_execution_candidate_ids") not in ([], None):
        failures.append("execution-admission readiness rollup report must keep admitted_real_execution_candidate_ids empty.")
    if readiness_rollup_payload.get("admitted_publication_candidate_ids") not in ([], None):
        failures.append("execution-admission readiness rollup report must keep admitted_publication_candidate_ids empty.")
    if readiness_rollup_payload.get("real_execution_preflight_passed_candidate_ids") not in ([], None):
        failures.append("execution-admission readiness rollup report must keep real_execution_preflight_passed_candidate_ids empty.")
    if readiness_rollup_payload.get("publication_preflight_passed_candidate_ids") not in ([], None):
        failures.append("execution-admission readiness rollup report must keep publication_preflight_passed_candidate_ids empty.")
    if readiness_rollup_payload.get("real_execution_admission_status") != "blocked":
        failures.append("execution-admission readiness rollup report must keep real_execution_admission_status=blocked.")
    if readiness_rollup_payload.get("publication_admission_status") != "blocked":
        failures.append("execution-admission readiness rollup report must keep publication_admission_status=blocked.")
    if readiness_rollup_payload.get("production_ready_claimed") is not False:
        failures.append("execution-admission readiness rollup report must keep production_ready_claimed=false.")
    if readiness_rollup_payload.get("unsafe_claims_detected") is not False:
        failures.append("execution-admission readiness rollup report must keep unsafe_claims_detected=false.")
    if dry_run_plan_code != 0:
        failures.append("release-candidate publication dry-run plan validator must return 0.")
    if dry_run_plan_payload.get("report_type") != "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_VALIDATION_v1_REPORT":
        failures.append(
            "release-candidate publication dry-run plan validator must emit RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_PLAN_VALIDATION_v1_REPORT."
        )
    if dry_run_plan_payload.get("status") != "pass":
        failures.append("release-candidate publication dry-run plan validator status must be pass.")
    if dry_run_plan_payload.get("release_candidate_publication_dry_run_plan_present") is not True:
        failures.append(
            "release-candidate publication dry-run plan report must confirm release_candidate_publication_dry_run_plan_present=true."
        )
    if dry_run_plan_payload.get("planned_candidate_id") != "release_candidate_package_publish_dry_run_v1":
        failures.append(
            "release-candidate publication dry-run plan report must keep planned_candidate_id=release_candidate_package_publish_dry_run_v1."
        )
    if dry_run_plan_payload.get("candidate_type") != "dry_run":
        failures.append("release-candidate publication dry-run plan report must keep candidate_type=dry_run.")
    if dry_run_plan_payload.get("plan_status") != "static_plan_valid_blocked":
        failures.append(
            "release-candidate publication dry-run plan report must keep plan_status=static_plan_valid_blocked."
        )
    if dry_run_plan_payload.get("dry_run_admitted") is not False:
        failures.append("release-candidate publication dry-run plan report must keep dry_run_admitted=false.")
    if dry_run_plan_payload.get("publication_admitted") is not False:
        failures.append(
            "release-candidate publication dry-run plan report must keep publication_admitted=false."
        )
    if dry_run_plan_payload.get("real_execution_admitted") is not False:
        failures.append(
            "release-candidate publication dry-run plan report must keep real_execution_admitted=false."
        )
    if dry_run_plan_payload.get("production_ready_claimed") is not False:
        failures.append(
            "release-candidate publication dry-run plan report must keep production_ready_claimed=false."
        )
    if dry_run_plan_payload.get("publication_surfaces_blocked") is not True:
        failures.append(
            "release-candidate publication dry-run plan report must keep publication_surfaces_blocked=true."
        )
    if dry_run_plan_payload.get("execution_surfaces_blocked") is not True:
        failures.append(
            "release-candidate publication dry-run plan report must keep execution_surfaces_blocked=true."
        )
    if dry_run_plan_payload.get("approval_phrase_required") != (
        "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    ):
        failures.append(
            "release-candidate publication dry-run plan report must keep exact candidate-specific approval phrase."
        )
    if int(dry_run_plan_payload.get("missing_evidence_items_count", 0)) <= 0:
        failures.append(
            "release-candidate publication dry-run plan report must keep missing_evidence_items_count > 0."
        )
    if not dry_run_plan_payload.get("blocked_reason_codes"):
        failures.append(
            "release-candidate publication dry-run plan report must keep blocked_reason_codes non-empty."
        )
    dry_run_alignment = (
        dry_run_plan_payload.get("readiness_rollup_alignment")
        if isinstance(dry_run_plan_payload.get("readiness_rollup_alignment"), dict)
        else {}
    )
    if dry_run_alignment.get("safest_next_preparation_slice_id") != "candidate_specific_dry_run_planning_v1":
        failures.append(
            "release-candidate publication dry-run plan report must align with readiness rollup slice candidate_specific_dry_run_planning_v1."
        )
    if dry_run_alignment.get("safest_next_preparation_candidate_id") != "release_candidate_package_publish_dry_run_v1":
        failures.append(
            "release-candidate publication dry-run plan report must align with readiness rollup candidate release_candidate_package_publish_dry_run_v1."
        )
    computed_source_status = (
        dry_run_plan_payload.get("computed_source_artifact_validation_status")
        if isinstance(dry_run_plan_payload.get("computed_source_artifact_validation_status"), dict)
        else {}
    )
    for key in (
        "candidate_matrix_status",
        "preflight_contracts_status",
        "preflight_proof_packages_status",
        "readiness_rollup_status",
        "production_readiness_status",
        "noop_receipt_status",
    ):
        if computed_source_status.get(key) != "pass":
            failures.append(
                f"release-candidate publication dry-run plan computed source status must keep {key}=pass."
            )
    if dry_run_receipt_contract_code != 0:
        failures.append(
            "release-candidate publication dry-run receipt contract validator must return 0."
        )
    if dry_run_receipt_contract_payload.get("report_type") != "RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_VALIDATION_v1_REPORT":
        failures.append(
            "release-candidate publication dry-run receipt contract validator must emit RELEASE_CANDIDATE_PUBLICATION_DRY_RUN_RECEIPT_CONTRACT_VALIDATION_v1_REPORT."
        )
    if dry_run_receipt_contract_payload.get("status") != "pass":
        failures.append("release-candidate publication dry-run receipt contract validator status must be pass.")
    if dry_run_receipt_contract_payload.get("release_candidate_publication_dry_run_receipt_contract_present") is not True:
        failures.append(
            "release-candidate publication dry-run receipt contract report must confirm release_candidate_publication_dry_run_receipt_contract_present=true."
        )
    if dry_run_receipt_contract_payload.get("planned_candidate_id") != "release_candidate_package_publish_dry_run_v1":
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep planned_candidate_id=release_candidate_package_publish_dry_run_v1."
        )
    if dry_run_receipt_contract_payload.get("candidate_type") != "dry_run":
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep candidate_type=dry_run."
        )
    if dry_run_receipt_contract_payload.get("receipt_type") != "release_candidate_package_publish_dry_run_receipt_v1":
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep receipt_type=release_candidate_package_publish_dry_run_receipt_v1."
        )
    if dry_run_receipt_contract_payload.get("receipt_contract_status") != "static_contract_valid_blocked":
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep receipt_contract_status=static_contract_valid_blocked."
        )
    if dry_run_receipt_contract_payload.get("receipt_issued") is not False:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep receipt_issued=false."
        )
    if dry_run_receipt_contract_payload.get("dry_run_admitted") is not False:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep dry_run_admitted=false."
        )
    if dry_run_receipt_contract_payload.get("publication_admitted") is not False:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep publication_admitted=false."
        )
    if dry_run_receipt_contract_payload.get("real_execution_admitted") is not False:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep real_execution_admitted=false."
        )
    if dry_run_receipt_contract_payload.get("production_ready_claimed") is not False:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep production_ready_claimed=false."
        )
    if dry_run_receipt_contract_payload.get("publication_surfaces_blocked") is not True:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep publication_surfaces_blocked=true."
        )
    if dry_run_receipt_contract_payload.get("execution_surfaces_blocked") is not True:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep execution_surfaces_blocked=true."
        )
    if dry_run_receipt_contract_payload.get("cache_live_db_access_blocked") is not True:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep cache_live_db_access_blocked=true."
        )
    if dry_run_receipt_contract_payload.get("authoritative_id_claims_blocked") is not True:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep authoritative_id_claims_blocked=true."
        )
    if dry_run_receipt_contract_payload.get("approval_phrase_required") != (
        "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
    ):
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep exact candidate-specific approval phrase."
        )
    if int(dry_run_receipt_contract_payload.get("missing_evidence_items_count", 0)) <= 0:
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep missing_evidence_items_count > 0."
        )
    if not dry_run_receipt_contract_payload.get("blocked_reason_codes"):
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep blocked_reason_codes non-empty."
        )
    receipt_source_status = (
        dry_run_receipt_contract_payload.get("computed_source_artifact_validation_status")
        if isinstance(dry_run_receipt_contract_payload.get("computed_source_artifact_validation_status"), dict)
        else {}
    )
    for key in (
        "candidate_matrix_status",
        "preflight_contracts_status",
        "preflight_proof_packages_status",
        "readiness_rollup_status",
        "dry_run_plan_status",
        "production_readiness_status",
        "noop_receipt_status",
    ):
        if receipt_source_status.get(key) != "pass":
            failures.append(
                f"release-candidate publication dry-run receipt contract computed source status must keep {key}=pass."
            )
    receipt_rollup_alignment = (
        dry_run_receipt_contract_payload.get("readiness_rollup_alignment")
        if isinstance(dry_run_receipt_contract_payload.get("readiness_rollup_alignment"), dict)
        else {}
    )
    if receipt_rollup_alignment.get("safest_next_preparation_slice_id") != "candidate_specific_dry_run_planning_v1":
        failures.append(
            "release-candidate publication dry-run receipt contract report must align with readiness rollup slice candidate_specific_dry_run_planning_v1."
        )
    if receipt_rollup_alignment.get("safest_next_preparation_candidate_id") != "release_candidate_package_publish_dry_run_v1":
        failures.append(
            "release-candidate publication dry-run receipt contract report must align with readiness rollup candidate release_candidate_package_publish_dry_run_v1."
        )
    receipt_dry_run_alignment = (
        dry_run_receipt_contract_payload.get("dry_run_plan_alignment")
        if isinstance(dry_run_receipt_contract_payload.get("dry_run_plan_alignment"), dict)
        else {}
    )
    if receipt_dry_run_alignment.get("planned_candidate_id") != "release_candidate_package_publish_dry_run_v1":
        failures.append(
            "release-candidate publication dry-run receipt contract report must align with dry-run plan candidate release_candidate_package_publish_dry_run_v1."
        )
    if receipt_dry_run_alignment.get("alignment_status") != "aligned":
        failures.append(
            "release-candidate publication dry-run receipt contract report must keep dry_run_plan_alignment.alignment_status=aligned."
        )

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
            "production_readiness_report": production_readiness_payload,
            "release_candidate_package_receipt_noop_report": receipt_payload,
            "controlled_real_evidence_inventory_report": controlled_inventory_payload,
            "execution_admission_candidate_matrix_report": candidate_matrix_payload,
            "execution_admission_preflight_contracts_report": preflight_contracts_payload,
            "execution_admission_preflight_proof_packages_report": preflight_proof_packages_payload,
            "execution_admission_readiness_rollup_report": readiness_rollup_payload,
            "release_candidate_publication_dry_run_plan_report": dry_run_plan_payload,
            "release_candidate_publication_dry_run_receipt_contract_report": dry_run_receipt_contract_payload,
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
