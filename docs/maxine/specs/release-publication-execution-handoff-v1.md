# Release Publication Execution Handoff v1 (Evidence-Only)

## What This Slice Does

`Release publication execution handoff v1` defines an evidence-only synthesis contract that converts release-publication chain evidence into a single immutable execution-handoff packet.

- validates structured execution-handoff report JSON
- checks required release QC gate completeness before handoff-ready decision
- checks required handoff-artifact hash coverage and mismatch/missing tracking
- checks manual approval threshold plus rollback/cleanup verification
- checks immutable handoff-packet path/hash/artifact evidence
- checks command execution remains unadmitted and unrecorded
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute O3DE
- does not execute Asset Processor
- does not execute Blender/DCC tools
- does not execute publication commands
- does not admit publication execution
- does not spawn runtime entities
- does not read Cache or live asset databases
- does not perform destructive cleanup

## Report Contract

Schema:

- `schemas/maxine_release_publication_execution_handoff_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- readiness contract:
  - `contract_id=RELEASE_PUBLICATION_EXECUTION_HANDOFF_v1`
  - `required_gate_ids`
  - `required_handoff_artifact_ids`
  - `required_approvals`
  - `manual_review_required`
  - `immutable_handoff_packet_required=true`
  - `hash_verification_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- execution handoff packet:
  - `handoff_id`
  - `handoff_recorded_utc`
  - `handed_off_by`
  - `handoff_action=record_release_publication_execution_handoff`
  - `handoff_scope=release_publication_chain`
  - `source_ready_for_execution_request_id`
  - `source_ready_for_execution_request_packet_path`
  - `source_ready_for_execution_request_packet_sha256`
  - `promotion_decision_id`
  - `execution_receipt_id`
  - `rollback_drill_id`
  - `evidence_integrity_index_id`
  - `hash_algorithm=sha256`
  - `handoff_packet_artifact_hashes`
  - `artifact_count`
  - `handoff_verification_status`
  - `missing_handoff_artifact_ids`
  - `hash_mismatch_handoff_artifact_ids`
  - `chain_manifest_path`
  - `no_command_execution_recorded=true`
  - `handoff_packet_path`
  - `handoff_packet_sha256`
  - `handoff_packet_artifacts`
  - `handoff_packet_immutable=true`
- approval state:
  - `decision` (`execution_handoff_recorded_for_future_execution_admission_request|pending_manual_review|rejected`)
  - `approver_ids`
  - `blocked_reason_codes`
  - `rollback_plan_verified`
  - `cleanup_plan_verified`
  - all execution-admission flags remain `false`
- readiness:
  - `required_gate_ids`
  - `present_gate_ids`
  - `missing_gate_ids`
  - `execution_handoff_readiness_state`
- findings
- manifest attachment payload

## Validation Logic

- missing required gates is fail-level
- missing required handoff-artifact hashes is fail-level
- pass verification status with missing/mismatched artifacts is fail-level
- handoff-ready decision with insufficient approvals is fail-level
- handoff-ready decision with blocked reasons is fail-level
- handoff-ready decision without rollback/cleanup verification is fail-level
- pending manual review decision is manual-review status
- rejected decision is fail-level
- unsafe path tokens for manifest/handoff-packet/artifacts are blocked
- disallowed runtime/cache/database artifacts are blocked
- all execution-admission flags remain false

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_publication_execution_handoff_v1`

## Validator

Validator script:

- `tools/release-publication-execution-handoff/validate_release_publication_execution_handoff_report.py`

Behavior:

- exits `0` on `pass`
- exits `0` on `warn` only with `--allow-warn`
- exits nonzero on `warn` without `--allow-warn`
- exits nonzero on `fail`
- exits nonzero on `pending_manual`

## Safety Boundaries

This slice is report-validation-only and preserves blocked/unadmitted surfaces:

- no Blender execution
- no O3DE execution
- no real Asset Processor execution
- no spawn/publish execution admission
- no Cache/live DB access
- no source/product UUID claims
- no new generation lanes
- no destructive cleanup

## Future Path (Not Implemented Here)

A future admitted publication-control slice may consume this immutable execution-handoff packet as the final evidence prerequisite before any live execution admission.
