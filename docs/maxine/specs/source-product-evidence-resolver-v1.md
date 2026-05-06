# Source Product Evidence Resolver v1 (Evidence-Only)

## What This Slice Does

`Source Product Evidence Resolver v1` defines an evidence-only deterministic mapping contract from one source asset reference to expected and observed product evidence.

- validates structured source->product evidence report JSON
- checks required expected product coverage
- checks optional product coverage as warning-level gaps
- enforces blocked claim/access status surfaces
- emits manifest-attachable QC output

## What This Slice Does Not Do Yet

- does not execute Blender or DCC tools
- does not execute O3DE
- does not execute Asset Processor
- does not read live Cache
- does not read live asset database
- does not claim authoritative Source UUID, Asset ID, or Product ID
- does not spawn or publish

## Report Contract

Schema:

- `schemas/maxine_source_product_evidence_resolver_report.schema.json`

Core fields:

- identity/routing: `job_id`, `package_id`, `lane`, `status`
- source reference: `source_asset_reference`, `source_asset_path`
- evidence source type: `fixture`, `imported_ap_evidence`, `future_asset_system_query`
- expected products:
  - `actor`
  - `motion`
  - `procprefab`
  - `azmodel`
  - `material`
  - `texture`
  - `pxmesh`
- observed products:
  - `product_type`
  - `product_path_or_hint`
  - `evidence_status`
  - `evidence_source`
  - `confidence`
- claim/access state guards:
  - `source_uuid_claim_status`
  - `asset_id_claim_status`
  - `product_id_claim_status`
  - `cache_access_status`
  - `live_db_access_status`
- structured findings
- manifest attachment payload

## Validation Logic

- required expected product missing -> fail
- optional expected product missing -> warn
- low-confidence observed product evidence -> warn
- future admission claim status while blocked -> fail
- cache/live DB access not blocked -> fail
- report/status mismatch -> fail

## Manifest v1 Integration

Current attachment path:

- `qc.gates[]`

Future-compatible path:

- `qc.checks[]`

QC check id:

- `source_product_evidence_resolver_v1`

## Bounded Extraction Input (v1)

The pilot release-chain runner now generates resolver input from admitted sources before validating this report contract:

- `tools/release-lane/extract_source_product_evidence_resolver_report.py`
- controlled inventory records
- approved local input candidate inventory
- optional imported AP evidence import records
- fixture-backed hints when imported AP evidence is absent

## Validator

Validator script:

- `tools/source-product-evidence-resolver/validate_source_product_evidence_resolver_report.py`

Behavior:

- exits `0` on `pass`
- exits `0` on `warn` only with `--allow-warn`
- exits nonzero on `warn` without `--allow-warn`
- exits nonzero on `fail`

## Safety Boundaries

This slice is report-validation-only and preserves blocked/unadmitted surfaces:

- no O3DE execution
- no real or broad Asset Processor execution
- no Blender/DCC execution
- no spawn/publish
- no Cache/live DB access
- no source/product UUID authoritative claims
- no new generation lanes
- no destructive cleanup

## Future Path (Not Implemented Here)

A future explicit admission slice may permit bounded deterministic query sources beyond fixtures/imported AP evidence. That admission is not implemented here.
