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

Approved prefab save/update route and scratch-proof diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-route --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

This diagnostic proves the next bounded step through the repo-owned Editor host. It calls `azlmbr.maxine.prefab_bridge.save_prefab_update_scratch_probe`, which is reflected for Automation under `maxine.prefab_bridge` and invokes the source-validated `AzToolsFramework::Prefab::PrefabPublicInterface::CreatePrefabAndSaveToDisk` route on a scratch-only Editor entity. The route accepts only absolute `.prefab` paths under the active project root returned by `AZ::Utils::GetProjectPath`, specifically `<active-project>/Assets/_maxine_smoke/prefabs/`; it rejects defaultlevel, production-level, generated product/cache, outside-project substring, other-project, unapproved absolute, and traversal paths, writes a scratch prefab, verifies JSON parse/reload semantics by parsing the saved prefab, records a SHA-256 after-hash, and removes the scratch file.

Route/scratch proof may set `approved_prefab_save_update_bridge_verified=true`, `approved_prefab_save_update_scratch_save_verified=true`, `approved_prefab_save_update_scratch_reload_or_parse_verified=true`, and `approved_prefab_save_update_scratch_cleanup_verified=true` only when the live route call, all path-policy rejections, parse, and cleanup evidence are present. It must keep `approved_runtime_animation_component_wiring_source_prefab_modified=false`, avoid APB/runtime mutation proof when the approved source prefab is untouched, and keep runtime component wiring, runtime animation, and full runtime character proof unclaimed.

Approved source-prefab Actor + Simple Motion wiring diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-source-prefab-actor-simple-motion-wiring --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

This diagnostic uses the PR #149 bridge host and route as the prerequisite surface, then exposes narrower approved-source-only routes under `azlmbr.maxine.prefab_bridge`. The routes may operate only on `<active-project>/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab`; they reject defaultlevel, production-level, generated product/cache, unapproved absolute, other-project, traversal, and non-prefab paths, and do not expose unrestricted `SavePrefab`.

The diagnostic instantiates the approved source prefab in the temp sandbox level, adds source-validated `EMotionFX::Integration::EditorActorComponent` and `EMotionFX::Integration::EditorSimpleMotionComponent` with `EditorComponentAPIBus`, assigns the approved actor and motion AssetIds with property readback, attempts to commit generated entity changes through `PrefabPublicInterface::GenerateUndoNodesForEntityChangeAndUpdateCache`, attempts component override application through `PrefabOverridePublicInterface::ApplyComponentOverrides`, saves through `PrefabPublicInterface::SavePrefab`, parses the saved prefab JSON, and verifies the saved source contains `ActorAsset` and `MotionAsset` markers before copying any Editor-generated source prefab back to the repo-owned path. The current live result is the typed blocker `blocked_by_editor_generated_instance_changes_not_propagated_to_source_template`: assignment readback and the source-backed save route pass, but the approved source template does not persist Actor/Motion markers. APB/runtime mutation proof must not run and runtime component wiring must not be claimed until a later source-validated propagation/apply route actually persists the source prefab.

Approved source-prefab propagation/apply-step diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-source-prefab-propagation-apply-step --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

This diagnostic pins the missing source-template apply context without mutating the approved prefab. Required repo-owned validation covers the current `MaxineRuntimeExitFixture.Editor` approved-source routes and the PR #150 blocker path. Optional engine-source validation, resolved from `O3DE_ENGINE_ROOT` or the current local engine checkout when available, records `PrefabOverridePublicHandler::ApplyComponentOverrides`, `GetComponentPathAndLinkIdFromFocusedPrefab`, `PrefabFocusInterface`, `PrefabFocusPublicInterface`, `InstanceToTemplateInterface`, and `InstanceUpdateExecutorInterface`.

The pinned source fact is that `ApplyComponentOverrides` computes component paths relative to the focused prefab and returns false when the edited entity is owned by the currently focused instance; successful propagation needs a parent/link context before `PushOverridesToPrefab` can update the source template. Until that route is implemented and proves `ActorAsset` / `MotionAsset` markers in the saved source file, reports must keep `approved_source_prefab_propagation_apply_step_verified=false`, use the typed blocker `blocked_by_prefab_instance_to_template_propagation_requires_parent_link_context`, keep `approved_source_prefab_modified=false`, and leave APB/runtime component wiring, animation playback, and full runtime character proof false.

Approved source-prefab parent-focus/link-context override apply route diagnostic:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-source-prefab-parent-link-override-apply-route --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

This diagnostic implements the next bounded bridge route under `azlmbr.maxine.prefab_bridge.apply_approved_source_prefab_parent_link_component_overrides`. The route first focuses the prefab instance owning the edited approved entity, then focuses the parent of that instance so O3DE can derive a link-context path, calls `PrefabOverridePublicInterface::ApplyComponentOverrides` for the Actor and Simple Motion component references, and restores focus to the edited prefab instance. The route is still approved-source-only and must not hand-author unknown component JSON.

Verification remains marker-backed. A callable route and successful override status only prove the parent/link route surface. The diagnostic may claim source-template propagation only if the saved approved source prefab parses and contains `ActorAsset` and `MotionAsset` marker evidence; APB/runtime TypeId proof, animation playback, and full runtime character proof remain false until those downstream gates actually run.

The first live route result is intentionally blocked at `blocked_by_prefab_link_context_unavailable`: parent focus context is established and restored, but O3DE still does not expose the component override/link path needed to update the approved source template. This bridge does not prove final runtime gameplay readiness.
