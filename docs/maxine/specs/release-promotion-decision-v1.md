# Release Promotion Decision v1 (Evidence-Only)

## What This Slice Does

`Release promotion decision v1` defines an evidence-only contract for release-lane promotion decisions. It validates whether a package has complete gate evidence and enough manual approvals before release promotion is marked approved.

- validates structured release promotion decision report JSON
- checks required gate completeness against declared promotion policy
- checks required manual approval counts
- checks rollback/cleanup verification flags for approved decisions
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

- `schemas/maxine_release_promotion_decision_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- promotion policy:
  - `contract_id=RELEASE_PROMOTION_DECISION_v1`
  - `required_gate_ids`
  - `required_approvals`
  - `manual_review_required`
  - `evidence_only=true`
  - `runtime_execution_admitted=false`
- decision:
  - `promotion_decision` (`approved|pending|rejected`)
  - `decision_recorded_utc`
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
- pending promotion decisions are manual-review status
- rejected decisions are fail-level

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `release_promotion_decision_v1`

## Validator

Validator script:

- `tools/release-promotion-decision/validate_release_promotion_decision_report.py`

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

A future slice may connect this decision contract to controlled publication orchestration. Publication execution is not implemented in v1.
