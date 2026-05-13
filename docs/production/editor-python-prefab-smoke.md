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

Approved prefab save/update automation surface diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-automation-surface --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

This diagnostic source-validates the O3DE prefab save/update API without mutating the approved source prefab. The pinned local source surface is `AzToolsFramework::Prefab::PrefabPublicInterface::CreatePrefabAndSaveToDisk`, `AzToolsFramework::Prefab::PrefabPublicInterface::SavePrefab`, `PrefabPublicHandler::CreatePrefabAndSaveToDisk`, `PrefabPublicHandler::SavePrefab`, and `PrefabLoaderInterface::SaveTemplate` / `SaveTemplateToFile`. It also records that `PrefabPublicRequestHandler::Reflect` exposes `CreatePrefabInMemory` and `InstantiatePrefab` through the Python-accessible `PrefabPublicRequestBus`, but does not expose `SavePrefab` or `CreatePrefabAndSaveToDisk`.

Until a narrow source-backed bridge or equivalent automation route is implemented and scratch-save verified, the diagnostic must report `blocked_by_prefab_save_interface_not_available_to_automation`, keep `approved_prefab_save_update_automation_surface_verified=false`, keep `approved_runtime_animation_component_wiring_source_prefab_modified=false`, and keep runtime component wiring, runtime animation, and full runtime character proof unclaimed. Hand-authored unknown `.prefab` component JSON, production/defaultlevel mutation, generated product commits, and Asset Cache deletion remain forbidden.

Approved prefab save/update bridge diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-bridge --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

This diagnostic narrows the next bridge implementation requirement without mutating the approved source prefab. It preserves the PR #146 observed-event surface, then checks whether the repo-owned O3DE Gem/tooling layout currently provides an Editor-capable bridge host. The current selected result is `blocked_by_prefab_save_bridge_requires_editor_gem_registration`: `MaxineRuntimeExitFixture` is a runtime client fixture with Clients/Servers/Unified aliases, but no `.Editor` / `.Tools` host module, no `PAL_TRAIT_BUILD_HOST_TOOLS` Editor target, and no `AzToolsFramework` bridge dependency. Until a repo-owned Editor module is registered, built, and callable from Editor Python, the diagnostic must keep `approved_prefab_save_update_bridge_verified=false`, `approved_prefab_save_update_scratch_save_verified=false`, `approved_runtime_animation_component_wiring_source_prefab_modified=false`, and all runtime component wiring / animation / full-character proof flags false.

Approved prefab save/update bridge-host diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-bridge-host --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

This diagnostic checks the next bounded step: whether a repo-owned Editor/Tools host for the prefab save/update bridge is registered, built, and callable from Editor Python. The host lives in the `MaxineRuntimeExitFixture` Gem behind the O3DE `PAL_TRAIT_BUILD_HOST_TOOLS` Editor target pattern, keeps the `AzToolsFramework` dependency on the Editor target only, and reflects a harmless `get_prefab_save_update_bridge_host_status` BehaviorContext method under `azlmbr.maxine.prefab_bridge`. The status route does not expose `SavePrefab`, does not perform scratch saves, and does not mutate the approved character prefab.

Required bridge-host source validation is based on repo-owned Gem, CMake, module, and host-component files. Local O3DE engine source references are optional environment evidence resolved from `O3DE_ENGINE_ROOT` when available; reports should record `approved_prefab_save_update_bridge_host_engine_source_refs_status` as `pass`, `engine_source_refs_unavailable`, or `engine_source_refs_not_available_in_this_environment` without turning missing machine-local `C:/src/o3de` files into a host-validation failure.

When the host is callable, reports may set `approved_prefab_save_update_bridge_host_callable_from_editor_python=true` while still keeping `approved_prefab_save_update_bridge_verified=false` and `approved_prefab_save_update_scratch_save_verified=false`. A later slice must expose the bounded save/update route, prove scratch save/update/parse/cleanup, and only then consider approved source-prefab mutation with APB/runtime follow-up.

`live_editor_execution` remains false unless a future explicitly gated command actually runs O3DE Editor and parses its evidence. This bridge does not prove final runtime gameplay readiness.
