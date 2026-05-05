import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _proof_script() -> Path:
    return _repo_root() / "tools" / "release-lane" / "generate_execution_admission_receipt_dry_run.py"


def _decision_record() -> Path:
    return (
        _repo_root()
        / "examples"
        / "execution-admission"
        / "max_biped_v1_execution_admission_decision_approved.json"
    )


def _extract_payload(stdout: str) -> dict:
    start = stdout.find("{")
    assert start >= 0, f"stdout did not include JSON payload:\n{stdout}"
    return json.loads(stdout[start:])


@pytest.fixture()
def repo_tmp_dir() -> Path:
    base = _repo_root() / "examples" / "manifests" / "_pytest_execution_admission_receipt_dry_run"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_dry_run_receipt_proof_passes_and_writes_output(repo_tmp_dir: Path):
    output_path = repo_tmp_dir / "execution-admission-receipt-dry-run.json"
    cmd = [
        sys.executable,
        str(_proof_script()),
        "--decision-record",
        str(_decision_record()),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    payload = _extract_payload(result.stdout)
    assert payload["status"] == "pass"
    assert payload["report_type"] == "EXECUTION_ADMISSION_RECEIPT_DRY_RUN_v1_REPORT"
    assert payload["execution_mode"] == "no_op_dry_run"
    assert payload["execution_performed"] is False
    assert payload["dry_run_receipt"]["no_command_execution_recorded"] is True
    assert Path(payload["output_path"]).exists()
    assert output_path.exists()


def test_dry_run_receipt_proof_fails_without_approved_state(repo_tmp_dir: Path):
    bad_decision = json.loads(_decision_record().read_text(encoding="utf-8-sig"))
    bad_decision["decision_state"] = "pending_review"
    bad_decision["approval"]["approval_received"] = False
    bad_decision["approval"]["approval_phrase_received"] = ""

    decision_path = repo_tmp_dir / "decision-pending.json"
    decision_path.write_text(json.dumps(bad_decision, indent=2) + "\n", encoding="utf-8")
    output_path = repo_tmp_dir / "execution-admission-receipt-dry-run.json"
    cmd = [
        sys.executable,
        str(_proof_script()),
        "--decision-record",
        str(decision_path),
        "--output",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode != 0
    payload = _extract_payload(result.stdout)
    assert payload["status"] == "fail"
    assert payload["failures"]
