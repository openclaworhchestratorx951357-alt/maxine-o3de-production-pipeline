import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_max_biped_v1_spec_exists():
    repo_root = _repo_root()
    spec_path = repo_root / "docs" / "maxine" / "specs" / "MAX_BIPED_v1.md"
    assert spec_path.exists(), f"Missing spec file: {spec_path}"


def test_max_biped_v1_contract_and_schema_exist():
    repo_root = _repo_root()
    schema_path = repo_root / "schemas" / "maxine_skeleton_contract.schema.json"
    contract_path = repo_root / "examples" / "skeleton-contracts" / "MAX_BIPED_v1.json"
    assert schema_path.exists(), f"Missing schema file: {schema_path}"
    assert contract_path.exists(), f"Missing contract file: {contract_path}"


def test_max_biped_v1_contract_validates_against_schema_or_minimal_rules():
    repo_root = _repo_root()
    schema = _load_json(repo_root / "schemas" / "maxine_skeleton_contract.schema.json")
    contract = _load_json(repo_root / "examples" / "skeleton-contracts" / "MAX_BIPED_v1.json")

    try:
        from jsonschema import Draft202012Validator
    except Exception:
        Draft202012Validator = None

    if Draft202012Validator is not None:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(contract), key=lambda err: list(err.path))
        assert not errors, "Contract schema validation errors: " + "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        )
    else:
        required = {
            "schema_version",
            "contract_id",
            "required_bones",
            "required_hierarchy_edges",
            "naming_rules",
            "validation_rules",
            "severity_mapping",
            "manifest_integration",
        }
        assert required.issubset(contract.keys())
        assert contract["contract_id"] == "MAX_BIPED_v1"


def test_skeleton_examples_exist():
    repo_root = _repo_root()
    for name in ("max_biped_v1_pass.json", "max_biped_v1_warn.json", "max_biped_v1_fail.json"):
        path = repo_root / "examples" / "skeletons" / name
        assert path.exists(), f"Missing skeleton example: {path}"
