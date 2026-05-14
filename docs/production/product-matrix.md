# Product Matrix

The product matrix defines which O3DE products a lane must resolve before a package can claim readiness.

## Lane Rules

- `draft_mesh`: `azmodel` required; `procprefab` and `azmaterial` optional.
- `release_rigged`: `actor` required, at least one `motion` required, `motionset` and `animgraph` required for release publish tier, and `procprefab` required for package publication.
- `external_rig_import`: `actor` required, `motion` optional unless the manifest marks it required, and `procprefab` required for package publication.
- Physics-enabled release requires `pxmesh` or a collider waiver.
- Materialized release requires `azmaterial` or a material waiver.

Product resolution must come from the Asset System adapter contract or deterministic fixtures. Release validators fail if a manifest uses cache newest-file or best-looking-file heuristics.

## APB Release-Rigged Evidence Notes

For live APB evidence, source capability is not enough by itself. A rigged source scene, motion source, motionset, animgraph, and collider scene settings may all be present while the release lane still fails if Asset Processor database evidence does not contain the required products.

The first 2026-05-09 controlled `MAXINE_GoldenCorpus` follow-up produced `actor`, `motion`, `motionset`, `animgraph`, `azmodel`, `procprefab`, and `azmaterial` evidence, but still failed because physics-enabled `release_rigged` did not produce `.pxmesh`. That remained `MXN_ASSET_PRODUCT_MISSING`; it was not converted into pass by cache heuristics or by silently dropping the `pxmesh` expectation.

The pxmesh resolution follow-up produced trusted `.pxmesh` evidence from the Asset Processor database:

```text
pc/assets/characters/maxine/release/r0-b_body.fbx.pxmesh
```

That resolves the release-rigged product matrix evidence for `pxmesh`; all required release-rigged product types are now present with `cache_heuristic_used=false`.

The follow-up DiffuseProbeGrid slice removed the unnecessary direct `DiffuseProbeGrid` Gem enablement from the controlled `MAXINE_GoldenCorpus` project and regenerated project-specific CMake registry metadata. APB now exits `0`, the wrapper/suite pass, and the product matrix remains `pass` without weakening the release-rigged product contract.

After the approved `release_rigged.prefab` source-template persisted Actor + Simple Motion wiring, live APB must preserve the normal release-rigged product matrix and find the approved character spawnable at `pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable`. That spawnable evidence is a prerequisite for runtime wiring proof, but it is not itself runtime component wiring or animation proof.

## Cache Heuristic Policy

Release lanes fail with `MXN_ASSET_CACHE_HEURISTIC_FORBIDDEN` when product resolution depends only on:

- newest Cache file
- best-looking filename
- glob-based Cache guess
- fallback mesh selection
- Cache path without source UUID or trusted product metadata

Draft lanes may record cache-heuristic evidence only as a warning. That warning cannot satisfy release publication and must not be described as source-UUID product resolution.

## Skipped Versus Passed Integration

A skipped local O3DE integration check is not a pass. It means fixture validation passed and the gated live adapter did not run. Product matrix pass in default CI means the deterministic fixture contract is coherent, not that Asset Processor or Editor executed.
