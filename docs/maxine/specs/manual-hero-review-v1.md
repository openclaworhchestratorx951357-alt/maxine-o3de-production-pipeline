# Manual Hero Review v1 (Evidence-Only)

## What This Slice Does

`Manual hero review v1` defines an evidence-only contract for release-lane human review gating for hero-tier characters.

- validates structured manual-review report JSON
- enforces hero-tier manual gate requirements
- checks required evidence attachment completeness
- checks approval/rejection state consistency
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute Blender
- does not execute O3DE
- does not execute Asset Processor
- does not perform runtime spawning or publishing
- does not read Cache or live asset databases
- does not mutate source art assets

## Report Contract

Schema:

- `schemas/maxine_manual_hero_review_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- review scope:
  - `review_contract_id=MANUAL_HERO_REVIEW_v1`
  - `target_tier=hero`
  - `required_reviewers`
  - `required_evidence_ids`
  - `evidence_only=true`
  - `runtime_execution_admitted=false`
- review decision:
  - `review_required`
  - `review_state` (`not_required|pending|approved|rejected`)
  - `reviewer_count`
  - `approver_ids`
  - `attached_evidence_ids`
  - `missing_evidence_ids`
  - `rejection_reasons`
  - optional `approved_at_utc`
- findings
- manifest attachment payload

## Validation Logic

- Hero tier requires manual review gate.
- Missing required evidence is fail-level.
- `approved` requires enough reviewers/approvers and no rejection reasons.
- `rejected` requires explicit rejection reasons.
- `pending` emits manual-review status for operator follow-up.

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `manual_hero_review_v1`

## Validator

Validator script:

- `tools/manual-hero-review/validate_manual_hero_review_report.py`

Behavior:

- exits `0` on `pass`
- exits `0` on `warn` only with `--allow-warn`
- exits nonzero on `pending_manual`
- exits nonzero on `fail`

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

A future slice may attach this gate directly to release promotion controls. That promotion execution path is not implemented in v1.
