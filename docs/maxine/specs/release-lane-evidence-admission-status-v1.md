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

- `overall_release_lane_state = evidence_only_pre_production`
- required release-lane gate chain can be pass-complete
- controlled real evidence remains missing
- explicit approved execution-admission remains missing

This report provides the deterministic status statement required before any execution-admission discussion.
