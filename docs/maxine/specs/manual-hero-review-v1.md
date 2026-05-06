# Manual Hero Review v1 (Evidence-Only)

## What This Slice Does

`manual_hero_review_v1` defines an evidence-only contract for release-lane human review gating for hero-tier candidates.

- validates structured manual-review JSON reports
- requires hero-tier review to reference required controlled-real gate evidence
- validates decision/recommendation consistency and waiver policy
- emits manifest-attachable QC output

## What This Slice Does Not Do

- does not execute O3DE, Editor, runtime, Asset Processor, Blender, or DCC
- does not capture live screenshots
- does not spawn/publish
- does not access Cache/live asset DB
- does not create authoritative source UUID / Asset ID / Product ID claims
- does not admit execution or publication

## Report Contract

Schema:

- `schemas/maxine_manual_hero_review_report.schema.json`

Core fields include:

- identity/routing: `job_id`, `package_id`, `lane`, `candidate_id`, `review_id`
- review profile: `review_profile_id`, `review_profile_version`, `review_tier`
- reviewer identity: `reviewer_identity_status`, `reviewer_name_or_handle`, `review_timestamp`
- evidence references: `reviewed_evidence_refs`, `required_evidence_present_status`
- quality statuses: visual/material/skeleton/animation/scale/package readiness
- review governance: `waiver_status`, `waiver_reasons`, `reviewer_findings`, `decision`, `release_recommendation`
- claim/safety posture: `claim_status`, blocked execution/write safety fields
- manifest attachment payload

Required hero evidence refs:

- `dcc_conform_v1`
- `max_biped_v1_skeleton_contract`
- `material_uv_qc_v1`
- `animation_smoke_v1`
- `screenshot_evidence_v1`
- `source_product_evidence_resolver_v1`

## Validation Logic

- Hero tier must reference all required controlled-real evidence gates.
- Missing required evidence is fail-level or pending-manual depending on decision state.
- `pass` requires approved reviewer identity, complete required evidence, and no blocking findings.
- `warn` requires non-blocking concerns only and explicit warning/waiver signal.
- `fail` requires blocking quality or evidence findings.
- `pending_manual` requires an explicit pending signal.
- Manual review cannot admit execution or publication.

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

This slice is review-workflow validation only and keeps blocked/unadmitted surfaces:

- no O3DE execution
- no Editor/runtime execution
- no Asset Processor execution
- no Blender/DCC execution
- no live screenshot capture
- no spawn/publish
- no Cache/live DB access
- no authoritative source/product identity claims
