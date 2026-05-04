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

## Phase 2 Sandbox-Only Write Prototype Design

Phase 2 is design-only.

- no sandbox write command exists yet
- no authoritative write command exists
- future sandbox writes require separate acceptance

References:

- `docs/roadmap/PHASE-2-SANDBOX-WRITE-PROTOTYPE-DESIGN.md`
- `docs/contracts/SANDBOX-WRITE-PROTOTYPE-CONTRACT.md`

## Phase 2 Rollback Artifact Design

Phase 2 rollback artifact design is non-executing.

- no rollback command exists yet
- no sandbox write command exists
- rollback artifacts are contract/design only

References:

- `docs/roadmap/PHASE-2-ROLLBACK-ARTIFACT-DESIGN.md`
- `docs/contracts/SANDBOX-ROLLBACK-ARTIFACT-CONTRACT.md`

## Phase 2 Sandbox Fixture Path-Safety Design

Phase 2 sandbox fixture layout and path-safety policy are design-only.

- path-safety verification is read-only
- no sandbox write command exists
- no rollback execution command exists
- no authoritative write command exists

References:

- `docs/roadmap/PHASE-2-SANDBOX-FIXTURE-PATH-SAFETY-DESIGN.md`
- `docs/contracts/SANDBOX-FIXTURE-PATH-SAFETY-CONTRACT.md`
- `examples/sandbox/README.md`

## Phase 2 Acceptance Review

Phase 2 acceptance review is design-only.

- approval is requested before any sandbox-only write prototype branch is created
- acceptance does not authorize writes
- no sandbox write command exists
- no rollback execution command exists
- no authoritative write command exists

References:

- `docs/reviews/PHASE-2-ACCEPTANCE-REVIEW.md`
- `docs/reviews/phase2_acceptance_review_package.json`

## Phase 2 Acceptance Decision

Phase 2 decision record exists.

- decision may be accepted, rejected, or hold
- acceptance permits only future sandbox prototype planning, not write implementation
- no sandbox write command exists
- no rollback execution command exists
- no authoritative write command exists

References:

- `docs/reviews/PHASE-2-ACCEPTANCE-DECISION.md`
- `docs/reviews/phase2_acceptance_decision.json`

## Sandbox Prototype Rollback Execution Design

Sandbox prototype rollback execution design is planning only.

- rollback execution command is not implemented
- sandbox write command is not implemented
- authoritative write command is not implemented
- accepted Phase 2 allows planning only

References:

- `docs/roadmap/SANDBOX-PROTOTYPE-ROLLBACK-EXECUTION-DESIGN.md`
- `docs/contracts/SANDBOX-ROLLBACK-EXECUTION-CONTRACT.md`

## Sandbox Write Planning Contract

Sandbox write planning contract is planning only.

- sandbox write command is not implemented
- rollback execution command is not implemented
- authoritative write command is not implemented
- accepted Phase 2 allows planning only
- sandbox write planning depends on rollback execution design

References:

- `docs/roadmap/SANDBOX-WRITE-PLANNING-CONTRACT-DESIGN.md`
- `docs/contracts/SANDBOX-WRITE-PLANNING-CONTRACT.md`
- `examples/manifests/example-sandbox-write-plan.json`

M.A.X.I.N.E. production pipeline for O3DE character, asset, prefab, QC, and automation workflows.
