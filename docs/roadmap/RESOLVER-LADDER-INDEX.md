# M.A.X.I.N.E. Resolver Ladder Index

This index captures the full read-only resolver ladder from manifest adapter through final execution gate policy.

## 1. Manifest-first Adapter

- Purpose: wrap the existing MaxineShow factory with manifest-first job orchestration.
- Input evidence: job request parameters and lane inputs.
- Output field: `manifest` root contract plus job/evidence scaffolding.
- Safety status: read-only wrapper around existing scripts; preserves working factory scripts.
- Why this is not product resolution: creates and updates manifests but does not authoritatively resolve O3DE products.

## 2. Product Contract Resolver

- Purpose: record lane-specific required/optional/planned product contracts.
- Input evidence: lane selection and `tools/asset-resolver/product_contracts.json`.
- Output field: `manifest.o3de.asset_resolution`.
- Safety status: read-only contract recording; no AP query.
- Why this is not product resolution: it defines expectations only, not authoritative product identity.

## 3. Filesystem Probe

- Purpose: capture local project/source/cache filesystem evidence.
- Input evidence: manifest plus provided project/cache paths.
- Output field: `manifest.o3de.asset_probe`.
- Safety status: read-only filesystem metadata checks.
- Why this is not product resolution: candidate files are evidence only and cannot prove AP product identity.

## 4. AP Metadata Discovery

- Purpose: discover candidate O3DE/AP metadata sources and locations.
- Input evidence: project path plus metadata candidate config.
- Output field: `manifest.o3de.ap_metadata_discovery`.
- Safety status: read-only discovery; no live AP query.
- Why this is not product resolution: discovered logs/db paths are location evidence, not product truth.

## 5. AP Database Schema Inspection

- Purpose: inspect AP SQLite schema shape in read-only mode.
- Input evidence: discovered database candidates.
- Output field: `manifest.o3de.ap_database_inspection`.
- Safety status: read-only SQLite open (`mode=ro`) and schema extraction.
- Why this is not product resolution: table/column existence does not prove valid source/product records.

## 6. AP Row Mapping

- Purpose: sample candidate source/product/job/dependency rows.
- Input evidence: AP schema inspection results and candidate table roles.
- Output field: `manifest.o3de.ap_row_mapping`.
- Safety status: read-only `SELECT` sampling only.
- Why this is not product resolution: sampled rows are candidates and not authoritative product linkage.

## 7. Source Identity Matching

- Purpose: compare manifest source input to sampled source rows.
- Input evidence: `manifest.inputs.input_path` and `manifest.o3de.ap_row_mapping`.
- Output field: `manifest.o3de.ap_source_identity_match`.
- Safety status: read-only manifest evidence matching.
- Why this is not product resolution: candidate source match does not prove final product identity.

## 8. Product Candidate Matching

- Purpose: link sampled product rows to candidate source evidence and expected product types.
- Input evidence: `asset_resolution`, `ap_row_mapping`, and `ap_source_identity_match`.
- Output field: `manifest.o3de.ap_product_candidate_match`.
- Safety status: read-only candidate classification.
- Why this is not product resolution: product candidates remain non-authoritative until later proofs pass.

## 9. Product File Validation

- Purpose: verify candidate product path existence under explicit safe roots.
- Input evidence: `ap_product_candidate_match` plus project/cache roots.
- Output field: `manifest.o3de.ap_product_file_validation`.
- Safety status: read-only filesystem checks, safe-path restrictions.
- Why this is not product resolution: file existence does not prove platform/job/freshness validity.

## 10. Resolver Readiness Gate

- Purpose: combine source, candidate, file, contract, and safety evidence into readiness status.
- Input evidence: `asset_resolution`, `ap_source_identity_match`, `ap_product_candidate_match`, `ap_product_file_validation`.
- Output field: `manifest.o3de.ap_resolver_readiness`.
- Safety status: read-only gate evaluation.
- Why this is not product resolution: readiness only signals possible future attempt, never resolved output.

## 11. Authoritative Dry-Run Plan

- Purpose: build required proof plan for future authoritative resolution.
- Input evidence: readiness and upstream proof blocks.
- Output field: external plan artifact (`maxine_authoritative_resolver_plan` contract).
- Safety status: read-only planning artifact.
- Why this is not product resolution: plan status does not permit product writes.

## 12. AP Job-state Proof

- Purpose: extract candidate AP job status/result evidence from sampled rows.
- Input evidence: `ap_row_mapping`, `ap_source_identity_match`, `ap_product_candidate_match`.
- Output field: `manifest.o3de.ap_job_state_proof`.
- Safety status: read-only evidence extraction.
- Why this is not product resolution: job-state hints alone cannot validate product identity or freshness.

## 13. AP Platform Proof

- Purpose: extract platform hints from job/product rows and product paths.
- Input evidence: `ap_product_candidate_match`, `ap_product_file_validation`, `ap_job_state_proof`.
- Output field: `manifest.o3de.ap_platform_proof`.
- Safety status: read-only hint extraction.
- Why this is not product resolution: platform hints are non-authoritative and may be incomplete.

## 14. AP Product Freshness Proof

- Purpose: compare source/product/job timestamps to detect freshness support.
- Input evidence: `asset_probe`, `ap_row_mapping`, `ap_product_candidate_match`, `ap_product_file_validation`, `ap_job_state_proof`.
- Output field: `manifest.o3de.ap_product_freshness_proof`.
- Safety status: read-only timestamp analysis.
- Why this is not product resolution: freshness support is necessary but not sufficient for resolution.

## 15. AP Product Identity Proof

- Purpose: combine proof dimensions into candidate product identity support.
- Input evidence: source, type, candidate, file, job-state, platform, freshness blocks.
- Output field: `manifest.o3de.ap_product_identity_proof`.
- Safety status: read-only multi-proof synthesis.
- Why this is not product resolution: identity remains candidate and non-authoritative.

## 16. Updated Authoritative Planner Full Proof Stack

- Purpose: evaluate dry-run plan with full proof stack satisfaction rules.
- Input evidence: readiness plus job-state/platform/freshness/identity proofs.
- Output field: authoritative dry-run plan status and missing proofs.
- Safety status: read-only plan evaluation.
- Why this is not product resolution: `dry_run_ready` is still not permission to write resolved products.

## 17. Authoritative Write Protocol Proposal

- Purpose: define proposed future write fields and approval requirements.
- Input evidence: dry-run plan artifact.
- Output field: write protocol proposal artifact.
- Safety status: read-only proposal generation.
- Why this is not product resolution: proposal defines future intent only and performs no writes.

## 18. Operator Approval Validation

- Purpose: validate approval artifact against proposal identity, scope, and safety.
- Input evidence: write proposal plus operator approval artifact.
- Output field: operator approval validation report.
- Safety status: read-only validation artifact.
- Why this is not product resolution: valid approval still does not execute writes.

## 19. Approved-write Pre-write Report

- Purpose: merge proposal and approval validation into final pre-write readiness report.
- Input evidence: write proposal plus approval validation report.
- Output field: pre-write report artifact.
- Safety status: read-only merger/reporting.
- Why this is not product resolution: pre-write readiness remains non-executing evidence.

## 20. Final Execution Gate Policy

- Purpose: define mandatory manual command shape, rollback requirements, and preconditions for any future write.
- Input evidence: pre-write report artifact.
- Output field: execution gate policy evaluation artifact.
- Safety status: read-only policy gate (`implementation_available=false`, `write_allowed=false`).
- Why this is not product resolution: execution policy is documentation/validation only; write-capable resolver is not implemented.
