# MAXINE Runtime Exit Fixture

This repo-owned O3DE Code Gem is a non-shipping runtime harness fixture. It is disabled by default and is intended only for controlled, bounded runtime command-envelope diagnostics.

The fixture source validates the after-initialization pattern discovered in local O3DE source:

- `AZ::Component::Activate`
- `AZ::TickBus::OnTick`
- `AzFramework::ApplicationRequests::ExitMainLoop`

Runtime harness gates must remain separate from the Gem source:

- `MAXINE_ENABLE_O3DE_RUNTIME_HARNESS=1`
- `MAXINE_ALLOW_LIVE_RUNTIME_COMMANDS=1`
- `MAXINE_ENABLE_RUNTIME_EXIT_FIXTURE=1`
- `MAXINE_ENABLE_RUNTIME_CHARACTER_PRODUCT_LOAD_PROBE=1` only when the optional product-load probe is intentionally enabled
- `MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWNABLE_SURFACE=1`, `MAXINE_ENABLE_RUNTIME_CHARACTER_SPAWN_INSTANTIATION=1`, and `MAXINE_ALLOW_RUNTIME_CHARACTER_SPAWN_INSTANTIATION=1` only when the optional spawn-instantiation probe is intentionally enabled
- `MAXINE_ENABLE_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE=1` and `MAXINE_ALLOW_RUNTIME_CHARACTER_ANIMATION_PLAYBACK_SURFACE=1` only when the harness is intentionally inspecting the spawned runtime animation playback surface

The component also requires Settings Registry keys before it connects to `AZ::TickBus`:

- `/Amazon/MAXINE/RuntimeHarness/EnableExitFixture=true`
- `/Amazon/MAXINE/RuntimeHarness/ExitAfterTicks=<positive integer>`

The optional character product-load probe is disabled by default. When explicitly enabled, it reads these Settings Registry keys:

- `/Amazon/MAXINE/RuntimeHarness/EnableCharacterProductLoadProbe=true`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductCount=<positive integer>`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductSpecs=<legacy compact product list>`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/ProductSpecsHex=<legacy compact product list encoded as hex>`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/TimeoutTicks=<positive integer>`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/RequireAllProductsReady=true`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/Kind`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/ProductPath`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/CatalogPath`
- `/Amazon/MAXINE/RuntimeHarness/CharacterProductLoadProbe/Products/<index>/ExpectedCategory`

The harness uses a temporary `.setreg` artifact with the indexed `Products/<index>` keys for live product-load attempts because long product lists should not be squeezed into command-line registry values. The artifact requires `MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH=1`, is harness-owned, and must not be committed.

The probe resolves product-relative catalog paths through `AZ::Data::AssetCatalogRequestBus::GetAssetIdByPath`, obtains the runtime asset type with `GetAssetInfoById`, verifies that `AZ::Data::AssetManager::GetHandler` exists for the asset type, requests an async load with `AZ::Data::AssetManager::GetAsset`, polls readiness on `AZ::TickBus`, and releases held asset references before exit. It emits stable markers:

- `MAXINE_RUNTIME_PRODUCT_LOAD_START`
- `MAXINE_RUNTIME_PRODUCT_LOAD_RESOLVED`
- `MAXINE_RUNTIME_PRODUCT_LOAD_READY`
- `MAXINE_RUNTIME_PRODUCT_LOAD_ERROR`
- `MAXINE_RUNTIME_PRODUCT_LOAD_TIMEOUT`
- `MAXINE_RUNTIME_PRODUCT_LOAD_SUMMARY`
- `MAXINE_RUNTIME_PRODUCT_LOAD_RELEASED`

Source readiness is not runtime execution proof. Rebuild readiness is not runtime execution proof. A clean fixture exit can prove only bounded runtime command-envelope execution. A clean product-load probe can prove only runtime product resolution/load readiness for approved products; it is not runtime instantiation, spawn, animation, full character proof, or production-ready release proof.

If `MAXINE_RUNTIME_PRODUCT_LOAD_ERROR` reports `error=asset_handler_missing`, the product resolved through the runtime AssetCatalog but cannot be counted as ready because no runtime `AssetManager` handler is registered for the reported asset type.

The optional character spawn-instantiation probe is disabled by default. When explicitly enabled, it reads these Settings Registry keys:

- `/Amazon/MAXINE/RuntimeHarness/EnableCharacterSpawnInstantiationProbe=true`
- `/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableProductPath`
- `/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableCatalogPath`
- `/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableAssetId`
- `/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/SpawnableAssetType`
- `/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/TimeoutTicks=<positive integer>`
- `/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/RequirePositiveEntityCount=true`
- `/Amazon/MAXINE/RuntimeHarness/CharacterSpawnInstantiationProbe/CleanupSpawnedEntities=true`

The spawn probe resolves and loads the approved `AzFramework::Spawnable`, verifies a game entity context, creates an `AzFramework::EntitySpawnTicket`, calls `AzFramework::SpawnableEntitiesInterface::SpawnAllEntities`, records completion with spawned entity evidence, and calls `DespawnAllEntities` when cleanup is enabled. It emits stable markers:

- `MAXINE_RUNTIME_CHARACTER_SPAWN_START`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_SOURCE_VALIDATED`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_CONTEXT`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_TICKET`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_REQUESTED`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_COMPLETED`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_ENTITY`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_ERROR`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_TIMEOUT`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_CLEANUP`
- `MAXINE_RUNTIME_CHARACTER_SPAWN_SUMMARY`

Spawn-instantiation proof requires positive spawned entity evidence and clean cleanup/exit. It is not animation proof, full runtime character proof, publication, packaging, or production-ready release evidence.

The animation playback-surface diagnostic currently consumes the spawn probe's bounded entity/component inventory from the Python harness rather than adding a shipping or Editor-only playback path to this Gem. Runtime animation proof remains unclaimed unless the approved spawned character exposes source-validated runtime EMotionFX playback-capable components and playback is requested, started, and observed in a bounded no-defaultlevel fixture. When the spawned surface contains only Transform components, the harness must report `runtime_animation_playback_surface_missing_on_approved_spawned_character`.

The Gem also contains an Editor/Tools-only bridge host for future prefab save/update automation. The `MaxineRuntimeExitFixture.Editor` target is guarded by `PAL_TRAIT_BUILD_HOST_TOOLS`, carries the `AzToolsFramework` dependency only on that Editor target, and reflects the harmless `azlmbr.maxine.prefab_bridge.get_prefab_save_update_bridge_host_status` BehaviorContext method. That host-status method proves load/callability readiness only; it does not expose `SavePrefab`, does not save scratch prefabs, does not mutate approved source prefabs, and is not runtime animation or full character proof.

The Gem is intended to be registered as an external subdirectory for private harness runs only. The root `CMakeLists.txt` delegates to `Code/CMakeLists.txt` so O3DE CMake can discover the Gem after project-scoped external-subdirectory registration. Registration, enablement, and rebuild require the runtime harness project-mutation and rebuild gates; build outputs and runtime binaries must not be committed.
