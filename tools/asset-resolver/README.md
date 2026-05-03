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
