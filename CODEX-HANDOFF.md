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

## Next Slice After AP Product Identity Proof

Update authoritative resolver dry-run planner to consume AP job-state, platform, freshness, and product identity proofs, still read-only and still without resolving products.

## Next Slice After Full Proof Stack Authoritative Planner

Design the first authoritative resolver write protocol as a gated proposal only, including exact manifest fields that would be written later, but do not implement writes.

Safety note:
Even `dry_run_ready` does not permit writes. A separate write protocol and explicit operator approval gate are required.

## Next Slice After Authoritative Write Protocol Proposal

Design operator approval artifact and approval validation for authoritative resolver proposals, still without writes.

## Next Slice After Operator Approval Validation

Design approved-write dry-run merger that combines proposal plus valid approval into a final pre-write report, still without writing resolved products.

Safety note:
Valid approval still does not execute writes. A final pre-write report and explicit execution gate are required.

## Next Slice After Approved-Write Dry-Run Pre-Write Report

Design final execution gate policy for future authoritative resolver writes, including mandatory manual command, branch protection expectations, and rollback artifact requirements, still without implementing writes.

Safety note:
Pre-write ready is not execution. A separate execution gate and rollback contract are required before any write-capable resolver exists.

## Next Slice After Final Execution Gate Policy

Consolidate PR stack after review/merge, then create a top-level roadmap index showing the full resolver ladder from manifest adapter through execution gate policy.

Safety note:
Do not implement authoritative writes until the execution gate policy is reviewed and explicitly accepted.

## Post-Consolidation Next Milestone

Review and merge the PR stack, then run the full test suite from `main`.

After that, design a separate experimental branch for a sandbox-only write prototype, but do not implement it until execution-gate policy is explicitly accepted.

## Phase 1 Operational Baseline Complete Criteria

- baseline audit report exists
- machine-readable baseline inventory exists
- baseline verifier exists
- baseline verifier passes
- pytest passes
- pester passes
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone

Phase 2 should be design-only review of a sandbox-only write prototype. Do not implement sandbox writes until the Phase 1 baseline and execution-gate policy are accepted.

## Phase 2 Design-Only Complete Criteria

- Phase 2 design document exists.
- Sandbox write prototype contract exists.
- Phase 2 design inventory exists.
- Phase 2 verifier exists.
- Phase 2 verifier passes.
- Sandbox write command remains absent.
- Authoritative write command remains absent.
- No products are resolved.
- No Asset IDs are claimed.

## Next Milestone After Phase 2 Design-Only

After Phase 2 design-only review is accepted, design a rollback artifact schema and rollback verifier for a future sandbox-only write prototype. Do not implement write execution yet.

## Phase 2 Rollback Design Complete Criteria

- rollback design document exists
- rollback contract exists
- rollback artifact schema exists
- rollback example exists
- rollback artifact verifier exists
- rollback phase verifier exists
- rollback command remains absent
- sandbox write command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Rollback Design

After rollback design is accepted, design a sandbox fixture layout and path-safety verifier for a future sandbox-only write prototype. Do not implement write execution yet.

## Phase 2 Sandbox Fixture Path-Safety Complete Criteria

- sandbox fixture layout exists
- path-safety policy exists
- path-safety verifier exists
- phase verifier exists
- accepted sandbox path test passes
- rejected production/escape path tests fail as expected
- sandbox write command remains absent
- rollback command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Sandbox Fixture Path-Safety Design

After sandbox fixture path-safety design is accepted, create a Phase 2 acceptance review package that summarizes Phase 2 design-only artifacts and explicitly asks for approval before any sandbox write prototype branch is created.

## Phase 2 Acceptance Review Complete Criteria

- acceptance review doc exists
- acceptance review package JSON exists
- acceptance review verifier exists
- acceptance review verifier passes
- all Phase 2 verifiers pass
- sandbox write command remains absent
- rollback command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Phase 2 Acceptance Review

If Phase 2 is explicitly accepted, create a separate branch for sandbox-only write prototype planning. The first sandbox prototype planning branch must still begin with rollback execution design and must not implement writes until approval is recorded.

## Phase 2 Acceptance Decision Complete Criteria

- acceptance decision doc exists
- acceptance decision JSON exists
- acceptance decision verifier exists
- acceptance decision verifier passes
- sandbox write command remains absent
- rollback command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Phase 2 Acceptance Decision

If the decision status is accepted, create a separate sandbox-only write prototype planning branch that starts with rollback execution design and still does not implement writes. If the decision is hold or rejected, revise the Phase 2 design package first.

## Sandbox Prototype Rollback Execution Design Complete Criteria

- rollback execution design doc exists
- rollback execution contract exists
- rollback execution design plan exists
- rollback execution design verifier exists
- rollback execution verifier passes
- rollback execution command remains absent
- sandbox write command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Sandbox Rollback Execution Design

Design the sandbox write planning contract that depends on rollback execution design, while still not implementing sandbox writes.

## Sandbox Write Planning Contract Complete Criteria

- sandbox write planning design doc exists
- sandbox write planning contract exists
- sandbox write planning plan JSON exists
- sandbox write plan example exists
- sandbox write plan verifier exists
- sandbox write planning contract verifier exists
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Sandbox Write Planning Contract

Design the sandbox write dry-run report contract that validates a sandbox write plan and rollback dependency, while still not implementing sandbox writes.

## Sandbox Write Dry-Run Report Contract Complete Criteria

- sandbox write dry-run design doc exists
- sandbox write dry-run contract exists
- sandbox write dry-run report schema exists
- sandbox write dry-run report example exists
- sandbox write dry-run report verifier exists
- sandbox write dry-run contract verifier exists
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Sandbox Write Dry-Run Report Contract

Design the sandbox write approval gate contract that accepts a dry-run report and operator approval, while still not implementing sandbox writes.

## Sandbox Write Approval Gate Contract Complete Criteria

- sandbox write approval gate design doc exists
- sandbox write approval gate contract exists
- sandbox write approval gate report schema exists
- sandbox write approval artifact example exists
- sandbox write approval gate report example exists
- sandbox write approval verifier exists
- sandbox write approval gate report verifier exists
- sandbox write approval gate contract verifier exists
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Sandbox Write Approval Gate Contract

Design the sandbox write final preflight contract that combines the write plan, dry-run report, approval gate, and rollback dependency, while still not implementing sandbox writes.

## Sandbox Write Final Preflight Contract Complete Criteria

- sandbox write final preflight design doc exists
- sandbox write final preflight contract exists
- sandbox write final preflight report schema exists
- sandbox write final preflight report example exists
- sandbox write final preflight report verifier exists
- sandbox write final preflight contract verifier exists
- sandbox write command remains absent
- rollback execution command remains absent
- authoritative write command remains absent
- no products are resolved
- no Asset IDs are claimed

## Next Milestone After Sandbox Write Final Preflight Contract

Design the sandbox execution intent contract and explicit operator execution-hold record, while still not implementing sandbox writes.
