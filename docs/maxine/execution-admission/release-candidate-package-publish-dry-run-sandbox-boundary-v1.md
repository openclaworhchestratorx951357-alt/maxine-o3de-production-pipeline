# Release Candidate Package Publish Dry-Run Sandbox Boundary v1

## Purpose

`release-candidate-package-publish-dry-run-sandbox-boundary-v1` is a static, auditable sandbox-boundary contract for:

- `release_candidate_package_publish_dry_run_v1`

This artifact is static contract/status only. It is not approval, not approval-ready, not admission, not runner implementation, not execution, not receipt issuance, and not publication.

## Current Posture

- candidate id:
  - `release_candidate_package_publish_dry_run_v1`
- candidate type:
  - `dry_run`
- sandbox boundary status:
  - `static_boundary_valid_blocked`
- admission status:
  - `unadmitted`
- runner implemented:
  - `false`
- approval request ready:
  - `false`
- operator approval granted:
  - `false`
- approval phrase present:
  - `false`
- dry-run admitted:
  - `false`
- dry-run executed:
  - `false`
- receipt issued:
  - `false`
- real execution admitted:
  - `false`
- publication admitted:
  - `false`
- production-ready claimed:
  - `false`

## Boundary Scope

The contract defines:

- allowed read roots for static artifacts
- allowed sandbox-only write roots for a future admitted dry-run
- allowed future receipt/report roots (future-facing only; no receipt is issued in this slice)
- forbidden roots and forbidden path patterns
- allowed report/receipt/hash file extensions
- forbidden executable/binary/cache/database extension classes
- required path normalization and containment checks
- required future output index and SHA-256 hashing expectations
- cleanup/rollback evidence requirements
- invalidation conditions for immediate boundary violation
- runner interface constraints that keep runner unimplemented

## Live Surface Blocks

Blocked surfaces remain blocked:

- no O3DE/Editor/runtime/AP/Blender/DCC/profiler execution
- no screenshot capture
- no spawn/publish
- no Cache/live DB access
- no production path writes
- no engine path writes
- no destructive cleanup
- no authoritative source UUID / Asset ID / Product ID claims

## Invalidation Conditions

Any future dry-run attempt would be invalidated immediately if it:

- writes outside approved sandbox roots
- touches production/engine/Cache/live DB paths
- attempts spawn/publish or live runtime/tool invocation
- emits executable/binary outputs outside allowed static formats
- issues receipt without explicit admission
- attempts path traversal or symlink/junction escape
- makes authoritative ID claims

## Relationship To Prior Static Artifacts

This contract cross-checks and remains aligned with:

- candidate matrix
- preflight contracts
- preflight proof packages
- readiness rollup
- dry-run plan
- dry-run receipt contract
- blocked/unissued receipt example
- admission blocker checklist
- operator approval packet
- operator approval packet completeness
- approval request readiness report
- non-approval decision record
- runner interface contract
- production-readiness report
- admitted no-op receipt decision status

## Required Future Approval Phrase

Any future dry-run admission for this candidate still requires this exact phrase in a separate future approval decision:

- `APPROVE EXECUTION ADMISSION release_candidate_package_publish_dry_run_v1`

This slice does not mark that phrase present and does not admit the candidate.

## Runner Interface Constraints

Runner remains unimplemented in this milestone:

- `runner_implemented=false`
- any future runner must be proposed in a separate slice
- any future runner must consume this contract and fail closed on violation
- any future runner must remain sandbox-only and must not publish/spawn/live-access

## Runner Interface Link

A separate static runner-interface contract now captures the candidate-specific future runner interface without implementing a runner:

- `docs/maxine/execution-admission/release-candidate-package-publish-dry-run-runner-interface-v1.md`
- `schemas/maxine_release_candidate_publication_dry_run_runner_interface.schema.json`
- `examples/execution-admission/release_candidate_package_publish_dry_run_runner_interface_v1.json`
- `tools/execution-admission/validate_release_candidate_publication_dry_run_runner_interface.py`

That interface remains `static_interface_valid_blocked`, `runner_implemented=false`, `runner_admitted=false`, and `runner_executed=false`.

## Artifacts

- schema:
  - `schemas/maxine_release_candidate_publication_dry_run_sandbox_boundary.schema.json`
- example contract:
  - `examples/execution-admission/release_candidate_package_publish_dry_run_sandbox_boundary_v1.json`
- validator:
  - `tools/execution-admission/validate_release_candidate_publication_dry_run_sandbox_boundary.py`
- proof integration:
  - `tools/release-lane/prove_pilot_release_chain.py`
- tests:
  - `tests/pytest/test_release_candidate_publication_dry_run_sandbox_boundary.py`
