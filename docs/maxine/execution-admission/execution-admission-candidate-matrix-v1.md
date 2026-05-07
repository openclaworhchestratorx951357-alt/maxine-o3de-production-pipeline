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

## Candidate-Specific Dry-Run Planning Link

The rollup-recommended next slice is now represented as a static planning artifact for the dry-run candidate:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-planning-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_plan.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_plan_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_plan.py`

`release_candidate_package_publish_dry_run_v1` remains `dry_run` and `unadmitted`.

## Candidate-Specific Dry-Run Receipt Contract Link

The dry-run candidate now also has a static receipt-boundary contract that keeps receipt issuance blocked while defining required future receipt fields and attestations:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-receipt-contract-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_receipt.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_receipt_blocked_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py`

## Candidate-Specific Dry-Run Admission Blockers Link

The dry-run candidate now also has a static final pre-approval checklist that keeps approval readiness/admission blocked while consolidating remaining blockers:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-admission-blockers-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_admission_blockers.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_admission_blockers_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_admission_blockers.py`

## Candidate-Specific Operator Approval Packet Link

The dry-run candidate now also has a static operator approval packet template that remains blocked/template-only and does not grant approval:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-operator-approval-packet-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_operator_approval_packet.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_operator_approval_packet_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_operator_approval_packet.py`

## Candidate-Specific Non-Approval Decision Link

The same candidate now also has an explicit static non-approval decision record:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-non-approval-decision-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_non_approval_decision.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_non_approval_decision_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_non_approval_decision.py`

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

## Candidate-Specific Sandbox Boundary Link

A separate static sandbox-boundary contract now defines future sandbox-only dry-run path/type limits while keeping admission and execution blocked:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-sandbox-boundary-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_sandbox_boundary.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_sandbox_boundary_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_sandbox_boundary.py`

The boundary remains `static_boundary_valid_blocked`, `runner_implemented=false`, `approval_request_ready=false`, `operator_approval_granted=false`, `approval_phrase_present=false`, `dry_run_admitted=false`, `dry_run_executed=false`, `receipt_issued=false`, `publication_admitted=false`, and `real_execution_admitted=false`.
