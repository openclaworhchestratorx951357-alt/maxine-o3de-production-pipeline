import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "schemas" / "maxine_nl_o3de_control_command.schema.json"
VALIDATOR = REPO_ROOT / "tools" / "nl-o3de-control" / "validate_nl_o3de_control_command.py"
COMPILER = REPO_ROOT / "tools" / "nl-o3de-control" / "compile_nl_o3de_command.py"
INSPECT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "nl-o3de-control"
    / "nl_o3de_control_command_inspect_actor_products_v1.json"
)
DRY_RUN_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "nl-o3de-control"
    / "nl_o3de_control_command_prepare_publication_dry_run_blocked_v1.json"
)


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
    start = result.stdout.find("{")
    assert start >= 0, f"expected JSON output:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    return result.returncode, json.loads(result.stdout[start:])


def _finding_ids(report: dict) -> set[str]:
    return {
        str(item.get("id", "")).strip()
        for item in report.get("findings", [])
        if isinstance(item, dict)
    }


def test_inspect_actor_products_example_validates_and_passes_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(SCHEMA)
    payload = _load(INSPECT_EXAMPLE)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    assert not errors, [f"{'.'.join(str(p) for p in err.path)}: {err.message}" for err in errors]

    code, report = _run_validator(INSPECT_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["normalized_intent"] == "inspect_actor_products"
    assert report["execution_mode"] == "read_only"


def test_publication_dry_run_planning_example_is_valid_but_not_publication():
    code, report = _run_validator(DRY_RUN_EXAMPLE)
    assert code == 0
    assert report["status"] == "pass"
    assert report["normalized_intent"] == "prepare_publication_dry_run"
    assert report["execution_mode"] == "dry_run_planning"
    assert report["admission_status"] == "unadmitted"


def test_validator_blocks_unsupported_intent_with_allow_blocked(tmp_path: Path):
    payload = copy.deepcopy(_load(INSPECT_EXAMPLE))
    payload["normalized_intent"] = "unknown_or_unsupported"
    path = tmp_path / "unsupported.json"
    _write(path, payload)
    code, report = _run_validator(path, "--allow-blocked")
    assert code == 0
    assert report["status"] == "blocked"
    assert "unsupported_intent" in _finding_ids(report)


def test_validator_rejects_high_risk_action_in_allowed_actions(tmp_path: Path):
    payload = copy.deepcopy(_load(INSPECT_EXAMPLE))
    payload["allowed_actions"].append("publication")
    path = tmp_path / "publication-allowed.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "forbidden_actions_also_allowed" in _finding_ids(report)


def test_validator_rejects_unsafe_safety_claims(tmp_path: Path):
    payload = copy.deepcopy(_load(INSPECT_EXAMPLE))
    payload["safety"]["real_execution_allowed"] = True
    payload["safety"]["publication_allowed"] = True
    payload["safety"]["production_ready_claimed"] = True
    path = tmp_path / "unsafe-claims.json"
    _write(path, payload)
    code, report = _run_validator(path)
    assert code != 0
    assert "unsafe_safety_claims" in _finding_ids(report)


def test_compiler_turns_plain_english_into_valid_command(tmp_path: Path):
    output_path = tmp_path / "compiled.json"
    request = "Inspect the latest MAXINE actor products in O3DE"
    result = subprocess.run(
        [sys.executable, str(COMPILER), request, "--output", str(output_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = _load(output_path)
    assert payload["natural_language_request"] == request
    assert payload["normalized_intent"] == "inspect_actor_products"
    code, report = _run_validator(output_path)
    assert code == 0
    assert report["status"] == "pass"
