# M.A.X.I.N.E. O3DE Production Pipeline

M.A.X.I.N.E. means **Multimodal Autonomous eXpressive Intelligence and Narrative Entity**.

This repository is the standalone **production-control repository** for M.A.X.I.N.E. O3DE character and media pipeline automation. It is where we define the contracts, manifests, validation gates, operator flows, and automation wrappers that move draft outputs into release-ready packages.

## First Milestone

The first milestone is to evolve the current working character factory into a:

- manifest-first
- prefab-first
- QC-gated

production pipeline that can be audited, retried safely, and rolled back.

## Current Pipeline Lanes

- photo to draft mesh
- text prompt to draft mesh
- photo/text to rig-prep
- rigged FBX import
- O3DE prefab/actor publication
- queue automation
- evidence and validation

## What This Repo Is Not

- not a full O3DE engine fork
- not a place for secrets
- not a raw asset dump

## Quick Start

Validate a manifest:

```powershell
python tools/manifest-validator/validate_manifest.py examples/manifests/example-draft-mesh.manifest.json
```

Run tests:

```powershell
python -m pytest tests/pytest
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\Test-MaxineManifest.ps1 -ManifestPath .\examples\manifests\example-draft-mesh.manifest.json
```

Inspect examples:

```powershell
Get-ChildItem .\examples\jobs
Get-ChildItem .\examples\manifests
```
M.A.X.I.N.E. production pipeline for O3DE character, asset, prefab, QC, and automation workflows.
