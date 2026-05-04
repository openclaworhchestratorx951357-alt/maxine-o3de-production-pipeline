import json
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRITER_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
ROLLBACK_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
AUTHORITATIVE_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
SANDBOX_ROOT = REPO_ROOT / "examples" / "sandbox"
STAGING_DIR = SANDBOX_ROOT / "staging"
LOGS_DIR = SANDBOX_ROOT / "logs"
REPORTS_DIR = SANDBOX_ROOT / "manifests" / "reports"


def run_powershell_script(script_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *args,
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def build_plan(target_path: str, explicit_approval: bool = True) -> dict:
    return {
        "schema_version": "1.0.0",
        "plan_id": f"pytest-sandbox-plan-{uuid.uuid4().hex}",
        "command_name": "Invoke-MaxineSandboxResolverWrite.ps1",
        "sandbox_scope": "sandbox_only",
        "sandbox_root": "examples/sandbox",
        "target_path": target_path,
        "approved_target_under_sandbox": True,
        "explicit_sandbox_approval": explicit_approval,
        "plan_signature": {
            "signed_by": "pytest-operator",
            "signature": "pytest-signed-plan",
        },
        "write_payload": {
            "proof_only": True,
            "origin": "pytest",
        },
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def test_valid_sandbox_write_succeeds_and_receipt_is_emitted(tmp_path: Path):
    target_name = f"pytest-sandbox-write-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-sandbox-write-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    plan_path = tmp_path / "valid-plan.json"

    write_json(plan_path, build_plan(target_rel, explicit_approval=True))
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)

    result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )

    assert result.returncode == 0, f"writer failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert target_abs.exists(), "sandbox file was not written"
    assert receipt_abs.exists(), "receipt was not written"

    receipt = read_json(receipt_abs)
    for required in [
        "command_name",
        "input_plan_path",
        "sandbox_root",
        "target_path",
        "write_attempted",
        "write_succeeded",
        "mutation_scope",
        "blocked_reason",
        "files_written",
        "sha256_before",
        "sha256_after",
        "rollback_receipt_hint",
        "timestamp_utc",
    ]:
        assert required in receipt, f"receipt missing required field '{required}'"

    assert receipt["write_succeeded"] is True
    assert receipt["mutation_scope"] == "sandbox_only"
    assert receipt["target_path"] == target_rel
    assert receipt["files_written"] == [target_rel]

    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)


def test_rollback_removes_only_the_written_sandbox_file(tmp_path: Path):
    written_name = f"pytest-sandbox-write-{uuid.uuid4().hex}.json"
    written_rel = f"examples/sandbox/staging/{written_name}"
    written_abs = REPO_ROOT / written_rel

    preserved_name = f"pytest-preserve-{uuid.uuid4().hex}.json"
    preserved_abs = STAGING_DIR / preserved_name

    receipt_name = f"pytest-sandbox-write-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    rollback_report_abs = REPORTS_DIR / f"{Path(receipt_name).stem}.rollback.json"
    plan_path = tmp_path / "rollback-plan.json"

    write_json(plan_path, build_plan(written_rel, explicit_approval=True))
    remove_if_exists(written_abs)
    remove_if_exists(preserved_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(rollback_report_abs)

    write_result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert write_result.returncode == 0, f"writer failed:\n{write_result.stdout}\n{write_result.stderr}"
    assert written_abs.exists()
    preserved_abs.write_text("keep-me", encoding="utf-8")

    rollback_result = run_powershell_script(
        ROLLBACK_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-ConfirmRollback",
    )
    assert rollback_result.returncode == 0, (
        "rollback failed:\n"
        f"STDOUT:\n{rollback_result.stdout}\nSTDERR:\n{rollback_result.stderr}"
    )
    assert not written_abs.exists(), "rollback did not remove written sandbox file"
    assert preserved_abs.exists(), "rollback removed a file not listed in the receipt"

    remove_if_exists(preserved_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(rollback_report_abs)


def run_blocked_write(tmp_path: Path, blocked_target: str, explicit_approval: bool = True):
    receipt_name = f"pytest-blocked-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    plan_path = tmp_path / f"blocked-{uuid.uuid4().hex}.json"
    write_json(plan_path, build_plan(blocked_target, explicit_approval=explicit_approval))
    remove_if_exists(receipt_abs)

    result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert result.returncode != 0, f"write unexpectedly succeeded for blocked target {blocked_target}"
    assert receipt_abs.exists(), "blocked write did not emit receipt"
    receipt = read_json(receipt_abs)
    assert receipt["write_succeeded"] is False
    assert receipt["blocked_reason"], "blocked write receipt must include blocked_reason"
    remove_if_exists(receipt_abs)
    return receipt


def test_production_path_is_blocked(tmp_path: Path):
    receipt = run_blocked_write(tmp_path, "Projects/MaxineShow/generated/prod.json")
    assert "blocked" in receipt["blocked_reason"].lower() or "forbidden" in receipt["blocked_reason"].lower()


def test_cache_path_is_blocked(tmp_path: Path):
    receipt = run_blocked_write(tmp_path, "examples/sandbox/staging/Cache/generated.json")
    assert "forbidden" in receipt["blocked_reason"].lower() or "blocked" in receipt["blocked_reason"].lower()


def test_engine_path_is_blocked(tmp_path: Path):
    receipt = run_blocked_write(tmp_path, "Engine/generated/engine-output.json")
    assert any(
        token in receipt["blocked_reason"].lower()
        for token in ("forbidden", "blocked", "escapes")
    )


def test_parent_traversal_is_blocked(tmp_path: Path):
    receipt = run_blocked_write(tmp_path, "examples/sandbox/staging/../outside.json")
    assert "traversal" in receipt["blocked_reason"].lower() or "blocked" in receipt["blocked_reason"].lower()


def test_missing_explicit_approval_is_blocked(tmp_path: Path):
    receipt = run_blocked_write(
        tmp_path,
        f"examples/sandbox/staging/no-approval-{uuid.uuid4().hex}.json",
        explicit_approval=False,
    )
    assert "explicit_sandbox_approval" in receipt["blocked_reason"]


def test_authoritative_resolver_write_remains_absent():
    assert not AUTHORITATIVE_SCRIPT.exists()


def test_o3de_ap_editor_execution_is_absent_from_new_scripts():
    writer_text = WRITER_SCRIPT.read_text(encoding="utf-8-sig").lower()
    rollback_text = ROLLBACK_SCRIPT.read_text(encoding="utf-8-sig").lower()
    combined = writer_text + "\n" + rollback_text
    for forbidden in [
        "o3de editor",
        "asset processor",
        "o3de.exe",
        "editor.exe",
        "assetprocessorbatch",
        "invoke-maxineauthoritativeresolverwrite.ps1",
    ]:
        assert forbidden not in combined


def test_sandbox_writer_safety_verifier_passes():
    verifier = REPO_ROOT / "tools" / "audit" / "verify_sandbox_writer_safety.py"
    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "sandbox writer safety verifier failed.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
