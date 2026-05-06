# Controlled Real Visual Evidence v1

## Summary

This slice promotes `screenshot_evidence_v1` from fixture-only extraction to controlled-real screenshot/visual evidence validation.

- check id: `screenshot_evidence_v1`
- manifest attachment now: `qc.gates[]`
- future manifest attachment: `qc.checks[]`
- execution posture: blocked (evidence-only)

## Implemented Inputs

- controlled-real visual evidence fixture:
  - `examples/sandbox/visual-evidence/pilot-candidates/max_biped_v1_visual_evidence_controlled_real.fixture.json`
- pass/warn/fail examples:
  - `examples/screenshot-evidence/max_biped_v1_visual_evidence_pass.json`
  - `examples/screenshot-evidence/max_biped_v1_visual_evidence_warn.json`
  - `examples/screenshot-evidence/max_biped_v1_visual_evidence_fail.json`
- report schema:
  - `schemas/maxine_screenshot_evidence_report.schema.json`
- validator:
  - `tools/screenshot-evidence/extract_screenshot_evidence_index.py`

## Evidence Coverage

The report contract covers:

- candidate and source evidence references
- visual profile id/version
- evidence class (`fixture`, `imported`, `controlled_real`)
- screenshot set id, screenshot refs, screenshot count
- required view coverage for:
  - `front`
  - `side`
  - `back`
  - `three_quarter`
  - `detail`
- visual status dimensions:
  - resolution
  - file reference integrity
  - identity/silhouette/scale/material/UV texture checks
  - skeleton/animation pose visual checks
  - missing asset/corruption/lighting/viewport/review frame checks
- claim status:
  - `evidence_only`
  - `not_authoritative`
- blocked safety statuses:
  - screenshot capture blocked
  - O3DE/Editor/runtime blocked
  - DCC/Blender blocked
  - Asset Processor blocked
  - production writes blocked

## Release-Lane Integration

`tools/release-lane/run_pilot_release_chain_validation.py` now validates:

- `examples/sandbox/visual-evidence/pilot-candidates/max_biped_v1_visual_evidence_controlled_real.fixture.json`

and attaches the resulting `screenshot_evidence_v1` payload into manifest QC gates.

`tools/release-lane/report_release_lane_evidence_admission_status.py` now classifies:

- `screenshot_evidence_v1` as `controlled_real`.

## Safety Posture

No execution is admitted.

- no live screenshot capture
- no O3DE execution
- no Editor/runtime execution
- no Asset Processor execution
- no Blender/DCC execution
- no spawn/publish
- no Cache/live DB access
- no authoritative Source UUID / Asset ID / Product ID claims
- no production/engine path writes
