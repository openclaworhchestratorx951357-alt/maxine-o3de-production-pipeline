# CI Artifact Retention v1 (Evidence-Only)

## What This Slice Does

`CI artifact retention v1` defines an evidence-only contract for validating release-lane artifact retention and QC-gate completeness.

- validates structured CI artifact retention report JSON
- checks retention policy compliance (required vs recommended duration)
- checks required artifact presence under a declared artifact root
- checks release-lane QC gate completeness
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not run O3DE
- does not run Asset Processor
- does not run Blender/DCC tools
- does not spawn or publish
- does not read Cache or live asset databases
- does not mutate production assets

## Report Contract

Schema:

- `schemas/maxine_ci_artifact_retention_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- retention policy:
  - `policy_id=CI_ARTIFACT_RETENTION_v1`
  - `retention_class`
  - `min_required_days`
  - optional `recommended_days`
  - `actual_retention_days`
  - `evidence_only=true`
  - `runtime_execution_admitted=false`
- artifact inventory:
  - `artifact_root`
  - `required_artifact_paths`
  - `present_artifact_paths`
  - `missing_artifacts`
  - `disallowed_artifact_paths`
- release validation:
  - `required_qc_gate_ids`
  - `present_qc_gate_ids`
  - `missing_qc_gate_ids`
  - `release_readiness_state`
  - `manual_review_required`
- findings
- manifest attachment payload

## Validation Logic

- Retention below required days is fail-level.
- Retention below recommended days (while still meeting required days) is warn-level.
- Missing required artifacts is fail-level.
- Disallowed artifact paths are fail-level.
- Missing required QC gate IDs is fail-level.
- Report status must match computed findings.

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `ci_artifact_retention_v1`

## Validator

Validator script:

- `tools/ci-artifact-retention/validate_ci_artifact_retention_report.py`

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

A future slice may connect this contract to CI retention jobs and release package promotion controls. That execution surface is not implemented in v1.
