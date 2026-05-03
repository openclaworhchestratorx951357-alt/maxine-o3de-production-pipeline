# Asset Resolver

## Purpose

The asset resolver records expected O3DE product contracts into M.A.X.I.N.E. manifests so downstream steps can reason about required outputs by lane.

## Scope of This POC

This proof-of-concept does **not** query the real O3DE Asset Processor yet. It focuses on contract recording only.

- records expected product contracts in the manifest
- keeps unresolved/planned outputs explicit
- prepares data model for future source UUID and product-type resolution

## Guardrails

- cache guessing is rejected
- fake O3DE product IDs are not generated
- unresolved/planned is valid and expected for this slice

## Supported Lanes

- `draft_mesh`
- `text_mesh`
- `photo_rig_prep`
- `text_full_rig`
- `external_rig_import`
- `release_character`

## Resolver Modes

### `contract` mode

- records expected product contract only
- uses `product_contracts.json`
- does not inspect local O3DE filesystem
- never resolves Asset IDs

### `filesystem_probe` mode

- inspects declared O3DE project/source/cache locations
- records existence, sizes, timestamps, likely source-relative path, and candidate product-like files
- does not claim authoritative Asset IDs
- does not use cache guessing as success
- records all findings under `manifest.o3de.asset_probe`

### future `o3de_api` mode

- will call O3DE Asset Processor / Asset Catalog APIs or official CLI/AP tooling
- will resolve source UUID and products by product type
- not implemented in this slice

## Expected Product Contracts

### `draft_mesh`

- `azmodel` required
- `procprefab` optional
- `azmaterial` optional

### `text_mesh`

- `azmodel` required
- `procprefab` optional
- `azmaterial` optional

### `photo_rig_prep`

- `fbx_source` required
- `mixamo_handoff_package` planned
- `actor` unresolved until rig import

### `text_full_rig`

- `fbx_source` required
- `actor` planned
- `motion` optional
- `procprefab` planned

### `external_rig_import`

- `actor` required
- `motion` optional
- `motionset` planned
- `animgraph` planned
- `procprefab` planned

### `release_character`

- `actor` required
- `motion` optional
- `motionset` required
- `animgraph` required
- `procprefab` required
- `azmaterial` required
- `collider` optional depending on policy

## Asset Processor Metadata Discovery

This discovery layer does not query a live Asset Processor process. It records discovered candidate metadata sources only.

Discovery checks candidate locations for:

- `project.json`
- `user/project.json`
- `Registry/*.setreg`
- `Registry/*.setregpatch`
- project user log files
- Asset Processor log candidates
- Asset Processor database/cache candidates
- cache directory candidates

Findings are written to `manifest.o3de.ap_metadata_discovery`.

This layer does not write:

- `manifest.o3de.products` as resolved
- real Asset IDs
- authoritative source UUIDs

A later slice may use discovered locations to implement read-only database/API queries.

## Asset Processor Database Schema Inspection

This layer opens discovered SQLite database candidates in read-only mode and extracts schema shape only.

Captured schema shape includes:

- table names
- column names and types
- indexes
- row counts when safely requested
- heuristic source/product/job/dependency/scanfolder/builder table candidates based on table names

This layer does not modify databases.

This layer does not claim source UUID or product resolution.

Findings are written to `manifest.o3de.ap_database_inspection`.

A future slice may map actual source/product rows after schema shape is understood.

## Read-only Source/Product Row Mapping

This layer reads candidate source/product/job/dependency tables identified by schema inspection.

It samples rows using `SELECT` only and applies conservative mapping hints from table names and column names.

Findings are written to `manifest.o3de.ap_row_mapping`.

This layer does not:

- mark `manifest.o3de.products` as resolved
- claim source UUID truth
- claim product Asset ID truth

Product rows remain candidate rows until later source UUID and product-type proof exists.

## Read-only Source Identity Matching

This layer compares manifest input source asset data against candidate source rows from `manifest.o3de.ap_row_mapping`.

It uses conservative matching heuristics:

- exact normalized path match
- path suffix match
- filename match
- stem match
- UUID-like field presence

Findings are written to `manifest.o3de.ap_source_identity_match`.

This layer does not:

- update `manifest.o3de.products` as resolved
- claim product validity
- claim authoritative source identity

It only emits confidence-ranked candidate source identity evidence.

## Read-only Candidate Product Matching

This layer reads:

- `manifest.o3de.asset_resolution` required/optional/planned products
- `manifest.o3de.ap_row_mapping` sampled product rows
- `manifest.o3de.ap_source_identity_match` best/candidate source match

It links candidate product rows to a candidate source row when values suggest shared source identifiers.

It classifies product rows against expected product contract types using conservative filename/extension/name matching.

Findings are written to `manifest.o3de.ap_product_candidate_match`.

This layer does not:

- update `manifest.o3de.products` as resolved
- claim product Asset IDs
- publish or spawn entities

Product candidates remain evidence only.

## Read-only Product File Existence Validation

This layer reads candidate products from `manifest.o3de.ap_product_candidate_match`.

It checks possible product path fields from candidate row values under explicitly supplied safe roots only:

- project root
- cache root
- optional additional roots

Findings are written to `manifest.o3de.ap_product_file_validation`.

This layer does not:

- update `manifest.o3de.products` as resolved
- claim Asset IDs
- treat file existence as product resolution

Existing files remain candidate product files until platform/job-state/source identity validation is added.

## Non-authoritative Resolver Readiness Gate

This gate combines evidence from:

- `manifest.o3de.asset_resolution`
- `manifest.o3de.ap_source_identity_match`
- `manifest.o3de.ap_product_candidate_match`
- `manifest.o3de.ap_product_file_validation`

It answers one question:
Is there enough evidence to attempt a future authoritative resolver?

Findings are written to `manifest.o3de.ap_resolver_readiness`.

Required readiness dimensions:

- source identity evidence
- product candidate evidence
- file existence evidence
- required contract coverage
- safety compliance

Readiness statuses:

- `ready_for_authoritative_resolution_attempt`
- `blocked_missing_source_identity`
- `blocked_missing_product_candidates`
- `blocked_missing_required_product_files`
- `blocked_safety_violation`
- `incomplete_evidence`

This layer does not:

- resolve products
- claim Asset IDs
- publish or spawn entities

## Authoritative Resolver Dry-Run Planning

This layer consumes `manifest.o3de.ap_resolver_readiness` and produces a dry-run plan for a future authoritative resolver.

The dry-run planner:

- consumes readiness/source/product/file evidence
- produces a non-authoritative plan object
- lists missing future proofs required for write-capable resolution
- records read-only proposed actions for future slices

This layer does not:

- write resolved products
- claim Asset IDs
- run O3DE Editor or Asset Processor
- spawn entities or publish prefabs

This is the final planning gate before designing a future authoritative resolver implementation.
