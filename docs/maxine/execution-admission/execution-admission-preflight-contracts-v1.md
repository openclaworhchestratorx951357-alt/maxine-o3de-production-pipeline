# Execution Admission Preflight Contracts v1

## Purpose

`execution-admission-preflight-contracts-v1` defines candidate-specific preflight requirements.

These contracts are requirements only. They are not execution admission and they are not publication admission.

## Scope

- machine-readable preflight requirements for every candidate listed in the execution-admission candidate matrix
- strict cross-check between candidate matrix ids/types and preflight contract ids/types
- explicit approval phrase requirement for future real-execution/publication candidates:
  - `APPROVE EXECUTION ADMISSION <candidate_id>`
- sandbox-boundary, blocked-surface, receipt, rollback, validator, and test requirements per candidate

## Current Posture

- admitted no-op receipt candidate:
  - `release_candidate_package_receipt_noop_v1`
- no-op receipt candidate admission class:
  - `admitted_no_op_only`
- admitted real execution candidates:
  - none
- admitted publication candidates:
  - none
- real execution preflight passed candidates:
  - none
- publication preflight passed candidates:
  - none
- real execution admission status:
  - `blocked`
- publication admission status:
  - `blocked`
- production-ready claim:
  - `false`

## Candidate Coverage

Preflight contracts are defined for all current matrix entries:

- `release_candidate_package_receipt_noop_v1`
- `dcc_conform_execution_v1`
- `asset_processor_batch_execution_v1`
- `max_biped_skeleton_validation_execution_v1`
- `material_uv_qc_execution_v1`
- `animation_smoke_execution_v1`
- `visual_evidence_capture_execution_v1`
- `release_candidate_package_publish_dry_run_v1`
- `release_candidate_package_publication_v1`

## Guardrails

- no-op receipt admission must not be treated as real execution admission
- no-op receipt admission must not be treated as publication admission
- future real execution/publication candidates must remain unadmitted in this milestone
- future real execution/publication candidates must not be marked preflight `passed` in this milestone
- production-ready and publication-admitted claims remain blocked in this milestone

## Artifacts

- schema:
  - `schemas/maxine_execution_admission_preflight_contracts.schema.json`
- example:
  - `examples/execution-admission/execution_admission_preflight_contracts_v1.json`
- validator:
  - `tools/execution-admission/validate_execution_admission_preflight_contracts.py`
- proof integration:
  - `tools/release-lane/prove_pilot_release_chain.py`
- tests:
  - `tests/pytest/test_execution_admission_preflight_contracts.py`

## Preflight Proof Package Layer

A static proof-evaluation layer now explains current evidence coverage and missing requirements per candidate:

- `docs/maxine/execution-admission/execution-admission-preflight-proof-packages-v1.md`
- `schemas/maxine_execution_admission_preflight_proof_packages.schema.json`
- `examples/execution-admission/execution_admission_preflight_proof_packages_v1.json`
- `tools/execution-admission/validate_execution_admission_preflight_proof_packages.py`

This layer remains requirements/reporting only. It does not admit execution or publication.

## Readiness Rollup Link

Readiness rollup now consolidates candidate matrix, preflight contracts, and preflight proof package posture in one static report:

- `docs/maxine/execution-admission/execution-admission-readiness-rollup-v1.md`
- `schemas/maxine_execution_admission_readiness_rollup.schema.json`
- `examples/execution-admission/execution_admission_readiness_rollup_v1.json`
- `tools/execution-admission/validate_execution_admission_readiness_rollup.py`

## Safety Notes

This milestone preserves blocked execution/publication surfaces:

- no O3DE/Editor/runtime execution
- no Asset Processor execution
- no Blender/DCC execution
- no profiler/benchmark execution
- no live screenshot capture
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production or engine path writes
