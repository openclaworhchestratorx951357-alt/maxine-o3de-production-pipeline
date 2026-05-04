import json
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRITER_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxResolverWrite.ps1"
ROLLBACK_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxRollback.ps1"
INSPECT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxReceiptInspect.ps1"
REVIEW_PACKET_BUILD_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxReviewPacketBuild.ps1"
)
REVIEW_PACKET_INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxReviewPacketInspect.ps1"
)
REVIEW_DECISION_RECORD_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxReviewDecisionRecord.ps1"
)
REVIEW_DECISION_INSPECT_SCRIPT = (
    REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxReviewDecisionInspect.ps1"
)
AUTHORITATIVE_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"
SANDBOX_ROOT = REPO_ROOT / "examples" / "sandbox"
STAGING_DIR = SANDBOX_ROOT / "staging"
LOGS_DIR = SANDBOX_ROOT / "logs"
RECEIPTS_DIR = SANDBOX_ROOT / "receipts"
REVIEW_PACKETS_DIR = SANDBOX_ROOT / "review-packets"
REVIEW_DECISIONS_DIR = SANDBOX_ROOT / "review-decisions"
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


def build_plan(target_path: str, receipt_index_path: str, explicit_approval: bool = True) -> dict:
    return {
        "schema_version": "1.0.0",
        "plan_id": f"pytest-sandbox-plan-{uuid.uuid4().hex}",
        "command_name": "Invoke-MaxineSandboxResolverWrite.ps1",
        "sandbox_scope": "sandbox_only",
        "sandbox_root": "examples/sandbox",
        "receipt_index_path": receipt_index_path,
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


def assert_index_entry(index_path: Path, receipt_id: str, expected_status: str) -> dict:
    assert index_path.exists(), f"index missing: {index_path}"
    index = read_json(index_path)
    entries = [entry for entry in index.get("receipts", []) if entry.get("receipt_id") == receipt_id]
    assert entries, f"receipt_id {receipt_id} not found in index"
    entry = entries[0]
    assert entry["status"] == expected_status
    return entry


def test_valid_sandbox_write_succeeds_and_receipt_is_emitted_and_index_updated(tmp_path: Path):
    target_name = f"pytest-sandbox-write-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-sandbox-write-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-receipt-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    plan_path = tmp_path / "valid-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)

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
        "receipt_id",
        "command_name",
        "input_plan_path",
        "sandbox_root",
        "target_path",
        "write_attempted",
        "write_succeeded",
        "mutation_scope",
        "blocked_reason",
        "status",
        "rollback_status",
        "files_written",
        "sha256_before",
        "sha256_after",
        "rollback_receipt_hint",
        "receipt_path",
        "receipt_index_path",
        "timestamp_utc",
    ]:
        assert required in receipt, f"receipt missing required field '{required}'"

    assert receipt["write_succeeded"] is True
    assert receipt["status"] == "written"
    assert receipt["rollback_status"] == "not_requested"
    assert receipt["mutation_scope"] == "sandbox_only"
    assert receipt["target_path"] == target_rel
    assert receipt["files_written"] == [target_rel]
    assert receipt["receipt_index_path"] == index_rel

    index_entry = assert_index_entry(index_abs, receipt["receipt_id"], "written")
    assert index_entry["rollback_status"] == "not_requested"

    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)


def test_rollback_removes_only_the_written_sandbox_file_and_preserves_receipt_history(tmp_path: Path):
    written_name = f"pytest-sandbox-write-{uuid.uuid4().hex}.json"
    written_rel = f"examples/sandbox/staging/{written_name}"
    written_abs = REPO_ROOT / written_rel

    preserved_name = f"pytest-preserve-{uuid.uuid4().hex}.json"
    preserved_abs = STAGING_DIR / preserved_name

    receipt_name = f"pytest-sandbox-write-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    rollback_report_abs = REPORTS_DIR / f"{Path(receipt_name).stem}.rollback.json"
    index_name = f"pytest-receipt-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    plan_path = tmp_path / "rollback-plan.json"

    write_json(plan_path, build_plan(written_rel, receipt_index_path=index_rel, explicit_approval=True))
    remove_if_exists(written_abs)
    remove_if_exists(preserved_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(rollback_report_abs)
    remove_if_exists(index_abs)

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

    receipt_before = read_json(receipt_abs)
    entry_before = assert_index_entry(index_abs, receipt_before["receipt_id"], "written")
    assert entry_before["rollback_status"] == "not_requested"

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

    receipt_after = read_json(receipt_abs)
    assert receipt_after["status"] == "rolled_back"
    assert receipt_after["rollback_status"] == "rolled_back"

    entry_after = assert_index_entry(index_abs, receipt_after["receipt_id"], "rolled_back")
    assert entry_after["rollback_status"] == "rolled_back"

    remove_if_exists(preserved_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(rollback_report_abs)
    remove_if_exists(index_abs)


def run_blocked_write(tmp_path: Path, blocked_target: str, *, explicit_approval: bool = True, index_rel: str | None = None):
    receipt_name = f"pytest-blocked-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    if not index_rel:
        index_rel = f"examples/sandbox/receipts/pytest-blocked-index-{uuid.uuid4().hex}.json"
    index_abs = REPO_ROOT / index_rel

    plan_path = tmp_path / f"blocked-{uuid.uuid4().hex}.json"
    write_json(plan_path, build_plan(blocked_target, receipt_index_path=index_rel, explicit_approval=explicit_approval))
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)

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
    assert receipt["status"] == "blocked"
    assert receipt["blocked_reason"], "blocked write receipt must include blocked_reason"

    index_entry = assert_index_entry(index_abs, receipt["receipt_id"], "blocked")
    assert index_entry["rollback_status"] == "not_requested"

    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)
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


def test_receipt_index_cannot_point_outside_sandbox_root(tmp_path: Path):
    receipt_name = f"pytest-blocked-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    plan_path = tmp_path / "blocked-index-plan.json"
    target_rel = f"examples/sandbox/staging/index-test-{uuid.uuid4().hex}.json"
    default_index_abs = RECEIPTS_DIR / "index.json"
    before_default_index = default_index_abs.read_bytes()

    plan = build_plan(target_rel, receipt_index_path="../outside/index.json", explicit_approval=True)
    write_json(plan_path, plan)
    remove_if_exists(receipt_abs)

    result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert result.returncode != 0
    assert receipt_abs.exists()
    receipt = read_json(receipt_abs)
    assert "receipt_index_path" in receipt["blocked_reason"].lower() or "sandbox root" in receipt["blocked_reason"].lower()
    assert receipt["receipt_index_path"] in (None, "")
    assert default_index_abs.read_bytes() == before_default_index

    remove_if_exists(receipt_abs)


def test_receipt_inspect_is_read_only_and_can_lookup_receipt(tmp_path: Path):
    target_name = f"pytest-inspect-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-inspect-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-inspect-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    plan_path = tmp_path / "inspect-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)

    write_result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert write_result.returncode == 0

    receipt = read_json(receipt_abs)
    before = index_abs.read_bytes()

    inspect_list = run_powershell_script(
        INSPECT_SCRIPT,
        "-List",
        "-IndexPath",
        index_rel,
    )
    assert inspect_list.returncode == 0, inspect_list.stderr
    list_payload = json.loads(inspect_list.stdout)
    assert list_payload["receipt_count"] >= 1

    inspect_one = run_powershell_script(
        INSPECT_SCRIPT,
        "-ReceiptId",
        receipt["receipt_id"],
        "-IndexPath",
        index_rel,
    )
    assert inspect_one.returncode == 0, inspect_one.stderr
    one_payload = json.loads(inspect_one.stdout)
    assert one_payload["status"] in {"written", "rolled_back", "blocked", "failed"}
    assert one_payload["files_written"] == [target_rel]

    after = index_abs.read_bytes()
    assert before == after, "inspect command changed the receipt index; it must be read-only"

    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)


def test_review_packet_can_be_built_from_existing_sandbox_receipt_without_mutating_source(tmp_path: Path):
    target_name = f"pytest-review-build-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-review-build-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-review-build-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    packet_name = f"pytest-review-packet-{uuid.uuid4().hex}.json"
    packet_rel = f"examples/sandbox/review-packets/{packet_name}"
    packet_abs = REPO_ROOT / packet_rel
    plan_path = tmp_path / "review-build-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)
    remove_if_exists(packet_abs)

    write_result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert write_result.returncode == 0, write_result.stderr
    assert receipt_abs.exists()
    assert index_abs.exists()

    receipt_before = receipt_abs.read_bytes()
    index_before = index_abs.read_bytes()
    source_receipt = read_json(receipt_abs)

    build_result = run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-OutputPath",
        packet_rel,
        "-OperatorDecisionState",
        "pending_review",
    )
    assert build_result.returncode == 0, build_result.stderr
    assert packet_abs.exists()

    packet = read_json(packet_abs)
    for required in [
        "review_packet_id",
        "source_receipt_id",
        "sandbox_root",
        "target_path",
        "files_written",
        "write_status",
        "rollback_status",
        "sha256_before",
        "sha256_after",
        "blocked_reason",
        "safety_summary",
        "operator_decision_state",
        "next_safest_step",
        "explicit_blocked_capabilities",
    ]:
        assert required in packet, f"review packet missing '{required}'"

    assert packet["source_receipt_id"] == source_receipt["receipt_id"]
    assert packet["sandbox_root"] == "examples/sandbox"
    assert packet["operator_decision_state"] == "pending_review"
    assert "authoritative_writes" in packet["explicit_blocked_capabilities"]
    assert "asset_processor_execution" in packet["explicit_blocked_capabilities"]

    receipt_after = receipt_abs.read_bytes()
    index_after = index_abs.read_bytes()
    assert receipt_before == receipt_after, "review packet build mutated source receipt"
    assert index_before == index_after, "review packet build mutated source index"

    remove_if_exists(packet_abs)
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)


def test_review_packet_cannot_be_built_from_receipt_outside_sandbox_root(tmp_path: Path):
    outside_receipt = tmp_path / "outside-receipt.json"
    write_json(
        outside_receipt,
        {
            "receipt_id": f"outside-{uuid.uuid4().hex}",
            "command_name": "Invoke-MaxineSandboxResolverWrite.ps1",
            "sandbox_root": "examples/sandbox",
            "target_path": "examples/sandbox/staging/outside.json",
            "files_written": ["examples/sandbox/staging/outside.json"],
            "status": "written",
            "rollback_status": "not_requested",
        },
    )

    result = run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        str(outside_receipt),
    )
    assert result.returncode != 0
    assert "sandbox root" in (result.stderr + result.stdout).lower()


def test_review_packet_forbidden_operator_decisions_are_rejected(tmp_path: Path):
    target_name = f"pytest-review-forbidden-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-review-forbidden-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-review-forbidden-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    packet_name = f"pytest-review-forbidden-packet-{uuid.uuid4().hex}.json"
    packet_rel = f"examples/sandbox/review-packets/{packet_name}"
    packet_abs = REPO_ROOT / packet_rel
    plan_path = tmp_path / "review-forbidden-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)
    remove_if_exists(packet_abs)

    write_result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert write_result.returncode == 0, write_result.stderr

    forbidden = run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-OutputPath",
        packet_rel,
        "-OperatorDecisionState",
        "approve_authoritative_write",
    )
    assert forbidden.returncode != 0
    assert not packet_abs.exists()
    assert "forbidden" in (forbidden.stderr + forbidden.stdout).lower()

    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)


def test_review_packet_inspect_is_read_only(tmp_path: Path):
    target_name = f"pytest-review-inspect-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-review-inspect-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-review-inspect-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    packet_name = f"pytest-review-inspect-packet-{uuid.uuid4().hex}.json"
    packet_rel = f"examples/sandbox/review-packets/{packet_name}"
    packet_abs = REPO_ROOT / packet_rel
    plan_path = tmp_path / "review-inspect-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)
    remove_if_exists(packet_abs)

    write_result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert write_result.returncode == 0

    build_result = run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-OutputPath",
        packet_rel,
    )
    assert build_result.returncode == 0

    packet = read_json(packet_abs)
    before = packet_abs.read_bytes()

    inspect_list = run_powershell_script(
        REVIEW_PACKET_INSPECT_SCRIPT,
        "-List",
    )
    assert inspect_list.returncode == 0
    list_payload = json.loads(inspect_list.stdout)
    assert list_payload["packet_count"] >= 1

    inspect_one = run_powershell_script(
        REVIEW_PACKET_INSPECT_SCRIPT,
        "-ReviewPacketId",
        packet["review_packet_id"],
    )
    assert inspect_one.returncode == 0
    one_payload = json.loads(inspect_one.stdout)
    assert one_payload["review_packet_id"] == packet["review_packet_id"]

    after = packet_abs.read_bytes()
    assert before == after, "review packet inspect mutated packet content"

    remove_if_exists(packet_abs)
    remove_if_exists(target_abs)
    remove_if_exists(receipt_abs)
    remove_if_exists(index_abs)


def test_review_decision_record_can_be_created_and_preserves_source_ids(tmp_path: Path):
    target_name = f"pytest-decision-write-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-decision-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-decision-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    packet_name = f"pytest-decision-packet-{uuid.uuid4().hex}.json"
    packet_rel = f"examples/sandbox/review-packets/{packet_name}"
    packet_abs = REPO_ROOT / packet_rel
    decision_name = f"pytest-decision-{uuid.uuid4().hex}.json"
    decision_rel = f"examples/sandbox/review-decisions/{decision_name}"
    decision_abs = REPO_ROOT / decision_rel
    plan_path = tmp_path / "decision-build-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    for path in (target_abs, receipt_abs, index_abs, packet_abs, decision_abs):
        remove_if_exists(path)

    write_result = run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    )
    assert write_result.returncode == 0, write_result.stderr

    packet_result = run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-OutputPath",
        packet_rel,
        "-OperatorDecisionState",
        "pending_review",
    )
    assert packet_result.returncode == 0, packet_result.stderr

    decision_result = run_powershell_script(
        REVIEW_DECISION_RECORD_SCRIPT,
        "-ReviewPacketPath",
        packet_rel,
        "-DecisionState",
        "accepted_for_sandbox_only",
        "-OperatorId",
        "pytest-operator",
        "-DecisionReason",
        "sandbox-safe evidence verified",
        "-OutputPath",
        decision_rel,
    )
    assert decision_result.returncode == 0, decision_result.stderr
    assert decision_abs.exists()

    packet = read_json(packet_abs)
    decision = read_json(decision_abs)
    assert decision["source_review_packet_id"] == packet["review_packet_id"]
    assert decision["source_receipt_id"] == packet["source_receipt_id"]
    assert decision["decision_state"] == "accepted_for_sandbox_only"
    assert decision["sandbox_root"] == "examples/sandbox"
    assert decision["rollback_execution_admitted"] is False
    assert "authoritative_writes" in decision["explicit_non_admissions"]

    for path in (target_abs, receipt_abs, index_abs, packet_abs, decision_abs):
        remove_if_exists(path)


def test_review_decision_forbidden_states_are_rejected(tmp_path: Path):
    target_name = f"pytest-decision-forbidden-write-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-decision-forbidden-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-decision-forbidden-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    packet_name = f"pytest-decision-forbidden-packet-{uuid.uuid4().hex}.json"
    packet_rel = f"examples/sandbox/review-packets/{packet_name}"
    packet_abs = REPO_ROOT / packet_rel
    decision_name = f"pytest-decision-forbidden-{uuid.uuid4().hex}.json"
    decision_rel = f"examples/sandbox/review-decisions/{decision_name}"
    decision_abs = REPO_ROOT / decision_rel
    plan_path = tmp_path / "decision-forbidden-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    for path in (target_abs, receipt_abs, index_abs, packet_abs, decision_abs):
        remove_if_exists(path)

    assert run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    ).returncode == 0

    assert run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-OutputPath",
        packet_rel,
        "-OperatorDecisionState",
        "pending_review",
    ).returncode == 0

    forbidden = run_powershell_script(
        REVIEW_DECISION_RECORD_SCRIPT,
        "-ReviewPacketPath",
        packet_rel,
        "-DecisionState",
        "approve_authoritative_write",
        "-OperatorId",
        "pytest-operator",
        "-DecisionReason",
        "forbidden state test",
        "-OutputPath",
        decision_rel,
    )
    assert forbidden.returncode != 0
    assert not decision_abs.exists()

    for path in (target_abs, receipt_abs, index_abs, packet_abs):
        remove_if_exists(path)


def test_review_decision_cannot_reference_packet_outside_sandbox(tmp_path: Path):
    outside_packet = tmp_path / "outside-review-packet.json"
    write_json(
        outside_packet,
        {
            "schema_version": "1.0.0",
            "review_packet_id": f"outside-review-packet-{uuid.uuid4().hex}",
            "source_receipt_id": f"outside-receipt-{uuid.uuid4().hex}",
            "sandbox_root": "examples/sandbox",
        },
    )

    decision_result = run_powershell_script(
        REVIEW_DECISION_RECORD_SCRIPT,
        "-ReviewPacketPath",
        str(outside_packet),
        "-DecisionState",
        "accepted_for_sandbox_only",
        "-OperatorId",
        "pytest-operator",
        "-DecisionReason",
        "outside packet must be blocked",
    )
    assert decision_result.returncode != 0
    combined = (decision_result.stdout + decision_result.stderr).lower()
    assert "sandbox root" in combined or "review packets root" in combined


def test_review_decision_inspect_is_read_only(tmp_path: Path):
    target_name = f"pytest-decision-inspect-write-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-decision-inspect-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-decision-inspect-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    packet_name = f"pytest-decision-inspect-packet-{uuid.uuid4().hex}.json"
    packet_rel = f"examples/sandbox/review-packets/{packet_name}"
    packet_abs = REPO_ROOT / packet_rel
    decision_name = f"pytest-decision-inspect-{uuid.uuid4().hex}.json"
    decision_rel = f"examples/sandbox/review-decisions/{decision_name}"
    decision_abs = REPO_ROOT / decision_rel
    plan_path = tmp_path / "decision-inspect-plan.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    for path in (target_abs, receipt_abs, index_abs, packet_abs, decision_abs):
        remove_if_exists(path)

    assert run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    ).returncode == 0
    assert run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-OutputPath",
        packet_rel,
        "-OperatorDecisionState",
        "pending_review",
    ).returncode == 0
    assert run_powershell_script(
        REVIEW_DECISION_RECORD_SCRIPT,
        "-ReviewPacketPath",
        packet_rel,
        "-DecisionState",
        "needs_more_evidence",
        "-OperatorId",
        "pytest-operator",
        "-DecisionReason",
        "need more evidence",
        "-OutputPath",
        decision_rel,
    ).returncode == 0

    decision = read_json(decision_abs)
    before = decision_abs.read_bytes()

    inspect_list = run_powershell_script(
        REVIEW_DECISION_INSPECT_SCRIPT,
        "-List",
    )
    assert inspect_list.returncode == 0
    list_payload = json.loads(inspect_list.stdout)
    assert list_payload["decision_count"] >= 1

    inspect_one = run_powershell_script(
        REVIEW_DECISION_INSPECT_SCRIPT,
        "-DecisionId",
        decision["decision_id"],
    )
    assert inspect_one.returncode == 0
    one_payload = json.loads(inspect_one.stdout)
    assert one_payload["decision_id"] == decision["decision_id"]

    after = decision_abs.read_bytes()
    assert before == after, "review decision inspect mutated decision content"

    for path in (target_abs, receipt_abs, index_abs, packet_abs, decision_abs):
        remove_if_exists(path)


def test_review_decision_request_rollback_records_intent_only_and_does_not_execute(tmp_path: Path):
    target_name = f"pytest-decision-rollback-write-{uuid.uuid4().hex}.json"
    target_rel = f"examples/sandbox/staging/{target_name}"
    target_abs = REPO_ROOT / target_rel
    receipt_name = f"pytest-decision-rollback-receipt-{uuid.uuid4().hex}.json"
    receipt_rel = f"examples/sandbox/logs/{receipt_name}"
    receipt_abs = REPO_ROOT / receipt_rel
    index_name = f"pytest-decision-rollback-index-{uuid.uuid4().hex}.json"
    index_rel = f"examples/sandbox/receipts/{index_name}"
    index_abs = REPO_ROOT / index_rel
    packet_name = f"pytest-decision-rollback-packet-{uuid.uuid4().hex}.json"
    packet_rel = f"examples/sandbox/review-packets/{packet_name}"
    packet_abs = REPO_ROOT / packet_rel
    decision_name = f"pytest-decision-rollback-{uuid.uuid4().hex}.json"
    decision_rel = f"examples/sandbox/review-decisions/{decision_name}"
    decision_abs = REPO_ROOT / decision_rel
    plan_path = tmp_path / "decision-rollback-plan.json"
    rollback_report_abs = REPORTS_DIR / f"{Path(receipt_name).stem}.rollback.json"

    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))
    for path in (target_abs, receipt_abs, index_abs, packet_abs, decision_abs, rollback_report_abs):
        remove_if_exists(path)

    assert run_powershell_script(
        WRITER_SCRIPT,
        "-PlanPath",
        str(plan_path),
        "-ReceiptPath",
        receipt_rel,
    ).returncode == 0
    assert run_powershell_script(
        REVIEW_PACKET_BUILD_SCRIPT,
        "-ReceiptPath",
        receipt_rel,
        "-OutputPath",
        packet_rel,
    ).returncode == 0

    decision_result = run_powershell_script(
        REVIEW_DECISION_RECORD_SCRIPT,
        "-ReviewPacketPath",
        packet_rel,
        "-DecisionState",
        "request_rollback",
        "-OperatorId",
        "pytest-operator",
        "-DecisionReason",
        "rollback requested by reviewer",
        "-OutputPath",
        decision_rel,
    )
    assert decision_result.returncode == 0

    decision = read_json(decision_abs)
    assert decision["decision_state"] == "request_rollback"
    assert decision["requested_next_action"] == "rollback_requested"
    assert decision["rollback_execution_admitted"] is False
    assert target_abs.exists(), "decision recording must not auto-execute rollback"
    assert not rollback_report_abs.exists(), "decision recording unexpectedly executed rollback"

    for path in (target_abs, receipt_abs, index_abs, packet_abs, decision_abs, rollback_report_abs):
        remove_if_exists(path)


def test_authoritative_resolver_write_remains_absent():
    assert not AUTHORITATIVE_SCRIPT.exists()


def test_o3de_ap_editor_execution_is_absent_from_new_scripts():
    writer_text = WRITER_SCRIPT.read_text(encoding="utf-8-sig").lower()
    rollback_text = ROLLBACK_SCRIPT.read_text(encoding="utf-8-sig").lower()
    inspect_text = INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
    review_build_text = REVIEW_PACKET_BUILD_SCRIPT.read_text(encoding="utf-8-sig").lower()
    review_inspect_text = REVIEW_PACKET_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
    review_decision_record_text = REVIEW_DECISION_RECORD_SCRIPT.read_text(encoding="utf-8-sig").lower()
    review_decision_inspect_text = REVIEW_DECISION_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
    combined = (
        writer_text
        + "\n"
        + rollback_text
        + "\n"
        + inspect_text
        + "\n"
        + review_build_text
        + "\n"
        + review_inspect_text
        + "\n"
        + review_decision_record_text
        + "\n"
        + review_decision_inspect_text
    )
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
