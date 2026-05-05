#!/usr/bin/env python3
"""Run implemented release-lane validators and attach QC payloads into a pilot manifest."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


BLOCKED_PATH_TOKENS = {"cache", "engine", ".git", "site-packages"}
RUNNER_SCRIPT_ID = "run_pilot_release_chain_validation.py"
ATTACHMENT_TARGET_PATH = "qc.gates[]"
ATTACHMENT_FUTURE_TARGET_PATH = "qc.checks[]"
DEFAULT_BASE_MANIFEST = "examples/manifests/example-release-character-pilot-chain-base.manifest.json"
DEFAULT_OUTPUT_MANIFEST = (
    "examples/sandbox/manifests/reports/example-release-character-pilot-chain.generated.manifest.json"
)
DEFAULT_OUTPUT_DIR = "examples/sandbox/manifests/reports/pilot-release-chain-validation"
DEFAULT_CHAIN_PATH = "examples/release-lane-gate-chain/max_biped_v1_release_lane_gate_chain.json"
REQUIRED_IMPLEMENTED_CHECK_IDS = [
    "max_biped_v1_skeleton_contract",
    "dcc_conform_v1",
    "source_product_evidence_resolver_v1",
    "material_uv_qc_v1",
    "animation_smoke_v1",
    "screenshot_evidence_v1",
    "manual_hero_review_v1",
    "ci_artifact_retention_v1",
    "release_package_bundle_v1",
    "release_promotion_decision_v1",
    "release_publication_preflight_v1",
    "release_publication_request_approval_v1",
    "release_publication_execution_admission_gate_v1",
    "release_publication_rollback_drill_v1",
    "release_publication_ready_for_execution_request_v1",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run implemented release-lane validators and attach their manifest payloads "
            "into a pilot release-chain manifest."
        )
    )
    parser.add_argument(
        "--base-manifest",
        default=DEFAULT_BASE_MANIFEST,
        help="Base manifest fixture path used to build output manifest.",
    )
    parser.add_argument(
        "--output-manifest",
        default=DEFAULT_OUTPUT_MANIFEST,
        help="Output manifest path for attached QC gate results.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for validator payload snapshots and run summary.",
    )
    parser.add_argument(
        "--chain-path",
        default=DEFAULT_CHAIN_PATH,
        help="Release-lane gate chain definition path.",
    )
    parser.add_argument(
        "--strict-chain",
        action="store_true",
        help="Fail when pilot chain status is warn.",
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


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + os.linesep, encoding="utf-8")


def _get_qc_gates(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    qc = manifest.get("qc")
    if not isinstance(qc, dict):
        manifest["qc"] = {"overall": "not_run", "gates": [], "checks": []}
        qc = manifest["qc"]
    gates = qc.get("gates")
    if not isinstance(gates, list):
        qc["gates"] = []
        gates = qc["gates"]
    return [item for item in gates if isinstance(item, dict)]


def parse_payload_from_stdout(stdout: str) -> Dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise ValueError("validator output did not include JSON payload")
    return json.loads(stdout[start:])


def ensure_attachment_paths(payload: Dict[str, Any], step_name: str) -> None:
    attachment = payload.get("manifest_attachment", {})
    if not isinstance(attachment, dict):
        raise ValueError(f"{step_name} payload missing manifest_attachment object")
    target_path = str(attachment.get("target_path", "")).strip()
    future_target_path = str(attachment.get("future_target_path", "")).strip()
    if target_path != ATTACHMENT_TARGET_PATH:
        raise ValueError(
            f"{step_name} payload target_path must be {ATTACHMENT_TARGET_PATH}, got {target_path!r}"
        )
    if future_target_path != ATTACHMENT_FUTURE_TARGET_PATH:
        raise ValueError(
            f"{step_name} payload future_target_path must be {ATTACHMENT_FUTURE_TARGET_PATH}, "
            f"got {future_target_path!r}"
        )


def run_command(repo_root: Path, cmd: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    try:
        base_manifest_path = resolve_safe_path(repo_root, args.base_manifest, "base_manifest")
        output_manifest_path = resolve_safe_path(repo_root, args.output_manifest, "output_manifest")
        output_dir = resolve_safe_path(repo_root, args.output_dir, "output_dir")
        chain_path = resolve_safe_path(repo_root, args.chain_path, "chain_path")
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    if not base_manifest_path.exists():
        print(f"FAIL: base manifest not found: {base_manifest_path}")
        return 2
    if not chain_path.exists():
        print(f"FAIL: chain definition not found: {chain_path}")
        return 2
    if output_manifest_path.suffix.lower() != ".json":
        print("FAIL: output_manifest must be a .json file.")
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)
    attachment_dir = output_dir / "attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)

    base_manifest = load_json(base_manifest_path)
    base_pending_gates = _get_qc_gates(base_manifest)
    # Start from an empty gate list so implemented validator payloads attach first.
    base_manifest_qc = base_manifest.get("qc")
    if isinstance(base_manifest_qc, dict):
        base_manifest_qc["gates"] = []
    write_json(output_manifest_path, base_manifest)

    validator_steps: List[Dict[str, Any]] = [
        {
            "name": "skeleton",
            "command": [
                sys.executable,
                "tools/skeleton-validator/validate_skeleton_contract.py",
                "examples/skeleton-contracts/MAX_BIPED_v1.json",
                "examples/skeletons/max_biped_v1_pass.json",
            ],
            "payload_path": attachment_dir / "max_biped_v1_skeleton_contract.json",
        },
        {
            "name": "dcc_conform",
            "command": [
                sys.executable,
                "tools/dcc-conform/validate_dcc_conform_report.py",
                "examples/dcc-conform/max_biped_v1_conform_pass.json",
            ],
            "payload_path": attachment_dir / "dcc_conform_v1.json",
        },
        {
            "name": "source_product_resolver",
            "command": [
                sys.executable,
                "tools/source-product-evidence-resolver/validate_source_product_evidence_resolver_report.py",
                "examples/source-product-evidence-resolver/max_biped_v1_source_product_resolver_pass.json",
            ],
            "payload_path": attachment_dir / "source_product_evidence_resolver_v1.json",
        },
        {
            "name": "material_uv_qc",
            "command": [
                sys.executable,
                "tools/material-uv-qc/validate_material_uv_qc_report.py",
                "examples/material-uv-qc/max_biped_v1_material_uv_pass.json",
            ],
            "payload_path": attachment_dir / "material_uv_qc_v1.json",
        },
        {
            "name": "animation_smoke",
            "command": [
                sys.executable,
                "tools/animation-smoke/validate_animation_smoke_report.py",
                "examples/animation-smoke/max_biped_v1_animation_smoke_pass.json",
            ],
            "payload_path": attachment_dir / "animation_smoke_v1.json",
        },
        {
            "name": "screenshot_evidence_extractor",
            "command": [
                sys.executable,
                "tools/screenshot-evidence/extract_screenshot_evidence_index.py",
                "--source-index",
                "examples/screenshot-evidence/max_biped_v1_screenshot_source_index.json",
            ],
            "payload_path": attachment_dir / "screenshot_evidence_v1.json",
        },
        {
            "name": "manual_hero_review",
            "command": [
                sys.executable,
                "tools/manual-hero-review/validate_manual_hero_review_report.py",
                "examples/manual-hero-review/max_biped_v1_manual_hero_review_pass.json",
            ],
            "payload_path": attachment_dir / "manual_hero_review_v1.json",
        },
        {
            "name": "ci_artifact_retention",
            "command": [
                sys.executable,
                "tools/ci-artifact-retention/validate_ci_artifact_retention_report.py",
                "examples/ci-artifact-retention/max_biped_v1_ci_artifact_retention_pass.json",
            ],
            "payload_path": attachment_dir / "ci_artifact_retention_v1.json",
        },
        {
            "name": "release_package_bundle",
            "command": [
                sys.executable,
                "tools/release-package-bundle/validate_release_package_bundle_report.py",
                "examples/release-package-bundle/max_biped_v1_release_package_bundle_pass.json",
            ],
            "payload_path": attachment_dir / "release_package_bundle_v1.json",
        },
        {
            "name": "release_promotion_decision",
            "command": [
                sys.executable,
                "tools/release-promotion-decision/validate_release_promotion_decision_report.py",
                "examples/release-promotion-decision/max_biped_v1_release_promotion_decision_pass.json",
            ],
            "payload_path": attachment_dir / "release_promotion_decision_v1.json",
        },
        {
            "name": "release_publication_preflight",
            "command": [
                sys.executable,
                "tools/release-publication-preflight/validate_release_publication_preflight_report.py",
                "examples/release-publication-preflight/max_biped_v1_release_publication_preflight_pass.json",
            ],
            "payload_path": attachment_dir / "release_publication_preflight_v1.json",
        },
        {
            "name": "release_publication_request_approval",
            "command": [
                sys.executable,
                "tools/release-publication-request-approval/validate_release_publication_request_approval_report.py",
                "examples/release-publication-request-approval/max_biped_v1_release_publication_request_approval_pass.json",
            ],
            "payload_path": attachment_dir / "release_publication_request_approval_v1.json",
        },
        {
            "name": "release_publication_execution_admission_gate",
            "command": [
                sys.executable,
                "tools/release-publication-execution-admission-gate/validate_release_publication_execution_admission_gate_report.py",
                "examples/release-publication-execution-admission-gate/max_biped_v1_release_publication_execution_admission_gate_pass.json",
            ],
            "payload_path": attachment_dir / "release_publication_execution_admission_gate_v1.json",
        },
        {
            "name": "release_publication_rollback_drill_fixture",
            "mode": "override_existing_gate",
            "attachment_fixture": "examples/manifest-qc-attachments/max_biped_v1_release_publication_rollback_drill_attach_pass.json",
            "payload_path": attachment_dir / "release_publication_rollback_drill_v1.json",
        },
        {
            "name": "release_publication_ready_for_execution_request_fixture",
            "mode": "override_existing_gate",
            "attachment_fixture": "examples/manifest-qc-attachments/max_biped_v1_release_publication_ready_for_execution_request_attach_pass.json",
            "payload_path": attachment_dir / "release_publication_ready_for_execution_request_v1.json",
        },
    ]

    step_results: List[Dict[str, Any]] = []
    attachment_paths: List[str] = []
    snapshot_paths: List[str] = []
    attached_check_ids: List[str] = []
    gate_override_payloads: Dict[str, Dict[str, Any]] = {}

    for step in validator_steps:
        if "attachment_fixture" in step:
            fixture_path = repo_root / str(step["attachment_fixture"])
            if not fixture_path.exists():
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "failed_step": step["name"],
                            "reason": f"attachment_fixture_missing: {fixture_path}",
                        },
                        indent=2,
                    )
                )
                return 1
            try:
                payload = load_json(fixture_path)
                ensure_attachment_paths(payload, step["name"])
            except Exception as exc:
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "failed_step": step["name"],
                            "reason": f"attachment_fixture_invalid: {exc}",
                            "fixture_path": str(fixture_path),
                        },
                        indent=2,
                    )
                )
                return 1
        else:
            proc = run_command(repo_root, step["command"])
            if proc.returncode != 0:
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "failed_step": step["name"],
                            "command": step["command"],
                            "stdout": proc.stdout,
                            "stderr": proc.stderr,
                        },
                        indent=2,
                    )
                )
                return 1

            try:
                payload = parse_payload_from_stdout(proc.stdout)
                ensure_attachment_paths(payload, step["name"])
            except Exception as exc:
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "failed_step": step["name"],
                            "reason": f"payload_parse_error: {exc}",
                            "stdout": proc.stdout,
                        },
                        indent=2,
                    )
                )
                return 1

        payload_path: Path = step["payload_path"]
        write_json(payload_path, payload)
        snapshot_paths.append(str(payload_path))

        check_id = (
            payload.get("manifest_attachment", {})
            .get("qc_check", {})
            .get("check_id", "")
        )
        check_id_str = check_id.strip() if isinstance(check_id, str) else ""
        if step.get("mode") == "override_existing_gate":
            qc_check = payload.get("manifest_attachment", {}).get("qc_check", {})
            if not check_id_str or not isinstance(qc_check, dict):
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "failed_step": step["name"],
                            "reason": "override_fixture_missing_qc_check",
                            "payload_path": str(payload_path),
                        },
                        indent=2,
                    )
                )
                return 1
            gate_override_payloads[check_id_str] = qc_check
        else:
            attachment_paths.append(str(payload_path))

        if isinstance(check_id, str) and check_id.strip():
            attached_check_ids.append(check_id.strip())

        step_results.append(
            {
                "step": step["name"],
                "status": payload.get("status"),
                "payload_path": str(payload_path),
                "check_id": check_id,
            }
        )

    attach_cmd: List[str] = [
        sys.executable,
        "tools/manifest-validator/attach_qc_gate.py",
        "--manifest",
        str(output_manifest_path),
    ]
    for path in attachment_paths:
        attach_cmd.extend(["--attachment", path])

    attach_proc = run_command(repo_root, attach_cmd)
    if attach_proc.returncode != 0:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failed_step": "manifest_qc_attachment",
                    "command": attach_cmd,
                    "stdout": attach_proc.stdout,
                    "stderr": attach_proc.stderr,
                },
                indent=2,
            )
        )
        return 1

    # Re-append downstream pending gates from the base manifest after implemented gates.
    manifest_after_attachments = load_json(output_manifest_path)
    qc_after_attachments = manifest_after_attachments.get("qc")
    if not isinstance(qc_after_attachments, dict):
        print("FAIL: output manifest is missing qc object after attachment.")
        return 1
    gates_after_attachments = qc_after_attachments.get("gates")
    if not isinstance(gates_after_attachments, list):
        print("FAIL: output manifest qc.gates is not an array after attachment.")
        return 1
    attached_ids = {
        str(item.get("check_id", "")).strip()
        for item in gates_after_attachments
        if isinstance(item, dict)
    }
    for gate in base_pending_gates:
        gate_id = str(gate.get("check_id", "")).strip()
        if not gate_id or gate_id in attached_ids:
            continue
        gates_after_attachments.append(gate)

    missing_overrides: List[str] = []
    for check_id, qc_check in gate_override_payloads.items():
        replaced = False
        for idx, gate in enumerate(gates_after_attachments):
            gate_id = str(gate.get("check_id", "")).strip() if isinstance(gate, dict) else ""
            if gate_id == check_id:
                gates_after_attachments[idx] = qc_check
                replaced = True
                break
        if not replaced:
            missing_overrides.append(check_id)
    if missing_overrides:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failed_step": "apply_gate_overrides",
                    "missing_override_check_ids": missing_overrides,
                },
                indent=2,
            )
        )
        return 1
    write_json(output_manifest_path, manifest_after_attachments)

    chain_cmd: List[str] = [
        sys.executable,
        "tools/release-lane/validate_pilot_release_chain.py",
        str(output_manifest_path),
        "--chain",
        str(chain_path),
    ]
    if not args.strict_chain:
        chain_cmd.append("--allow-warn")

    chain_proc = run_command(repo_root, chain_cmd)
    try:
        chain_payload = parse_payload_from_stdout(chain_proc.stdout)
        ensure_attachment_paths(chain_payload, "pilot_release_chain_validation")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failed_step": "pilot_release_chain_validation",
                    "reason": f"payload_parse_error: {exc}",
                    "stdout": chain_proc.stdout,
                },
                indent=2,
            )
        )
        return 1

    chain_payload_path = attachment_dir / "pilot_release_chain_v1.json"
    write_json(chain_payload_path, chain_payload)

    attach_chain_cmd = [
        sys.executable,
        "tools/manifest-validator/attach_qc_gate.py",
        "--manifest",
        str(output_manifest_path),
        "--attachment",
        str(chain_payload_path),
    ]
    attach_chain_proc = run_command(repo_root, attach_chain_cmd)
    if attach_chain_proc.returncode != 0:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failed_step": "attach_pilot_release_chain_payload",
                    "command": attach_chain_cmd,
                    "stdout": attach_chain_proc.stdout,
                    "stderr": attach_chain_proc.stderr,
                },
                indent=2,
            )
        )
        return 1

    expected_missing = [
        check_id for check_id in REQUIRED_IMPLEMENTED_CHECK_IDS if check_id not in attached_check_ids
    ]
    if expected_missing:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failed_step": "implemented_gate_attachment_check",
                    "missing_check_ids": expected_missing,
                },
                indent=2,
            )
        )
        return 1

    final_manifest = load_json(output_manifest_path)
    qc = final_manifest.get("qc", {}) if isinstance(final_manifest.get("qc"), dict) else {}
    gate_count = len(qc.get("gates", [])) if isinstance(qc.get("gates"), list) else 0

    summary = {
        "runner_script_id": RUNNER_SCRIPT_ID,
        "status": "completed",
        "output_manifest_path": str(output_manifest_path),
        "base_manifest_path": str(base_manifest_path),
        "chain_path": str(chain_path),
        "attachment_paths": snapshot_paths + [str(chain_payload_path)],
        "validator_steps": step_results,
        "pilot_chain_status": chain_payload.get("status"),
        "pilot_chain_exit_code": chain_proc.returncode,
        "strict_chain": bool(args.strict_chain),
        "final_qc_overall": qc.get("overall"),
        "final_gate_count": gate_count,
        "attached_check_ids": sorted(attached_check_ids + ["pilot_release_chain_v1"]),
    }
    summary_path = output_dir / "run-summary.json"
    write_json(summary_path, summary)
    summary["summary_path"] = str(summary_path)
    print(json.dumps(summary, indent=2))

    if chain_proc.returncode != 0:
        return chain_proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
