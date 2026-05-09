# Editor Python Package/Prefab Smoke Fixture Bridge

The Editor smoke bridge validates package/prefab instantiation evidence without requiring O3DE Editor in default CI.

Default fixture validation:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode fixture
```

Default mode reads JSON fixtures from `examples/editor-smoke`, checks product matrix expectations, package/prefab/procprefab refs, product resolver refs, Asset Processor Batch proof refs, component expectations, source UUID identity, and release cache-heuristic rejection. It does not run Editor, Asset Processor, publication, network calls, or external services.

Optional local Editor detection:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke
```

Strict local detection:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration
```

When local tooling is unavailable, non-strict mode reports `skipped` with `MXN_VALIDATION_TOOL_UNAVAILABLE`. Strict mode fails with the same code. Skipped integration is not a pass.

`live_editor_execution` remains false unless a future explicitly gated command actually runs O3DE Editor and parses its evidence. This bridge does not prove final runtime gameplay readiness.
