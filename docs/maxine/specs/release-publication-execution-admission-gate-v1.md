# Release Publication Execution Admission Gate v1 (Evidence-Only)

## What This Slice Does

`Release publication execution admission gate v1` defines an evidence-only contract that validates whether a release package has complete evidence for a future manual execution-admission review.

- validates structured execution admission gate report JSON
- checks required QC gate completeness before any execution admission review
- checks approval counts and admission decision consistency
- checks display-only publish/rollback command evidence
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

- `schemas/maxine_release_publication_execution_admission_gate_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- admission contract:
  - `contract_id=RELEASE_PUBLICATION_EXECUTION_ADMISSION_GATE_v1`
  - `required_gate_ids`
  - `required_approvals`
  - `manual_review_required`
  - `explicit_execution_admission_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- execution gate request:
  - `request_id`
  - `request_recorded_utc`
  - `requested_by`
  - `requested_action=admit_publication_execution`
  - `target_environment`
  - `publish_command_display` (display-only)
  - `rollback_command_display` (display-only)
  - `no_command_execution_recorded=true`
  - `dry_run_evidence_paths`
- admission assessment:
  - `admission_decision` (`ready_for_future_admission_review|pending_manual_review|rejected`)
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
- ready decision with insufficient approvals is fail-level
- ready decision with blocked reasons is fail-level
- ready decision without rollback/cleanup verification is fail-level
- pending manual review decision is manual-review status
- rejected decision is fail-level
- command displays must remain display-only and block unsafe command tokens

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_publication_execution_admission_gate_v1`

## Validator

Validator script:

- `tools/release-publication-execution-admission-gate/validate_release_publication_execution_admission_gate_report.py`

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

A future slice may propose explicit execution-admission workflow and separate controls for any eventual admitted publish execution. This v1 gate remains non-executing and non-admitting.
