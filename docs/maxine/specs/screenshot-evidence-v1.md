# Screenshot Evidence v1 (Evidence-Only)

## What This Slice Does

`Screenshot evidence v1` defines an evidence-only contract for validating screenshot-capture readiness reports in the release lane.

- validates structured screenshot evidence report JSON
- checks required view coverage against captured view records
- checks screenshot path safety boundaries for manifest-linked artifacts
- checks minimum resolution policy with explicit warning/error/manual-review severity
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute Blender
- does not execute O3DE
- does not execute Asset Processor
- does not run real screenshot capture tools
- does not spawn or publish
- does not read Cache or live asset databases

## Report Contract

Schema:

- `schemas/maxine_screenshot_evidence_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source.source_path`, `source.source_kind`, optional `source.sha256`
- capture profile:
  - `capture_contract_id=SCREENSHOT_EVIDENCE_v1`
  - `target_skeleton_contract_id=MAX_BIPED_v1`
  - `required_view_ids`
  - `evidence_only=true`
  - `runtime_execution_admitted=false`
  - `min_width`, `min_height`, `low_resolution_severity`
- screenshot summary:
  - `captured_view_ids`
  - `missing_view_ids`
  - `screenshot_paths[]` with `view_id`, `path`, `width`, `height`, `format`
  - `invalid_screenshot_paths`
- findings
- manifest attachment payload

## Validation Logic

- Missing required views are fail-level.
- Unsafe screenshot paths are fail-level.
- Low-resolution screenshots emit findings using `low_resolution_severity`.
- Declared report `status` must match computed finding severity.

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `screenshot_evidence_v1`

## Validator

Validator script:

- `tools/screenshot-evidence/validate_screenshot_evidence_report.py`

Behavior:

- exits `0` on `pass`
- exits `0` on `warn` only with `--allow-warn`
- exits nonzero on `warn` without `--allow-warn`
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

A future bounded slice may attach controlled runtime screenshot-capture evidence. That execution path is not implemented in v1.
