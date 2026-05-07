import copy
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER = REPO_ROOT / "tools" / "nl-o3de-control" / "compile_nl_o3de_command.py"
VALIDATOR = (
    REPO_ROOT
    / "tools"
    / "execution-admission"
    / "validate_natural_language_o3de_command_pack.py"
)
PACK_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "natural_language_o3de_command_pack_v1.json"
)
SAFE_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "nl-o3de-control"
    / "natural_language_o3de_command_inspect_actor_products_static_v1.json"
)
BLOCKED_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "nl-o3de-control"
    / "natural_language_o3de_command_prepare_publication_dry_run_blocked_v1.json"
)
DOC = REPO_ROOT / "docs" / "maxine" / "nl-o3de-control" / "nl-o3de-command-pack-boundary-v1.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_validator(path: Path, *extra_args: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(path), *extra_args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip(), result.stderr
    return result.returncode, json.loads(result.stdout)


def _compile(request: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COMPILER), request, *extra_args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _finding_ids(report: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in report.get("findings", [])
        if isinstance(item, dict)
    }


def test_command_pack_validator_accepts_hardened_pack_example():
    code, report = _run_validator(PACK_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["runner_implemented"] is False
    assert report["runner_admitted"] is False
    assert report["execution_admitted"] is False
    assert report["publication_admitted"] is False
    assert report["production_ready_claimed"] is False


def test_safe_static_command_compiles_to_non_executing_envelope():
    result = _compile("Inspect MAXINE actor products from static evidence only")
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)

    assert envelope["command_envelope_status"] == "static_envelope_valid"
    assert envelope["command_admission_status"] == "unadmitted"
    assert envelope["execution_mode"] == "static_read_only"
    assert envelope["runner_required"] is False
    assert envelope["runner_implemented"] is False
    assert envelope["runner_admitted"] is False
    assert envelope["execution_admitted"] is False
    assert envelope["publication_admitted"] is False
    assert envelope["production_ready_claimed"] is False
    assert envelope["approval_phrase_present"] is False
    assert envelope["planned_actions"] == []


def test_non_read_only_command_compiles_to_blocked_refused_envelope():
    result = _compile("Run the O3DE Editor and prepare a publication dry run")
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)

    assert envelope["command_envelope_status"] == "static_envelope_blocked"
    assert envelope["command_admission_status"] == "blocked"
    assert envelope["runner_required"] is True
    assert envelope["runner_implemented"] is False
    assert envelope["runner_admitted"] is False
    assert envelope["execution_admitted"] is False
    assert envelope["publication_admitted"] is False
    assert envelope["production_ready_claimed"] is False
    assert envelope["approval_phrase_present"] is False
    assert envelope["refusal_reason_code"] in {
        "unsupported_execution_mode",
        "direct_o3de_execution_forbidden",
        "publication_mode_unadmitted",
    }
    assert envelope["planned_actions"] == []


def test_blocked_example_validates_only_when_blocked_is_allowed():
    blocked_code, blocked_report = _run_validator(BLOCKED_EXAMPLE)
    assert blocked_code != 0
    assert blocked_report["status"] == "blocked"

    allowed_code, allowed_report = _run_validator(BLOCKED_EXAMPLE, "--allow-blocked")
    assert allowed_code == 0
    assert allowed_report["status"] == "blocked"


def test_command_envelope_cannot_mark_protected_status_fields_true(tmp_path: Path):
    protected_fields = [
        "runner_implemented",
        "runner_admitted",
        "execution_admitted",
        "publication_admitted",
        "production_ready_claimed",
        "approval_phrase_present",
    ]
    for field in protected_fields:
        payload = copy.deepcopy(_load(SAFE_EXAMPLE))
        payload[field] = True
        path = tmp_path / f"{field}.json"
        _write(path, payload)

        code, report = _run_validator(path)

        assert code != 0
        assert field in report["blocked_or_failed_fields"]


def test_command_envelope_cannot_bypass_required_admission_chain_refs(tmp_path: Path):
    required_refs = [
        "candidate_matrix_ref",
        "preflight_contracts_ref",
        "preflight_proof_packages_ref",
        "readiness_rollup_ref",
        "dry_run_plan_ref",
        "dry_run_receipt_contract_ref",
        "blocked_unissued_receipt_ref",
        "admission_blocker_checklist_ref",
        "operator_approval_packet_ref",
        "operator_approval_packet_completeness_ref",
        "approval_request_readiness_ref",
        "non_approval_decision_ref",
        "sandbox_boundary_ref",
        "runner_interface_ref",
        "production_readiness_report_ref",
        "noop_receipt_status_ref",
    ]
    for ref_name in required_refs:
        payload = copy.deepcopy(_load(SAFE_EXAMPLE))
        payload["source_artifacts"][ref_name] = ""
        path = tmp_path / f"missing-{ref_name}.json"
        _write(path, payload)

        code, report = _run_validator(path)

        assert code != 0
        assert "source_artifact_ref_missing" in _finding_ids(report)


def test_command_envelope_cannot_bypass_runner_sandbox_or_receipt_gates(tmp_path: Path):
    required_true_fields = [
        "sandbox_boundary_required",
        "sandbox_boundary_validation_required",
        "runner_interface_required",
        "receipt_contract_required",
        "receipt_contract_validation_required",
        "candidate_admission_required",
    ]
    for field in required_true_fields:
        payload = copy.deepcopy(_load(BLOCKED_EXAMPLE))
        payload[field] = False
        path = tmp_path / f"bypass-{field}.json"
        _write(path, payload)

        code, report = _run_validator(path)

        assert code != 0
        assert field in report["blocked_or_failed_fields"]


def test_command_envelope_cannot_treat_approval_phrase_as_decision(tmp_path: Path):
    payload = copy.deepcopy(_load(BLOCKED_EXAMPLE))
    payload["approval_phrase_present"] = True
    payload["approval_decision_ref"] = None
    path = tmp_path / "approval-phrase-without-decision.json"
    _write(path, payload)

    code, report = _run_validator(path)

    assert code != 0
    assert "approval_phrase_without_decision_ref" in _finding_ids(report)


def test_compiler_rejects_output_paths_outside_allowed_sandbox():
    invalid_outputs = [
        ("examples/sandbox/nl-o3de-control/../escape.json", "parent_traversal"),
        ("C:/tmp/nl-o3de-control.json", "absolute_output_path"),
        ("//server/share/nl-o3de-control.json", "network_output_path"),
        ("examples/sandbox/engine/nl-o3de-control.json", "forbidden_output_root"),
        ("examples/sandbox/production/nl-o3de-control.json", "forbidden_output_root"),
        ("examples/sandbox/Cache/live.sqlite", "forbidden_output_root"),
        ("examples/sandbox/publish/nl-o3de-control.json", "forbidden_output_root"),
        ("examples/sandbox/spawn/nl-o3de-control.json", "forbidden_output_root"),
        ("examples/sandbox/nl-o3de-control/report.exe", "forbidden_output_extension"),
        ("examples/sandbox/nl-o3de-control/report.zip", "forbidden_output_extension"),
    ]
    for output_path, reason in invalid_outputs:
        result = _compile(
            "Inspect MAXINE actor products from static evidence only",
            "--output",
            output_path,
        )

        assert result.returncode != 0
        assert reason in result.stderr


def test_compiler_rejects_unsafe_or_unimplemented_modes_fail_closed():
    unsafe_requests = [
        ("Directly execute O3DE and load the level", "direct_o3de_execution_forbidden"),
        ("Run the O3DE Editor runtime now", "editor_runtime_execution_forbidden"),
        ("Run Asset Processor for the actor products", "asset_processor_execution_forbidden"),
        ("Open Blender and export the character", "blender_dcc_execution_forbidden"),
        ("Spawn a publication output and publish the prefab", "spawn_publish_forbidden"),
        ("Implement the MaxineAgentControl Gem adapter", "maxine_agent_control_gem_unimplemented"),
        ("Implement the Gem adapter for O3DE control", "gem_adapter_unimplemented"),
    ]
    for request, refusal_reason_code in unsafe_requests:
        result = _compile(request)
        assert result.returncode == 0, result.stderr
        envelope = json.loads(result.stdout)
        assert envelope["command_envelope_status"] == "static_envelope_blocked"
        assert envelope["command_admission_status"] == "blocked"
        assert envelope["refusal_reason_code"] == refusal_reason_code
        assert envelope["planned_actions"] == []


def test_docs_include_explicit_non_execution_and_non_admission_disclaimers():
    text = DOC.read_text(encoding="utf-8").lower()
    required_phrases = [
        "not a runner implementation",
        "not runner admission",
        "not command admission",
        "not direct o3de execution",
        "not gem adapter implementation",
        "not maxineagentcontrol gem implementation",
        "not publication",
        "not production-ready",
        "cannot bypass runner interface",
        "cannot bypass sandbox boundary",
        "cannot bypass receipt contract",
        "cannot bypass approval or admission gates",
    ]

    for phrase in required_phrases:
        assert phrase in text
