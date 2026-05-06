# Controlled Real Evidence Inventory v1

`controlled_real_evidence_inventory_v1` is an inventory-only release-lane report.

It enumerates approved local input candidates and linked sandbox evidence sources from:

- project inventory (`examples/sandbox/project-inventory/...`)
- asset candidate inventory (`examples/sandbox/asset-candidates/...`)

This slice does not admit real execution.

## Command

```powershell
python tools/release-lane/report_controlled_real_evidence_inventory.py
```

Optional inputs/output:

```powershell
python tools/release-lane/report_controlled_real_evidence_inventory.py --project-inventory examples/sandbox/project-inventory/max_biped_v1_project_inventory.fixture.json --asset-candidate-inventory examples/sandbox/asset-candidates/max_biped_v1_asset_candidate_inventory.fixture.json --output examples/sandbox/manifests/reports/pilot-release-chain-proof/controlled-real-evidence-inventory.json
```

## Contract

- report type: `CONTROLLED_REAL_EVIDENCE_INVENTORY_v1_REPORT`
- current manifest attachment target reference: `qc.gates[]`
- future manifest attachment target reference: `qc.checks[]`
- inventory mode: `approved_local_inputs_and_evidence_sources_only`
- execution remains unadmitted (`execution_admitted=false`)

## Safety Boundaries

The report preserves blocked surfaces:

- no O3DE execution
- no real Asset Processor execution
- no Blender/DCC execution
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production path writes
- no engine path writes

## Proof Integration

`python tools/release-lane/prove_pilot_release_chain.py` now runs this reporter and records:

- `examples/sandbox/manifests/reports/pilot-release-chain-proof/controlled-real-evidence-inventory.json`

This keeps controlled real evidence inventory visible in the release-lane proof flow while execution remains blocked.
