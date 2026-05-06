# Manual Hero Review Controlled-Real Evidence v1

## Summary

This slice hardens `manual_hero_review_v1` so hero-tier review must reference required controlled-real release-lane evidence gates.

- check id: `manual_hero_review_v1`
- manifest attachment now: `qc.gates[]`
- future manifest attachment: `qc.checks[]`
- execution/publication posture: blocked (evidence-only review workflow)

## Implemented Inputs

- controlled-real hero review fixture used by pilot runner:
  - `examples/sandbox/manual-hero-review-evidence/pilot-candidates/max_biped_v1_manual_hero_review_controlled_real.fixture.json`
- pass/warn/fail/pending examples:
  - `examples/manual-hero-review/max_biped_v1_manual_hero_review_pass.json`
  - `examples/manual-hero-review/max_biped_v1_manual_hero_review_warn.json`
  - `examples/manual-hero-review/max_biped_v1_manual_hero_review_fail.json`
  - `examples/manual-hero-review/max_biped_v1_manual_hero_review_pending.json`
- schema:
  - `schemas/maxine_manual_hero_review_report.schema.json`
- validator:
  - `tools/manual-hero-review/validate_manual_hero_review_report.py`

## Required Hero Evidence References

Hero-tier review now requires references to:

- `dcc_conform_v1`
- `max_biped_v1_skeleton_contract`
- `material_uv_qc_v1`
- `animation_smoke_v1`
- `screenshot_evidence_v1`
- `source_product_evidence_resolver_v1`

Missing required references fail the review or keep it pending manual depending on decision state.

## Contract Highlights

The report includes:

- reviewer identity, timestamp, review tier, and review profile metadata
- reviewed evidence references and required-evidence-present status
- visual/material/skeleton/animation/scale/package quality statuses
- explicit waiver state and waiver reasons
- decision and release recommendation consistency
- claim status (`evidence_only` or `not_authoritative`)
- blocked safety statuses for execution surfaces and production writes

## Release-Lane Integration

`tools/release-lane/run_pilot_release_chain_validation.py` now validates manual hero review from:

- `examples/sandbox/manual-hero-review-evidence/pilot-candidates/max_biped_v1_manual_hero_review_controlled_real.fixture.json`

The resulting `manual_hero_review_v1` payload is attached to manifest QC gates and remains classified as manual evidence in release-lane evidence admission reporting.

## Safety Posture

No execution or publication is admitted.

- no O3DE execution
- no Editor/runtime execution
- no real/broad Asset Processor execution
- no Blender/DCC execution
- no live screenshot capture
- no spawn/publish
- no Cache/live DB access
- no authoritative Source UUID / Asset ID / Product ID claims
- no production/engine path writes
