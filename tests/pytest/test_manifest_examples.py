import json
from pathlib import Path


VALID_LANES = {
    "draft_mesh",
    "text_mesh",
    "photo_rig_prep",
    "text_full_rig",
    "external_rig_import",
    "release_character",
}

VALID_STATUSES = {"pass", "warn", "fail", "pending_manual", "running", "queued"}


def test_example_manifest_required_fields():
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    required_top_level = [
        "schema_version",
        "job",
        "identity",
        "inputs",
        "generation",
        "dcc_conform",
        "o3de",
        "qc",
        "runtime_validation",
        "evidence",
        "provenance",
        "undo",
        "cleanup",
    ]

    for key in required_top_level:
        assert key in data, f"Missing top-level field: {key}"


def test_example_manifest_job_constraints():
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "examples" / "manifests" / "example-draft-mesh.manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    job = data["job"]
    assert job.get("job_id"), "job_id must exist"
    assert job.get("lane") in VALID_LANES, "lane must be valid"
    assert job.get("status") in VALID_STATUSES, "status must be valid"
