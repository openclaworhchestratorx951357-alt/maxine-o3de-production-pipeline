# Release-Lane Evidence Admission Status v1

`release_lane_evidence_admission_status_v1` is an integration status report for the pilot release lane.

It does not add a new QC gate. It summarizes:

- full-chain gate presence/pass state from the pilot manifest
- evidence class split per gate (`fixture`, `manual`, `imported`, `controlled_real`, `future`)
- execution-admission posture (`execution_admitted=false` in current evidence-only phase)
- concrete remaining gaps before AAA operational execution claims

## Command

```powershell
python tools/release-lane/report_release_lane_evidence_admission_status.py --manifest examples/manifests/example-release-character-pilot-chain.manifest.json
```

Optional output file:

```powershell
python tools/release-lane/report_release_lane_evidence_admission_status.py --manifest examples/manifests/example-release-character-pilot-chain.manifest.json --output examples/sandbox/manifests/reports/release-lane-evidence-admission-status.json
```

## Contract

- report type: `RELEASE_LANE_EVIDENCE_ADMISSION_STATUS_v1_REPORT`
- current manifest attachment target reference: `qc.gates[]`
- future manifest attachment target reference: `qc.checks[]`
- scope: evidence-only reporting
- does not admit O3DE, Asset Processor, Blender/DCC, spawn, or publish execution

## Current Expected Outcome

For the representative pilot fixture:

- `overall_release_lane_state = controlled_evidence_ready_execution_blocked`
- required release-lane gate chain can be pass-complete
- controlled real evidence is present for `max_biped_v1_skeleton_contract`, `dcc_conform_v1`, `material_uv_qc_v1`, and `animation_smoke_v1`
- explicit approved execution-admission remains missing

This report provides the deterministic status statement required before any execution-admission discussion.

## CI Proof Integration

`python tools/release-lane/prove_pilot_release_chain.py` now runs this reporter against the strict-run generated pilot manifest and records the artifact at:

- `examples/sandbox/manifests/reports/pilot-release-chain-proof/release-lane-evidence-admission-status.json`

This keeps pilot-chain proof and evidence/admission posture in one deterministic validation command.
