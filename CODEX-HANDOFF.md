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
