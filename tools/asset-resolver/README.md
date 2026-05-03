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
