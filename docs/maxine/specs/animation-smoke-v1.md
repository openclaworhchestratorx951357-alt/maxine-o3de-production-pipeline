# Animation Smoke v1 (Evidence-Only)

## What This Slice Does

`Animation smoke v1` defines an evidence-only contract for reporting clip-level smoke readiness in the release lane.

- validates structured animation smoke report JSON
- validates controlled-real metadata for candidate/source/profile/skeleton linkage
- validates required clip presence against reported available clips
- validates clip count consistency and per-dimension readiness statuses
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

Core controlled-real fields:

- identity/reference:
  - `candidate_id`
  - `source_asset_reference`
  - `source_evidence_ref`
- profile:
  - `animation_profile_id=ANIMATION_SMOKE_v1`
  - `animation_profile_version`
  - `evidence_class` (`fixture|imported|controlled_real`)
- asset links:
  - `actor_asset_reference`
  - `motion_asset_reference`
  - optional `motion_set_reference`
  - optional `anim_graph_reference`
- skeleton compatibility:
  - `skeleton_profile_id=MAX_BIPED_v1`
  - `skeleton_compatibility_status`
  - `bind_pose_compatibility_status`
  - `root_motion_status`
- clip/readiness statuses:
  - `clip_count`
  - `smoke_clip_names`
  - `clip_duration_status`
  - `missing_clip_status`
  - `retarget_readiness_status`
  - optional `loopability_status`
  - optional `motion_event_status`
  - `frame_range_status`
  - `animation_budget_status`
- claim/safety:
  - `claim_status` (`evidence_only|not_authoritative`)
  - `dcc_execution_status=blocked`
  - `blender_execution_status=blocked`
  - `o3de_execution_status=blocked`
  - `asset_processor_execution_status=blocked`
  - `runtime_playback_status=blocked`
  - `production_write_status=blocked`

Legacy summary fields remain validated for continuity:

- `required_clips`
- `present_clips`
- `missing_clips`
- summary clip/status dimensions

## Validation Logic

- At least one smoke-test clip must be present.
- Missing required clips are fail-level.
- Clip-count mismatch is warning-level.
- Summary clip data and top-level smoke clip data are cross-checked.
- `controlled_real` reports must reference sandbox evidence roots.
- All execution/runtime safety statuses must remain `blocked`.

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
- no runtime playback execution
- no spawn/publish
- no Cache/live DB access
- no source/product UUID claims
- no destructive cleanup
