# Source Product Evidence Real Extraction v1 (Bounded, Non-Executing)

## What This Slice Adds

This slice adds a bounded extraction step that builds the resolver report using admitted evidence sources only:

- controlled real evidence inventory report
- approved local input inventories
- optional imported AP evidence import records
- sandbox evidence links carried by candidate inventory
- fixture-backed resolver hints as non-authoritative fallback

No execution is admitted in this slice.

## Command

```powershell
python tools/release-lane/extract_source_product_evidence_resolver_report.py
```

Optional inputs/output:

```powershell
python tools/release-lane/extract_source_product_evidence_resolver_report.py --project-inventory examples/sandbox/project-inventory/max_biped_v1_project_inventory.fixture.json --asset-candidate-inventory examples/sandbox/asset-candidates/max_biped_v1_asset_candidate_inventory.fixture.json --controlled-inventory-report examples/controlled-real-evidence-inventory/max_biped_v1_controlled_real_evidence_inventory_pass.json --output examples/sandbox/manifests/reports/pilot-release-chain-proof/source-product-evidence-resolver-extracted.json
```

## Runner Integration

`tools/release-lane/run_pilot_release_chain_validation.py` now:

1. generates controlled inventory report
2. extracts source/product resolver report from admitted sources
3. validates the extracted resolver report with:
   - `tools/source-product-evidence-resolver/validate_source_product_evidence_resolver_report.py`
4. attaches the resulting QC gate payload to the pilot manifest

## Safety Boundaries Preserved

- no O3DE execution
- no real/broad Asset Processor execution
- no Blender/DCC execution
- no spawn/publish
- no Cache/live DB access
- no authoritative source UUID / Asset ID / Product ID claims
- no production/engine writes

## Evidence Source Notes

- `evidence_source_type=imported_ap_evidence` when admitted AP import records provide product-like mentions.
- otherwise `evidence_source_type=fixture` with fixture-backed resolver hints.
- both paths remain non-authoritative and non-executing.
