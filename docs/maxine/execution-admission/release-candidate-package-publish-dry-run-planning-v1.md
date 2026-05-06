# Release Candidate Package Publish Dry-Run Planning v1

## Purpose

`release-candidate-package-publish-dry-run-planning-v1` is a static, candidate-specific planning artifact for:

- `release_candidate_package_publish_dry_run_v1`

This artifact is planning-only. It is not dry-run admission, not real execution admission, not publication admission, and not a runner.

## Current Posture

- candidate id:
  - `release_candidate_package_publish_dry_run_v1`
- candidate type:
  - `dry_run`
- admission status:
  - `unadmitted`
- dry-run admitted:
  - `false`
- real execution admitted:
  - `false`
- publication admitted:
  - `false`
- production-ready claimed:
  - `false`
- plan status:
  - `static_plan_valid_blocked`

## Scope

The plan defines, without execution:

- future dry-run objective
- future dry-run inputs
- forbidden inputs and forbidden outputs
- future allowed sandbox-only output paths
- required future receipts/validators/tests
- required future rollback or cleanup evidence
- missing evidence and blocked reason codes
- why the candidate remains blocked and unadmitted now

## Safety Model

The plan keeps blocked surfaces blocked:

- publication surfaces blocked
- execution surfaces blocked
- no O3DE/Editor/runtime execution
- no Asset Processor execution
- no Blender/DCC execution
- no profiler/benchmark execution
- no live screenshot capture
- no spawn/publish
- no Cache/live DB access
- no production path writes
- no engine path writes
- no authoritative source UUID / Asset ID / Product ID claims

## Approval Phrase

Any future admission request for this candidate still requires:

- `APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1`

This planning slice does not include an admitted decision reference.

## Source Artifact Alignment

The plan is generated from static artifact references only:

- execution-admission candidate matrix
- execution-admission preflight contracts
- execution-admission preflight proof packages
- execution-admission readiness rollup
- production-readiness report
- admitted no-op receipt decision status

Readiness-rollup alignment remains:

- `slice_id`: `candidate_specific_dry_run_planning_v1`
- `candidate_id`: `release_candidate_package_publish_dry_run_v1`

## Dry-Run Receipt Contract Link

The next static boundary layer is now defined as a receipt contract:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-receipt-contract-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_receipt.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_receipt_contract_v1.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_receipt_blocked_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_receipt.py`

This receipt contract remains static/unissued (`receipt_issued=false`) and does not admit or execute dry-run publication flow.

## Artifacts

- schema:
  - `schemas/maxine_release_candidate_publication_dry_run_plan.schema.json`
- example:
  - `examples/execution-admission/release_candidate_package_publish_dry_run_plan_v1.json`
- validator:
  - `tools/execution-admission/validate_release_candidate_publication_dry_run_plan.py`
- proof integration:
  - `tools/release-lane/prove_pilot_release_chain.py`
- tests:
  - `tests/pytest/test_release_candidate_publication_dry_run_plan.py`
