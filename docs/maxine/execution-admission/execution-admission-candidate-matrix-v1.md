# Execution Admission Candidate Matrix v1

## Purpose

`execution-admission-candidate-matrix-v1` is a planning/status contract only.

It inventories future execution/publication candidates in a machine-readable format so widening can remain explicit, bounded, reversible, and receipt-backed.

This matrix does not admit real execution or publication by itself.

## Current Posture

- admitted no-op receipt candidate: `release_candidate_package_receipt_noop_v1`
- admitted real execution candidates: none
- admitted publication candidates: none
- real execution admission status: `blocked`
- publication admission status: `blocked`
- production-ready claim: `false`

## Candidate Types

- `evidence_only`
- `no_op_receipt`
- `dry_run`
- `real_execution`
- `publication`

## Candidate Statuses

- `proposed`
- `blocked`
- `review_ready`
- `admitted`
- `superseded`
- `rejected`

## Guardrails

- no-op receipt admission is not real execution admission
- no-op receipt admission is not publication admission
- real/publication candidates require explicit approval and receipt/rollback/validator/test requirements
- no `production_ready` claim is allowed in this matrix
- blocked safety surfaces must remain blocked

## Required Approval Phrase

- `APPROVE EXECUTION ADMISSION <candidate_id>`

## Core Artifacts

- schema:
  - `schemas/maxine_execution_admission_candidate_matrix.schema.json`
- example matrix:
  - `examples/execution-admission/execution_admission_candidate_matrix_v1.json`
- validator:
  - `tools/execution-admission/validate_execution_admission_candidate_matrix.py`
- proof integration:
  - `tools/release-lane/prove_pilot_release_chain.py`

## Preflight Contract Link

Candidate-specific preflight requirements are now captured separately and cross-checked against this matrix:

- `docs/maxine/execution-admission/execution-admission-preflight-contracts-v1.md`
- `schemas/maxine_execution_admission_preflight_contracts.schema.json`
- `examples/execution-admission/execution_admission_preflight_contracts_v1.json`
- `tools/execution-admission/validate_execution_admission_preflight_contracts.py`

Preflight contracts are requirements-only. They do not admit execution or publication.

## Preflight Proof Package Link

Static preflight proof packages are now defined and cross-checked against both matrix and contracts:

- `docs/maxine/execution-admission/execution-admission-preflight-proof-packages-v1.md`
- `schemas/maxine_execution_admission_preflight_proof_packages.schema.json`
- `examples/execution-admission/execution_admission_preflight_proof_packages_v1.json`
- `tools/execution-admission/validate_execution_admission_preflight_proof_packages.py`

These proof packages remain static evidence-only explanations. They do not admit execution or publication.

## Readiness Rollup Link

The control-tower readiness rollup now consolidates matrix/contracts/proof-package posture into one static blocked-status view:

- `docs/maxine/execution-admission/execution-admission-readiness-rollup-v1.md`
- `schemas/maxine_execution_admission_readiness_rollup.schema.json`
- `examples/execution-admission/execution_admission_readiness_rollup_v1.json`
- `tools/execution-admission/validate_execution_admission_readiness_rollup.py`

## Safety Notes

This slice remains non-executing and non-publishing:

- no O3DE/Editor/runtime execution
- no Asset Processor execution
- no Blender/DCC execution
- no profiler/benchmark execution
- no live screenshot capture
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production or engine path writes
