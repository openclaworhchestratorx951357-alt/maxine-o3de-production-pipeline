# Animation Smoke v1 (Evidence-Only)

## What This Slice Does

`Animation smoke v1` defines an evidence-only contract for reporting clip-level smoke readiness in the release lane.

- validates structured animation smoke report JSON
- checks required clip presence against reported available clips
- checks clip count consistency
- checks loop/pose/root-motion status fields
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute animation runtimes
- does not execute O3DE
- does not execute Asset Processor
- does not execute Blender/DCC tools
- does not capture screenshots
- does not spawn/publish
- does not read Cache or live asset databases

## Report Contract

Schema:

- `schemas/maxine_animation_smoke_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source evidence: `source_path`, `source_kind`, optional `sha256`
- smoke profile:
  - `smoke_contract_id=ANIMATION_SMOKE_v1`
  - `target_skeleton_contract_id=MAX_BIPED_v1`
  - `evidence_only=true`
  - `runtime_execution_admitted=false`
- animation summary:
  - `required_clips`
  - `present_clips`
  - `missing_clips`
  - `clip_count`
  - `loop_playback_status`
  - `pose_stability_status`
  - `root_motion_status`
- findings
- manifest attachment payload

## Validation Logic

- Missing required clips are fail-level.
- `clip_count` mismatch is warning-level.
- `loop_playback_status`, `pose_stability_status`, `root_motion_status` are interpreted as:
  - `fail` -> fail-level finding
  - warning-state values (`warn`, `unknown`) -> warning-level finding

## Manifest Integration

Current target path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `animation_smoke_v1`

## Validator

Validator script:

- `tools/animation-smoke/validate_animation_smoke_report.py`

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

A future slice may consume runtime playback evidence from controlled execution surfaces. That path is not implemented in v1.
