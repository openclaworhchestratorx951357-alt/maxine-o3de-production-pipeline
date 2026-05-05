import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_capability_matrix() -> dict:
    matrix_path = REPO_ROOT / "examples" / "capabilities" / "maxine-capability-matrix.json"
    return json.loads(matrix_path.read_text(encoding="utf-8-sig"))


def test_release_publication_validation_capabilities_are_proof_only():
    matrix = _load_capability_matrix()
    caps = matrix["capabilities"]
    assert caps["release_publication_execution_window_ticket_report_validation"] == "proof_only"
    assert caps["release_publication_execution_window_state_report_validation"] == "proof_only"
    assert caps["release_publication_gate_set_report_validation"] == "proof_only"


def test_window_validation_capabilities_do_not_admit_execution_surfaces():
    matrix = _load_capability_matrix()
    caps = matrix["capabilities"]
    assert caps["asset_processor_execution"] == "blocked"
    assert caps["real_asset_processor_execution"] == "blocked"
    assert caps["o3de_editor_execution"] == "blocked"
    assert caps["o3de_cli_execution"] == "blocked"
    assert caps["spawning"] == "blocked"
    assert caps["publishing"] == "blocked"
