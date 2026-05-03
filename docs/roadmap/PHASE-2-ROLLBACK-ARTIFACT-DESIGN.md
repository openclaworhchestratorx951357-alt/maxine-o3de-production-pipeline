# Phase 2 Rollback Artifact Design

## 1. Purpose

This phase defines rollback artifacts for a future sandbox-only write prototype.

## 2. Non-goals

- no rollback execution is implemented
- no sandbox write is implemented
- no authoritative write is implemented
- no products are resolved
- no Asset IDs are claimed
- no O3DE/AP execution occurs

## 3. Rollback Artifact Purpose

Every future sandbox write must produce a rollback artifact before any write is allowed.

## 4. Required Rollback Artifact Inputs

- `sandbox_id`
- `target_manifest_copy`
- `pre_write_snapshot`
- `proposed_post_write_state`
- `proposed_field_changes`
- `operator_approval_ref`
- `execution_gate_ref`
- `timestamp`
- operator identity

## 5. Required Rollback Proof

A future rollback-capable prototype must prove:

- pre-write snapshot exists
- snapshot hash is recorded
- proposed post-write state is recorded
- exact changed fields are listed
- rollback can restore target manifest to pre-write snapshot
- rollback verification compares hashes
- no file outside sandbox is touched

## 6. Rollback Stop Conditions

Stop immediately if:

- target path is outside sandbox
- pre-write snapshot is missing
- rollback plan is missing
- rollback command is invoked without explicit `ConfirmRollback`
- production path is detected
- snapshot hash does not match
- rollback report cannot be written

## 7. Phase Verdict

Phase 2 rollback design remains non-executing. It defines rollback acceptance criteria only and does not authorize sandbox writes or rollback execution.
