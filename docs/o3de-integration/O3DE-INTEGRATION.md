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

## AP Source Identity Matching

The resolver stack now has six layers:

1. product contract recording
2. filesystem evidence probing
3. AP metadata source discovery
4. read-only AP database schema inspection
5. read-only candidate row mapping
6. read-only source identity candidate matching

Layer 6 remains discovery only and is not product resolution.

- candidate source identity is not proof of products
- source row matching is not publication readiness
- product resolution later requires source identity evidence, expected product type, platform, and current AP job/product state

## AP Candidate Product Matching

The resolver stack now has seven layers:

1. product contract recording
2. filesystem evidence probing
3. AP metadata source discovery
4. read-only AP database schema inspection
5. read-only candidate row mapping
6. read-only source identity candidate matching
7. read-only candidate product matching

Layer 7 is still not resolution.

- product candidates are not valid until product type, source identity, platform, job status, and file existence are proven
- this layer prepares evidence for future resolver decisions only

## AP Product File Existence Validation

The resolver stack now has eight layers:

1. product contract recording
2. filesystem evidence probing
3. AP metadata source discovery
4. read-only AP database schema inspection
5. read-only candidate row mapping
6. read-only source identity candidate matching
7. read-only candidate product matching
8. read-only product file existence validation

Layer 8 remains evidence only and is not product resolution.

- existence does not prove freshness, platform correctness, source linkage, or job success
- a future authoritative resolver must validate platform/job-state/current product records before resolving products

## AP Resolver Readiness Gate

The resolver stack now has nine layers:

1. product contract recording
2. filesystem evidence probing
3. AP metadata source discovery
4. read-only AP database schema inspection
5. read-only candidate row mapping
6. read-only source identity candidate matching
7. read-only candidate product matching
8. read-only product file existence validation
9. non-authoritative resolver readiness gate

Layer 9 is still not product resolution.

- it only decides whether evidence is complete enough for a future authoritative resolver attempt
- it does not mark products resolved or claim Asset IDs
- authoritative resolution must still validate platform, AP job status, source UUID/product identity, and product freshness
