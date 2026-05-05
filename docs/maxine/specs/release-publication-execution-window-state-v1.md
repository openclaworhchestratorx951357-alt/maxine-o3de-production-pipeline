# Release Publication Execution Window State v1 (Evidence-Only)

## What This Slice Does

`Release publication execution window state v1` defines an evidence-only contract that records a bounded manual execution window state derived from previously validated publication-chain evidence.

- validates structured execution window state report JSON
- requires prior `release_publication_execution_authorization_record_v1` gate evidence
- verifies required source artifact hash coverage and mismatch/missing tracking
- verifies manual approval threshold plus rollback/cleanup verification flags
- verifies immutable window-state path/hash/artifact evidence
- validates bounded lifecycle window fields and timestamp ordering
- keeps command execution unadmitted and unrecorded
- emits manifest-attachable QC output

## What This Slice Does Not Do

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

- `schemas/maxine_release_publication_execution_window_state_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- readiness contract:
  - `contract_id=RELEASE_PUBLICATION_EXECUTION_WINDOW_STATE_v1`
  - `required_gate_ids` (must include `release_publication_execution_authorization_record_v1`)
  - `required_window_state_artifact_ids` (must include `release_publication_execution_authorization_record`)
  - `required_approvals`
  - `manual_review_required`
  - `immutable_window_state_required=true`
  - `hash_verification_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- execution window state:
  - `window_state` (`scheduled|active|expired|revoked|closed_no_execution`)
  - `window_start_utc`
  - `window_end_utc`
  - `window_state_id`
  - `window_state_recorded_utc`
  - `window_state_recorded_by`
  - `window_state_action=record_release_publication_execution_window_state`
  - `window_state_scope=release_publication_chain`
  - `source_execution_authorization_record_id`
  - `source_execution_authorization_record_path`
  - `source_execution_authorization_record_sha256`
  - `hash_algorithm=sha256`
  - `window_state_artifact_hashes`
  - `artifact_count`
  - `window_state_verification_status`
  - `missing_window_state_artifact_ids`
  - `hash_mismatch_window_state_artifact_ids`
  - `chain_manifest_path`
  - `no_command_execution_recorded=true`
  - `window_state_path`
  - `window_state_sha256`
  - `window_state_artifacts`
  - `window_state_immutable=true`
  - `window_state=expired|revoked` cannot be marked ready-for-future-manual-execution
- approval state:
  - `decision` (`execution_window_state_recorded_for_future_manual_execution_window|pending_manual_review|rejected`)
  - `approver_ids`
  - `blocked_reason_codes`
  - `rollback_plan_verified`
  - `cleanup_plan_verified`
  - all execution-admission flags remain `false`
- readiness:
  - `required_gate_ids`
  - `present_gate_ids`
  - `missing_gate_ids`
  - `execution_window_state_readiness_state`
- findings
- manifest attachment payload

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_publication_execution_window_state_v1`

## Validator

Validator script:

- `tools/release-publication-execution-window-state/validate_release_publication_execution_window_state_report.py`

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
