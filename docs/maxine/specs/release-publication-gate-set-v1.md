# Release Publication Gate Set v1

## Purpose

`release_publication_gate_set_v1` verifies that a release-lane manifest has a complete, deterministic QC gate chain before publication can be considered ready.

This slice is evidence-only:

- no O3DE execution
- no Asset Processor execution
- no spawn/publish admission
- no Cache or live DB access

## Inputs

- Manifest JSON path (`job.lane`, `identity`, `qc.gates[]`) to derive a gate-set report.
- Or a prebuilt gate-set report JSON (`report_type = RELEASE_PUBLICATION_GATE_SET_v1_REPORT`) for report-only validation.

## Validator

- `tools/release-publication-gate-set/validate_release_publication_gate_set_report.py`

The validator:

- checks required release-publication gate IDs in `qc.gates[]`
- enforces deterministic order across the required gate chain
- enforces hero-tier inclusion of `manual_hero_review_v1`
- surfaces warn/fail/pending_manual gate results as blocking evidence
- emits a structured report and manifest-attachable payload
- accepts either manifest input (derive + validate) or report input (validate-only)

## Report Contract

- `schemas/maxine_release_publication_gate_set_report.schema.json`
- `report_type = RELEASE_PUBLICATION_GATE_SET_v1_REPORT`
- `check_id = release_publication_gate_set_v1`
- manifest attachment:
  - current target: `qc.gates[]`
  - future target: `qc.checks[]`

## Golden Examples

- `examples/release-publication-gate-set/max_biped_v1_release_publication_gate_set_pass.json`
- `examples/release-publication-gate-set/max_biped_v1_release_publication_gate_set_warn.json`
- `examples/release-publication-gate-set/max_biped_v1_release_publication_gate_set_fail.json`

Manifest fixtures used by validator tests:

- `examples/manifests/example-release-publication-gate-set-pass.manifest.json`
- `examples/manifests/example-release-publication-gate-set-warn.manifest.json`
- `examples/manifests/example-release-publication-gate-set-fail.manifest.json`
