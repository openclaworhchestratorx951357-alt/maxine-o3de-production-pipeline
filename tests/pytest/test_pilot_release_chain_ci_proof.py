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
    return _repo_root() / "tools" / "release-lane" / "prove_pilot_release_chain.py"


@pytest.fixture()
def repo_tmp_dir() -> Path:
    base = _repo_root() / "examples" / "manifests" / "_pytest_pilot_chain_proof"
    run_dir = base / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield run_dir
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_pilot_chain_proof_command_passes_expected_warn_baseline(repo_tmp_dir: Path):
    cmd = [
        sys.executable,
        str(_proof_script()),
        "--output-root",
        str(repo_tmp_dir / "proof-output"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_repo_root()))
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"

    start = result.stdout.find("{")
    assert start >= 0, f"proof output did not include JSON payload:\n{result.stdout}"
    payload = json.loads(result.stdout[start:])
    assert payload["status"] == "pass"
    assert payload["check_id"] == "pilot_release_chain_ci_proof_v1"
    assert payload["details"]["normal_run"]["pilot_chain_status"] == "warn"
    assert payload["details"]["strict_run"]["pilot_chain_status"] == "warn"
    assert payload["details"]["normal_run"]["runner_return_code"] == 0
    assert payload["details"]["strict_run"]["runner_return_code"] != 0
