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

## Next Slice After AP Source Identity Matching

Implement candidate product matching for rows linked to a candidate source row, requiring source match evidence plus expected product contract type, still without marking products resolved.

Safety note:
Source identity candidate match is required before product candidate matching, but it is still not enough to publish or resolve products.

## Next Slice After AP Product Candidate Matching

Implement product file existence validation for candidate product rows, using safe path normalization and project/cache roots, still without resolving products until file existence plus product type plus source identity are all proven.

Safety note:
Product candidate rows are not enough. Require file existence and product contract validation before any product can move toward resolved.

## Next Slice After AP Product File Validation

Implement non-authoritative resolver readiness gate that combines source identity, product candidate, and file existence evidence into a single readiness report, still without marking products resolved.

Safety note:
Readiness is not resolution. A future authoritative resolver must still verify platform, AP job status, and product identity before writing resolved products.

## Next Slice After AP Resolver Readiness Gate

Implement authoritative-resolution design document and dry-run contract for the first future write-capable resolver, but keep implementation read-only until platform/job-state/product freshness checks are defined.

Safety note:
Do not implement resolved product writes until authoritative AP product identity, platform, job status, and freshness checks are specified and tested.

## Next Slice After Authoritative Resolver Dry-Run Contract

Design AP job-state proof by discovering read-only job/status fields from the AP database schema and row samples, without marking products resolved.

Safety note:
Job-state proof must remain read-only. Do not resolve products from stale or failed AP jobs.

## Next Slice After AP Job-State Proof

Implement platform proof extraction from candidate product/job rows and path evidence, still read-only and still without resolving products.

## Next Slice After AP Platform Proof

Implement product freshness proof extraction using timestamps from source rows, product rows, file metadata, and job-state evidence, still read-only and still without resolving products.

## Next Slice After AP Product Freshness Proof

Implement product identity proof design using product type, source identity, platform, job-state, freshness, and file evidence, still read-only and still without resolving products.
