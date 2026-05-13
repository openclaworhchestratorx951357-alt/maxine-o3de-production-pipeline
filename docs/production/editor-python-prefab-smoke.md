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

Approved animation component wiring generation diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-runtime-animation-component-wiring-editor-generation --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

This diagnostic probes the source-validated Editor `Actor` + `Simple Motion` component assignment path with `EditorComponentAPIBus` and `azlmbr.asset.AssetId` readback, then records whether a safe source-prefab save/update path exists. The current local O3DE automation surface blocks the approved source-prefab update because `SavePrefab` and `CreatePrefabAndSaveToDisk` are available on `PrefabPublicInterface`, not on the Python-exposed `PrefabPublicRequestBus`. The diagnostic must therefore report `blocked_by_editor_generated_prefab_update_save_semantics`, keep `approved_runtime_animation_component_wiring_source_prefab_modified=false`, and keep component-wiring, runtime animation, and full runtime character proof unclaimed until a source-backed save path is implemented and APB/runtime inventory verifies the generated spawnable.

`live_editor_execution` remains false unless a future explicitly gated command actually runs O3DE Editor and parses its evidence. This bridge does not prove final runtime gameplay readiness.
