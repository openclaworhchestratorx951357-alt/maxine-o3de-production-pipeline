# Screenshot Evidence Extractor v1

## What This Slice Does

This slice adds a safe screenshot evidence extractor that turns controlled screenshot source-index input into a manifest-attachable QC payload.

- script: `tools/screenshot-evidence/extract_screenshot_evidence_index.py`
- source index fixture:
  - `examples/screenshot-evidence/max_biped_v1_screenshot_source_index.json`
- controlled screenshot fixtures:
  - `examples/sandbox/evidence-sources/screenshots/pilot-shot-001.txt`
  - `examples/sandbox/evidence-sources/screenshots/pilot-shot-002.txt`

The extractor is integrated into:

- `tools/release-lane/run_pilot_release_chain_validation.py`

## What This Slice Does Not Do

- does not run Blender
- does not run O3DE
- does not run Asset Processor
- does not spawn/publish
- does not read Cache/live DB

## Extraction Rules

- source index path must remain inside repository root
- screenshot paths must remain under `examples/sandbox`
- blocked path tokens remain blocked (`cache`, `engine`, `.git`, `site-packages`)
- status is:
  - `pass` when minimum required screenshots exist and no errors/warnings
  - `warn` on warning-only findings (exit 0 only with `--allow-warn`)
  - `fail` on any error finding

## Manifest Integration

- current target path: `qc.gates[]`
- future target path: `qc.checks[]`
- check id: `screenshot_evidence_v1`

## Safety Boundary

This is evidence-only extraction from controlled fixture inputs. No runtime execution admissions are added.
