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

## M.A.X.I.N.E. Resolver Ladder

This repository now contains a read-only, manifest-first resolver ladder that progressively builds non-authoritative evidence from contract recording through final execution gate policy.

- product resolution remains disabled
- authoritative writes remain unimplemented
- execution gate policy exists only as a policy artifact

The next major milestone after PR-stack consolidation is review and acceptance of policy/contracts, not write-capable resolver implementation.

## Phase 1 Operational Baseline

Phase 1 is a read-only operational baseline for the production-control repository.

- the resolver ladder is documented and auditable
- tests pass on consolidated `main`
- authoritative writes remain unimplemented
- the final execution command is intentionally absent

References:

- `docs/audits/PHASE-1-OPERATIONAL-BASELINE.md`
- `docs/roadmap/RESOLVER-LADDER-INDEX.md`
- `docs/o3de-integration/AUTHORITATIVE-EXECUTION-GATE-POLICY.md`
M.A.X.I.N.E. production pipeline for O3DE character, asset, prefab, QC, and automation workflows.
