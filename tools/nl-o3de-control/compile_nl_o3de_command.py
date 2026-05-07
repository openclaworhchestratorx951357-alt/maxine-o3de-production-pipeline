#!/usr/bin/env python3
"""Compile a natural-language O3DE request into a guarded command envelope."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_OUTPUT_DIR = Path("examples/sandbox/manifests/reports/nl-o3de-control")
DEFAULT_SOURCE_ARTIFACTS = {
    "candidate_matrix_ref": "examples/execution-admission/execution_admission_candidate_matrix_v1.json",
    "preflight_contracts_ref": "examples/execution-admission/execution_admission_preflight_contracts_v1.json",
    "preflight_proof_packages_ref": "examples/execution-admission/execution_admission_preflight_proof_packages_v1.json",
    "readiness_rollup_ref": "examples/execution-admission/execution_admission_readiness_rollup_v1.json",
    "production_readiness_report_ref": "examples/production-readiness-report/max_biped_v1_production_readiness_report_pass.json",
}
HIGH_RISK_FORBIDDEN = [
    "write_production_asset",
    "live_o3de_editor_execution",
    "asset_processor_execution",
    "real_execution",
    "publication",
    "engine_path_write",
    "production_path_write",
    "cache_live_db_access",
    "destructive_cleanup",
]
FORBIDDEN_PATH_TOKENS = [
    ".git",
    "engine",
    "cache",
    "production",
    "site-packages",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile natural language into a MAXINE NL O3DE control command envelope."
    )
    parser.add_argument("request", help="Natural-language O3DE request.")
    parser.add_argument(
        "--output",
        help="Optional path to write the compiled command JSON.",
    )
    return parser.parse_args()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:64] or "nl-o3de-command"


def classify_request(text: str) -> Tuple[str, float, str, List[str], str]:
    lower = text.lower()
    if any(term in lower for term in ["proof", "release chain", "pilot chain"]):
        return (
            "run_pilot_release_chain_proof",
            0.86,
            "evidence_only",
            ["read_file", "validate_schema", "run_validator", "write_sandbox_report"],
            "Run the non-executing release-lane proof and write bounded evidence reports.",
        )
    if any(term in lower for term in ["receipt", "no-op", "noop"]):
        return (
            "generate_noop_receipt",
            0.82,
            "noop_receipt",
            ["read_file", "validate_schema", "run_validator", "generate_noop_receipt"],
            "Generate or validate a no-op receipt without executing O3DE or publishing.",
        )
    if "manifest" in lower and any(term in lower for term in ["validate", "check", "verify"]):
        return (
            "validate_manifest",
            0.84,
            "read_only",
            ["read_file", "validate_schema", "run_validator"],
            "Validate the referenced manifest and report schema/QC status.",
        )
    if any(term in lower for term in ["publish", "publication", "prefab"]):
        return (
            "prepare_publication_dry_run",
            0.78,
            "dry_run_planning",
            ["read_file", "validate_schema", "run_validator", "write_sandbox_report"],
            "Prepare publication dry-run planning artifacts while keeping publication blocked.",
        )
    if any(term in lower for term in ["actor", "asset processor", "product", "fbx"]):
        return (
            "inspect_actor_products",
            0.76,
            "read_only",
            ["read_file", "validate_schema", "run_validator", "query_asset_processor_metadata"],
            "Inspect actor/product evidence from admitted local sources without running O3DE.",
        )
    if any(term in lower for term in ["project", "o3de"]):
        return (
            "inspect_o3de_project",
            0.68,
            "read_only",
            ["read_file", "validate_schema", "run_validator"],
            "Inspect known O3DE project metadata and report what is available.",
        )
    return (
        "unknown_or_unsupported",
        0.25,
        "read_only",
        ["read_file", "validate_schema"],
        "Ask for clarification before attempting O3DE control.",
    )


def extract_manifest_ref(text: str) -> str | None:
    match = re.search(r"([\w./\\-]+\.manifest\.json|[\w./\\-]+\.json)", text)
    if not match:
        return None
    return match.group(1).replace("\\", "/")


def build_command(text: str) -> Dict[str, object]:
    intent, confidence, mode, allowed_actions, expected = classify_request(text)
    candidate_id = "release_candidate_package_publish_dry_run_v1" if "publish" in text.lower() else "max_biped_v1"
    approval_required = mode in {"dry_run_planning", "sandbox_dry_run", "real_execution", "publication"}
    writes_allowed = mode in {"dry_run_planning", "noop_receipt"}
    return {
        "schema_version": "1.0.0",
        "record_type": "NL_O3DE_CONTROL_COMMAND_v1",
        "command_id": slugify(text),
        "command_version": "v1",
        "natural_language_request": text,
        "normalized_intent": intent,
        "intent_confidence": confidence,
        "target": {
            "candidate_id": candidate_id,
            "manifest_ref": extract_manifest_ref(text),
            "asset_query": text,
            "o3de_project_path": None,
        },
        "execution_mode": mode,
        "admission_status": "unadmitted",
        "allowed_actions": allowed_actions,
        "forbidden_actions": HIGH_RISK_FORBIDDEN,
        "source_artifacts": DEFAULT_SOURCE_ARTIFACTS,
        "approval": {
            "required": approval_required,
            "phrase_required": (
                "APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1"
                if approval_required
                else None
            ),
            "phrase_present": False,
            "decision_ref": None,
        },
        "safety": {
            "sandbox_only": True,
            "writes_allowed": writes_allowed,
            "real_execution_allowed": False,
            "publication_allowed": False,
            "production_ready_claimed": False,
            "requires_human_review": approval_required or intent == "unknown_or_unsupported",
        },
        "output_contract": {
            "receipt_required": mode in {"noop_receipt", "dry_run_planning"},
            "allowed_output_paths": [
                str(DEFAULT_OUTPUT_DIR).replace("\\", "/"),
                "examples/sandbox/execution-receipts/release-candidate-package-publication-dry-run",
            ],
            "forbidden_path_tokens": FORBIDDEN_PATH_TOKENS,
        },
        "expected_result": expected,
    }


def main() -> int:
    args = parse_args()
    payload = build_command(args.request)
    output = json.dumps(payload, indent=2) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
