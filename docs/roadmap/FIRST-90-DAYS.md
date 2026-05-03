# First 90 Days Roadmap

## Phase 1: Repository Foundation and Schemas

- Objective: establish repo guardrails, folder conventions, and schema baseline.
- Deliverables:
  - repository scaffold
  - manifest schema draft
  - example jobs/manifests
  - base validator and starter tests
- Validation command or proof:
  - `python tools/manifest-validator/validate_manifest.py examples/manifests/example-draft-mesh.manifest.json`
- Risks:
  - schema too rigid for early iteration
  - schema too loose for release traceability
- Stop conditions:
  - manifest schema cannot represent existing draft workflows
  - validation does not produce deterministic pass/fail output

## Phase 2: Manifest-First Wrapper Around Current Factory

- Objective: wrap existing working factory scripts without breaking them.
- Deliverables:
  - adapter layer for intake jobs to manifests
  - manifest emission on pass/fail/pending
  - evidence stubs and job IDs
- Validation command or proof:
  - run wrapper job and verify manifest artifact for both success and forced failure
- Risks:
  - accidental regression in working queue scripts
  - mismatch between legacy job fields and new schema
- Stop conditions:
  - backward compatibility breaks
  - failed jobs do not emit manifests

## Phase 3: O3DE Product Resolver and Prefab Publication

- Objective: replace path guessing with source/product resolution and publish prefab-first artifacts.
- Deliverables:
  - product resolver module
  - prefab/actor publication manifest entries
  - rollback-aware publish operation
- Validation command or proof:
  - resolver returns correct products after AP run and publication manifest points to canonical products
- Risks:
  - AP output variability
  - incomplete mapping of source identities
- Stop conditions:
  - resolver cannot consistently find required products
  - publication emits non-reproducible artifacts

## Phase 4: QC Gates and Evidence Bundles

- Objective: enforce policy gates before publish and produce auditable evidence.
- Deliverables:
  - QC runner skeleton and gate contracts
  - evidence bundle structure (logs/screenshots/metrics)
  - quarantine path for fail outcomes
- Validation command or proof:
  - at least one pass, one warn, and one fail scenario with evidence references in manifest
- Risks:
  - noisy false positives
  - gate runtime too slow for operator flow
- Stop conditions:
  - gates produce inconsistent outcomes for same input
  - evidence references missing from manifest

## Phase 5: CI Validation and Release Packaging

- Objective: enforce baseline checks in CI and standardize release package metadata.
- Deliverables:
  - GitHub Actions CI for schema/tests/smoke checks
  - release manifest policy checks
  - initial release packaging checklist
- Validation command or proof:
  - CI green on mainline with manifest validation and tests
- Risks:
  - flaky CI behavior
  - environment-dependent validation mismatches
- Stop conditions:
  - CI is non-deterministic
  - release package policy cannot be verified automatically
