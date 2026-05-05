# Release Publication Execution Receipt v1 (Evidence-Only)

## What This Slice Does

`Release publication execution receipt v1` defines an evidence-only contract for recording manual publication execution receipt outcomes plus immutable audit-bundle evidence.

- validates structured execution receipt report JSON
- checks required QC gate completeness before receipt-ready state
- checks manual approval counts and decision consistency
- checks display-only publish/rollback command evidence
- checks immutable audit bundle, publication log, and rollback log path/hash artifact evidence
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

- `schemas/maxine_release_publication_execution_receipt_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- receipt contract:
  - `contract_id=RELEASE_PUBLICATION_EXECUTION_RECEIPT_v1`
  - `required_gate_ids`
  - `required_approvals`
  - `manual_review_required`
  - `immutable_audit_bundle_required=true`
  - `external_execution_evidence_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- execution receipt:
  - `receipt_id`
  - `receipt_recorded_utc`
  - `recorded_by`
  - `receipt_action=record_manual_publication_execution_receipt`
  - `publication_result`
  - `request_ledger_entry_id`
  - `publish_command_display` (display-only)
  - `rollback_command_display` (display-only)
  - `target_environment`
  - `no_command_execution_recorded=true`
  - `publication_log_path`
  - `publication_log_sha256`
  - `rollback_log_path`
  - `rollback_log_sha256`
  - `evidence_bundle_path`
  - `evidence_bundle_sha256`
  - `evidence_bundle_artifacts`
  - `evidence_bundle_immutable=true`
- approval state:
  - `decision` (`receipt_recorded_for_audit|pending_manual_review|rejected`)
  - `approver_ids`
  - `blocked_reason_codes`
  - `rollback_plan_verified`
  - `cleanup_plan_verified`
  - all execution-admission flags remain `false`
- readiness:
  - `required_gate_ids`
  - `present_gate_ids`
  - `missing_gate_ids`
  - `release_readiness_state`
- findings
- manifest attachment payload

## Validation Logic

- missing required gates is fail-level
- receipt-ready decision with insufficient approvals is fail-level
- receipt-ready decision with blocked reasons is fail-level
- receipt-ready decision without rollback/cleanup verification is fail-level
- pending manual decision is manual-review status
- rejected decision is fail-level
- command displays must remain display-only and block unsafe command tokens
- publication/rollback log path/hash checks are enforced
- immutable audit bundle path/hash/artifact safety is enforced
- publication result and report status must remain consistent

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_publication_execution_receipt_v1`

## Validator

Validator script:

- `tools/release-publication-execution-receipt/validate_release_publication_execution_receipt_report.py`

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

A future admitted execution-control slice may consume this manual receipt evidence alongside request-ledger evidence. This v1 slice remains non-executing and non-admitting.
