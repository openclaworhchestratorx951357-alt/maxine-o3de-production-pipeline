import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "maxine_execution_admission_decision_record.schema.json"
PENDING_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "max_biped_v1_execution_admission_decision_pending.json"
)
APPROVED_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "max_biped_v1_execution_admission_decision_approved.json"
)
REJECTED_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "max_biped_v1_execution_admission_decision_rejected.json"
)
NOOP_APPROVED_PATH = (
    REPO_ROOT
    / "examples"
    / "execution-admission"
    / "release_candidate_package_receipt_noop_execution_admission_decision_approved.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _try_jsonschema_validator():
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        return None
    return Draft202012Validator


def _is_state_consistent(instance: dict) -> bool:
    decision_state = instance["decision_state"]
    approval_received = instance["approval"]["approval_received"]
    approval_phrase = instance["approval"]["approval_phrase_received"]
    execution_admitted = instance["admission_outcome"]["execution_admitted"]
    admission_scope = instance["admission_outcome"]["admission_scope"]

    if decision_state == "approved":
        return approval_received and approval_phrase.startswith("APPROVE EXECUTION ADMISSION ")

    return (not approval_received) and (not execution_admitted) and admission_scope == "none"


def test_examples_validate_against_schema_or_minimal_rules():
    schema = _load_json(SCHEMA_PATH)
    validator_cls = _try_jsonschema_validator()
    for example_path in [PENDING_PATH, APPROVED_PATH, REJECTED_PATH, NOOP_APPROVED_PATH]:
        instance = _load_json(example_path)
        if validator_cls is not None:
            validator = validator_cls(schema)
            errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
            assert not errors, "Schema validation errors: " + "; ".join(
                f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
                for e in errors
            )
        else:
            # Minimal fallback keeps coverage when jsonschema is unavailable.
            assert instance["schema_version"] == "1.0.0"
            assert instance["record_type"] == "EXECUTION_ADMISSION_DECISION_v1"
            assert isinstance(instance["candidate_id"], str) and instance["candidate_id"]
            assert instance["decision_state"] in {"pending_review", "approved", "rejected"}
            assert _is_state_consistent(instance)


def test_approved_requires_explicit_phrase_and_approval_received():
    schema = _load_json(SCHEMA_PATH)
    instance = _load_json(APPROVED_PATH)
    instance["approval"]["approval_received"] = False
    validator_cls = _try_jsonschema_validator()
    if validator_cls is not None:
        validator = validator_cls(schema)
        errors = list(validator.iter_errors(instance))
        assert errors
    else:
        assert not _is_state_consistent(instance)


def test_non_approved_state_cannot_admit_execution():
    schema = _load_json(SCHEMA_PATH)
    instance = _load_json(PENDING_PATH)
    instance["admission_outcome"]["execution_admitted"] = True
    validator_cls = _try_jsonschema_validator()
    if validator_cls is not None:
        validator = validator_cls(schema)
        errors = list(validator.iter_errors(instance))
        assert errors
    else:
        assert not _is_state_consistent(instance)
