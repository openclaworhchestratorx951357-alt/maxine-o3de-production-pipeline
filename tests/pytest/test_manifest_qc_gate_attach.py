import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTACH_SCRIPT = REPO_ROOT / "tools" / "manifest-validator" / "attach_qc_gate.py"
EXAMPLE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "example-draft-mesh.manifest.json"


def _run_attach(manifest_path: Path, payload_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ATTACH_SCRIPT),
            str(manifest_path),
            str(payload_path),
            "--write-back",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _base_payload(check_id: str, result: str) -> dict:
    severity = "info"
    if result == "warn":
        severity = "warning"
    elif result == "fail":
        severity = "error"
    elif result == "pending_manual":
        severity = "manual_review"

    return {
        "status": result,
        "check_id": check_id,
        "contract_id": "TEST_CONTRACT",
        "findings": [],
        "manifest_attachment": {
            "target_path": "qc.gates[]",
            "future_target_path": "qc.checks[]",
            "qc_check": {
                "check_id": check_id,
                "result": result,
                "severity": severity,
                "details": {"source": "unit-test"},
            },
        },
    }


def test_attach_adds_new_qc_gate_and_updates_overall(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    payload_path = tmp_path / "payload.json"
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8-sig"))
    manifest["qc"]["overall"] = "pass"
    manifest["qc"]["gates"] = []
    _write_json(manifest_path, manifest)
    _write_json(payload_path, _base_payload("dcc_conform_v1", "warn"))

    result = _run_attach(manifest_path, payload_path)
    assert result.returncode == 0, result.stdout + result.stderr

    updated = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assert updated["qc"]["overall"] == "warn"
    assert len(updated["qc"]["gates"]) == 1
    assert updated["qc"]["gates"][0]["check_id"] == "dcc_conform_v1"
    assert updated["qc"]["gates"][0]["result"] == "warn"


def test_attach_replaces_existing_gate_by_check_id_without_duplicate(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    payload_path = tmp_path / "payload.json"
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8-sig"))
    manifest["qc"]["overall"] = "warn"
    manifest["qc"]["gates"] = [
        {"check_id": "material_uv_qc_v1", "result": "warn", "severity": "warning", "details": {}}
    ]
    _write_json(manifest_path, manifest)
    _write_json(payload_path, _base_payload("material_uv_qc_v1", "fail"))

    result = _run_attach(manifest_path, payload_path)
    assert result.returncode == 0, result.stdout + result.stderr

    updated = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    matching = [g for g in updated["qc"]["gates"] if g.get("check_id") == "material_uv_qc_v1"]
    assert len(matching) == 1
    assert matching[0]["result"] == "fail"
    assert updated["qc"]["overall"] == "fail"


def test_attach_rejects_non_gates_target_path(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    payload_path = tmp_path / "payload.json"
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8-sig"))
    _write_json(manifest_path, manifest)
    payload = _base_payload("animation_smoke_v1", "pass")
    payload["manifest_attachment"]["target_path"] = "qc.checks[]"
    _write_json(payload_path, payload)

    result = _run_attach(manifest_path, payload_path)
    assert result.returncode != 0
    assert "unsupported manifest target path" in (result.stdout + result.stderr)


def test_attach_preserves_unknown_manifest_fields(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    payload_path = tmp_path / "payload.json"
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8-sig"))
    manifest["custom_future_field"] = {"unchanged": True, "version": 2}
    _write_json(manifest_path, manifest)
    _write_json(payload_path, _base_payload("screenshot_evidence_v1", "pass"))

    result = _run_attach(manifest_path, payload_path)
    assert result.returncode == 0, result.stdout + result.stderr

    updated = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assert updated["custom_future_field"] == {"unchanged": True, "version": 2}


def test_attach_maps_pending_manual_to_warn_qc_overall(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    payload_path = tmp_path / "payload.json"
    manifest = json.loads(EXAMPLE_MANIFEST.read_text(encoding="utf-8-sig"))
    manifest["qc"]["overall"] = "pass"
    _write_json(manifest_path, manifest)
    _write_json(payload_path, _base_payload("manual_hero_review_v1", "pending_manual"))

    result = _run_attach(manifest_path, payload_path)
    assert result.returncode == 0, result.stdout + result.stderr

    updated = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assert updated["qc"]["overall"] == "warn"
