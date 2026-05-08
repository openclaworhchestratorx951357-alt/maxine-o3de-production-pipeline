# Product Matrix

The product matrix defines which O3DE products a lane must resolve before a package can claim readiness.

## Lane Rules

- `draft_mesh`: `azmodel` required; `procprefab` and `azmaterial` optional.
- `release_rigged`: `actor` required, at least one `motion` required, `motionset` and `animgraph` required for release publish tier, and `procprefab` required for package publication.
- `external_rig_import`: `actor` required, `motion` optional unless the manifest marks it required, and `procprefab` required for package publication.
- Physics-enabled release requires `pxmesh` or a collider waiver.
- Materialized release requires `azmaterial` or a material waiver.

Product resolution must come from the Asset System adapter contract or deterministic fixtures. Release validators fail if a manifest uses cache newest-file or best-looking-file heuristics.
