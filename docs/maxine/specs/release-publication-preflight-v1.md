# Release Publication Preflight v1 (Evidence-Only)

## What This Slice Does

`Release publication preflight v1` defines an evidence-only contract that validates whether a release package is publication-ready under explicit manual approval boundaries.

- validates structured release publication preflight report JSON
- checks required QC gate completeness before publication readiness
- checks manual approval counts and decision consistency
- checks display-only publication and rollback command plans
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute O3DE
- does not execute Asset Processor
- does not execute Blender/DCC tools
- does not publish packages
- does not spawn runtime entities
- does not read Cache or live asset databases
- does not perform destructive cleanup

## Report Contract

Schema:

- `schemas/maxine_release_publication_preflight_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- preflight contract:
  - `contract_id=RELEASE_PUBLICATION_PREFLIGHT_v1`
  - `required_gate_ids`
  - `required_approvals`
  - `manual_review_required`
  - `explicit_publication_approval_required=true`
  - `evidence_only=true`
  - `execution_admitted=false`
- publication plan:
  - `publication_mode=non_executing_preflight_only`
  - `publish_command_display` (display-only)
  - `rollback_command_display` (display-only)
  - `planned_target_environment`
  - `no_command_execution_recorded=true`
  - `dry_run_evidence_paths`
- decision context:
  - `proposed_decision` (`approved|pending|rejected`)
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
- pending proposed decision is manual-review status
- rejected proposed decision is fail-level
- command displays must remain display-only and block unsafe command tokens

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_publication_preflight_v1`

## Validator

Validator script:

- `tools/release-publication-preflight/validate_release_publication_preflight_report.py`

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
- no spawn/publish
- no Cache/live DB access
- no source/product UUID claims
- no new generation lanes
- no destructive cleanup

## Future Path (Not Implemented Here)

A future slice may add explicit publication request/approval orchestration and then a separate admission slice for controlled publish execution. This preflight v1 does not admit execution.
