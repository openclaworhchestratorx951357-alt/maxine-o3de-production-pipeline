# Private Windows O3DE Integration Runner

This runner wiring is for future local O3DE integration checks on a trusted private Windows machine. It does not install, register, or configure a self-hosted runner, and it does not require a runner token.

The manual workflow is:

```text
.github/workflows/o3de-private-windows-integration.yml
```

It is `workflow_dispatch` only and targets:

```yaml
runs-on: [self-hosted, Windows, X64, o3de, maxine-private]
```

The workflow has no `push` or `pull_request` trigger. It requires the confirmation phrase:

```text
I_UNDERSTAND_THIS_REQUIRES_A_PRIVATE_SELF_HOSTED_WINDOWS_RUNNER
```

For an operator checklist before any APB live attempt, use:

```powershell
python tools/ci/private_runner_apb_dry_run_checklist.py
python tools/ci/private_runner_apb_dry_run_checklist.py --json
```

The environment template is:

```text
examples/private-runner/o3de-runner.env.example
```

That template contains no credentials, keeps Editor smoke disabled, and keeps live commands disabled for dry-run readiness.

A sample skipped/unavailable dry-run report is checked in at:

```text
examples/private-runner/apb-dry-run-checklist.unavailable.example.json
```

## Local Environment

Set these on the private runner before attempting integration mode:

```powershell
$env:O3DE_ENGINE_ROOT = "C:\path\to\o3de"
$env:O3DE_PROJECT_PATH = "C:\path\to\maxine-project"
$env:O3DE_EDITOR_EXECUTABLE = "C:\path\to\Editor.exe"
$env:ASSET_PROCESSOR_BATCH_EXECUTABLE = "C:\path\to\AssetProcessorBatch.exe"
```

Validate the golden project fixture before APB or Editor smoke commands:

```powershell
python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness
```

The fixture defines safe project roots, the `Levels/_maxine_smoke` temp-level policy, evidence/log/screenshot roots, and package/prefab proof requirements. It does not create or mutate a real project.

Integration gates:

```powershell
$env:MAXINE_ENABLE_O3DE_INTEGRATION = "1"
$env:MAXINE_ENABLE_ASSET_PROCESSOR_BATCH = "1"
$env:MAXINE_ENABLE_O3DE_EDITOR_SMOKE = "1"
$env:MAXINE_ALLOW_LIVE_O3DE_COMMANDS = "1"
$env:MAXINE_ALLOW_LIVE_EDITOR_COMMANDS = "0"
$env:MAXINE_ALLOW_LIVE_PUBLICATION = "0"
$env:MAXINE_ENABLE_RELEASE_PACKAGING = "0"
```

`MAXINE_ALLOW_LIVE_O3DE_COMMANDS=1` is a hard runner signal. Live Editor smoke additionally requires `MAXINE_ALLOW_LIVE_EDITOR_COMMANDS=1`; keep it `0` for readiness-only checks. Publication and release packaging gates must stay `0`.

Live runtime harness execution has its own non-secret gates and must not reuse Editor gates by accident:

```powershell
$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
```

Keep those unset for fixture/readiness checks. Setting them only permits the harness to consider a bounded runtime command; it does not by itself prove runtime execution or runtime character content.

Runtime exit-fixture execution, if it is ever implemented, adds one more non-secret gate:

```powershell
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
```

That gate must remain unset unless the report has a source-validated, non-shipping, project-scoped fixture command. Project registration/enablement and rebuilds each require their own additional gates:

```powershell
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD="1"
```

Cache-bootstrap diagnostics add two narrower gates. Use `MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_REFRESH=1` only for a source-validated scoped bootstrap refresh, and `MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION=1` only for the backup/neutralize/restore fixture path. Neither gate permits Asset Cache deletion or committing generated cache/bootstrap files.

Runtime character product-load probing adds its own gate and remains disabled by default:

```powershell
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
```

That gate only permits the non-shipping fixture to read the explicit product-load Settings Registry keys and request runtime asset loads for approved products. It does not permit production/defaultlevel mutation, Asset Cache deletion, publication, packaging, spawning, animation proof, or full runtime character proof.

The `.procprefab` handler/surface diagnostic has a separate explicit gate for any future live handler/surface fixture work:

```powershell
$env:MAXINE_ENABLE_RUNTIME_PROCPREFAB_HANDLER_OR_SPAWNABLE_SURFACE="1"
```

The current diagnostic is read-only source discovery. It records that direct `.procprefab` runtime AssetManager load uses the builder/tools-only `AZ::Prefab::PrefabGroupAssetHandler`, while the runtime prefab-equivalent surface is expected to be an AzFramework spawnable surface if a character spawnable product exists. That gate does not permit production/defaultlevel mutation, Asset Cache deletion, publication, packaging, spawning, animation proof, or direct `.procprefab` proof while the handler remains missing.

Approved runtime character spawnable-surface probing has its own gate for any future live fixture work:

```powershell
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
```

The current `--diagnose-runtime-character-spawnable-surface` mode is read-only and does not require launching runtime. It source-validates `AzFramework::Spawnable` and the Prefab Builder `*.prefab` to `.spawnable` product path, then searches APB/AP DB/AssetCatalog-style evidence for character-specific release spawnables. It must reject `Levels/defaultlevel`, production/level spawnables, temp smoke levels, and generic non-character prefabs. This gate does not permit publishing, packaging, Asset Cache deletion, defaultlevel/production mutation, spawning, animation proof, or runtime character proof.

Runtime character spawn-instantiation probing requires both the surface gate and two explicit spawn gates:

```powershell
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
```

These gates only permit the non-shipping fixture to instantiate the already-approved character `.spawnable` through the source-validated `AzFramework::SpawnableEntitiesInterface::SpawnAllEntities` path. The fixture must also keep the product-load gate, temp registry patch gate, project/cache-bootstrap mutation gates, no-defaultlevel strategy, AP/shader classification, and timeout/log capture in place. Spawn proof requires request, ticket, completion, positive spawned entity evidence, selected-surface log scans, cleanup/despawn status, no defaultlevel or production level loads, and clean exit. It does not permit publication, packaging, Asset Cache deletion, production/defaultlevel mutation, animation proof, or full runtime character proof.

Runtime character animation playback-surface probing requires all spawn gates plus two explicit animation-surface gates:

```powershell
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
```

These gates permit only a bounded inspection of the approved spawned entity/component surface and, if source validation and runtime inventory prove a playback-capable EMotionFX surface exists, a bounded playback attempt through source-validated runtime APIs. Product-load or spawn proof alone is insufficient. If the approved spawnable exposes no runtime `ActorComponent`, `AnimGraphComponent`, or `SimpleMotionComponent`, the harness must report `runtime_animation_playback_surface_missing_on_approved_spawned_character` and keep animation/full-character proof false.

Runtime character animation component-wiring surface probing requires all playback-surface gates plus two explicit wiring-surface gates:

```powershell
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
```

These gates permit only a bounded, source-backed check of the approved prefab/component wiring path. The diagnostic source-validates EMotionFX Editor `Actor`, `Simple Motion`, and `Anim Graph` components, `EditorComponentAPIBus` add/property APIs, `PrefabPublicRequestBus` prefab APIs, and prefab-to-spawnable conversion surfaces. It does not hand-author unknown O3DE component JSON and does not mutate defaultlevel or production content. Until an Editor-generated approved prefab update is safely proven and the regenerated approved spawnable exposes runtime EMotionFX component TypeIds after spawn, the harness must keep `runtime_character_animation_component_wiring_claimed=false`, `runtime_character_animation_component_wiring_verified=false`, `runtime_character_animation_claimed=false`, and `runtime_character_proof_verified=false`.

Runtime Actor + Simple Motion component wiring after APB requires the product-load, spawn, playback-surface, and component-wiring gates plus two explicit after-APB gates:

```powershell
$env:MAXINE_ENABLE_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ALLOW_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-actor-simple-motion-component-wiring-after-apb-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

This proof is allowed only after live APB verifies the approved spawnable from the modified source prefab. The runtime fixture records Actor/Simple Motion assignment evidence in `MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY` markers with `actor_asset_id` and `motion_asset_id`, source-validated against `EMotionFX::Integration::ActorComponent::GetActorAsset` and `EMotionFX::Integration::SimpleMotionComponent::GetMotion`. Runtime TypeIds alone are insufficient; the harness may claim `runtime_character_animation_component_wiring_verified=true` only when APB/spawnable proof, runtime Actor and Simple Motion TypeIds, runtime Actor and Motion assignment IDs, cleanup/despawn, and selected log/error scans all pass. If a selected product log scan fails, the result must stay blocked even when TypeIds and assignment IDs are visible.

The approved motion product handler-unregistered diagnostic is source-only unless combined with the strict after-APB fixture. The selected approved motion handler line may be classified harmless only after the spawned runtime Simple Motion component readback verifies the approved motion AssetId; APB product readiness, TypeIds, or handler teardown text alone are not enough:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-approved-motion-product-handler-unregistered-signal --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

It pins the selected signal from `AssetManager.cpp`, `MotionAsset`, `EMotionFXAssetHandler`, `SystemComponent`, `AnimationModule`, and `SimpleMotionComponent`: `No handler was registered for asset of type {00494B8E-7578-4BA2-8B28-272E90680787} but it was still in the AssetManager as {794D1588-3C41-5795-8A9A-EEBD6A663A60}:ddcbe0`. The harness may classify that line as harmless only for the bounded component-wiring proof when the approved motion product was already resolved, handler-checked, loaded ready, released, paired with the handler-unregister teardown line, and the spawned Simple Motion component read back the approved motion AssetId. A live `MAXINE_RUNTIME_PRODUCT_LOAD_ERROR ... error=asset_handler_missing`, a different motion AssetId, a missing ready/release marker, or any other selected product error remains a blocker. This classification is not animation playback proof and is not full runtime character proof.

Runtime shutdown PoolAllocator assertion diagnosis is source-backed and intentionally conservative:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-shutdown-poolallocator-assertions --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-poolallocator-signal-classification-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

The source pin is `AzCore/AzCore/Memory/PoolAllocator.cpp`: `PoolAllocation<Allocator>::~PoolAllocation()` asserts `bucket.m_pages.empty()` at line 470 before `GarbageCollect()`. A selected `PoolAllocator.cpp:470` / `PoolAllocator.cpp(470)` `Found page for bucket` line therefore remains a real runtime shutdown allocator blocker (`blocked_by_runtime_shutdown_poolallocator_assertion`) and is not classified harmless. Runtime TypeIds and assignment readback are still preserved as surface evidence, but formal component wiring must remain false when this selected shutdown assertion is present. Non-matching memory/assertion lines remain blocking under the normal selected log/error scan.

Bounded runtime animation playback execution diagnostics pin the Simple Motion runtime playback API and keep the proof separate from component wiring:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-animation-playback-execution-api --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ALLOW_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ENABLE_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
$env:MAXINE_ALLOW_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-animation-playback-execution-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

The source pin is `EMotionFX::Integration::SimpleMotionComponentRequestBus::PlayMotion`, `GetPlayTime`, `GetDuration`, and `GetMotion`, plus `SimpleMotionComponent::GetMotionInstance`, `MotionInstance::GetIsPlaying`, and `MotionSystem::PlayMotion` / update surfaces. The fixture may claim runtime animation playback only when APB/spawnable proof, runtime Actor and Simple Motion TypeIds, runtime actor/motion assignment readback, the PR #155 motion-handler classification, the PR #157 PoolAllocator selected-log policy, playback request success, bounded tick/time-advance observation, cleanup/despawn, and no-defaultlevel/no-production gates all pass. Motion assignment, TypeIds, product-load evidence, or playback markers alone are not full proof. Full runtime character behavior remains a later gate even if playback is observed.

Runtime animation product-load prerequisite diagnostics isolate access-violation-like failures before any playback claim:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-animation-product-load-prerequisite --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ALLOW_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ENABLE_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
$env:MAXINE_ALLOW_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-animation-product-load-prerequisite-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

This diagnostic records `runtime_animation_product_load_prerequisite_marker_sequence`, `runtime_animation_product_load_prerequisite_spawn_reached`, `runtime_animation_product_load_prerequisite_assignment_readback_reached`, `runtime_animation_product_load_prerequisite_playback_request_reached`, `runtime_animation_product_load_prerequisite_cleanup_reached`, and the runtime exit code. A `0xC0000005` exit remains `blocked_by_runtime_animation_product_load_access_violation`; it is not softened by earlier product-load, spawn, assignment, or playback request markers. If the access violation is absent and the marker sequence reaches the playback request, the product-load prerequisite can be recorded separately from the next playback blocker. Animation proof still requires request success plus bounded observation/time advance.

Runtime Simple Motion playback request-failure diagnostics pin the request preconditions before a playback claim:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-simple-motion-playback-request-failure --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ALLOW_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ENABLE_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
$env:MAXINE_ALLOW_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-simple-motion-playback-request-failure-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

The source pin is `SimpleMotionComponentRequestBus::PlayMotion` and `SimpleMotionComponent::PlayMotionInternal`, which require a non-null `ActorInstance`, a ready `MotionAsset`, and an actor motion system before a `MotionInstance` can be created. The fixture records `MAXINE_RUNTIME_SIMPLE_MOTION_PLAYBACK_REQUEST_PREFLIGHT` and `MAXINE_RUNTIME_SIMPLE_MOTION_PLAYBACK_REQUEST_CALL` markers for ActorInstance availability, actor MotionSystem availability, MotionAsset readiness through `AssetManager::FindAsset<MotionAsset>(..., AssetLoadBehavior::NoLoad).IsReady()`, MotionInstance availability before and after the call, and whether the `PlayMotion` call was reached and returned. Playback may be claimed only when those request preconditions pass, the request succeeds, playback is observed through source-validated runtime state, play time advances across bounded ticks, cleanup/despawn completes, and selected log/error scans remain clean. If a `0xC0000005` exit, PoolAllocator shutdown assertion, selected product-load error, defaultlevel/production-level load, missing ActorInstance, missing MotionAsset readiness, or missing MotionInstance remains, the typed blocker must be preserved and animation proof stays false.

Runtime character behavior smoke diagnostics build on bounded Simple Motion playback without claiming full runtime character proof:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-character-behavior-smoke-gate --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ALLOW_RUNTIME_ACTOR_SIMPLE_MOTION_COMPONENT_WIRING_AFTER_APB="1"
$env:MAXINE_ENABLE_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
$env:MAXINE_ALLOW_RUNTIME_ANIMATION_PLAYBACK_EXECUTION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_BEHAVIOR_SMOKE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_BEHAVIOR_SMOKE="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-character-behavior-smoke-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

The source pin adds `AZ::Entity::GetState` / `GetComponents`, `AZ::TransformBus::HasHandlers`, `AZ::TransformBus::Events::GetWorldTM`, and `AZ::Transform::IsFinite` to the existing Actor/Simple Motion playback surface. The live fixture records `MAXINE_RUNTIME_CHARACTER_BEHAVIOR_SMOKE_OBSERVE` and `MAXINE_RUNTIME_CHARACTER_BEHAVIOR_SMOKE_SUMMARY` markers for actual pre-observation entity state, post-observation entity state, remained-valid status, component inventory stability, ActorInstance and MotionInstance availability before/after the observation window, transform readback validity, monotonic playback time, cleanup/despawn, clean exit, and selected log scan status. The smoke gate may claim only `runtime_character_behavior_smoke_verified=true` when APB/spawnable proof, component wiring, playback request/observation/time advance, repeated bounded ticks, sampled entity state before and after observation, entity/component/transform state, cleanup, clean exit, and selected log/error scans all pass. It must keep `runtime_character_proof_claimed=false` and `runtime_character_proof_verified=false`; visual behavior, locomotion/controller behavior, material/render validation, physics/collision behavior, publication, release packaging, and production-ready release status remain later gates.

Full runtime character proof contract diagnostics are source/report-only unless a future slice explicitly implements every full-character gate:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-full-runtime-character-proof-contract --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --runtime-character-behavior-smoke-report artifacts/o3de-integration/runtime-harness/runtime-character-behavior-smoke-live-report.json --timeout-seconds 120
```

The contract diagnostic pins the difference between verified spawn/instantiation, runtime component wiring, bounded Simple Motion playback, broader behavior smoke, and full runtime character proof. It may set `full_runtime_character_proof_contract_pinned=true` and `full_runtime_character_proof_contract_verified=true` when the contract/report is source-validated, but those fields verify only the contract. Full character proof still requires explicit gates for visual/render/material validation, longer/repeated behavior stability, selected log/error scan cleanliness, cleanup/recovery, and any source-backed locomotion/controller or collision/physics claims that apply to the approved character. Behavior smoke is rejected as full proof, publication/release packaging is rejected for this slice, and Understand-Anything graphs remain developer comprehension only. The diagnostic must keep `runtime_character_proof_claimed=false` and `runtime_character_proof_verified=false` until every required full-character gate is implemented and passed.

Visual/material proof-surface diagnostics pin the authorized proof lane without claiming rendered visual evidence:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-visual-material-proof-surface --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --runtime-character-behavior-smoke-report artifacts/o3de-integration/runtime-harness/runtime-character-behavior-smoke-live-report.json --timeout-seconds 120
```

The source pin records that the existing no-defaultlevel runtime envelope uses `-NullRenderer` / `-rhi=null`, which O3DE launcher source treats as console mode, and that Atom `FrameCaptureRequestBus` explicitly reports capture availability with `CanCapture` that may be false when null renderer is used. NullRenderer is not visual proof. The same diagnostic source-validates deferred capture candidates through Atom frame capture and Editor screenshot helper surfaces, plus material/product readiness through `AZ::RPI::MaterialAsset` (`azmaterial`), `MaterialComponentController` material asset readback/readiness, and `MeshComponentController` model asset/model readback. APB material inventory is a readiness sub-gate, not rendered visual/material proof: ready `azmodel`, `actor`, and `azmaterial` products may set `visual_material_product_inventory_gate_verified=true`, but `visual_material_rendered_evidence_gate_verified=false`, `visual_material_gate_verified=false`, `full_runtime_character_visual_material_gate_verified=false`, `runtime_character_proof_claimed=false`, and `runtime_character_proof_verified=false` must remain until a future renderer or Editor viewport proof actually captures and validates visual/material evidence without production/defaultlevel mutation.

Editor viewport visual/material evidence diagnostics are bounded to the current safe Editor command envelope:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-editor-viewport-visual-material-evidence --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

The diagnostic source-validates Atom `FrameCaptureRequestBus::CanCapture`, `CaptureScreenshot`, `CaptureScreenshotForWindow`, the Editor screenshot helper viewport preparation path, and Editor viewport camera framing helpers. It also records that the current Editor smoke wrapper still launches with `-NullRenderer` / `-rhi=Null`; because frame capture may be unavailable under null renderer, this diagnostic must block rendered evidence with `blocked_by_editor_viewport_capture_requires_non_null_rhi` instead of requesting capture or claiming visual/material proof. Screenshot existence alone, APB material inventory, behavior smoke, and component wiring are not rendered visual/material proof. Until a future non-null Editor/renderer lane captures and validates content, nonblank pixels, character presence, and material presence in a safe temp context, the report must keep `visual_material_rendered_evidence_gate_verified=false`, `visual_material_gate_verified=false`, `full_runtime_character_visual_material_gate_verified=false`, `runtime_character_proof_claimed=false`, and `runtime_character_proof_verified=false`.

Non-null Editor render capture envelope diagnostics define the separate visual-capture command lane while preserving the existing smoke lane:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-non-null-editor-render-capture-envelope --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --editor-render-capture-rhi dx12 --timeout-seconds 180
```

The NullRenderer-safe Editor smoke envelope remains unchanged for non-visual automation. The non-null capture diagnostic uses a separate mode and selected RHI (`dx12` or `vulkan`), omits `-NullRenderer`, records `non_null_editor_render_capture_null_renderer_used=false`, and source-validates the O3DE command-line boundary through `GameApplication.cpp` (`commandSwitchNullRenderer`, `commandSwitchRhi`, and the `rhi=null` console/null-renderer branch). It also reuses the Atom `FrameCaptureRequestBus` source pins from the viewport proof-surface slice and records DX12/Vulkan RHI module availability from the local engine source. This is a command envelope, not rendered visual/material proof: launch/RHI readiness or screenshot API availability may at most prove capture readiness. The visual/material gate remains false until a safe temp visual context is created, the approved character is displayed/framed, capture is requested and completed, artifact format/dimensions/size are validated, content/nonblank/character/material presence checks pass, cleanup/log scans pass, and no production/defaultlevel/Asset Cache/cache-heuristic safety violation occurs.

Non-null Editor visual runner readiness diagnostics pin the next safety boundary without launching Editor:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-non-null-editor-visual-runner-readiness
```

This mode is a readiness contract, not rendered visual/material proof. It source-validates the wrapper/report/schema/docs contract, preserves the PR #165 non-null render/capture command envelope, keeps the existing NullRenderer-safe Editor smoke lane unchanged, records `selected_rhi=dx12` by default (`vulkan` remains schema-routed), and blocks live launch with `blocked_by_non_null_editor_render_capture_requires_visible_desktop_session` until visible desktop/session and GPU/driver readiness are proven by the runner. It pins the future temp visual scene root to `Levels/_maxine_visual_smoke`, forbids defaultlevel and production-level mutation, requires cleanup policy verification, and pins sanitized capture artifacts under `artifacts/o3de-integration/editor-smoke`. Screenshot capture, character display, content validation, rendered visual/material evidence, the visual/material gate, and full runtime character proof all remain false until a later live non-null visual capture slice actually satisfies those gates.

Non-null Editor desktop/RHI readiness diagnostics verify the runner prerequisites without launching Editor:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-non-null-editor-desktop-rhi-readiness --editor-render-capture-rhi dx12
```

This mode is readiness only, not rendered visual/material proof. The source contract pins Microsoft Windows session checks through `ProcessIdToSessionId`, `WTSGetActiveConsoleSessionId`, and `OpenInputDesktop` (Microsoft Learn: `https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-processidtosessionid`, `https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-wtsgetactiveconsolesessionid`, `https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop`), GPU/driver inventory through `Win32_VideoController` (`https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-videocontroller`), and O3DE RHI source availability through the existing `GameApplication.cpp` RHI command surface plus Atom DX12/Vulkan module source files. The diagnostic may record `visible_desktop_session_verified`, `gpu_or_driver_readiness_verified`, and `rhi_readiness_verified`, but it must keep `non_null_editor_launch_attempted=false`, `editor_visual_material_capture_requested=false`, `visual_material_capture_readiness_verified=false`, `visual_material_gate_verified=false`, and `runtime_character_proof_verified=false` in this slice. If a current runner lacks an interactive input desktop, usable GPU/driver, or selected RHI source/module availability, the report must preserve a precise blocker such as `blocked_by_non_null_editor_render_capture_requires_visible_desktop_session`, `blocked_by_non_null_editor_render_capture_requires_gpu_or_driver`, or `blocked_by_non_null_editor_render_capture_rhi_unavailable`. The temp visual scene policy remains pinned to `Levels/_maxine_visual_smoke`, capture artifacts remain pinned to `artifacts/o3de-integration/editor-smoke`, and the existing NullRenderer-safe Editor smoke lane remains unchanged.

Bounded live non-null Editor launch without screenshot diagnostics verify only the next launch-readiness step:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-live-non-null-editor-launch --editor-render-capture-rhi dx12
```

The `live-non-null-editor-launch` mode first preserves the desktop/session/GPU/RHI readiness contract and validates the live launch source contract, then launches Editor only when both gates are verified for the current run. The launch command omits `-NullRenderer`, records the selected non-null RHI (`dx12` by default, with `vulkan` still schema-allowed for a later source-validated fallback), uses `--skipWelcomeScreenDialog`, `--autotest_mode`, `--project-path`, and a repo-root-bootstrapped `--runpython` wrapper, and exits through the existing Editor Python `exit_no_prompt` path. This is a live launch proof and not rendered visual/material proof: it must not request screenshot/frame capture, must not create a temp visual scene, must not mutate defaultlevel or production levels, must not delete Asset Cache, and must keep `visual_material_capture_readiness_verified=false`, `visual_material_rendered_evidence_gate_verified=false`, `visual_material_gate_verified=false`, and `runtime_character_proof_verified=false` until a later slice captures and validates rendered content/material evidence.

Bounded Editor screenshot capture artifact readiness diagnostics pin the narrowest source-validated capture artifact step:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-editor-screenshot-capture-artifact-readiness --editor-render-capture-rhi dx12
```

The `editor-screenshot-capture-artifact-readiness` mode preserves the PR #167 desktop/session/GPU/RHI gates and the PR #168 live non-null launch source gate, then launches only when its own source validation for Atom `FrameCaptureRequestBus` screenshot capture and `FrameCaptureNotificationBusHandler` completion is verified. The command omits `-NullRenderer` and records the approved `.png` artifact path under `artifacts/o3de-integration/editor-smoke`, but it does not request capture by default until an active viewport/window or temp visual scene contract is separately verified for the live context. A capture request requires the explicit request gate plus active-viewport verification; without both, the mode reports `blocked_by_editor_screenshot_capture_requires_active_viewport` and keeps capture requested/completed false. When that later gate is satisfied, the mode records request acceptance, completion signal, artifact existence, format, dimensions, size, and sha256. Screenshot artifact readiness is not visual/material proof: artifact existence or dimensions do not prove nonblank content, approved-character presence, material presence, material correctness, the visual/material gate, or full runtime character proof. This lane must not create a temp visual scene, mutate defaultlevel or production levels, delete Asset Cache, use cache heuristics, publish, package a release, or commit raw private logs/generated products. If capture cannot be requested or completed, it reports a typed blocker such as `blocked_by_editor_screenshot_capture_requires_active_viewport`, `blocked_by_editor_screenshot_capture_request_failed`, `blocked_by_editor_screenshot_capture_completion_not_observed`, or `blocked_by_editor_screenshot_capture_artifact_missing`.

Active Editor viewport/temp visual scene readiness diagnostics verify the missing capture-target precondition without requesting capture:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-editor-active-viewport-readiness --editor-render-capture-rhi dx12
```

The `editor-active-viewport-temp-scene-readiness` mode preserves the desktop/session/GPU/RHI gates and the live non-null launch gate, launches with the selected non-null RHI, and source-validates the active viewport/temp scene boundary before screenshot capture is allowed in any later slice. The source pins Atom `FrameCaptureRequestBus::CaptureScreenshot` using the default viewport context window handle, the `InternalCaptureScreenshot` failure paths for missing window handle or missing `SwapChainPass`, the Editor Python viewport APIs (`get_viewport_count`, `get_active_viewport`, `get_viewport_size`, `update_viewport`), and the safe temp scene creation/opening APIs under `Levels/_maxine_visual_smoke`. The diagnostic may verify a temp visual scene/display contract and record a capture-target readiness sub-gate, but it does not create a temp scene by default, does not instantiate the approved character, and does not request screenshot/frame capture. Active viewport/temp scene readiness is not visual/material proof: rendered evidence, nonblank/content validation, character presence, material presence, the visual/material gate, and full runtime character proof remain false until a later bounded capture/content slice actually obtains and validates source-backed rendered evidence.

Exercise safe temp visual scene display context diagnostics move the temp-scene contract one step forward without requesting capture:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-editor-safe-temp-visual-scene-display-context --editor-render-capture-rhi dx12
```

The `editor-safe-temp-visual-scene-display-context` mode launches the non-null Editor lane, source-validates `azlmbr.legacy.general.create_level_no_prompt` / `open_level_no_prompt`, the `CCryEditApp::CreateLevel` save path, viewport readiness probes, FrameCapture target blockers, and the wrapper cleanup contract. It creates only a run-owned temp scene under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context`, then the outer harness performs post-Editor-exit cleanup for that exact run-owned path. No screenshot request is made, no FrameCapture artifact is produced, no approved character is instantiated, and no visual/material proof is claimed. The report must verify cleanup, defaultlevel mutation false, production-level mutation false, production character asset mutation false, release packaging false, publication false, and production-ready status false. Expected blockers include `blocked_by_temp_visual_scene_source_validation_unavailable`, `blocked_by_mutation_policy`, `blocked_by_editor_launch`, `blocked_by_temp_scene_create_or_open`, `blocked_by_active_viewport_window_handle_unavailable`, `blocked_by_framecapture_target_unavailable`, `failed_safe_cleanup_completed`, and `failed_safe_cleanup_incomplete`.

Source-validate nonblocking viewport or SwapChain readiness probe diagnostics reuse the safe temp visual scene/display context and check only capture-target readiness signals:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-editor-nonblocking-viewport-swapchain-readiness --editor-render-capture-rhi dx12
```

The `editor-nonblocking-viewport-swapchain-readiness` mode launches the non-null Editor lane, exercises the run-owned temp scene under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context`, then attempts bounded readiness-only probes for Editor Python active/default viewport metric source availability, Qt viewport widget inventory, Atom `FrameCaptureRequestBus` binding availability, and the FrameCapture target precondition. Source validation pins `azlmbr.legacy.general` viewport methods, default viewport camera context readback, Atom `FrameCaptureRequestBus` reflection, and the C++ path where `CaptureScreenshot` internally obtains the default viewport window handle before requiring a `SwapChainPass`; the potentially blocking live C++ viewport/camera readback calls remain deferred unless `MAXINE_ALLOW_EDITOR_ACTIVE_VIEWPORT_PYTHON_PROBE=1` is set deliberately for a narrow investigation. No screenshot request is made, no FrameCapture artifact is produced, no approved character is instantiated, no rendered visual/material evidence is claimed, and the diagnostic keeps `visual_material_gate_verified=false` and `runtime_character_proof_verified=false`. Expected blockers include `blocked_by_nonblocking_viewport_or_swapchain_probe_source_validation_unavailable`, `blocked_by_python_binding_unavailable`, `blocked_by_qt_viewport_widget_unavailable`, `blocked_by_editor_active_viewport_window_handle_unavailable`, `blocked_by_editor_default_viewport_camera_context_unavailable`, `blocked_by_active_viewport_window_handle_unavailable`, `blocked_by_swapchain_probe_unavailable`, and `blocked_by_framecapture_target_unavailable`.

Approved Editor-generated runtime animation component wiring diagnostics require the Editor smoke gates plus an explicit generation marker:

```powershell
$env:MAXINE_ENABLE_APPROVED_RUNTIME_ANIMATION_COMPONENT_WIRING_EDITOR_GENERATION="1"
```

The optional `MAXINE_ALLOW_APPROVED_RUNTIME_ANIMATION_COMPONENT_WIRING_EDITOR_GENERATION=1` marker may be set only for a bounded Editor-generated update path after source validation proves save semantics. The current pinned result is a typed blocker: `PrefabPublicRequestBus` exposes `CreatePrefabInMemory` and `InstantiatePrefab`, but `CreatePrefabAndSaveToDisk` and `SavePrefab` are source-valid only on `PrefabPublicInterface` and are not reflected onto the Editor Python automation bus. That means the diagnostic may probe Editor Actor + Simple Motion add/property assignment in the approved temp smoke level, but it must keep `approved_runtime_animation_component_wiring_source_prefab_modified=false`, `approved_runtime_animation_component_wiring_prefab_save_verified=false`, `runtime_character_animation_component_wiring_verified=false`, and all runtime animation/full-character proof flags false.

Approved prefab save/update automation surface diagnostics require the Editor smoke gates plus an explicit save/update surface marker:

```powershell
$env:MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_AUTOMATION_SURFACE="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-automation-surface --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

The optional `MAXINE_ALLOW_APPROVED_PREFAB_SAVE_UPDATE_AUTOMATION_SURFACE=1` marker may be set only for a bounded scratch save/update fixture after source validation proves a callable save route. The current diagnostic is source-validation-only: `PrefabPublicInterface::CreatePrefabAndSaveToDisk` and `PrefabPublicInterface::SavePrefab` are available in C++, with `PrefabPublicHandler` using `CreatePrefabInMemory`, `SaveTemplateToFile`, `GetTemplateIdFromFilePath`, and `SaveTemplate`, but the Python-exposed `PrefabPublicRequestBus` does not reflect the save events. The diagnostic must report `blocked_by_prefab_save_interface_not_available_to_automation`, reject defaultlevel/production paths, leave scratch save unattempted, keep the approved source prefab unmodified, and keep runtime component wiring, runtime animation, and full runtime character proof false.

Approved prefab save/update bridge diagnostics require the Editor smoke gates plus an explicit bridge marker:

```powershell
$env:MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_BRIDGE="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-bridge --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

The optional `MAXINE_ALLOW_APPROVED_PREFAB_SAVE_UPDATE_BRIDGE=1` marker may be set only after a source-backed Editor bridge is registered and scratch save/update is ready to execute. The current bridge diagnostic is source-validation-only: it confirms the C++ prefab save APIs and Editor-module patterns, but the repo-owned `MaxineRuntimeExitFixture` Gem is runtime-client-only and has no `.Editor` / `.Tools` module registration or `AzToolsFramework` bridge dependency. It must report `blocked_by_prefab_save_bridge_requires_editor_gem_registration`, keep scratch save unattempted, keep the approved source prefab unmodified, and keep runtime component wiring, runtime animation, and full runtime character proof false.

Approved prefab save/update bridge-host diagnostics require the Editor smoke gates plus the explicit bridge-host marker:

```powershell
$env:MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_BRIDGE_HOST="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-bridge-host --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

This diagnostic is still host-readiness only. It may prove that the repo-owned `MaxineRuntimeExitFixture.Editor` target is present, has an Editor-only `AzToolsFramework` dependency, reflects `azlmbr.maxine.prefab_bridge.get_prefab_save_update_bridge_host_status`, and is callable from Editor Python. Bridge-host source validation is repo-owned; `O3DE_ENGINE_ROOT` only enables optional engine-source reference evidence, and unavailable engine refs must be reported separately instead of blocking host proof. It must not claim `approved_prefab_save_update_bridge_verified=true`, scratch save/update verification, approved source-prefab mutation, runtime component wiring, runtime animation, or full runtime character proof.

Approved prefab save/update route diagnostics require the Editor smoke gates plus the explicit route marker:

```powershell
$env:MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_ROUTE="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-route --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

The optional `MAXINE_ALLOW_APPROVED_PREFAB_SAVE_UPDATE_ROUTE=1` marker is used only for bounded route fixture execution. The route is scratch-only: it calls `azlmbr.maxine.prefab_bridge.save_prefab_update_scratch_probe`, writes only under `<active-project>/Assets/_maxine_smoke/prefabs/` after resolving the active project root from `AZ::Utils::GetProjectPath`, rejects defaultlevel, production-level, generated product/cache, outside-project substring, other-project, unapproved absolute, and traversal paths, parses the saved prefab JSON, records the after-hash, and cleans the scratch file. It must keep the approved source prefab unmodified, leave Actor + Simple Motion persistence false, skip APB/runtime mutation verification when no approved source mutation occurred, and keep runtime component wiring, runtime animation, and full runtime character proof false.

Approved source-prefab parent-focus/link-context override apply route diagnostics require the Editor smoke gates plus the explicit parent-link marker:

```powershell
$env:MAXINE_ENABLE_APPROVED_SOURCE_PREFAB_PARENT_LINK_OVERRIDE_APPLY_ROUTE="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-source-prefab-parent-link-override-apply-route --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

This diagnostic may mutate only the approved source prefab path through source-backed Editor/prefab APIs. It first verifies that the entity and Actor/Simple Motion component IDs belong to the approved source prefab, then focuses the owning prefab, switches to the parent focus/link context, applies Actor + Simple Motion component overrides, restores focus, saves the approved source prefab, and claims success only if the source prefab changed in this run and parsed source-template marker evidence finds both `ActorAsset` and `MotionAsset`. It must not hand-author unknown JSON, run APB/runtime proof without fresh persisted markers, claim runtime component wiring from Editor-only evidence, or claim animation/full-character proof.

Approved source-prefab source-backed override-path/template-update diagnostics use the same live Editor gates plus the explicit template-update marker:

```powershell
$env:MAXINE_ENABLE_APPROVED_SOURCE_PREFAB_OVERRIDE_PATH_GENERATION_TEMPLATE_UPDATE="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-source-prefab-override-path-generation-template-update --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 900
```

This diagnostic selects the source-backed `InstanceToTemplateInterface::GenerateEntityDomBySerializing` + `GeneratePatch` + `PatchEntityInTemplate` route when the parent-link override path is unavailable. It may claim source-template persistence only when the saved approved source prefab changes in the current run, parsed marker evidence finds both `ActorAsset` and `MotionAsset`, and route-specific rejection probes call `apply_approved_source_prefab_override_path_generation_template_update` directly. Legacy `save_approved_source_prefab_wiring` rejection probes are preserved separately and do not verify the new route safety contract. A positive source-template result still does not claim APB regeneration, runtime Actor/Simple Motion TypeIds, runtime asset assignments, animation playback, full runtime character behavior, publication, or release packaging.

Approved runtime character prefab-source generation has a narrower gate when a repo-owned source must be staged into the live project scanfolder:

```powershell
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_PREFAB_SOURCE_GENERATION="1"
```

The committed source contract lives at `examples/o3de-golden-project/source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab` and targets the project-relative scanfolder path `Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab`. The APB harness stages that source into the live project scanfolder only when the gate above is set, refuses to overwrite mismatched existing source, and records `approved_runtime_character_prefab_source_staging` evidence in the APB report. It is source input only; never commit generated `.spawnable` products, Asset Cache files, or live private project content. The read-only diagnostic entry point is:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-character-prefab-source --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

That diagnostic records whether the repo-owned `.prefab` is approved, non-defaultlevel, non-production, non-temp, and character-specific by referencing the approved release `.procprefab`. It then checks whether APB/AP DB evidence contains `pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable`. Finding that product is not product-load proof until a bounded runtime fixture safely loads it ready with no defaultlevel or production-level side effects.

The repository now owns source for `o3de/gems/MaxineRuntimeExitFixture`, but it is disabled by default and is not runtime execution proof. Without the mutation/rebuild gates, the runner records source and rebuild-gate readiness only; it must not register the Gem, rebuild runtime targets, or launch a fixture command.

## Beginner Commands

Default offline validation:

```powershell
python tools/validation/validate_all.py
```

Runner readiness:

```powershell
python tools/ci/o3de_runner_readiness.py
python tools/ci/o3de_runner_readiness.py --strict
```

Suite dry-run/readiness only:

```powershell
python tools/ci/run_o3de_integration_suite.py --dry-run
```

Fixture suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --mode fixture
```

Gated local integration suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --strict-integration
```

APB-only live suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --apb-only --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --apb-only --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

Editor smoke readiness:

```powershell
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root $env:O3DE_ENGINE_ROOT --project $env:O3DE_PROJECT_PATH --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict
```

Runtime harness fixture and readiness:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --mode fixture
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --pin-runtime-command --strict --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json --timeout-seconds 120
```

The pinned runtime command envelope is:

```text
C:/src/o3de/build/windows/bin/profile/MAXINE_GoldenCorpus.HeadlessServerLauncher.exe --project-path=C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus -NullRenderer -rhi=null --regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0 --console-command-file=<runtime-harness-artifact>/maxine_runtime_command_quit.cfg
```

The generated command file contains only `quit`. Command pinning verifies the bounded, non-publishing envelope and does not claim runtime execution or runtime character proof.

On the current paired runner, the first gated live execution of this pinned envelope captured stdout/stderr plus `user/log/Server.log`, exited before timeout with code `3221225477`, and recorded no missing actor, mesh, material, animation, asset, or load-error signals. The harness renders the code as `0xC0000005` and `-1073741819`, classifies it as `runtime_execution_failed_access_violation_like_exit`, and summarizes observed AssetManager shutdown asserts, Asset Processor negotiation failure, and shader serializer errors. That result is a runtime execution failure, not runtime character proof; keep `runtime_execution_verified=false` and `runtime_character_proof_claimed=false` until a bounded live command exits cleanly and captures character-specific evidence.

Do not broaden expected exit codes to accept `3221225477`. Safer runtime variants may be tried only through the harness, with the same gates, timeout, stdout/stderr/log capture, no production level, no publication, no release packaging, and an explicit `runtime_command_variant_*` result.

The safer quit-variant diagnostic entry point is:

```powershell
$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-quit-variants --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The diagnostic preserves the original pinned command, records rejected help/version/no-console/delayed/fallback variants unless source validates a bounded exit strategy, and attempts only source-validated no-level variants. `-NullRenderer`-only and `-rhi=null`-only are currently the first attemptable HeadlessServerLauncher variants because local source validates both as console-mode triggers. A clean quit variant can verify bounded runtime command execution, but not runtime character proof.

The source-validated exit-strategy diagnostic entry point is:

```powershell
$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-exit-strategies --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

This diagnostic focuses on the exit mechanism instead of more renderer-flag permutations. It records source refs for console-command-file timing, `quit`, Settings Registry runtime console commands, and launcher lifecycle callbacks before deciding whether a candidate can run. On the current source inspection, immediate console-file quit and Settings Registry runtime-console quit are source-validated but rejected because they still execute before the launcher main loop; delayed/tick-queued quit, help/version/no-op, command-line-plus-quit, ServerLauncher fallback, and temp/sandbox level exit remain rejected until source validates a bounded no-production-level exit path. A blocked diagnostic is honest evidence and must not be converted into runtime execution proof.

The harness-side exit-fixture diagnostic entry point is:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-exit-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

This diagnostic stops probing unsupported launcher flags. It records the #129 fixture-discovery result and keeps runtime execution unattempted and runtime character proof unclaimed.

The repo-owned fixture source and rebuild-gate checks are:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --check-runtime-exit-fixture-source --strict --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON>
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --check-runtime-exit-fixture-rebuild-gate --strict --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON>
```

The source check validates `o3de/gems/MaxineRuntimeExitFixture`, Gem metadata, CMake/source shape, disabled-by-default behavior, `AZ::TickBus::OnTick`, `AzFramework::ApplicationRequests::ExitMainLoop`, and Settings Registry keys. The rebuild-gate check records registration, enablement, and build command candidates but does not mutate the live project or rebuild unless the explicit gates above are set.

The product-load source diagnostic and gated fixture entry points are:

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

Run APB product evidence first and rebuild the fixture under `MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD=1` whenever the fixture C++ source changed. The harness writes the product list as an artifact `.setreg` file under the temp-registry-patch gate so command-line registry value limits cannot truncate the product matrix. The product-load pass criteria require every approved selected product to resolve to a valid runtime `AssetId`, have a registered runtime `AssetManager` handler, reach ready state, avoid selected-product load errors, preserve no-defaultlevel launch hygiene, and keep the PR #137 AP/shader signals within their classified harmless conditions. A resolved product that reports `asset_handler_missing` remains a typed product-load blocker, not a partial pass.

The `.procprefab` handler/surface diagnostic entry point is:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-procprefab-handler-or-spawnable-surface --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

This mode does not launch runtime. It source-validates `AZ::Prefab::ProceduralPrefabAsset`, `AZ::Prefab::PrefabGroupAssetHandler`, `PrefabBuilder.Builders/Tools`, `AzFramework::Spawnable`, `SpawnableAssetHandler`, `SpawnableSystemComponent`, and `SpawnableEntitiesInterface`. It preserves the `.procprefab` `asset_handler_missing` blocker and records whether a runtime-equivalent spawnable/prefab candidate exists; source discovery alone cannot claim product-load, spawn, animation, or runtime character proof.

The approved character spawnable-surface diagnostic entry point is:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-character-spawnable-surface --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

Historical PR #140 evidence recorded `runtime_character_spawnable_surface_generation_required` before the approved source existed. Current PR #141 evidence expects and can verify `pc/assets/characters/maxine_goldencorpus/prefabs/release_rigged.spawnable` after APB stages the repo-owned source. The diagnostic still does not launch runtime by itself; product-load and spawn proof require their gated fixture modes.

Runtime spawn-instantiation diagnostic and fixture entry points are:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-character-spawn-instantiation --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-character-spawn-instantiation-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

Runtime animation playback-surface diagnostic and fixture entry points are:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-character-animation-playback-surface --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-character-animation-playback-surface-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

Runtime animation component-wiring surface diagnostic and fixture entry points are:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-character-animation-component-wiring-surface --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE="1"
$env:MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_COMPONENT_WIRING_SURFACE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-character-animation-component-wiring-surface-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

Approved Editor-generated animation component wiring diagnostic entry points are:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-runtime-animation-component-wiring-editor-generation --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180

$env:MAXINE_ENABLE_APPROVED_RUNTIME_ANIMATION_COMPONENT_WIRING_EDITOR_GENERATION="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnostic-mode approved-animation-component-wiring-generation --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

Approved prefab save/update automation surface diagnostic entry points are:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-automation-surface --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180

$env:MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_AUTOMATION_SURFACE="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnostic-mode approved-prefab-save-update-automation-surface --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 180
```

Approved prefab save/update route and scratch-proof diagnostic entry points are:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnose-approved-prefab-save-update-route --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240

$env:MAXINE_ENABLE_APPROVED_PREFAB_SAVE_UPDATE_ROUTE="1"
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode local_editor_python --enable-editor-smoke --strict-integration --diagnostic-mode approved-prefab-save-update-route --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 240
```

When the APB evidence, runtime readiness, and command pinning gates are clean, registration and enablement are run through the harness rather than by hand:

```powershell
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --register-runtime-exit-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON>
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON>
```

The mutation is limited to project Gem metadata. Rollback is: disable/remove `MaxineRuntimeExitFixture` from `gem_names`, remove the repo fixture path from `external_subdirectories`, then rebuild the scoped launcher if needed. Do not commit the live project `project.json`.

The scoped rebuild and fixture command require their own gates:

```powershell
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --rebuild-runtime-exit-fixture --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 1800

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-command --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The fixture command must use Settings Registry keys and must not use `--console-command-file`. If the launcher auto-loads `Levels/defaultlevel/defaultlevel.spawnable` or emits Asset Processor negotiation/shader serializer/AssetManager/assert errors, the harness records a failure such as `runtime_exit_fixture_execution_failed_disqualifying_log_signal` and keeps runtime execution proof and runtime character proof false.

Launch-hygiene diagnostics inspect and, when gated, exercise the no-default-level fixture command:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-launch-hygiene --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-no-default-level --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The current project autoload source is `Registry/load_level.setreg`, which sets `/O3DE/Autoexec/ConsoleCommands/LoadLevel=defaultlevel`. The no-default-level command uses `--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel` so the process does not execute that autoexec level command. This does not mutate `Levels/defaultlevel`, does not edit production content, and does not claim character proof. A pass still requires no unexpected level loads, no production level load, fixture marker evidence, expected exit code, no timeout, and absent or source-classified Asset Processor negotiation and shader serializer signals.

If the command exits `0` but still reports `runtime_default_level_autoload_detected=true`, stop at that report. The expected typed blocker is `blocked_by_default_level_autoload`; do not try to compensate by editing `Levels/defaultlevel`, broadening exit codes, or treating the fixture marker as proof.

LoadLevel override diagnostics add the Settings Registry merge-order and deferred-load candidate matrix:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-loadlevel-override --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-loadlevel-override --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The selected LoadLevel candidate removes both `/O3DE/Autoexec/ConsoleCommands/LoadLevel` and `/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel` per process. If stdout reports those JSON pointers as missing and defaultlevel still autoloads, record `blocked_by_settings_registry_merge_order` for the candidate and keep runtime proof false. This is still not permission to mutate `Registry/load_level.setreg`, `Levels/defaultlevel`, production levels, or shipping behavior.

Later-precedence registry patch diagnostics add the final command-line `--regset-file` path:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-later-registry-patch --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-later-registry-patch --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The selected candidate is `artifact_setreg_merge_patch_null_autoexec_and_deferred_loadlevel`. The harness writes a temporary `maxine_runtime_later_precedence_loadlevel_null_remove.setreg` under runtime harness artifacts and passes it as `--regset-file=<artifact patch>`. Source refs pin that this file is merged at the final command-line pass after project/project-user registry, and `.setreg` is parsed as JSON Merge Patch. This patch null-deletes the Autoexec `LoadLevel` key and the `SpawnableLevelSystem` deferred load key without editing live project registry files or `Levels/defaultlevel`. The failed JSON Patch remove candidate remains recorded as unsafe for absent targets. Do not commit active generated patch files; sanitized examples are the only acceptable committed patch evidence.

If the fixture run still records defaultlevel autoload after the `.setreg` patch and no Settings Registry merge failure is present, keep the runtime result failed with `blocked_by_settings_registry_merge_order`. The later file merge is then source-valid but too late for this launcher path's autoexec notification timing.

Pre-autoexec LoadLevel suppression diagnostics inspect the earlier side-effect surface and may run a reversible project-registry suppression only under an explicit mutation gate:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-pre-autoexec-loadlevel-suppression --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-pre-autoexec-loadlevel-suppression --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

The selected pre-autoexec candidate is `project_registry_load_level_setreg_temporarily_disabled_pre_autoexec`. Source inspection shows that project-user registry overlays either merge before the project registry file or after the autoexec notification has already fired, while project registry files notify the console as each file merges. The harness therefore temporarily renames `C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus/Registry/load_level.setreg` before launch, writes `maxine_runtime_pre_autoexec_load_level_setreg_backup.txt` under runtime artifacts, and restores the original file in a `finally` path. Manual rollback after interruption is to move `load_level.setreg.maxine_pre_autoexec_disabled` back to `load_level.setreg`.

This mode must not edit `Levels/defaultlevel`, production levels, shipping fixture behavior, or committed project-private content. A clean exit and fixture marker are still insufficient if defaultlevel autoload, AP negotiation, shader serializer, missing/load/error/assert, timeout, or crash-like signals remain unclassified and disqualifying.

If the project registry file is restored but defaultlevel still loads, inspect the pre-autoexec report fields `runtime_pre_autoexec_cache_bootstrap_loadlevel_sources` and `runtime_pre_autoexec_cache_bootstrap_loadlevel_blocker`. Generated `Cache/pc/bootstrap*.setreg` files can carry the same Autoexec LoadLevel setting into the runtime before source-registry suppression helps. Those cache bootstrap files are generated products and must not be edited or deleted in this slice; classify the result as `blocked_by_project_cache_bootstrap_defaultlevel_autoload` and keep runtime proof false.

Cache-bootstrap LoadLevel source diagnostics inventory that generated layer and may run a stricter gated fixture strategy:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-cache-bootstrap-loadlevel-source --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-cache-bootstrap-loadlevel-source --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

This mode source-validates `SettingsRegistryBuilder.cpp` as the generator of `bootstrap.<launcher>.<config>.setreg` products and `GameApplication.cpp` as the runtime cache-bootstrap loader. It scans `Cache/pc/bootstrap*.setreg` read-only by default. The fixture strategy can temporarily backup, neutralize, restore, and hash-verify scoped bootstrap files, but only under `MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION=1`; Asset Cache deletion remains forbidden, generated cache/bootstrap files must not be committed, and runtime proof still requires no defaultlevel load plus resolved or source-classified AP/shader signals.

AP/shader signal classification diagnostics source-validate the remaining no-defaultlevel fixture blockers:

```powershell
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-runtime-ap-shader-signals --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120

$env:MAXINE_ENABLE_O3DE_RUNTIME_HARNESS="1"
$env:MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS="1"
$env:MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION="1"
$env:MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION="1"
python tools/o3de/runtime_harness.py --manifest examples/manifests/release_rigged.pass.example.json --enable-runtime-exit-fixture-ap-shader-signal-classification --strict-integration --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --apb-report <LATEST_APB_REPORT_JSON> --timeout-seconds 120
```

This mode preserves the PR #136 cache-bootstrap no-defaultlevel strategy and then classifies only source-pinned signal families. Asset Processor negotiation is harmless only when `Launcher.cpp` is using `wait_for_connect=0`, APB product evidence is complete, no selected product fails to load, and the fixture remains bounded/no-level. Shader serializer lines are harmless only when they match the known stale non-selected DX12/Vulkan RHI class IDs under the `-NullRenderer` plus `-rhi=null` fixture envelope. Any different AP/shader/assert/load-error signature remains disqualifying, and runtime character proof remains false.

When using the produced paired Editor on the controlled runner, pass it explicitly:

```powershell
$env:O3DE_EDITOR_EXECUTABLE = "C:/src/o3de/build/windows/bin/profile/Editor.exe"
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable $env:O3DE_EDITOR_EXECUTABLE --strict --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict --editor-executable $env:O3DE_EDITOR_EXECUTABLE --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

Gated Editor smoke suite:

```powershell
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --include-editor-smoke --allow-live-o3de-commands --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --editor-smoke-manifest examples/manifests/release_rigged.pass.example.json --strict-integration
```

When `--include-editor-smoke` is set, the suite runs the APB strict baseline first and then invokes the gated live Editor smoke wrapper. The wrapper requires `MAXINE_ALLOW_LIVE_EDITOR_COMMANDS=1`, a paired Editor executable, complete APB product evidence, valid `EditorPythonBindings`, and the temp-level policy under `Levels/_maxine_smoke`.

The direct live smoke command is:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

The manual workflow modes `apb_live_non_strict` and `apb_live_strict` set APB gates only. The modes `editor_smoke_readiness`, `editor_smoke_live_non_strict`, and `editor_smoke_live_strict` add Editor smoke readiness/live checks. Live Editor modes require both live gates, run the APB strict baseline first, keep publication and release packaging disabled, and fail closed if the paired Editor executable is unavailable, strict readiness regresses, the Editor process exits nonzero, or the Editor smoke stalls.

The first local gated live Editor smoke attempt against the produced paired Editor is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.stalled.example.json
```

That report is a blocker record: Editor launched and created an approved temp level, but the smoke timed out before the in-Editor report completed. It is not a pass.

The follow-up diagnostic slice adds explicit Editor smoke modes:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode hello --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode product-evidence --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode temp-level --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode entity-minimal --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode full --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

Run them in order, stopping at the first failure or stall. Each run writes a `progress.jsonl` file that classifies the latest script-side phase. The PR #116 stall was isolated to `idle_wait_stall`; the smoke now skips that blocking `idle_wait_frames(5)` by default after `create_level_no_prompt` returns. Use `MAXINE_EDITOR_SMOKE_ENABLE_IDLE_WAIT=1` only for targeted debugging of the old stalled behavior.

The fixed full smoke pass is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.pass.example.json
```

After this fix, the direct full smoke and the `--include-editor-smoke` suite path pass on the controlled runner. Publication and release packaging gates remain closed, and production levels remain forbidden.

Actor/prefab/component binding hardening adds focused modes after APB product evidence is clean:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode component-binding --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode actor-binding --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode actor-asset-assignment --timeout-seconds 360 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode prefab-binding --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode prefab-instantiation --timeout-seconds 360 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode procprefab-product-instantiation --timeout-seconds 420 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode procprefab-content-assertions --timeout-seconds 420 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode procprefab-character-component-assertions --timeout-seconds 480 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode runtime-spawnable-proof-surface --timeout-seconds 540 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

These commands still require `MAXINE_ALLOW_LIVE_EDITOR_COMMANDS=1`, complete APB product evidence, strict Editor readiness, and the approved temp-level policy. Actor and prefab checks must report typed non-pass blockers when a binding call, component type ID, property path, or instantiation surface is not safely validated; skipped, unavailable, blocked, or unsupported states must not be counted as pass.

On the current paired runner, `component-binding` passes with Transform and Tag TypeIds plus Tag add/property readback. `actor-binding` proves Actor TypeId discovery, component add, and property readback. `actor-asset-assignment` resolves `jack.actor` through the Asset Catalog and sets `Actor asset` with `EditorComponentAPIBus.SetComponentProperty` using an `azlmbr.asset.AssetId`, then verifies the readback. `prefab-binding` proves `procprefab` product evidence and discovers `azlmbr.prefab` surfaces. `prefab-instantiation` creates a temporary source `.prefab` under `Levels/_maxine_smoke` with `PrefabPublicRequestBus.CreatePrefabInMemory`, instantiates it with `PrefabPublicRequestBus.InstantiatePrefab`, and verifies the created entity/container evidence. `procprefab-product-instantiation` keeps that source-prefab baseline separate and proves direct `.procprefab` product instantiation through `PrefabPublicRequestBus.InstantiatePrefab` using the AssetCatalog-selected product path `assets/characters/maxine/release/maxine_idle_fbx.procprefab`. `procprefab-content-assertions` hardens that direct path by checking created container/entity validity, owning path match, created entity count, component inventory where exposed, and bounded missing-asset/load-error log signals. `procprefab-character-component-assertions` adds character-specific candidate component discovery and presence/readback checks; the current direct product instance does not expose Actor, Mesh, Material, Animation, PhysX, or APB-product asset-reference components through the validated Editor component inventory, so that result is typed unavailable rather than passed, while selected-path missing actor/mesh/material/animation/load-error scans pass. `runtime-spawnable-proof-surface` records local spawnable/ProductDependency source surfaces and a read-only Asset Processor database dependency query for the direct `.procprefab` product; the current product dependency graph is empty for character products. `tools/o3de/runtime_harness.py` now records dedicated runtime launcher readiness and a pinned non-publishing command envelope for `MAXINE_GoldenCorpus.HeadlessServerLauncher.exe`. Runtime execution remains distinct from command pinning: `runtime_execution_attempted=false` and `runtime_execution_verified=false` until the live gated harness actually launches the pinned command and records process evidence.

Skipped/unavailable is not pass. Strict mode fails with `MXN_VALIDATION_TOOL_UNAVAILABLE` when required local tools are missing.

This wiring does not publish, mutate production levels, contact external services, or claim production-ready completion.

## Repair Editor Asset Processor negotiation and viewport materialization readiness

The Editor/AP negotiation diagnostic is invoked with:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-editor-ap-negotiation-viewport-materialization-readiness --strict-integration --editor-render-capture-rhi dx12 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

The diagnostic mode is `editor-ap-negotiation-viewport-materialization-readiness`. It source-validates Editor startup negotiation through `CCryEditApp::ConnectToAssetProcessor`, AzFramework `AssetProcessorConnection` branch-token/project-name matching, `AssetSystemComponent::EstablishAssetProcessorConnection`, Asset Processor `ConnectionWorker::NegotiateDirect`, and the Asset Processor `GUIApplicationManager::NegotiationFailed` message-box surface. It records sanitized process inventory only: executable basename/alignment booleans, project/build alignment booleans, and redaction markers. Raw command lines, environment dumps, secrets, and private logs must not be committed.

AP restart is blocked unless ownership is source-validated. The current slice classifies project/build mismatch or the `Negotiation Failed` modal, then reuses the safe temp visual scene/display context under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context` before re-running readiness-only viewport, SwapChain, and FrameCapture target probes. Cleanup remains run-owned and constrained to that approved temp root.

The current live diagnostic evidence is `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T010146Z/editor_smoke_live_report.json`. That run verified the live non-null Editor launch and safe temp scene cleanup, detected no `Negotiation Failed` modal, and classified the AP process as not aligned with the target project/build by sanitized inventory. Expected blocked states include `blocked_by_editor_asset_processor_project_mismatch`, `blocked_by_editor_asset_processor_build_root_mismatch`, `blocked_by_asset_processor_process_ownership_unverified`, `blocked_by_editor_active_viewport_window_handle_unavailable`, `blocked_by_swapchain_probe_unavailable`, and `blocked_by_active_viewport_window_handle_unavailable`.

No screenshot request is made. This diagnostic does not complete screenshot capture, does not verify rendered visual evidence, does not verify material correctness, does not verify character visual presence, does not satisfy `visual_material`, does not prove full runtime character behavior, and does not perform release packaging or publication.

## Repair Asset Processor project and build-root alignment

The deterministic AP alignment diagnostic is invoked with:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-asset-processor-project-build-alignment-repair --strict-integration --editor-render-capture-rhi dx12 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

The diagnostic mode is `asset-processor-project-build-alignment-repair`. It source-validates the AP launch and path-selection boundary through `AzFramework::AssetSystem::LaunchAssetProcessor`, the Windows `AssetSystemComponentHelper_Windows.cpp` command that launches `AssetProcessor.exe --start-hidden --engine-path=... --project-path=...`, `SettingsRegistryMergeUtils` handling of `--engine-path` and `--project-path`, and the existing Editor/AP branch-token plus project-name negotiation checks. It then records target rig fields for engine root, build/bin root, project path, AP executable, project name, branch-token availability, and sanitized process inventory.

AP repair is conservative. The harness may classify a missing, aligned, project-mismatched, or build-root-mismatched AP process, but it restarts or terminates AP only when a source-validated ownership signal proves the process is diagnostic-owned or target-owned. Same executable basename is not ownership proof. Diagnostic ownership can be supplied only through explicit run-owned PID markers such as `MAXINE_ASSET_PROCESSOR_DIAGNOSTIC_OWNED_PIDS`, `MAXINE_AP_DIAGNOSTIC_OWNED_PROCESS_IDS`, or `MAXINE_AP_DIAGNOSTIC_OWNED_PROCESS_ID`; absent those markers, a matching process remains unowned for repair purposes. If a mismatched AP is present and ownership is not verified, the report emits a typed blocker such as `blocked_by_asset_processor_process_ownership_unverified` plus a sanitized operator remediation command using the source-validated `AssetProcessor.exe --start-hidden --engine-path="C:/src/o3de" --project-path="C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus"` pattern. Close the mismatched AP manually, start AP with that target-rig command, and rerun the diagnostic to transition from safe-blocked to verified without code changes.

The current live diagnostic evidence is `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T031126Z/editor_smoke_live_report.json`. That run verified the non-null Editor launch, visible desktop/session, GPU/driver readiness, RHI readiness, selected `dx12`, and safe temp scene cleanup. AP project/build-root alignment remained blocked by a mismatched AP process whose ownership was not verified; the diagnostic therefore did not restart or kill AP and emitted only the sanitized remediation command. After that safe-block classification, active/default viewport window-handle, Atom SwapChain, and FrameCapture target readiness remained blocked by their existing readiness-only blockers.

No Asset Cache deletion is allowed. No AP database wipe is allowed. The diagnostic does not clear fingerprints, does not delete generated caches, does not kill arbitrary `AssetProcessor.exe` or `Editor.exe` processes, and does not emit raw command lines, raw environment dumps, private logs, secrets, or private live project content. It reuses the safe temp visual scene/display context under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context`, then reruns Editor/AP negotiation and readiness-only viewport/window, SwapChain, and FrameCapture target probes after AP alignment is verified, repaired, or truthfully blocked. Cleanup remains run-owned and constrained to the approved temp root.

No screenshot request is made. This diagnostic does not complete screenshot capture, does not verify rendered visual evidence, does not verify material correctness, does not verify character visual presence, does not satisfy `visual_material`, does not prove full runtime character behavior, and does not perform release packaging or publication. Expected blocked states include `blocked_by_asset_processor_alignment_repair_source_validation_unavailable`, `blocked_by_asset_processor_not_running`, `blocked_by_asset_processor_project_mismatch`, `blocked_by_asset_processor_build_root_mismatch`, `blocked_by_asset_processor_branch_project_token_mismatch`, `blocked_by_asset_processor_process_ownership_unverified`, `blocked_by_editor_active_viewport_window_handle_unavailable`, `blocked_by_swapchain_probe_unavailable`, and `blocked_by_framecapture_target_unavailable`.

## Verify operator-run Asset Processor alignment remediation

The post-remediation verification diagnostic is invoked with:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-operator-ap-alignment-remediation-verification --strict-integration --editor-render-capture-rhi dx12 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

The diagnostic mode is `operator-run-ap-alignment-remediation-verification`. It source-validates and preserves the PR #174 operator remediation command:

```powershell
"C:/src/o3de/build/windows/bin/profile/AssetProcessor.exe" --start-hidden --engine-path="C:/src/o3de" --project-path="C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus"
```

Use this mode after an operator has manually closed a mismatched unowned Asset Processor or when checking whether the target AP is already aligned. The report records whether the command is available, whether the operator remediation appears applied, whether target AP is running, whether a mismatched AP is still running, whether no AP is running, and whether AP project/build-root alignment is verified. If a mismatched AP is still running and ownership is not verified, the diagnostic does not kill or restart it; it emits `blocked_by_operator_ap_remediation_not_applied` and repeats the exact next steps: manually close the mismatched AP, run the source-validated command above, and rerun this diagnostic.

Launch-if-missing remains conservative. AP may be launched only when source validation proves the invocation, no mismatched unowned AP process is running, and the mode explicitly marks launch-if-missing as allowed. Restart and termination paths remain blocked for unowned AP or Editor processes. Same executable basename is not ownership proof, and raw process command lines, raw environment dumps, private logs, secrets, generated products, Asset Cache contents, and AP database/cache contents are not emitted or committed.

Current post-operator rerun evidence is `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T052202Z/editor_smoke_live_report.json`. That run verified the operator remediation state, found the target AP running, found no mismatched AP process, verified AP project and build-root alignment, and verified Editor/AP negotiation after remediation. The AP process still is not diagnostic-owned, so the harness used `classify_only` and did not launch, restart, terminate, delete Asset Cache, or wipe AP databases. Viewport/window materialization, active/default viewport window-handle, Atom SwapChain, and FrameCapture target readiness remained blocked by their existing readiness-only blockers, so the next implementation slice is focused Editor viewport activation/default viewport materialization v2 rather than screenshot or visual/material proof.

After AP alignment is verified, safely launched, or truthfully blocked, the diagnostic reruns bounded Editor/AP negotiation classification, reuses the safe temp visual scene/display context under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context`, and reruns readiness-only viewport/window, Atom SwapChain, and FrameCapture target probes. Cleanup remains run-owned and constrained to `Levels/_maxine_visual_smoke`; defaultlevel, production-level, and production character mutation remain forbidden.

No screenshot request is made. This diagnostic does not complete screenshot capture, does not verify rendered visual evidence, does not verify material correctness, does not verify character visual presence, does not satisfy `visual_material`, does not prove full runtime character behavior, and does not perform release packaging or publication. No Asset Cache deletion or AP database/cache wipe is allowed. Expected blocked states include `blocked_by_operator_ap_remediation_not_applied`, `blocked_by_operator_ap_alignment_verification_source_validation_unavailable`, `blocked_by_asset_processor_process_ownership_unverified`, `blocked_by_asset_processor_not_running`, `blocked_by_asset_processor_project_mismatch`, `blocked_by_asset_processor_build_root_mismatch`, `blocked_by_editor_active_viewport_window_handle_unavailable`, `blocked_by_swapchain_probe_unavailable`, and `blocked_by_framecapture_target_unavailable`.

## Activate Editor viewport and materialize default viewport readiness

The focused viewport materialization diagnostic is invoked with:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-focused-editor-viewport-materialization --strict-integration --editor-render-capture-rhi dx12 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

The diagnostic mode is `focused-editor-viewport-activation-default-viewport-materialization`. It assumes the PR #176 preconditions are still verified: target Asset Processor running against `C:/src/o3de` and `C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus`, AP project/build-root alignment verified, Editor/AP negotiation after operator remediation verified, selected non-null RHI `dx12`, and safe temp visual scene context under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context`.

The viewport activation/materialization strategy is source-validated before use. It pins O3DE `ViewPane.cpp` bindings for `get_viewport_count`, `get_active_viewport`, `set_active_viewport`, `update_viewport`, `QtViewPaneManager`, `EditorViewportWidget`, and `SetFocusToViewport`; `CryEditPy.cpp` Qt idle/event-loop and default viewport context helpers; and AzToolsFramework `EditorRequests` / view-pane APIs such as `GetMainWindow`, `OpenViewPane`, `InstanceViewPane`, and `GetViewPaneWidget`. The live step detects known blocking modals including `Negotiation Failed`, discovers Editor main-window candidates through sanitized Qt inventory, and activates only an already-visible main-window candidate. If only hidden main-window candidates are found, hidden show/raise/activate is blocked and recorded as `blocked_by_editor_main_window_activation_unavailable` to avoid unsafe Editor UI mutation. Default viewport pane/widget discovery, bounded Qt idle/render tick wait, and readiness-only active/default viewport, Atom SwapChain, and FrameCapture target probes are selected only after main-window activation is verified.

Current focused viewport evidence is `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T062855Z/editor_smoke_live_report.json` with progress log `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T062855Z/progress.jsonl`. AP alignment, Editor/AP negotiation, selected `dx12`, non-null Editor launch, and safe temp visual scene cleanup were preserved. Focused viewport materialization remained blocked by `blocked_by_editor_main_window_activation_unavailable`; the active/default viewport window handle remained blocked by `blocked_by_editor_active_viewport_window_handle_unavailable`, Atom SwapChain by `blocked_by_swapchain_probe_unavailable`, and FrameCapture target by `blocked_by_active_viewport_window_handle_unavailable`.

The mode records only booleans, counts, class/type names, typed blockers, and sanitized evidence summaries. It must not emit raw command lines, raw environment dumps, private logs, raw window titles/object names, screenshots, generated products, Asset Cache contents, AP database/cache contents, secrets, or private live project content. It does not kill or restart unowned AP or Editor processes and does not alter Asset Cache or AP databases.

No screenshot request is made. This diagnostic does not complete screenshot capture, does not verify rendered visual evidence, does not verify material correctness, does not verify character visual presence, does not satisfy `visual_material`, does not prove full runtime character behavior, and does not perform release packaging or publication. Expected blocked states include `blocked_by_focused_viewport_materialization_source_validation_unavailable`, `blocked_by_editor_main_window_unavailable`, `blocked_by_editor_main_window_activation_unavailable`, `blocked_by_editor_blocking_modal`, `blocked_by_editor_asset_processor_negotiation_failed_modal`, `blocked_by_default_viewport_pane_unavailable`, `blocked_by_default_viewport_pane_activation_unavailable`, `blocked_by_default_viewport_widget_unavailable`, `blocked_by_editor_active_viewport_window_handle_unavailable`, `blocked_by_active_viewport_window_handle_unavailable`, `blocked_by_swapchain_probe_unavailable`, and `blocked_by_framecapture_target_unavailable`.

If this mode verifies focused viewport materialization and a viewport window handle, SwapChain, or FrameCapture target becomes available, the next slice is bounded screenshot request/completion proof in the safe temp visual scene. If viewport pane/widget materializes but capture targets remain unavailable, the next slice is an alternate Atom capture target readiness probe or render tick / Atom viewport scene readiness deep-dive. Screenshot existence, viewport readiness, AP alignment, and behavior smoke remain separate from rendered visual/material proof.

## Editor main-window activation and materialization readiness

The Editor main-window activation/materialization deep-dive diagnostic is invoked with:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-editor-main-window-activation-materialization --strict-integration --editor-render-capture-rhi dx12 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

The diagnostic mode is `editor-main-window-activation-materialization-deep-dive`. It preserves the PR #176/#177 preconditions: target AP aligned with the expected engine/project/build rig, verified Editor/AP negotiation, selected non-null `dx12`, visible desktop/GPU/RHI readiness, and safe temp visual scene context under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context`.

This mode classifies sanitized Qt top-level main-window candidates by class/type name, visible/hidden/minimized state, QMainWindow shape, likely Editor-shell role, and activation eligibility. Hidden or minimized main-window candidates are not shown, raised, or activated unless a source-validated safe path proves the target is a valid Editor shell and does not mutate project, level, layout, capture, Asset Cache, or AP database state. The current policy for hidden candidates is `blocked_without_source_validated_safe_path`.

When preconditions allow, the diagnostic reruns modal detection, default viewport pane/widget readiness inventory, bounded idle/render wait only after safe activation/materialization, and readiness-only active/default viewport, Atom SwapChain, and FrameCapture target probes. The default viewport follow-up may discover widgets without activating them when main-window activation remains blocked.

Current main-window deep-dive evidence is `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T075051Z/editor_smoke_live_report.json` with progress log `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T075051Z/progress.jsonl`. AP alignment and Editor/AP negotiation remained verified with selected `dx12`, no `Negotiation Failed` modal was detected, and safe temp cleanup completed. The live Qt inventory classified two hidden QMainWindow-shaped candidates and no visible activation-eligible candidate, so main-window activation/materialization remained blocked by `blocked_by_editor_main_window_hidden_candidate_activation_unsafe`. Default viewport widget discovery verified, default viewport pane discovery remained blocked by `blocked_by_default_viewport_pane_unavailable`, active/default viewport window-handle remained blocked by `blocked_by_editor_active_viewport_window_handle_unavailable`, Atom SwapChain by `blocked_by_swapchain_probe_unavailable`, and FrameCapture target by `blocked_by_active_viewport_window_handle_unavailable`.

No screenshot request is made. This diagnostic does not complete screenshot capture, does not verify rendered visual evidence, does not verify material correctness, does not verify character visual presence, does not satisfy `visual_material`, does not prove full runtime character behavior, and does not perform release packaging or publication. Expected blocked states include `blocked_by_editor_main_window_activation_source_validation_unavailable`, `blocked_by_editor_main_window_unavailable`, `blocked_by_editor_main_window_hidden_candidate_activation_unsafe`, `blocked_by_editor_main_window_activation_unavailable`, `blocked_by_editor_main_window_materialization_unavailable`, `blocked_by_default_viewport_pane_unavailable`, `blocked_by_default_viewport_widget_unavailable`, `blocked_by_editor_active_viewport_window_handle_unavailable`, `blocked_by_active_viewport_window_handle_unavailable`, `blocked_by_swapchain_probe_unavailable`, and `blocked_by_framecapture_target_unavailable`.

## Discover visible Editor shell and materialization path

The alternate Editor window discovery / visible shell materialization diagnostic is invoked with:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --diagnose-alternate-editor-window-discovery-visible-shell --strict-integration --editor-render-capture-rhi dx12 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de --apb-report artifacts/o3de-integration/apb/<run>/asset_processor_batch_live_report.json
```

The diagnostic mode is `alternate-editor-window-discovery-visible-shell-materialization`. It preserves the verified AP alignment and Editor/AP negotiation preconditions from PR #176, reuses the safe temp visual scene/display context under `Levels/_maxine_visual_smoke/editor_safe_temp_visual_scene_display_context`, and extends the PR #178 main-window deep dive by classifying alternate Qt Editor shell candidates before any viewport/capture-target follow-up.

Source validation distinguishes O3DE `MainWindow` / `CryEdit` shell code from EMotionFX `EMStudio::MainWindow` code. Hidden `EMStudio::MainWindow` candidates are classified as Animation Editor/tool-shell candidates, not visible O3DE Editor shell proof. The generic hidden `QMainWindow` path remains an unknown unsafe hidden candidate unless source-validated signals prove it is the real Editor shell. Hidden-window show, raise, or activate stays blocked by policy unless the candidate is already source-validated as a valid, visible Editor shell and the action is bounded and readiness only.

The mode records only sanitized Qt inventory: class/type names, role classifications, visibility booleans, counts, and typed blockers. Native window inventory remains unselected until a sanitized, source-validated native path exists. Raw window titles, raw object names, raw native handles, raw process command lines, environment dumps, private logs, screenshots, generated products, Asset Cache contents, AP database/cache contents, secrets, and private live project content must not be emitted or committed.

Current alternate visible-shell evidence is `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T085217Z/editor_smoke_live_report.json` with progress log `artifacts/o3de-integration/editor-smoke/editor-smoke-20260516T085217Z/progress.jsonl`. AP alignment and Editor/AP negotiation remained verified with selected `dx12`, no screenshot was requested, and safe temp cleanup completed. The live Qt inventory classified two hidden QMainWindow-shaped candidates, `EMStudio::MainWindow` and `QMainWindow`; no visible Editor shell candidate was found. `EMStudio::MainWindow` was classified as an EMotionFX/Animation Editor tool shell, while the generic hidden `QMainWindow` remained an unknown unsafe hidden candidate. Visible Editor shell discovery/materialization therefore remained blocked by `blocked_by_visible_editor_shell_unavailable`, and hidden show/raise/activate remained blocked by `blocked_by_hidden_editor_shell_candidate_activation_unsafe`. Default viewport widget discovery remained verified, default viewport pane discovery remained blocked by `blocked_by_default_viewport_pane_unavailable`, active/default viewport window-handle remained blocked by `blocked_by_editor_active_viewport_window_handle_unavailable`, Atom SwapChain by `blocked_by_swapchain_probe_unavailable`, and FrameCapture target by `blocked_by_active_viewport_window_handle_unavailable`.

When preconditions allow, the diagnostic reruns modal detection, hidden/visible shell classification, default viewport pane/widget readiness inventory, bounded idle/render wait only after safe visible-shell materialization and viewport pane activation, and readiness-only active/default viewport, Atom SwapChain, and FrameCapture target probes. No screenshot request is made. This diagnostic does not complete screenshot capture, does not verify rendered visual evidence, does not verify material correctness, does not verify character visual presence, does not satisfy `visual_material`, does not prove full runtime character behavior, and does not perform release packaging or publication. Expected blocked states include `blocked_by_alternate_editor_window_discovery_source_validation_unavailable`, `blocked_by_visible_editor_shell_unavailable`, `blocked_by_visible_editor_shell_materialization_unavailable`, `blocked_by_hidden_editor_shell_candidate_activation_unsafe`, `blocked_by_hidden_editor_shell_candidate_not_valid_target`, `blocked_by_default_viewport_pane_unavailable`, `blocked_by_default_viewport_widget_unavailable`, `blocked_by_editor_active_viewport_window_handle_unavailable`, `blocked_by_active_viewport_window_handle_unavailable`, `blocked_by_swapchain_probe_unavailable`, and `blocked_by_framecapture_target_unavailable`.
