# Release Publication Request Approval v1 (Evidence-Only)

## What This Slice Does

`Release publication request approval v1` defines an evidence-only contract for publication request records and manual approval evidence.

- validates structured publication request approval report JSON
- checks required QC gate completeness before publication request approval
- checks manual approval counts and approval decision consistency
- checks display-only publish/rollback request command evidence
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute O3DE
- does not execute Asset Processor
- does not execute Blender/DCC tools
- does not execute publication commands
- does not spawn runtime entities
- does not read Cache or live asset databases
- does not perform destructive cleanup

## Report Contract

Schema:

- `schemas/maxine_release_publication_request_approval_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- request contract:
  - `contract_id=RELEASE_PUBLICATION_REQUEST_APPROVAL_v1`
  - `required_gate_ids`
  - `required_approvals`
  - `manual_review_required`
  - `explicit_publish_execution_request_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- publication request:
  - `request_id`
  - `request_recorded_utc`
  - `requested_by`
  - `requested_action=publish_release_bundle`
  - `target_environment`
  - `publish_request_command_display` (display-only)
  - `rollback_request_command_display` (display-only)
  - `no_command_execution_recorded=true`
  - `dry_run_evidence_paths`
- approval state:
  - `decision` (`approved|pending|rejected`)
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
- approved decisions with insufficient approvals is fail-level
- approved decisions with blocked reasons is fail-level
- approved decisions without rollback/cleanup verification is fail-level
- pending decision is manual-review status
- rejected decision is fail-level
- command displays must remain display-only and block unsafe command tokens

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_publication_request_approval_v1`

## Validator

Validator script:

- `tools/release-publication-request-approval/validate_release_publication_request_approval_report.py`

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

A future slice may implement controlled execution-admission handshake after explicit approvals. This v1 request/approval contract remains non-executing.
