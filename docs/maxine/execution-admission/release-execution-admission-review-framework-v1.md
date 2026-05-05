# Release Execution-Admission Review Framework v1

## Purpose

Define a deterministic, review-first framework for future execution admission decisions without admitting execution in this slice.

This framework is policy and evidence only.

## Current State

- execution admission remains future work requiring explicit approval
- no broad O3DE execution is admitted
- no broad/real Asset Processor execution is admitted
- no Blender/DCC execution is admitted
- no spawn/publish execution is admitted
- no Cache/live DB access is admitted

## Decision Record Contract

Decision records must conform to:

- `schemas/maxine_execution_admission_decision_record.schema.json`

Fixture examples:

- `examples/execution-admission/max_biped_v1_execution_admission_decision_pending.json`
- `examples/execution-admission/max_biped_v1_execution_admission_decision_approved.json`
- `examples/execution-admission/max_biped_v1_execution_admission_decision_rejected.json`

## Required Admission Preconditions

Any future execution admission candidate must include all of the following:

1. decision record
2. `candidate_id`
3. exact command/tool path
4. exact allowed input paths
5. exact allowed output paths
6. explicit operator approval phrase
7. receipt contract reference
8. rollback/readiness reference
9. safety verifier coverage reference
10. post-execution validation command list

Without all ten, execution remains blocked.

## Approval Phrase Rule

Required phrase format for future admitted execution decisions:

- `APPROVE EXECUTION ADMISSION <candidate_id>`

This framework records the phrase requirement and whether it was received. It does not execute anything.

## Decision States

- `pending_review`: candidate is under review; execution not admitted
- `approved`: candidate is approved for a future bounded admission slice only
- `rejected`: candidate is explicitly denied; execution remains blocked

An `approved` decision record alone does not perform execution. Execution still requires explicit operator instruction in a later slice.

## Integration Boundaries

This slice does not:

- add new release-lane gates
- add new release-lane validators
- modify execution-capability matrix states
- widen any blocked surface

## Related Next Step

Execution receipt dry-run framework:

- `docs/maxine/execution-admission/release-execution-receipt-dry-run-framework-v1.md`

## Verification

Pytest schema coverage for this framework:

- `tests/pytest/test_execution_admission_decision_record_schema.py`
