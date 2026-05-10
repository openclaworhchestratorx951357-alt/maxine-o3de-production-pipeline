import json
import os
import subprocess
import sys
from pathlib import Path

import tools.ci.run_o3de_integration_suite as suite_module
from tools.ci.o3de_runner_readiness import build_readiness_report
from tools.ci.run_o3de_integration_suite import run_integration_suite


REPO_ROOT = Path(__file__).resolve().parents[2]
READINESS_SCRIPT = REPO_ROOT / "tools" / "ci" / "o3de_runner_readiness.py"
SUITE_SCRIPT = REPO_ROOT / "tools" / "ci" / "run_o3de_integration_suite.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "o3de-private-windows-integration.yml"
VALIDATE_ALL = REPO_ROOT / "tools" / "validation" / "validate_all.py"


def _unavailable_env(tmp_path: Path) -> dict:
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)
    env.pop("O3DE_ENGINE_ROOT", None)
    env.pop("O3DE_PROJECT_PATH", None)
    env.pop("O3DE_EDITOR_EXECUTABLE", None)
    env.pop("ASSET_PROCESSOR_BATCH", None)
    env.pop("ASSET_PROCESSOR_BATCH_EXECUTABLE", None)
    env.pop("MAXINE_ALLOW_LIVE_O3DE_COMMANDS", None)
    return env


def test_runner_readiness_default_skips_without_o3de(tmp_path):
    report = build_readiness_report(env=_unavailable_env(tmp_path), strict=False)

    assert report["status"] == "skipped"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["warnings"]
    assert report["live_commands_allowed"] is False
    assert report["tools"]["editor"]["available"] is False
    assert report["tools"]["asset_processor_batch"]["available"] is False


def test_runner_readiness_strict_fails_without_o3de(tmp_path):
    report = build_readiness_report(env=_unavailable_env(tmp_path), strict=True)

    assert report["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["errors"]


def test_runner_readiness_rejects_asset_processor_exe_substitute(tmp_path):
    env = _unavailable_env(tmp_path)
    engine_root = tmp_path / "o3de"
    project_path = tmp_path / "MAXINE_GoldenCorpus"
    editor = tmp_path / "Editor.exe"
    asset_processor = tmp_path / "AssetProcessor.exe"
    engine_root.mkdir()
    project_path.mkdir()
    editor.write_text("editor placeholder", encoding="utf-8")
    asset_processor.write_text("not the batch executable", encoding="utf-8")
    env["O3DE_ENGINE_ROOT"] = str(engine_root)
    env["O3DE_PROJECT_PATH"] = str(project_path)
    env["O3DE_EDITOR_EXECUTABLE"] = str(editor)
    env["ASSET_PROCESSOR_BATCH_EXECUTABLE"] = str(asset_processor)

    report = build_readiness_report(env=env, strict=True)

    assert report["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["errors"]
    assert report["tools"]["asset_processor_batch"]["available"] is False


def test_runner_readiness_apb_only_does_not_require_editor_when_editor_gate_disabled(tmp_path):
    env = _unavailable_env(tmp_path)
    engine_root = tmp_path / "o3de"
    project_path = tmp_path / "MAXINE_GoldenCorpus"
    apb = tmp_path / "AssetProcessorBatch.exe"
    engine_root.mkdir()
    project_path.mkdir()
    apb.write_text("batch placeholder", encoding="utf-8")
    env["O3DE_ENGINE_ROOT"] = str(engine_root)
    env["O3DE_PROJECT_PATH"] = str(project_path)
    env["ASSET_PROCESSOR_BATCH_EXECUTABLE"] = str(apb)
    env["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
    env["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"
    env["MAXINE_ENABLE_O3DE_EDITOR_SMOKE"] = "0"
    env["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] = "1"

    report = build_readiness_report(env=env, strict=True)

    assert report["status"] == "pass"
    assert report["tools"]["editor"]["required"] is False
    assert report["tools"]["editor"]["available"] is False
    assert report["would_run"]["asset_processor_batch"] is True
    assert report["would_run"]["editor_smoke"] is False


def test_runner_readiness_json_output_schema(tmp_path):
    result = subprocess.run(
        [sys.executable, str(READINESS_SCRIPT), "--json"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=_unavailable_env(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["report_type"] == "maxine_o3de_runner_readiness"
    assert payload["status"] == "skipped"
    assert payload["live_commands_allowed"] is False


def test_runner_readiness_cli_strict_fails_without_o3de(tmp_path):
    result = subprocess.run(
        [sys.executable, str(READINESS_SCRIPT), "--strict"],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=_unavailable_env(tmp_path),
    )

    assert result.returncode != 0
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in result.stdout


def test_integration_suite_dry_run_no_live_commands(tmp_path):
    report = run_integration_suite(mode="dry_run", env=_unavailable_env(tmp_path))

    assert report["mode"] == "dry_run"
    assert report["status"] == "skipped"
    assert report["live_commands_allowed"] is False
    assert report["live_o3de_execution"] is False
    assert report["commands"] == []


def test_integration_suite_fixture_mode_runs_offline_commands():
    report = run_integration_suite(mode="fixture")

    assert report["mode"] == "fixture"
    assert report["status"] == "pass"
    assert report["live_o3de_execution"] is False
    labels = {command["label"] for command in report["commands"]}
    assert {"validate_all fixture", "asset_processor_batch fixture", "editor_smoke fixture"} <= labels
    assert all(command["return_code"] == 0 for command in report["commands"])


def test_integration_suite_fixture_mode_scrubs_live_env_gates(monkeypatch):
    seen_envs = []

    def fake_run_command(label, args, env):
        seen_envs.append(dict(env))
        return {
            "label": label,
            "args": args,
            "return_code": 0,
            "stdout": "fixture command\n",
            "stderr": "",
            "reported_skipped": False,
        }

    monkeypatch.setattr(suite_module, "_run_command", fake_run_command)
    env = os.environ.copy()
    env["MAXINE_ENABLE_O3DE_INTEGRATION"] = "1"
    env["MAXINE_ENABLE_ASSET_PROCESSOR_BATCH"] = "1"
    env["MAXINE_ALLOW_LIVE_O3DE_COMMANDS"] = "1"

    report = suite_module.run_integration_suite(mode="fixture", env=env)

    assert report["status"] == "pass"
    assert seen_envs
    for command_env in seen_envs:
        assert command_env.get("MAXINE_ENABLE_O3DE_INTEGRATION") != "1"
        assert command_env.get("MAXINE_ENABLE_ASSET_PROCESSOR_BATCH") != "1"
        assert command_env.get("MAXINE_ALLOW_LIVE_O3DE_COMMANDS") != "1"


def test_integration_suite_integration_unavailable_skips_non_strict(tmp_path):
    report = run_integration_suite(
        mode="integration",
        enable_o3de_integration=True,
        strict_integration=False,
        env=_unavailable_env(tmp_path),
    )

    assert report["status"] == "skipped"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["warnings"]
    assert report["live_o3de_execution"] is False
    assert any(command["label"] == "validate_all integration" for command in report["commands"])


def test_integration_suite_integration_unavailable_fails_strict(tmp_path):
    report = run_integration_suite(
        mode="integration",
        enable_o3de_integration=True,
        strict_integration=True,
        env=_unavailable_env(tmp_path),
    )

    assert report["status"] == "fail"
    assert "MXN_VALIDATION_TOOL_UNAVAILABLE" in report["errors"]
    assert report["live_o3de_execution"] is False


def test_integration_suite_apb_only_does_not_run_editor_smoke(tmp_path):
    report = run_integration_suite(
        mode="integration",
        enable_o3de_integration=True,
        apb_only=True,
        strict_integration=False,
        env=_unavailable_env(tmp_path),
    )

    assert report["status"] == "skipped"
    assert report["apb_only"] is True
    assert report["live_editor_execution"] is False
    assert not any("editor_smoke" in command["label"] for command in report["commands"])


def test_workflow_is_manual_only():
    text = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "\npush:" not in text


def test_workflow_uses_self_hosted_windows_labels():
    text = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "runs-on: [self-hosted, Windows, X64, o3de, maxine-private]" in text


def test_workflow_has_private_runner_confirmation_guard():
    text = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "I_UNDERSTAND_THIS_REQUIRES_A_PRIVATE_SELF_HOSTED_WINDOWS_RUNNER" in text
    assert "confirm_private_runner" in text


def test_workflow_apb_live_mode_manual_only():
    text = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "apb_live_non_strict" in text
    assert "apb_live_strict" in text
    assert "editor_smoke_readiness" in text
    assert "editor_smoke_live_non_strict" in text
    assert "editor_smoke_live_strict" in text
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "\npush:" not in text


def test_workflow_sets_apb_gates_only_for_apb_mode_and_editor_gates_only_for_editor_mode():
    text = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "MAXINE_ENABLE_ASSET_PROCESSOR_BATCH" in text
    assert "--apb-only" in text
    assert "MAXINE_ENABLE_O3DE_EDITOR_SMOKE" in text
    assert "run_live_editor_commands" in text
    assert "MAXINE_ALLOW_LIVE_EDITOR_COMMANDS" in text
    assert "MAXINE_ALLOW_LIVE_PUBLICATION: \"0\"" in text
    assert "MAXINE_ENABLE_RELEASE_PACKAGING: \"0\"" in text


def test_workflow_editor_live_mode_requires_double_gate_and_apb_baseline():
    text = WORKFLOW.read_text(encoding="utf-8-sig")

    assert "Block Editor live mode unless live O3DE and Editor gates are explicit" in text
    assert "inputs.run_live_o3de_commands == false || inputs.run_live_editor_commands == false" in text
    assert "Editor smoke APB strict baseline" in text
    assert "--include-editor-smoke" in text
    assert "--editor-smoke-manifest" in text


def test_workflow_does_not_publish():
    text = WORKFLOW.read_text(encoding="utf-8-sig").lower()

    assert "publish" not in text
    assert "release packaging" not in text


def test_no_secrets_required_by_workflow():
    text = WORKFLOW.read_text(encoding="utf-8-sig").lower()

    assert "secrets." not in text
    assert "runner registration token" not in text
    assert "registration token" not in text


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
