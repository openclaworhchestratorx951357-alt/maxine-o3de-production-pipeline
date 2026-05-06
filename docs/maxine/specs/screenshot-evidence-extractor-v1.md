# Screenshot Evidence Extractor v1

## What This Slice Does

This slice validates controlled screenshot/visual evidence into a manifest-attachable QC payload.

- script: `tools/screenshot-evidence/extract_screenshot_evidence_index.py`
- primary report schema:
  - `schemas/maxine_screenshot_evidence_report.schema.json`
- controlled-real fixture used by release-lane runner:
  - `examples/sandbox/visual-evidence/pilot-candidates/max_biped_v1_visual_evidence_controlled_real.fixture.json`
- representative pass/warn/fail fixtures:
  - `examples/screenshot-evidence/max_biped_v1_visual_evidence_pass.json`
  - `examples/screenshot-evidence/max_biped_v1_visual_evidence_warn.json`
  - `examples/screenshot-evidence/max_biped_v1_visual_evidence_fail.json`
- controlled screenshot reference fixtures:
  - `examples/sandbox/evidence-sources/screenshots/pilot-shot-001.txt`
  - `examples/sandbox/evidence-sources/screenshots/pilot-shot-002.txt`
  - `examples/sandbox/evidence-sources/screenshots/pilot-shot-003.txt`
  - `examples/sandbox/evidence-sources/screenshots/pilot-shot-004.txt`
  - `examples/sandbox/evidence-sources/screenshots/pilot-shot-005.txt`

The extractor remains integrated in:

- `tools/release-lane/run_pilot_release_chain_validation.py`

## Visual Contract Coverage

The report contract now carries controlled-real visual metadata, including:

- candidate/source evidence references
- evidence class and claim status
- screenshot set and required view coverage (`front`, `side`, `back`, `three_quarter`, `detail`)
- visual quality statuses (resolution/material/UV/silhouette/identity/review frame)
- blocked safety statuses (screenshot capture, O3DE, Editor/runtime, DCC/Blender, AP, production writes)

Legacy source-index fixtures remain supported for non-breaking compatibility, but the pilot release-lane runner now uses controlled-real visual report fixtures.

## What This Slice Does Not Do

- does not capture live screenshots
- does not run O3DE or launch Editor/runtime
- does not run Asset Processor
- does not run Blender/DCC
- does not spawn/publish
- does not read Cache/live DB

## Validation Rules

- fixture path must remain inside repository root
- screenshot reference paths must remain under `examples/sandbox`
- blocked path tokens remain blocked (`cache`, `engine`, `.git`, `site-packages`)
- required views are enforced for controlled-real evidence
- status is:
  - `pass` when checks pass and no warnings/errors
  - `warn` on warning-only findings (exit 0 only with `--allow-warn`)
  - `fail` on any error finding

## Manifest Integration

- current target path: `qc.gates[]`
- future target path: `qc.checks[]`
- check id: `screenshot_evidence_v1`

## Safety Boundary

This is evidence-only validation from controlled fixture/import inputs. No screenshot capture or runtime execution admissions are added.
