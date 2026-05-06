# Release Candidate Package Publish Dry-Run Receipt Contract v1

## Purpose

`release-candidate-package-publish-dry-run-receipt-contract-v1` defines the static receipt boundary for the future dry-run candidate:

- `release_candidate_package_publish_dry_run_v1`

This artifact is a receipt contract only. It is not dry-run admission, not dry-run execution, not receipt issuance, not real execution admission, and not publication admission.

## Current Posture

- candidate id:
  - `release_candidate_package_publish_dry_run_v1`
- candidate type:
  - `dry_run`
- admission status:
  - `unadmitted`
- receipt issued:
  - `false`
- dry-run admitted:
  - `false`
- real execution admitted:
  - `false`
- publication admitted:
  - `false`
- production-ready claimed:
  - `false`
- contract status:
  - `static_contract_valid_blocked`

## Scope

The contract statically defines what a future admitted dry-run receipt must contain:

- required receipt fields
- required source references and input evidence references
- required sandbox output index and hash requirements
- required validation summary and blocked-surface attestations
- required rollback/no-op cleanup evidence
- required approval decision reference before any future receipt emission
- forbidden claims/outputs/paths
- blocked reason codes and missing evidence while unissued

## Blocked/Unissued Status

The contract and blocked example keep receipt issuance blocked in this slice:

- `receipt_issued=false`
- `receipt_status` is blocked/unissued contract-only
- `approval_decision_reference` remains null/empty
- no sandbox outputs are emitted now

## Safety Model

Blocked surfaces remain blocked:

- publication surfaces blocked
- execution surfaces blocked
- Cache/live DB access blocked
- authoritative source UUID / Asset ID / Product ID claims blocked
- no O3DE/Editor/runtime execution
- no Asset Processor execution
- no Blender/DCC execution
- no profiler/benchmark execution
- no live screenshot capture
- no spawn/publish
- no production path writes
- no engine path writes

## Approval Phrase

Any future dry-run admission for this candidate still requires:

- `APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1`

This slice does not include an admitted decision reference and does not issue a receipt.

## Source Artifact Alignment

The receipt contract is static and aligned to:

- execution-admission candidate matrix
- execution-admission preflight contracts
- execution-admission preflight proof packages
- execution-admission readiness rollup
- release-candidate publication dry-run plan
- production-readiness report
- admitted no-op receipt decision status

## Admission Blockers Link

A static admission-blocker checklist now tracks whether this candidate is ready to request approval:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-admission-blockers-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_admission_blockers.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_admission_blockers_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_admission_blockers.py`

Checklist posture remains blocked (`ready_to_request_approval=false`) and does not approve or admit dry-run execution.

## Artifacts

- schema:
  - `schemas/maxine_release_candidate_publication_dry_run_receipt.schema.json`
- contract example:
  - `examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json`
- blocked/unissued example:
  - `examples/execution-admission/release_candidate_package_publish_dry_run_receipt_blocked_v1.json`
- validator:
  - `tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py`
- proof integration:
  - `tools/release-lane/prove_pilot_release_chain.py`
- tests:
  - `tests/pytest/test_release_candidate_publication_dry_run_receipt_contract.py`
