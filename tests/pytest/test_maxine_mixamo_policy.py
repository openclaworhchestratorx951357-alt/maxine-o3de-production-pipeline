import json
from pathlib import Path

from tools.qc.mixamo_policy import validate_mixamo_policy
from tools.qc.publication_contract import validate_publication_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
MIXAMO_MANIFEST = (
    REPO_ROOT
    / "examples"
    / "manifests"
    / "external_rig_import.pending_manual.example.json"
)
RELEASE_MANIFEST = REPO_ROOT / "examples" / "manifests" / "release_rigged.pass.example.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_mixamo_pending_manual_manifest_validates():
    result = validate_mixamo_policy(_load(MIXAMO_MANIFEST), offline=True)

    assert result.status == "pending_manual"
    assert "MXN_MIXAMO_PENDING_MANUAL" in result.warning_codes


def test_release_pipeline_does_not_require_mixamo():
    manifest = _load(RELEASE_MANIFEST)
    manifest.pop("mixamo", None)

    result = validate_mixamo_policy(manifest, offline=True)

    assert result.status == "pass"


def test_unresolved_mixamo_handoff_does_not_pass_release_publication():
    manifest = _load(RELEASE_MANIFEST)
    manifest["mixamo"] = {
        "external_service_optional": True,
        "status": "pending_manual",
        "manual_action_required_at_utc": "2026-05-08T00:00:00Z",
    }

    result = validate_publication_contract(manifest, strict=True)

    assert result.status == "fail"
    assert "MXN_MIXAMO_PENDING_MANUAL" in result.error_codes


def test_offline_mode_blocks_mixamo_automation_attempts():
    manifest = _load(MIXAMO_MANIFEST)
    manifest["mixamo"]["automation_attempted"] = True

    result = validate_mixamo_policy(manifest, offline=True)

    assert result.status == "fail"
    assert "MXN_EXTERNAL_SERVICE_BLOCKED" in result.error_codes
