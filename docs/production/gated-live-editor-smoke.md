# Gated Live Editor Smoke

This slice prepares the first private-runner Editor Python smoke after the clean APB-only release-rigged baseline from PR #113.

The live Editor path remains fail-closed until all gates pass:

- APB clean baseline passes first.
- The selected project is the controlled `MAXINE_GoldenCorpus` project.
- The Editor executable is paired to `C:/src/o3de`.
- `EditorPythonBindings` is enabled and available in the profile build output.
- The smoke script is `tools/o3de/editor_python/maxine_package_prefab_smoke.py`.
- Temp levels stay under `Levels/_maxine_smoke`.
- Live publication is disabled.
- Release packaging is disabled.
- Cache heuristics are forbidden as release proof.

## Readiness

Run readiness without launching Editor:

```powershell
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict
```

Strict readiness fails with `MXN_VALIDATION_TOOL_UNAVAILABLE` when the project/engine-paired Editor executable is missing, when `EditorPythonBindings` is not enabled or unavailable, or when the temp-level/publication/packaging gates are unsafe.

## Live Gate

Before any live Editor smoke, set only non-secret session gates:

```powershell
$env:MAXINE_ENABLE_O3DE_INTEGRATION = "1"
$env:MAXINE_ENABLE_ASSET_PROCESSOR_BATCH = "1"
$env:MAXINE_ENABLE_O3DE_EDITOR_SMOKE = "1"
$env:MAXINE_ALLOW_LIVE_O3DE_COMMANDS = "1"
$env:MAXINE_ALLOW_LIVE_EDITOR_COMMANDS = "1"
$env:MAXINE_ALLOW_LIVE_PUBLICATION = "0"
$env:MAXINE_ENABLE_RELEASE_PACKAGING = "0"
```

The manual workflow adds `editor_smoke_readiness`, `editor_smoke_live_non_strict`, and `editor_smoke_live_strict` modes. Live modes require both `run_live_o3de_commands=true` and `run_live_editor_commands=true`, and they run the APB strict baseline before Editor smoke readiness.

## Editor Executable Handoff

The follow-up Editor executable slice produced the paired profile Editor executable:

```text
C:/src/o3de/build/windows/bin/profile/Editor.exe
```

Target discovery confirmed the generated Visual Studio target is `Editor`, with profile output under `C:/src/o3de/build/windows/bin/profile`. The successful bounded build command was:

```powershell
cmake --build C:/src/o3de/build/windows --target Editor --config profile --parallel 1 -- /m:1 /nodeReuse:false /p:CL_MPCount=1 /p:UseMultiToolTask=false /v:m
```

Strict readiness now passes when the executable is supplied explicitly:

```powershell
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --strict --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

Sanitized readiness evidence is:

```text
examples/editor-smoke/editor-smoke-readiness.release-rigged.editor-produced.example.json
```

Live Editor execution was still not attempted in the executable slice. The live smoke slice reran the APB clean baseline and strict Editor readiness in the same session before opening the live Editor gates.

## First Live Editor Smoke Attempt

The first gated live Editor smoke used the paired Editor executable and the controlled project:

```powershell
$env:MAXINE_ENABLE_O3DE_INTEGRATION = "1"
$env:MAXINE_ENABLE_ASSET_PROCESSOR_BATCH = "1"
$env:MAXINE_ENABLE_O3DE_EDITOR_SMOKE = "1"
$env:MAXINE_ALLOW_LIVE_O3DE_COMMANDS = "1"
$env:MAXINE_ALLOW_LIVE_EDITOR_COMMANDS = "1"
$env:MAXINE_ALLOW_LIVE_PUBLICATION = "0"
$env:MAXINE_ENABLE_RELEASE_PACKAGING = "0"
$env:MAXINE_EDITOR_SMOKE_TIMEOUT_SECONDS = "180"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

The wrapper launched Editor with the automation profile:

```text
C:/src/o3de/build/windows/bin/profile/Editor.exe -NullRenderer -rhi=Null --skipWelcomeScreenDialog --autotest_mode --project-path %USERPROFILE%/O3DE/Projects/MAXINE_GoldenCorpus --runpython tools/o3de/editor_python/maxine_package_prefab_smoke.py
```

The run is recorded as `stalled`, not pass. Editor launched, `live_editor_execution=true`, the approved temp level path was created under `Levels/_maxine_smoke/maxine_smoke_20260510T095910Z`, and the wrapper stopped the process tree after the 180 second timeout while Editor was still in the level load path. The in-Editor entity/prefab/actor/component checks did not complete. The APB prerequisite for the recorded attempt was `artifacts/o3de-integration/apb/apb-live-20260510T095743Z/asset_processor_batch_live_report.json`.

Sanitized evidence is:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.stalled.example.json
```

Safety outcome:

- live publication: false
- release packaging: false
- Asset Cache deletion: false
- production level mutation: false
- product evidence prerequisite: pass
- cache heuristic release proof: forbidden

The next Editor smoke slice should diagnose why the in-Editor Python flow does not reach report completion after temp level creation/loading, then rerun the same gated wrapper. Do not promote this stalled result to success.

## Temp-Level Stall Diagnostic

The follow-up diagnostic slice added bounded Editor smoke modes and JSONL progress markers:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode hello --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode product-evidence --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode temp-level --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode entity-minimal --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode full --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

Each live run writes `progress.jsonl` beside stdout, stderr, and the Editor smoke report. Wrapper markers cover launch, timeout, process-tree cleanup, report discovery, and final status. Script markers cover import, `azlmbr` import, product evidence loading, temp-level policy validation, level creation/opening, idle wait, entity creation, level save, report write, and exit request.

The stalled PR #116 behavior was narrowed to `idle_wait_stall`: `create_level_no_prompt` returned successfully and wrote the temp level under `Levels/_maxine_smoke`, then `azlmbr.legacy.general.idle_wait_frames(5)` did not return while Editor was loading the temp map. The smoke now skips that wait by default and records `idle_wait_skipped`; set `MAXINE_EDITOR_SMOKE_ENABLE_IDLE_WAIT=1` only for targeted debugging of the old behavior.

After the fix, the diagnostic sequence passed through `hello`, `product-evidence`, `temp-level`, and `entity-minimal`. Full gated Editor smoke also passed with `exit_code=0`, `live_editor_execution=true`, `live_publication=false`, `release_packaging=false`, `production_level_mutation=false`, and complete APB product evidence. Entity/component smoke passed; prefab and actor smoke remained non-pass until their component/binding surfaces were pinned.

Sanitized pass evidence is:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.pass.example.json
```

The include-editor-smoke integration suite path now passes after running the APB baseline first:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --include-editor-smoke --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

This remains a smoke milestone, not production readiness. Publication, release packaging, Asset Cache deletion, and production-level mutation remain blocked.

## Binding Diagnostics

The actor/prefab/component hardening slice adds targeted Editor diagnostic modes:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode component-binding --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode actor-binding --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode prefab-binding --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

These modes extend the report with `component_type_registry`, `binding_call_surface`, `safe_call_results`, `component_binding_checks`, `actor_binding_checks`, `prefab_binding_checks`, `property_path_discovery`, `property_list_summary`, and `no_fake_success`. Component checks use safe `EditorComponentAPIBus` discovery/probing inside the approved temp level. Actor checks require trusted APB `actor` product evidence before attempting component binding, and prefab checks require trusted `procprefab` product evidence before inspecting prefab surfaces.

Typed non-pass statuses are intentional and reviewable: `skipped_by_mode`, `unavailable_with_verified_reason`, `blocked_by_readiness`, `blocked_by_missing_product_evidence`, `blocked_by_missing_binding`, `blocked_by_unsafe_operation`, and `unsupported_by_engine_binding`. A report cannot count actor or prefab smoke as `pass` unless the matching binding check is also `pass`. Generic unavailable-by-design actor/prefab placeholders are no longer valid live-pass evidence.

Current live binding evidence pins these safe component IDs for the paired `C:/src/o3de` + `MAXINE_GoldenCorpus` rig:

- Transform: `{27F1E1A1-8D9D-4C3B-BD3A-AFB9762449C0}`
- Tag: `{5272B56C-6CCC-4118-8539-D881F463ACD1}`
- Actor: `{A863EE1B-8CFD-4EDD-BA0D-1CEC2879AD44}`

The smoke now proves component binding by creating a temp entity, verifying the default Transform, adding a Tag component through `EditorComponentAPIBus.AddComponentsOfType`, building property lists, and reading safe component properties. Actor component binding is partially validated: APB actor product evidence exists, Actor TypeId discovery passes, Actor component add passes, property-list/readback passes, and `Actor asset` appears in the property surface; the asset assignment itself remained `blocked_by_unsafe_operation` until the setter value type was pinned in the follow-up proof slice. Prefab/procprefab binding is also partially validated: APB `procprefab` evidence exists and `azlmbr.prefab` exposes prefab buses/load surfaces; live instantiation remained `blocked_by_unsafe_operation` until a safe call was pinned in the follow-up proof slice.

## Actor Assignment and Prefab Instantiation Proof

The actor/prefab proof slice adds two targeted Editor diagnostic modes:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode actor-asset-assignment --timeout-seconds 360 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode prefab-instantiation --timeout-seconds 360 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

Actor assignment is pinned to this observed safe call sequence:

- require trusted APB `actor` product evidence for `pc/assets/characters/maxine/release/jack.actor`
- add the Actor component with TypeId `{A863EE1B-8CFD-4EDD-BA0D-1CEC2879AD44}`
- discover the `Actor asset` property path from the live component property list
- resolve the approved product through `azlmbr.asset.AssetCatalogRequestBus.GetAssetIdByPath`; the resolving catalog path is `assets/characters/maxine/release/jack.actor`
- set the property with `azlmbr.editor.EditorComponentAPIBus.SetComponentProperty` and an `azlmbr.asset.AssetId`
- read back the property and verify it with `EditorComponentAPIBus.CompareComponentProperty`

Prefab instantiation is pinned to this temp-level-only Editor source-prefab sequence:

- require trusted APB `procprefab` product evidence for `pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab`
- create the smoke entity in an approved temp level under `Levels/_maxine_smoke`
- call `azlmbr.prefab.PrefabPublicRequestBus.CreatePrefabInMemory` to write a temporary source `.prefab` under the same temp level
- call `azlmbr.prefab.PrefabPublicRequestBus.InstantiatePrefab` with the temp source `.prefab`, an empty parent entity id, and `azlmbr.math.Vector3`
- verify a created entity/container id and confirm `GetOwningInstancePrefabPath` points back to the temp source prefab

This remains a true Editor prefab instantiation proof for an approved temporary source prefab. Direct `.procprefab` product instantiation is tracked separately so source-prefab success cannot be mistaken for direct product proof.

Full smoke now incorporates Actor assignment and prefab instantiation evidence. A `full` pass is rejected when `actor_asset_assignment.readback.matched_approved_product` is not true, or when prefab instantiation lacks a created entity or verified template-load evidence.

## Direct ProcPrefab Product Semantics

The direct procprefab slice adds one more targeted diagnostic mode:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode procprefab-product-instantiation --timeout-seconds 420 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

This mode specifically tests direct use of the APB product:

```text
pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab
```

It keeps the source-prefab baseline separate. `PrefabPublicRequestBus.CreatePrefabInMemory + PrefabPublicRequestBus.InstantiatePrefab` remains the stable Editor smoke path for a temporary source `.prefab` under `Levels/_maxine_smoke`. The direct product diagnostic records `direct_procprefab_product_semantics`, including APB product evidence, Asset Catalog lookup, the discovered `azlmbr.prefab` surface, the selected call and argument shape, direct load result, direct instantiation result, and explicit booleans for `direct_product_instantiation_claimed`, `direct_product_instantiation_supported`, and `direct_product_instantiation_verified`.

The current authoritative source inspection shows O3DE Editor UI paths for procedural-prefab selection pass `.procprefab` product paths into `PrefabPublicInterface::InstantiatePrefab`. Live evidence now pins the matching Python-exposed path: `PrefabPublicRequestBus.InstantiatePrefab` with the AssetCatalog-selected product path `assets/characters/maxine/release/maxine_idle_fbx.procprefab`, an empty parent entity id, and `azlmbr.math.Vector3`. The APB-style `pc/...` path is recorded as a failed attempt, while the AssetCatalog-selected path instantiates and returns verified created-entity evidence. Load-only and in-memory spawnable probes are opt-in debugging aids and are not required for the full smoke pass.

## Direct ProcPrefab Content Assertions

The content-assertion slice adds a stricter targeted mode for the already-proven direct product path:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode procprefab-content-assertions --timeout-seconds 420 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

This mode still requires the APB `procprefab` product evidence and still uses `PrefabPublicRequestBus.InstantiatePrefab` with the AssetCatalog-selected product path. It then records `direct_procprefab_content_assertions` separately from the source-prefab baseline. Required assertions cover a valid created container/entity, owning prefab path matching the direct product path, positive created entity count, and no relevant missing-asset/load-error signals in bounded Editor log scanning. Additional entity-name, child-structure, and component-inventory evidence is recorded as pass, informational, or unavailable with a typed reason depending on the exposed Editor Python surface.

Full smoke may pass only when direct product instantiation remains verified and no required content assertion fails. Source-prefab creation remains the stable Editor smoke baseline, but it is not counted as direct product content proof.

## Character-Specific ProcPrefab Assertions

The character-specific assertion slice adds a targeted diagnostic mode for the already-proven direct product path:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode procprefab-character-component-assertions --timeout-seconds 480 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

This mode keeps generic direct product content assertions separate from character-specific proof. It reuses the direct `.procprefab` instantiation path, validates the PR #121 container/entity/owning-path/content checks, traverses the created container/child entities through safe Editor APIs, probes candidate character component TypeIds with `EditorComponentAPIBus.FindComponentTypeIdsByEntityType` and `HasComponentOfType`, and records any safe component property or asset-reference readback.

The current paired runner discovers candidate TypeIds for Actor, Mesh, Material, Animation, and PhysX-related components, while Skinned Mesh discovery remains typed `blocked_by_missing_binding`. The instantiated direct `.procprefab` product currently exposes no Actor, Mesh, Material, Animation, PhysX, or APB-product asset-reference component evidence through the validated Editor component inventory. The report therefore records `procprefab_character_assertions.status=unavailable_with_verified_reason` with `direct_procprefab_character_components_not_exposed_in_editor_product_instance`; Transform-only evidence remains structural content evidence and is not counted as character-specific pass.

Required character assertions currently require the selected direct product path to have no missing actor, mesh, material, animation, or load-error signals in bounded Editor log scanning. Those required checks must pass for full smoke. Optional or unavailable character component surfaces remain explicit typed evidence and do not become required passes until live evidence proves they are stable and expected for this product.

## Runtime/Spawnable Proof Surface

The runtime/spawnable proof-surface slice adds a targeted diagnostic mode after the Editor component inventory result bottoms out:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode runtime-spawnable-proof-surface --timeout-seconds 540 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

This mode preserves direct `.procprefab` product instantiation, direct content assertions, and the Editor-side character-specific typed unavailable result. It then records `runtime_spawnable_proof` as a separate layer so product dependency proof cannot be mistaken for runtime execution proof.

The current pinned surface is non-publishing and non-runtime-launching:

- local O3DE source discovery confirms spawnable and product-dependency surfaces such as `AzFramework::Spawnable`, `SpawnableEntitiesInterface`, `SpawnableScriptMediator`, and Asset Catalog product-dependency APIs.
- the selected proof call is a read-only Asset Processor database `ProductDependencies` query for `pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab`.
- the direct `.procprefab` product dependency graph is empty for actor, azmodel, pxmesh, azmaterial, motion, motionset, and animgraph character products, so product dependency proof is recorded as `product_dependency_proof_unavailable` with `direct_procprefab_product_dependency_graph_empty_for_character_products`.
- local runtime launcher candidates may be recorded as candidates only; `runtime_spawnable_execution_attempted=false` and `runtime_spawnable_execution_verified=false` until a bounded dedicated runtime harness is pinned.

Full smoke may still pass when all prior Editor/APB gates pass and runtime/spawnable proof is explicitly typed unavailable or blocked with a precise reason. Full smoke must not imply runtime character proof unless `runtime_spawnable_execution_verified=true` is backed by an actual bounded runtime execution pass.

## Bounded Runtime Harness Contract

The dedicated runtime harness slice adds `tools/o3de/runtime_harness.py` as a standalone, non-publishing contract around runtime launcher discovery and readiness. The harness is intentionally separate from Editor component inventory proof, product dependency proof, runtime execution proof, and runtime character proof.

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --mode fixture
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --pin-runtime-command --strict --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json --timeout-seconds 120
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-exit-strategies --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json --timeout-seconds 120
```

Fixture mode validates the report contract without launching runtime. Readiness mode requires trusted APB product evidence for all release-rigged products, `cache_heuristic_used=false`, a project path paired to `MAXINE_GoldenCorpus`, an engine profile-bin launcher candidate, and closed publication/release-packaging/production-mutation gates.

Command-pinning mode records the concrete non-publishing command envelope without launching runtime. The pinned command uses the selected `MAXINE_GoldenCorpus.HeadlessServerLauncher.exe` with `--project-path=<project>`, `-NullRenderer`, `-rhi=null`, `--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0`, and `--console-command-file=<artifact cfg containing quit>`. The supporting local source evidence is `Launcher.cpp` for `--console-command-file`, `SystemInit.cpp` for the `quit` console command, `GameApplication.cpp` for `-NullRenderer`, and `SettingsRegistryMergeUtils.cpp` for `--project-path`.

Live bounded runtime mode is separately gated by `MAXINE_ENABLE_O3DE_RUNTIME_HARNESS=1` and `MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS=1`. It now requires readiness plus `runtime_command_pin_verified=true` before launching the pinned command. Harness readiness is not command-pinning proof, command-pinning proof is not runtime execution proof, and neither is runtime character proof. Runtime character proof remains unclaimed unless a bounded runtime process actually runs, completes, captures stdout/stderr/log refs, passes missing actor/mesh/material/animation/load-error scans, and records character-specific evidence.

The current paired runner records the pinned command envelope as pass, but the gated live command attempt exits before timeout with code `3221225477`. Runtime reports render that as decimal `3221225477`, hex `0xC0000005`, signed 32-bit `-1073741819`, and `runtime_execution_failed_access_violation_like_exit`. Treat the code as diagnostic evidence, not root cause by itself: stdout showed Asset Processor negotiation failure and shader serialization errors, stderr showed AssetManager shutdown asserts, and `Server.log` showed shader serializer errors. The harness summarizes those signals with bounded scans and keeps `runtime_execution_verified=false`, `runtime_character_proof_claimed=false`, and `runtime_character_proof_verified=false`.

Runtime quit-variant diagnostics preserve that failing baseline and add a separate source-validated variant matrix. The first attemptable variants are `-NullRenderer` without `-rhi=null` and `-rhi=null` without `-NullRenderer`; both keep `--project-path`, `--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0`, the generated `--console-command-file`, timeout, stdout/stderr/log capture, no level argument, no publication, no release packaging, and no production mutation. Help/version, delayed quit, no-console-file, and fallback launcher variants are recorded as rejected unless local source proves a bounded exit strategy. A clean variant may verify only bounded runtime command execution; `runtime_character_proof_claimed` remains false until character-specific runtime evidence is captured.

Command variants should only be attempted after source/log evidence justifies a safer envelope. The diagnostic report records `runtime_command_variant_not_attempted` when no source-validated variant has been selected, rather than broadening expected exit codes or changing flags to hide a crash-like exit.

Runtime exit-strategy diagnostics are the next layer above renderer-flag variants. This mode source-inspects actual launcher and console lifecycle surfaces before allowing any new runtime process: `Launcher.cpp` shows `--console-command-file` is executed before `RunMainLoop`, `SystemInit.cpp` and `System.cpp` show `quit` requests the main-loop exit, `Console.cpp` and `IConsole.h` show Settings Registry runtime console-command keys, and `Launcher.cpp` exposes an internal post-app-start callback that is not a CLI-pinnable surface for this harness. Immediate console-file quit and `.setregpatch` runtime-console quit are therefore source-validated but rejected as unsafe for this failure family because they still run before the main loop. Tick-queued delayed quit, help/version/no-op, command-line-plus-quit, ServerLauncher fallback, and temp/sandbox level exit remain rejected until local source identifies a bounded, no-production-level exit strategy.

The exit-strategy report records `runtime_exit_strategy_candidate_matrix`, source refs, typed candidate statuses, and a top-level blocker such as `blocked_by_missing_source_validated_runtime_exit_strategy` / `headless_launcher_no_level_exit_strategy_unavailable` when no candidate is safe to launch. Source validation is not runtime proof. A future clean no-op, help/version, after-init, or temp/sandbox exit could prove only bounded command-envelope execution; runtime character proof still requires character-specific runtime evidence, and expected exit codes must not be broadened to hide `0xC0000005`.

Runtime exit-fixture diagnostics are the layer after source-strategy discovery. The harness no longer probes more external launcher flags unless new source evidence appears. Instead it records whether a repo/project-scoped, non-shipping fixture can request exit after initialization. The #129 diagnostic remains preserved as `runtime_exit_fixture_status=blocked_by_fixture_requires_project_code_rebuild`, `runtime_exit_fixture_available=false`, `runtime_exit_fixture_execution_attempted=false`, and `runtime_exit_fixture_character_proof_claimed=false`.

The repository now owns a non-shipping external Code Gem source at `o3de/gems/MaxineRuntimeExitFixture`. Fixture source checks record `runtime_exit_fixture_source_status=runtime_exit_fixture_source_ready`, `runtime_exit_fixture_source_owned_by_repo=true`, `runtime_exit_fixture_enabled_by_default=false`, `runtime_exit_fixture_is_shipping_behavior=false`, the lifecycle point `AZ::Component::Activate plus AZ::TickBus::OnTick`, and the exit API `AzFramework::ApplicationRequests::ExitMainLoop`. The fixture remains unavailable for runtime execution until a controlled project registration/enablement and rebuild occur.

Rebuild-gate checks record the exact non-default controls without mutating the live project: `MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION=1` is required before registration/enablement and `MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD=1` is required before any target rebuild. The gate report records `runtime_exit_fixture_rebuild_gate_status=runtime_exit_fixture_rebuild_gate_pass`, `runtime_exit_fixture_rebuild_attempted=false`, and `runtime_exit_fixture_rebuild_result=runtime_exit_fixture_rebuild_not_attempted` when those gates are unset. A future clean fixture exit may prove only bounded runtime command-envelope execution; it is not runtime character proof.

The registration/enable/rebuild slice adds four explicit runtime harness modes:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --register-runtime-exit-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON>
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON>
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --rebuild-runtime-exit-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 1800
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-command --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

Registration uses O3DE CLI external-subdirectory project registration, enablement uses `enable-gem --gem-path`, and rebuild is scoped to `MAXINE_GoldenCorpus.HeadlessServerLauncher`. The live project mutation is limited to `project.json` Gem metadata and is reversible by disabling/removing `MaxineRuntimeExitFixture` and rebuilding the scoped launcher. The fixture command uses Settings Registry keys (`/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true`, `/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks=5`) and never uses `--console-command-file` for fixture proof.

The first live fixture command exited `0` and observed `MAXINE_RUNTIME_EXIT_FIXTURE_REQUESTING_EXIT`, but it was not accepted as runtime execution proof because the runtime output/log scan found Asset Processor negotiation failures, shader serializer errors, and an unexpected auto-load of `Levels/defaultlevel/defaultlevel.spawnable`. The harness records `runtime_exit_fixture_unexpected_level_load=true` and keeps `runtime_exit_fixture_execution_verified=false`, `runtime_execution_verified=false`, and runtime character proof unclaimed. A clean future fixture proof must avoid production/default level load and disqualifying runtime log signals.

Launch-hygiene diagnostics are the next layer. Source inspection on the paired project found the default-level source in `C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus/Registry/load_level.setreg`, where `/O3DE/Autoexec/ConsoleCommands/LoadLevel` is set to `defaultlevel`. O3DE source validation ties that setting to console autoexec processing and the spawnable level system: `SettingsRegistryMergeUtils` supports command-line `--regremove`, `IConsole.h`/`Console.cpp` define and execute `/O3DE/Autoexec/ConsoleCommands`, and `SpawnableLevelSystem.cpp` handles `LoadLevel` by loading the requested spawnable level.

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-launch-hygiene --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-no-default-level --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The no-default-level fixture command keeps the Settings Registry fixture exit keys and adds `--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel` to remove the autoexec `LoadLevel` key for that process. This is a runtime launch-hygiene strategy only: source validation does not prove runtime execution, and a fixture marker plus exit code `0` still fails verification if defaultlevel autoload, production level load, Asset Processor negotiation failures, shader serializer errors, AssetManager asserts, or selected-path missing/load-error signals remain unclassified and disqualifying.

The first bounded no-default-level run still observed `Levels/defaultlevel/defaultlevel.spawnable` and therefore records `blocked_by_default_level_autoload`. That result keeps `runtime_exit_fixture_execution_verified=false` and `runtime_execution_verified=false`; the next safe investigation must explain whether command-line `--regremove` is applied before project registry merge, whether a later per-process override can remove or neutralize the autoexec command, or whether this launcher configuration requires a non-production temp harness level.

LoadLevel override diagnostics pin that investigation as a separate runtime harness layer:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-loadlevel-override --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-loadlevel-override --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The source discovery records that command-line `--regremove` is parsed during command-line settings merges, while console autoexec command notifications can still produce a `SpawnableLevelSystem` deferred load at `/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel`. The selected per-process candidate therefore removes both `/O3DE/Autoexec/ConsoleCommands/LoadLevel` and `/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel`. It does not edit the live project registry or `Levels/defaultlevel`.

The bounded LoadLevel-override fixture run remains unverified: it exited `0` and observed the fixture marker, but still loaded `Levels/defaultlevel/defaultlevel.spawnable`. The report keeps `runtime_loadlevel_override_verified=false`, `runtime_exit_fixture_execution_verified=false`, and `runtime_execution_verified=false`; stdout reports both regremove targets as missing at parse time, so the candidate-specific blocker is `blocked_by_settings_registry_merge_order` while the launch blocker remains `blocked_by_default_level_autoload`. AP negotiation and shader serializer signals remain disqualifying until resolved or source/log-classified.

Later-precedence registry patch diagnostics move past early `--regremove` attempts and source-validate O3DE's final command-line registry-file merge:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-later-registry-patch --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-later-registry-patch --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The selected candidate is `artifact_setreg_merge_patch_null_autoexec_and_deferred_loadlevel`. It generates a temporary `maxine_runtime_later_precedence_loadlevel_null_remove.setreg` under the runtime harness artifact directory and passes it through `--regset-file=<artifact patch>`. Source evidence records `ComponentApplication::MergeUserSettings` final command-line merge after project/project-user registry loads, `SettingsRegistryMergeUtils` `--regset-file` parsing, `.setreg` JSON Merge Patch semantics, Console autoexec notifications, and `SpawnableLevelSystem` deferred-load handling. The generated patch null-deletes `/O3DE/Autoexec/ConsoleCommands/LoadLevel` and `/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel`; it must not be committed as active project configuration and must not mutate `Registry/load_level.setreg`, `Levels/defaultlevel`, or production levels. The rejected `artifact_setregpatch_remove_autoexec_and_deferred_loadlevel` candidate remains recorded because JSON Patch `remove` can fail when the target is absent at command-line parse time.

Patch generation and use require `MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH=1`. A generated patch is source-validated evidence only until a bounded fixture command exits cleanly with no defaultlevel or production level load and no disqualifying AP/shader/runtime log signals. A clean command-envelope proof is still not runtime character proof.

If the selected `.setreg` JSON Merge Patch merges cleanly but `Levels/defaultlevel/defaultlevel.spawnable` still loads, keep the result blocked as `blocked_by_settings_registry_merge_order` / `blocked_by_default_level_autoload`. That combination means the non-mutating final `--regset-file` pass exists but did not run early enough to prevent the project autoexec notification from invoking `LoadLevel`.

Pre-autoexec LoadLevel suppression records the next boundary explicitly:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-pre-autoexec-loadlevel-suppression --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-pre-autoexec-loadlevel-suppression --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

Source evidence now distinguishes early command-line merge, project-user registry merge, project registry merge, final command-line merge, console autoexec notification, and `SpawnableLevelSystem` deferred-load consumption. The selected candidate is `project_registry_load_level_setreg_temporarily_disabled_pre_autoexec`: under the project-mutation gate only, the harness temporarily renames `Registry/load_level.setreg` to a non-`.setreg` suffix before launching the bounded fixture command, writes an artifact backup/rollback reference, and restores the file after the process exits. This is a reversible live project registry mutation; it is not a defaultlevel content mutation, production level mutation, release package, or committed active registry patch. If generated `Cache/pc/bootstrap*.setreg` files still contain `Autoexec/LoadLevel=defaultlevel`, classify the remaining blocker as `blocked_by_project_cache_bootstrap_defaultlevel_autoload`; those cache bootstrap files are read-only evidence in this slice and must not be edited or deleted. A pass still requires no defaultlevel autoload, no production level load, fixture marker observed, expected exit code, and no unclassified AP/shader/runtime log blockers.

Runtime cache-bootstrap LoadLevel source diagnostics pin the generated product layer that can survive source-registry suppression:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-cache-bootstrap-loadlevel-source --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-cache-bootstrap-loadlevel-source --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

Source evidence records `SettingsRegistryBuilder.cpp` as the Asset Processor generator for `bootstrap.<launcher>.<config>.setreg` products and `GameApplication.cpp` as the runtime loader that merges the matching cache bootstrap file from `Cache/pc` before user settings. The diagnostic inventories every `Cache/pc/bootstrap*.setreg` path, hash, mtime, `LoadLevel` value, and `DeferredLoadLevel` value without deleting Asset Cache or treating cache contents as release product proof. The selected gated fixture strategy combines the PR #135 source-registry suppression with a temporary backup/neutralization/restore of generated bootstrap `LoadLevel` keys. It requires `MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION=1`, backs files up under runtime artifacts, restores in a `finally` path, hash-verifies restoration, and still cannot prove runtime execution while defaultlevel autoload or disqualifying AP/shader/runtime signals remain.

Runtime AP/shader signal classification records the final current launch-hygiene boundary:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-ap-shader-signals --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-ap-shader-signal-classification --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The diagnostic separates signal detection from classification and proof. Asset Processor negotiation can be harmless only under the source-validated `wait_for_connect=0` no-defaultlevel fixture envelope with complete APB product evidence and no selected-product load failures. Shader serializer lines can be harmless only when they match the known stale non-selected DX12/Vulkan RHI serialized class IDs while the command runs `-NullRenderer` plus `-rhi=null`. A clean AP/shader-classified fixture exit may verify only command-envelope runtime execution; runtime character proof remains unclaimed without character-specific runtime evidence.

Runtime character product-load evidence is the next layer above command-envelope proof:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-character-product-load --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-character-product-load-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

The product-load diagnostic source-validates `AssetCatalogRequestBus::GetAssetIdByPath`, `AssetCatalogRequests::GetAssetInfoById`, `AZ::Data::AssetManager::GetHandler`, `AZ::Data::AssetManager::GetAsset`, `AZ::Data::Asset::IsReady`, `AZ::Data::Asset::IsError`, and reset/release behavior before any live fixture attempt. The fixture probe is disabled by default and runs only through `/Amazon/MAXINE/RuntimeHarness/EnableCharacterProductLoadProbe=true` plus product list keys under `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/...`. The harness writes those keys into a temporary `.setreg` artifact under `MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH=1` for live attempts. It emits parseable `MAXINE_RUNTIME_PRODUCT_LOAD_*` markers for start, resolution, ready/error/timeout, summary, and release.

A runtime product-load pass requires the PR #136 cache/bootstrap no-defaultlevel strategy, the PR #137 AP/shader classified-harmless envelope, complete APB evidence, no defaultlevel or production level load, no selected-product missing/load-error logs, and every required approved product resolving to a valid `AssetId`, having a registered runtime handler, and reaching ready state. The approved categories are `azmodel`, `actor`, `procprefab`, `motion`, `motionset`, `animgraph`, `pxmesh`, and `azmaterial`. A resolved product with `asset_handler_missing` is a typed blocker. This proof is still narrower than runtime instantiation, spawning, animation, runtime character proof, or production-ready release proof.

Skipped/unavailable is not pass. Strict mode fails with `MXN_VALIDATION_TOOL_UNAVAILABLE` when required local tools are missing.

This wiring does not publish, mutate production levels, contact external services, or claim production-ready completion.
