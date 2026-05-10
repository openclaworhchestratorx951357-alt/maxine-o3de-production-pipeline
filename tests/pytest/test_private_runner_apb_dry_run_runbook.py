import json
import os
import subprocess
import sys
from pathlib import Path

from tools.ci.private_runner_apb_dry_run_checklist import build_dry_run_checklist_report


REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_TEMPLATE = REPO_ROOT / "examples" / "private-runner" / "o3de-runner.env.example"
DRY_RUN_EXAMPLE = REPO_ROOT / "examples" / "private-runner" / "apb-dry-run-checklist.unavailable.example.json"
CHECKLIST_SCRIPT = REPO_ROOT / "tools" / "ci" / "private_runner_apb_dry_run_checklist.py"
RUNBOOK = REPO_ROOT / "docs" / "production" / "private-runner-apb-dry-run-runbook.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "o3de-private-windows-integration.yml"
VALIDATE_ALL = REPO_ROOT / "tools" / "validation" / "validate_all.py"


def _unavailable_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    for key in [
        "O3DE_ENGINE_ROOT",
        "O3DE_PROJECT_PATH",
        "O3DE_EDITOR_EXECUTABLE",
        "ASSET_PROCESSOR_BATCH",
        "ASSET_PROCESSOR_BATCH_EXECUTABLE",
        "MAXINE_ENABLE_O3DE_INTEGRATION",
        "MAXINE_ENABLE_ASSET_PROCESSOR_BATCH",
        "MAXINE_ENABLE_O3DE_EDITOR_SMOKE",
        "MAXINE_ALLOW_LIVE_O3DE_COMMANDS",
        "MAXINE_ALLOW_LIVE_EDITOR_COMMANDS",
        "MAXINE_ALLOW_LIVE_PUBLICATION",
        "MAXINE_ENABLE_RELEASE_PACKAGING",
    ]:
        env.pop(key, None)
    return env


def _env_assignments() -> dict:
    assignments = {}
    for line in ENV_TEMPLATE.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        assignments[key.strip()] = value.strip()
    return assignments


def test_private_runner_env_template_exists():
    assert ENV_TEMPLATE.exists()


def test_private_runner_env_template_has_no_secret_assignments():
    text = ENV_TEMPLATE.read_text(encoding="utf-8-sig").lower()
    assignments = _env_assignments()

    forbidden_keys = ["token", "password", "secret", "credential", "api_key"]
    assert all(not any(marker in key.lower() for marker in forbidden_keys) for key in assignments)
    assert "ghp_" not in text
    assert "gho_" not in text
    assert "<token>" not in text


def test_private_runner_env_template_defaults_keep_live_paths_safe():
    assignments = _env_assignments()

    assert assignments["MAXINE_ENABLE_O3DE_INTEGRATION"] == "1"
    assert assignments["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] == "1"
    assert assignments["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] == "0"
    assert assignments["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] == "0"
    assert assignments["MAXINE_GOLDEN_PROJECT_FIXTURE"] == "examples/o3de-golden-project/maxine-golden-project.fixture.json"
    assert assignments["MAXINE_GOLDEN_CORPUS"] == "examples/golden-corpus"
    assert assignments["MAXINE_RUN_MODE"] == "readiness"


def test_private_runner_dry_run_example_fixture_documents_unavailable_shape():
    payload = json.loads(DRY_RUN_EXAMPLE.read_text(encoding="utf-8-sig"))

    assert payload["report_type"] == "maxine_private_runner_apb_dry_run_checklist"
    assert payload["status"] == "skipped"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in payload["warnings"]
    assert payload["live_asset_processor_batch_execution"] is False
    assert payload["live_editor_execution"] is False
    assert payload["live_publication"] is False
    assert payload["env_template_ref"] == "examples/private-runner/o3de-runner.env.example"


def test_private_runner_apb_dry_run_checklist_default_skips_without_o3de(tmp_path):
    report = build_dry_run_checklist_report(env=_unavailable_env(tmp_path), strict=False)

    assert report["report_type"] == "maxine_private_runner_apb_dry_run_checklist"
    assert report["status"] == "skipped"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["warnings"]
    assert report["live_asset_processor_batch_execution"] is False
    assert report["live_editor_execution"] is False
    assert report["live_publication"] is False
    assert report["checks"]["apb_readiness"]["status"] == "skipped"


def test_private_runner_apb_dry_run_checklist_strict_fails_without_o3de(tmp_path):
    report = build_dry_run_checklist_report(env=_unavailable_env(tmp_path), strict=True)

    assert report["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["errors"]
    assert report["live_asset_processor_batch_execution"] is False


def test_private_runner_apb_dry_run_checklist_json_valid(tmp_path):
    result = subprocess.run(
        [sys.executable, str(CHECKLIST_SCRIPT), "--json"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=_unavailable_env(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["report_type"] == "maxine_private_runner_apb_dry_run_checklist"
    assert payload["checks"]["env_template_present"]["status"] == "pass"
    assert payload["live_asset_processor_batch_execution"] is False


def test_private_runner_apb_dry_run_checklist_strict_cli_fails_without_o3de(tmp_path):
    result = subprocess.run(
        [sys.executable, str(CHECKLIST_SCRIPT), "--strict"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=_unavailable_env(tmp_path),
    )

    assert result.returncode != 0
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout
    assert "live_asset_processor_batch_execution: false" in result.stdout


def test_workflow_readiness_uses_dry_run_checklist():
    text = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "private_runner_apb_dry_run_checklist.py" in text
    assert "readiness" in text
    assert "fixture" in text
    assert "apb_live_non_strict" in text
    assert "apb_live_strict" in text
    assert "editor_smoke_readiness" in text


def test_workflow_stays_manual_private_and_non_publishing():
    text = WORKFLOW.read_text(encoding="utf-8-sig")
    lower = text.lower()

    assert "workflow_dispatch:" in text
    assert "\npush:" not in text
    assert "pull_request:" not in text
    assert "runs-on: [self-hosted, Windows, X64, o3de, maxine-private]" in text
    assert "I_UNDERSTAND_THIS_REQUIRES_A_PRIVATE_SELF_HOSTED_WINDOWS_RUNNER" in text
    assert "secrets." not in lower
    assert "publish" not in lower
    assert "MAXINE_ENABLE_O3DE_EDITOR_SMOKE" in text
    assert "run_live_editor_commands" in text
    assert "MAXINE_ALLOW_LIVE_PUBLICATION: \"0\"" in text
    assert "MAXINE_ENABLE_RELEASE_PACKAGING: \"0\"" in text


def test_runbook_references_expected_dry_run_commands():
    text = RUNBOOK.read_text(encoding="utf-8-sig")

    for snippet in [
        "python tools/ci/o3de_runner_readiness.py --json",
        "python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project",
        "python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness",
        "python tools/ci/run_o3de_integration_suite.py --dry-run",
        "python tools/ci/run_o3de_integration_suite.py --mode fixture",
        "python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --check-local-readiness",
    ]:
        assert snippet in text
    assert "run_live_o3de_commands" in text
    assert "I_UNDERSTAND_THIS_REQUIRES_A_PRIVATE_SELF_HOSTED_WINDOWS_RUNNER" in text


def test_validate_all_still_offline_by_default(tmp_path):
    result = subprocess.run(
        [sys.executable, str(VALIDATE_ALL)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=_unavailable_env(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "local O3DE integration: skipped" in result.stdout
    assert "Asset Processor Batch local integration: skipped" in result.stdout
    assert "Editor smoke local integration: skipped" in result.stdout
