import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_RUN_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxWorkflowRun.ps1"
WORKFLOW_INSPECT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxWorkflowInspect.ps1"
EVIDENCE_EXPORT_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxEvidenceBundleExport.ps1"
OPERATOR_SUMMARY_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineSandboxOperatorSummary.ps1"
AUTHORITATIVE_SCRIPT = REPO_ROOT / "scripts" / "powershell" / "Invoke-MaxineAuthoritativeResolverWrite.ps1"

SANDBOX_ROOT = REPO_ROOT / "examples" / "sandbox"
STAGING_DIR = SANDBOX_ROOT / "staging"
LOGS_DIR = SANDBOX_ROOT / "logs"
RECEIPTS_DIR = SANDBOX_ROOT / "receipts"
REVIEW_PACKETS_DIR = SANDBOX_ROOT / "review-packets"
REVIEW_DECISIONS_DIR = SANDBOX_ROOT / "review-decisions"
WORKFLOW_RUNS_DIR = SANDBOX_ROOT / "workflow-runs"
EVIDENCE_BUNDLES_DIR = SANDBOX_ROOT / "evidence-bundles"
OPERATOR_REPORTS_DIR = SANDBOX_ROOT / "operator-reports"


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


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def remove_if_exists(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


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


def create_workflow_chain(tmp_path: Path, mode: str = "WriteReviewAndDecision") -> dict:
    suffix = uuid.uuid4().hex
    target_rel = f"examples/sandbox/staging/pytest-operator-pack-target-{suffix}.json"
    target_abs = REPO_ROOT / target_rel
    index_rel = f"examples/sandbox/receipts/pytest-operator-pack-index-{suffix}.json"
    index_abs = REPO_ROOT / index_rel
    receipt_rel = f"examples/sandbox/logs/pytest-operator-pack-receipt-{suffix}.json"
    receipt_abs = REPO_ROOT / receipt_rel
    packet_rel = f"examples/sandbox/review-packets/pytest-operator-pack-packet-{suffix}.json"
    packet_abs = REPO_ROOT / packet_rel
    decision_rel = f"examples/sandbox/review-decisions/pytest-operator-pack-decision-{suffix}.json"
    decision_abs = REPO_ROOT / decision_rel
    run_rel = f"examples/sandbox/workflow-runs/pytest-operator-pack-run-{suffix}.json"
    run_abs = REPO_ROOT / run_rel

    plan_path = tmp_path / f"operator-pack-plan-{suffix}.json"
    write_json(plan_path, build_plan(target_rel, receipt_index_path=index_rel, explicit_approval=True))

    cleanup_paths = [
        target_abs,
        index_abs,
        receipt_abs,
        packet_abs,
        decision_abs,
        run_abs,
    ]
    for path in cleanup_paths:
        remove_if_exists(path)

    args = [
        "-PlanPath",
        str(plan_path),
        "-WorkflowMode",
        mode,
        "-ReceiptPath",
        receipt_rel,
        "-WorkflowRunPath",
        run_rel,
    ]

    if mode in {"WriteAndReview", "WriteReviewAndDecision", "RollbackRequestedOnly"}:
        args.extend(["-ReviewPacketPath", packet_rel])

    if mode in {"WriteReviewAndDecision", "RollbackRequestedOnly"}:
        args.extend(
            [
                "-DecisionPath",
                decision_rel,
                "-OperatorId",
                "pytest-operator",
                "-DecisionReason",
                "pytest decision reason",
            ]
        )

    if mode == "WriteReviewAndDecision":
        args.extend(["-DecisionState", "accepted_for_sandbox_only"])

    result = run_powershell_script(WORKFLOW_RUN_SCRIPT, *args)
    assert result.returncode == 0, (
        "workflow creation failed\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    assert run_abs.exists(), "workflow run file missing"
    assert receipt_abs.exists(), "receipt missing"
    if mode in {"WriteAndReview", "WriteReviewAndDecision", "RollbackRequestedOnly"}:
        assert packet_abs.exists(), "review packet missing"
    if mode in {"WriteReviewAndDecision", "RollbackRequestedOnly"}:
        assert decision_abs.exists(), "decision missing"

    return {
        "target_rel": target_rel,
        "target_abs": target_abs,
        "index_rel": index_rel,
        "index_abs": index_abs,
        "receipt_rel": receipt_rel,
        "receipt_abs": receipt_abs,
        "packet_rel": packet_rel,
        "packet_abs": packet_abs,
        "decision_rel": decision_rel,
        "decision_abs": decision_abs,
        "run_rel": run_rel,
        "run_abs": run_abs,
        "cleanup_paths": cleanup_paths,
    }


def test_evidence_bundle_export_succeeds_for_workflow_run_and_is_sandbox_local(tmp_path: Path):
    chain = create_workflow_chain(tmp_path, mode="WriteReviewAndDecision")
    bundle_rel = f"examples/sandbox/evidence-bundles/pytest-bundle-{uuid.uuid4().hex}/bundle.manifest.json"
    bundle_abs = REPO_ROOT / bundle_rel
    bundle_dir = bundle_abs.parent
    remove_if_exists(bundle_dir)

    result = run_powershell_script(
        EVIDENCE_EXPORT_SCRIPT,
        "-WorkflowRunPath",
        chain["run_rel"],
        "-BundlePath",
        bundle_rel,
    )
    assert result.returncode == 0, result.stderr
    assert bundle_abs.exists()

    workflow = read_json(chain["run_abs"])
    receipt = read_json(chain["receipt_abs"])
    packet = read_json(chain["packet_abs"])
    decision = read_json(chain["decision_abs"])
    bundle = read_json(bundle_abs)

    assert bundle["schema_version"] == "1.0.0"
    assert bundle["source_workflow_run_id"] == workflow["workflow_run_id"]
    assert bundle["source_receipt_id"] == receipt["receipt_id"]
    assert bundle["source_review_packet_id"] == packet["review_packet_id"]
    assert bundle["source_decision_id"] == decision["decision_id"]
    assert bundle["bundle_path"].startswith("examples/sandbox/evidence-bundles/")

    assert bundle["included_artifacts"]
    assert bundle["copied_artifact_paths"]
    for rel in bundle["copied_artifact_paths"]:
        assert rel.startswith("examples/sandbox/evidence-bundles/")
        assert rel.endswith(".json")
        assert (REPO_ROOT / rel).exists()

    assert "source_plan_metadata" in bundle["included_artifacts"]
    assert "safety_summary" in bundle

    remove_if_exists(bundle_dir)
    for path in chain["cleanup_paths"]:
        remove_if_exists(path)


def test_evidence_bundle_does_not_mutate_source_records(tmp_path: Path):
    chain = create_workflow_chain(tmp_path, mode="WriteReviewAndDecision")
    bundle_rel = f"examples/sandbox/evidence-bundles/pytest-bundle-mut-{uuid.uuid4().hex}/bundle.manifest.json"
    bundle_abs = REPO_ROOT / bundle_rel
    bundle_dir = bundle_abs.parent
    remove_if_exists(bundle_dir)

    source_paths = [chain["run_abs"], chain["receipt_abs"], chain["packet_abs"], chain["decision_abs"]]
    before = {str(path): path.read_bytes() for path in source_paths}

    result = run_powershell_script(
        EVIDENCE_EXPORT_SCRIPT,
        "-WorkflowRunPath",
        chain["run_rel"],
        "-BundlePath",
        bundle_rel,
    )
    assert result.returncode == 0

    after = {str(path): path.read_bytes() for path in source_paths}
    assert before == after, "evidence bundle export mutated source records"

    remove_if_exists(bundle_dir)
    for path in chain["cleanup_paths"]:
        remove_if_exists(path)


def test_evidence_bundle_rejects_workflow_path_outside_sandbox_root(tmp_path: Path):
    outside_workflow = tmp_path / "outside-workflow.json"
    write_json(
        outside_workflow,
        {
            "schema_version": "1.0.0",
            "workflow_run_id": "outside",
            "workflow_mode": "WriteOnly",
            "sandbox_root": "examples/sandbox",
        },
    )

    result = run_powershell_script(
        EVIDENCE_EXPORT_SCRIPT,
        "-WorkflowRunPath",
        str(outside_workflow),
    )
    assert result.returncode != 0
    assert "sandbox root" in (result.stdout + result.stderr).lower()


def test_operator_summary_is_read_only_by_default_and_reports_status_counts(tmp_path: Path):
    chain = create_workflow_chain(tmp_path, mode="WriteOnly")

    run_before = chain["run_abs"].read_bytes()
    reports_before = sorted(p.name for p in OPERATOR_REPORTS_DIR.glob("*.json"))

    result = run_powershell_script(OPERATOR_SUMMARY_SCRIPT)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)

    assert summary["total_workflow_runs"] >= 1
    assert isinstance(summary["workflow_status_counts"], dict)
    assert "completed" in summary["workflow_status_counts"] or "blocked" in summary["workflow_status_counts"]
    assert isinstance(summary["decision_counts"], dict)

    run_after = chain["run_abs"].read_bytes()
    reports_after = sorted(p.name for p in OPERATOR_REPORTS_DIR.glob("*.json"))
    assert run_before == run_after, "summary command mutated workflow run evidence"
    assert reports_before == reports_after, "summary command wrote reports without -WriteReport"

    for path in chain["cleanup_paths"]:
        remove_if_exists(path)


def test_operator_summary_counts_rollback_requested_decisions(tmp_path: Path):
    accepted_chain = create_workflow_chain(tmp_path, mode="WriteReviewAndDecision")
    rollback_chain = create_workflow_chain(tmp_path, mode="RollbackRequestedOnly")

    result = run_powershell_script(OPERATOR_SUMMARY_SCRIPT)
    assert result.returncode == 0
    summary = json.loads(result.stdout)

    assert summary["rollback_requested_decisions"] >= 1
    assert summary["accepted_for_sandbox_only_decisions"] >= 1
    assert isinstance(summary["latest_workflow_runs"], list)

    for path in accepted_chain["cleanup_paths"] + rollback_chain["cleanup_paths"]:
        remove_if_exists(path)


def test_operator_summary_write_report_is_sandbox_local_only(tmp_path: Path):
    report_rel = f"examples/sandbox/operator-reports/pytest-operator-summary-{uuid.uuid4().hex}.json"
    report_abs = REPO_ROOT / report_rel
    remove_if_exists(report_abs)

    result = run_powershell_script(
        OPERATOR_SUMMARY_SCRIPT,
        "-WriteReport",
        "-ReportPath",
        report_rel,
    )
    assert result.returncode == 0, result.stderr
    assert report_abs.exists()

    summary = json.loads(result.stdout)
    assert summary.get("report_path") == report_rel

    remove_if_exists(report_abs)


def test_operator_summary_blocks_report_paths_outside_sandbox_root(tmp_path: Path):
    result = run_powershell_script(
        OPERATOR_SUMMARY_SCRIPT,
        "-WriteReport",
        "-ReportPath",
        "../outside/operator-summary.json",
    )
    assert result.returncode != 0
    assert "sandbox root" in (result.stdout + result.stderr).lower() or "blocked" in (
        result.stdout + result.stderr
    ).lower()


def test_capability_matrix_states_are_explicit_and_narrow():
    matrix_path = REPO_ROOT / "examples" / "capabilities" / "maxine-capability-matrix.json"
    matrix = read_json(matrix_path)
    caps = matrix["capabilities"]

    assert caps["sandbox_resolver_write"] == "sandbox_only"
    assert caps["sandbox_rollback"] == "sandbox_only"
    assert caps["sandbox_receipt_inspect"] == "read_only"
    assert caps["sandbox_review_packet_build"] == "sandbox_only"
    assert caps["sandbox_review_packet_inspect"] == "read_only"
    assert caps["sandbox_review_decision_record"] == "sandbox_only"
    assert caps["sandbox_review_decision_inspect"] == "read_only"
    assert caps["sandbox_workflow_run"] == "sandbox_only"
    assert caps["sandbox_workflow_inspect"] == "read_only"
    assert caps["sandbox_evidence_bundle_export"] == "sandbox_only"
    assert caps["sandbox_operator_summary"] == "read_only"

    assert caps["authoritative_resolver_write"] == "forbidden"
    assert caps["o3de_editor_execution"] == "blocked"
    assert caps["asset_processor_execution"] == "blocked"
    assert caps["o3de_cli_execution"] == "blocked"
    assert caps["product_resolution"] == "blocked"
    assert caps["asset_id_claims"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"
    assert caps["production_path_write"] == "forbidden"
    assert caps["cache_path_write"] == "forbidden"
    assert caps["engine_path_write"] == "forbidden"


def test_authoritative_writer_absent_and_new_commands_do_not_admit_o3de_ap_editor_execution():
    assert not AUTHORITATIVE_SCRIPT.exists()

    combined = (
        EVIDENCE_EXPORT_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + OPERATOR_SUMMARY_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + WORKFLOW_RUN_SCRIPT.read_text(encoding="utf-8-sig").lower()
        + "\n"
        + WORKFLOW_INSPECT_SCRIPT.read_text(encoding="utf-8-sig").lower()
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


def test_sandbox_writer_safety_verifier_passes_for_operator_evidence_pack():
    verifier = REPO_ROOT / "tools" / "audit" / "verify_sandbox_writer_safety.py"
    result = subprocess.run(
        [sys.executable, str(verifier)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "sandbox writer safety verifier failed\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
