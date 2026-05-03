# CODEX Handoff

## Current Repository Purpose

This repository is the production-control home for the M.A.X.I.N.E. O3DE pipeline. It is intended to coordinate job contracts, manifests, QC policy, evidence, and publication automation across draft and release lanes without embedding the full O3DE engine source.

## Next Implementation Slice

Wrap the existing Codex-built MaxineShow character factory with a manifest-first adapter without changing the existing working scripts.

## Safety Rules for Next Slice

- read existing scripts first
- do not rewrite working queue system
- add adapter layer first
- preserve backward compatibility
- every new job emits manifest
- failed jobs emit manifest too

## Exact Next Files to Create

- `scripts/powershell/Invoke-MaxineJob.ps1`
- `scripts/powershell/New-MaxineManifest.ps1`
- `scripts/powershell/Write-MaxineEvidence.ps1`
- `tools/asset-resolver/README.md`
- `tools/qc-runner/README.md`

## Slice 2 Complete Criteria

- `Invoke-MaxineJob.ps1` exists
- `New-MaxineManifest.ps1` exists
- `Write-MaxineEvidence.ps1` exists
- DryRun generates manifest and evidence
- Failures still generate manifest
- Existing factory scripts were not modified

## Next Slice After Asset Resolver POC

Implement real O3DE Asset Processor query adapter or CLI-backed product discovery, using source identity and product types, still without spawn/publish side effects.

## Next Slice After Filesystem Probe Adapter

Implement real Asset Processor metadata discovery from official O3DE data sources, starting with read-only discovery of Asset Processor database/log/config locations.

## Next Slice After AP Metadata Discovery

Implement read-only Asset Processor database inspection against discovered database candidates, extracting source/product table names and schema shape only, without modifying the database and without claiming product resolution yet.

Safety note:
Do not open SQLite databases for writes. Use read-only mode only when database inspection begins.

## Next Slice After AP DB Schema Inspection

Implement read-only source/product row mapping for known AP database schema candidates, still without marking products resolved until source UUID/product type matching is proven.

Safety note:
Do not write to Asset Processor databases. Do not infer product validity from row presence alone.

## Next Slice After AP Row Mapping

Implement source identity matching rules that compare manifest source asset input against AP database source rows, using normalized paths and UUID-like fields, still without resolving products.

Safety note:
Candidate row matches are not product resolution. Require explicit source identity proof before product matching.
