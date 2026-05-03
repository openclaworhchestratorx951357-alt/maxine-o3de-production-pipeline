# O3DE Integration

O3DE source assets are processed into product assets by Asset Processor. Production automation should treat source assets as intent and product assets as resolved outputs.

## Product Resolution Strategy

Production code should resolve products by source identity and product type, rather than guessing cache filenames or assuming one fixed output path. This is critical for reliability across importers and reprocessing events.

## Expected Products by Lane

- **Draft mesh lane**: `.azmodel` and optional procedural prefab output.
- **Rigged lane**: `.actor` and `.motion`.
- **Release package**: actor, motions, motion set, animation graph, prefab/procprefab, materials, and collider assets when applicable.

## Editor Automation Bridge

Editor Python Bindings are the likely bridge for automated entity/component/level smoke tests, including:

- spawn checks
- component wiring checks
- level save/load checks
- runtime smoke capture

## Publication Preference

Prefab-first publication is preferred over only spawning entities into the current editor level. Prefabs are easier to version, validate, promote, and roll back as production artifacts.

## Asset Resolver POC

Current asset resolver behavior is contract-first:

- records expected product contracts into `manifest.o3de.asset_resolution`
- marks contract state as planned/unresolved unless explicitly allowed in test-only mode
- does not call real O3DE Asset Processor APIs yet

Guardrails in this slice:

- cache guessing is forbidden
- source UUID/product type real resolution is not yet implemented
- unresolved contract entries are explicit and expected

Next target after this proof is a real resolver adapter that queries O3DE/AP by source identity and product types.

## Filesystem Probe Adapter

The filesystem probe adapter records local evidence only. It does not provide authoritative product resolution.

- captures project path existence, project.json presence, and source asset file evidence
- can optionally scan a provided cache path for candidate product-like files
- records probe findings under `manifest.o3de.asset_probe`

Important constraints:

- findings are evidence of local filesystem state, not proof of O3DE Asset IDs
- cache guessing is not used as a success condition
- real product resolution requires official O3DE/AP APIs or tooling in a later slice

## Asset Processor Metadata Discovery

M.A.X.I.N.E. now has three resolver layers:

1. product contract recording
2. filesystem evidence probing
3. O3DE-aware metadata source discovery

This slice is layer 3 and remains read-only and non-authoritative.

- records candidate metadata source locations in `manifest.o3de.ap_metadata_discovery`
- does not run O3DE Editor or Asset Processor
- does not claim product publication or product validity

This prepares future source UUID and product-type resolution, but it must not be confused with product publication.

## AP Database Schema Inspection

The resolver stack now has four layers:

1. product contract recording
2. filesystem evidence probing
3. AP metadata source discovery
4. read-only AP database schema inspection

Layer 4 remains discovery only and is not product resolution.

- table names are not proof of product validity
- schema presence does not prove source/product correctness
- real product resolution comes later with verified source UUID and product-type matching

## AP Source/Product Row Mapping

The resolver stack now has five layers:

1. product contract recording
2. filesystem evidence probing
3. AP metadata source discovery
4. read-only AP database schema inspection
5. read-only candidate row mapping

Layer 5 is still not product resolution.

- row presence is not proof of product validity
- candidate row matches are not source identity proof
- real product resolution requires expected product type, source identity, platform, and current job-state matching
