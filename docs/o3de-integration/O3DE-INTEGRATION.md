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
