# Evidence Bundles

An evidence bundle is the reviewable index of files that support a manifest and QC report. It records IDs, kinds, paths, and hashes when known.

Evidence bundles in this slice are static and local. They must not claim live O3DE runtime success, Asset Processor success, or external service success unless those systems actually ran under a future admitted integration job.

The example bundle is:

```text
examples/production/evidence_bundle.release_rigged.pass.example.json
```

Strict manifest validation requires referenced evidence files to exist.

## Product Resolver Evidence

Evidence bundles and manifests should record the resolver result when product records are used:

- `resolver_mode`: `fixture`, `local_o3de`, `unavailable`, or `invalid`
- `integration_executed`: true only when the gated adapter actually performed a local query
- `live_o3de_execution`: true only when local O3DE tooling actually ran
- `fixture_data_used`: true for deterministic fixture validation
- `cache_heuristic_used`: true if any product evidence came from cache guessing
- `evidence_refs`: local evidence records that explain where the resolver data came from

Fixture examples set `integration_executed` and `live_o3de_execution` to false. Optional O3DE integration checks that are skipped must remain marked skipped or unavailable, not pass.

## Asset Processor Batch Proof Evidence

Asset Processor Batch proof evidence may be attached as:

- APB fixture report path, such as `examples/golden-corpus/release_rigged/asset_processor_batch.fixture.json`
- stdout/stderr refs only when a future gated APB command actually runs
- `integration_enabled`
- `live_asset_processor_batch_execution`
- skipped reason and error code when tooling is unavailable
- product resolver/product matrix refs used to classify products

Fixture reports must not claim real AP logs or live execution.

When APB live execution is explicitly admitted on a private runner, APB evidence may include:

- `golden_project_fixture_ref`
- `integration_executed`
- `live_asset_processor_batch_execution`
- safe command argv
- exit code and duration
- stdout/stderr refs under `artifacts/o3de-integration/apb/`
- APB live report ref
- `live_editor_execution=false`
- `live_publication=false`

Generated live APB logs are not fixture reports and are not committed by default.

Release-rigged APB evidence can also include a source capability audit:

```powershell
python tools/o3de/audit_golden_corpus_sources.py --corpus examples/golden-corpus --project $env:O3DE_PROJECT_PATH --json
```

The audit records whether controlled sources exist for actor, motion, motionset, animgraph, and pxmesh scene settings. It does not replace Asset Processor product evidence. If APB exits `0` but the database lacks `.pxmesh`, `actor`, `motion`, `motionset`, or `animgraph`, the evidence bundle remains failed until the product is produced or an explicit policy waiver is added and validated.

For product-specific live APB evidence, use the APB product evidence audit:

```powershell
python tools/o3de/audit_apb_product_evidence.py --project $env:O3DE_PROJECT_PATH --apb-report <asset_processor_batch_live_report.json> --apb-executable $env:ASSET_PROCESSOR_BATCH_EXECUTABLE --json
```

The audit verifies `.pxmesh` through APB report or Asset Processor database evidence tied to the controlled release source. It may list filename-like or physics-like products for diagnostics, but those diagnostic matches do not satisfy release proof.

As of the pxmesh resolution follow-up, `.pxmesh` is present for the controlled release source and the product matrix evidence is satisfied.

The follow-up DiffuseProbeGrid slice fixed the separate `MXN_APB_PROCESS_EXIT_NONZERO` condition by removing unnecessary `DiffuseProbeGrid` enablement from the controlled project and regenerating project-specific registry metadata. The clean APB-only evidence is represented by:

```text
examples/private-runner/apb-live-full-golden-corpus.release-rigged.apb-clean.pass.example.json
```

## Editor Smoke Evidence

Editor Python package/prefab smoke evidence may be attached as:

- Editor smoke fixture report path, such as `examples/editor-smoke/release_rigged.fixture.report.json`
- stdout/stderr/editor log refs only when a future gated Editor command actually runs
- `integration_enabled`
- `live_editor_execution`
- skipped reason and error code when tooling is unavailable
- product resolver and Asset Processor Batch proof refs used to connect instantiation evidence to source/product identity
- screenshot refs only when fixture-labeled or actually captured

Fixture reports must not claim real Editor logs, screenshots, level mutation, or live Editor execution.

Readiness-only Editor smoke evidence may be committed when it is sanitized and clearly unavailable/skipped or when it records a produced paired Editor executable without launching Editor. It can record the paired Editor executable status, `EditorPythonBindings` status, temp-level policy, APB baseline reference, and closed publication/release-packaging gates.

The unavailable readiness example is:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.unavailable.example.json
```

The produced-Editor readiness example is:

```text
examples/editor-smoke/editor-smoke-readiness.release-rigged.editor-produced.example.json
```

Live Editor smoke evidence may be committed only when it is sanitized and clearly labels the outcome. The first live attempt is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.stalled.example.json
```

That evidence records `live_editor_execution=true` because the Editor process actually launched, `status=stalled` because the wrapper timeout stopped the process, and closed safety gates:

- `live_publication=false`
- `release_packaging=false`
- `production_level_mutation=false`
- `live_asset_processor_batch_execution=false` for the Editor command itself

Live Editor evidence should also reference the APB baseline report that supplied complete product evidence. It must not duplicate APB report schema concepts beyond a compact product evidence summary and APB baseline ref.

`live_editor_execution=true` is allowed only when the Editor process actually ran. Missing Editor executables, build timeouts, failed readiness, nonzero Editor exits, and stalled Editor commands remain blockers, not passes.

The temp-level stall diagnostic adds a progress log reference to live Editor evidence:

- `progress_log_ref`: JSONL progress markers written beside the live report
- `last_progress_marker`: the final script-side marker used to classify a stall
- `stall_phase`: wrapper classification such as `runpython_not_invoked`, `azlmbr_import_stall`, `product_evidence_stall`, `temp_level_create_stall`, `idle_wait_stall`, `entity_create_stall`, or `report_write_stall`
- `diagnostic_mode`: `hello`, `product-evidence`, `temp-level`, `entity-minimal`, `component-binding`, `actor-binding`, `prefab-binding`, `prefab-instantiation`, `procprefab-product-instantiation`, `procprefab-content-assertions`, or `full`
- `process_tree_cleanup`: timeout cleanup status when a process tree must be stopped

The PR #116 stall was diagnosed as `idle_wait_stall`. The fixed full live smoke pass is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.pass.example.json
```

That pass evidence records `live_editor_execution=true`, `live_publication=false`, `release_packaging=false`, `production_level_mutation=false`, `cache_heuristic_used=false`, and entity/component smoke pass.

Actor/prefab/component binding evidence now has dedicated fields:

- `component_type_registry`: safe discovered or pinned component type information, with the discovery source and unattended-temp-level safety.
- `binding_call_surface`: Editor binding modules/buses and the validated call surface.
- `safe_call_results`: per-call status for safe Editor Python binding probes.
- `component_binding_checks`: entity naming, default Transform evidence, component add/probe, and property-list results.
- `actor_binding_checks`: APB actor product prerequisite, Actor component type discovery, add/property results, and typed blockers.
- `prefab_binding_checks`: APB procprefab prerequisite and prefab/procprefab binding or instantiation surface discovery.
- `property_path_discovery` and `property_list_summary`: property-list/property-path evidence without assuming undocumented paths.
- `no_fake_success`: live-pass reports must explicitly preserve the no-fake-success posture.

Actor or prefab smoke is not evidence of pass unless the matching binding check is also `pass`. When a live operation is not safe or not supported, the evidence must use a typed non-pass status such as `blocked_by_missing_binding`, `blocked_by_unsafe_operation`, or `unsupported_by_engine_binding`.

The current sanitized full-pass Editor smoke example includes live binding evidence for Transform, Tag, and Actor TypeId discovery, Tag component add/property readback, Actor component add/property readback, Actor asset assignment, prefab binding-surface discovery, and safe temp-level prefab instantiation.

Actor assignment evidence must include:

- `actor_asset_assignment.status=pass`
- `property_path=Actor asset`
- `setter_call=EditorComponentAPIBus.SetComponentProperty`
- `setter_value_shape=azlmbr.asset.AssetId`
- trusted APB actor product evidence for `pc/assets/characters/maxine/release/jack.actor`
- Asset Catalog resolution to the approved actor product
- readback with `matched_approved_product=true`

Prefab instantiation evidence must include:

- trusted APB `procprefab` product evidence for `pc/assets/characters/maxine/release/maxine_idle_fbx.procprefab`
- `prefab_binding_checks.binding_surface_status=pass`
- selected call evidence for `PrefabPublicRequestBus.CreatePrefabInMemory + PrefabPublicRequestBus.InstantiatePrefab`
- a temp source `.prefab` path under `Levels/_maxine_smoke`
- created entity/container evidence or verified template-load evidence

Direct `.procprefab` product instantiation is not implied by source-prefab instantiation evidence. It has its own evidence contract and must identify the exact binding call and value shape used. Unsupported or unsafe outcomes remain typed non-pass states.

Direct `.procprefab` product semantics evidence uses dedicated fields so source-prefab proof cannot be mistaken for direct product proof:

- `direct_procprefab_product_semantics`: APB product evidence, Asset Catalog lookup, discovered `azlmbr.prefab` surface, selected call, argument shape, direct load result, direct instantiation result, and created entity/template/instance evidence if any.
- `direct_procprefab_content_assertions`: post-instantiation evidence for the direct product path, including container/entity validity, owning path match, created entity count, entity-name/child-structure summaries, component inventory, missing-asset/load-error scans, required assertion pass/fail lists, and typed unavailable informational assertions.
- `procprefab_character_assertions`: character-specific evidence for the direct product path, including candidate component TypeId discovery, per-entity component presence checks, safe property/asset-reference readback when exposed, matched APB product evidence when available, selected-path missing actor/mesh/material/animation/load-error scans, required character assertion pass/fail lists, and typed unavailable or unsupported reasons.
- `runtime_spawnable_proof`: runtime/spawnable/product-side surface evidence after Editor component inventory is exhausted. This records source-discovered spawnable/ProductDependency APIs, the read-only ProductDependencies query result, runtime launcher candidates if present, runtime execution attempted/verified booleans, product dependency matches to APB evidence when available, selected-path missing character/load-error scans, and typed blocked or unavailable reasons.
- `source_prefab_baseline_result`: the already proven temp source-prefab create/instantiate result that remains the stable Editor smoke baseline.
- `direct_product_instantiation_claimed`: true only when direct `.procprefab` product behavior is actually claimed.
- `direct_product_instantiation_supported`: true only when the current binding surface supports the selected direct product path.
- `direct_product_instantiation_verified`: true only when direct product load/instantiation produced verified live evidence.

The current live full-pass evidence verifies direct `.procprefab` product instantiation through `PrefabPublicRequestBus.InstantiatePrefab` using the AssetCatalog-selected product path. A future full Editor smoke pass may still include a typed direct-product unsupported result on another rig, but only when `direct_product_instantiation_verified=false`, a precise unsupported or blocked reason is present, and the source-prefab baseline remains `pass`. It must never count direct product instantiation as pass from APB product existence alone or from temp source-prefab instantiation alone.

Direct product instantiation is now distinct from direct product content assertion quality. A full pass cannot hide failed required content assertions such as an invalid container/entity, missing owning-path match, missing created entity count, or relevant missing-asset/load-error signal. Component inventory, child traversal, and detailed asset-reference readback may be informational or typed unavailable when the current Editor Python surface does not expose a stable call, but those states must be explicit and cannot be reported as required assertion passes.

Character-specific direct product evidence is a separate layer above generic content proof. Transform-only inventory is structural evidence and must not count as character-specific pass. On the current paired runner, the smoke discovers candidate TypeIds for Actor, Mesh, Material, Animation, and PhysX-related components, but the direct `.procprefab` Editor product instance does not expose those components or APB-product asset references through the validated Editor component inventory. The evidence records that as `unavailable_with_verified_reason` with `direct_procprefab_character_components_not_exposed_in_editor_product_instance`, while still requiring selected-path missing actor, mesh, material, animation, and load-error scans to pass.

Runtime/spawnable proof is distinct from both Editor component inventory and product dependency proof. The current paired runner records source-discovered spawnable surfaces and a read-only Asset Processor database query for the direct `.procprefab` product, but that product dependency graph exposes no actor, azmodel, pxmesh, azmaterial, motion, motionset, or animgraph references. The evidence must therefore keep `runtime_spawnable_execution_attempted=false`, `runtime_spawnable_execution_verified=false`, and `product_dependency_proof_status=product_dependency_proof_unavailable` unless a future bounded runtime harness actually runs and passes. Product dependency proof must never be counted as runtime execution proof.

Runtime harness evidence is now a fifth layer. It records launcher candidates, selected executable provenance, project/engine pairing, live runtime gate state, timeout policy, command-pinning state, stdout/stderr/log refs when a process is actually launched, and typed blockers such as `blocked_by_missing_runtime_gate`, `blocked_by_missing_runtime_executable`, or `blocked_by_unpinned_runtime_flags`. Harness readiness may be committed as sanitized evidence, but it must not be counted as command-pinning proof, runtime execution proof, or runtime character proof. The committed live Editor example now carries `runtime_harness.runtime_harness_status=runtime_command_pinning_pass`, `runtime_command_pinned=true`, `runtime_command_pin_verified=true`, `runtime_execution_attempted=false`, `runtime_execution_verified=false`, and `runtime_character_proof_claimed=false`.

Runtime command-pinning evidence is intentionally narrow. It proves the command envelope for the selected HeadlessServerLauncher using `--project-path`, `-NullRenderer`, `-rhi=null`, `--regset=/Amazon/AzCore/Bootstrap/wait_for_connect=0`, and a generated `--console-command-file` whose contents are `quit`. That command does not use a production level, does not request release packaging, does not publish, and does not claim runtime character evidence.

Runtime exit diagnostic evidence is a sixth layer. When a gated bounded command launches, the harness records `runtime_exit_code_decimal`, `runtime_exit_code_hex`, `runtime_exit_code_signed`, `runtime_exit_classification`, stdout/stderr/log summaries, AssetManager shutdown assert summaries, timeout/kill state, and missing actor/mesh/material/animation/load-error scans. The first live attempt of the pinned envelope exited `3221225477` (`0xC0000005`) and is classified as crash-like, with AssetManager shutdown asserts observed in stderr. That evidence remains a failed runtime execution and must not be counted as runtime execution proof or runtime character proof.

Runtime quit-variant evidence is a seventh layer. The harness records `runtime_command_variant_matrix` entries for the preserved baseline, source-validated attemptable variants, and rejected variants with typed reasons. Each attempted variant carries command arguments, source-validation notes, timeout, stdout/stderr/log refs, exit code decimal/hex/classification, AssetManager/shader serializer/Asset Processor negotiation summaries, and missing actor/mesh/material/animation/load-error scans. A variant pass requires expected exit code `0` and no disqualifying scanned signals; expected exit codes must not be widened to hide `0xC0000005`.

Runtime exit-strategy evidence is an eighth layer. It records `runtime_exit_strategy_candidate_matrix` entries for source-supported exit surfaces, source refs, rejected candidates, attempted candidates, per-candidate stdout/stderr/log refs, exit code decimal/hex/classification, timeout/kill state, AssetManager/shader serializer/Asset Processor negotiation summaries, and missing actor/mesh/material/animation/load-error scans. Source validation alone is not runtime execution proof: immediate `--console-command-file` quit and Settings Registry runtime-console quit are source-validated but rejected for this failure family because local launcher source executes the command file before `RunMainLoop`. Candidate passes require strict expected exit semantics and no disqualifying scanned signals. The current blocker is `blocked_by_missing_source_validated_runtime_exit_strategy`, with runtime character proof still unclaimed.

Runtime exit-fixture evidence is a ninth layer. It records whether a harness-side or project-side fixture exists that can request runtime exit after initialization without loading production levels or shipping production behavior. The preserved #129 diagnostic still records the prior blocker `blocked_by_fixture_requires_project_code_rebuild` for the live project Gem hook. The newer source/rebuild diagnostics add repo-owned evidence for `o3de/gems/MaxineRuntimeExitFixture`: Gem manifest parse, root and `Code/` CMake shape, `AZ::TickBus::OnTick`, `AzFramework::ApplicationRequests::ExitMainLoop`, Settings Registry keys, non-shipping status, disabled-by-default status, and explicit project-mutation/rebuild gates. Fixture source readiness, registration readiness, rebuild-gate readiness, and build success are not runtime execution proof, and a clean fixture command is still not runtime character proof.

Registration and enablement evidence is recorded separately from runtime proof. The live registration report records `external_subdirectories:+o3de/gems/MaxineRuntimeExitFixture`; the live enablement report records `gem_names:+MaxineRuntimeExitFixture`; both list `C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus/project.json` as the only project metadata file and include rollback text. The rebuild report records the scoped target `MAXINE_GoldenCorpus.HeadlessServerLauncher`, stdout/stderr refs, and artifact refs without committing runtime binaries or build outputs.

Fixture runtime execution evidence is stricter than process exit evidence. A fixture command must use Settings Registry fixture keys rather than `--console-command-file`, must observe the fixture marker, must exit with an expected code, must not time out or require an unsafe kill, must not load production/default levels, and must not emit disqualifying log signals. The first live fixture command observed the marker and exit code `0`, but failed verification due to Asset Processor negotiation failures, shader serializer errors, and unexpected `Levels/defaultlevel/defaultlevel.spawnable` load. That evidence remains `runtime_exit_fixture_execution_verified=false`, `runtime_execution_verified=false`, and `runtime_character_proof_claimed=false`.

Runtime launch-hygiene evidence is separate again. It records whether the project is configured to autoexec `LoadLevel`, which source/config surface caused a defaultlevel load, and which command-line or Settings Registry strategy is used to prevent it. The current source-validated no-default-level strategy removes `/O3DE/Autoexec/ConsoleCommands/LoadLevel` for the process with `--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel`; source refs include the project `Registry/load_level.setreg`, AzCore Settings Registry merge command parsing, console autoexec command execution, and the spawnable level system `LoadLevel` path. Evidence must list expected and actual level loads, AP negotiation status, shader serializer status, fixture marker state, exit code, and any disqualifying signals. No-default-level validation is not character proof, and it is not runtime execution proof unless a bounded fixture process actually runs cleanly with no default/production level load and no disqualifying signals.

If the no-default-level command still loads defaultlevel, the evidence bundle must keep the failure as `blocked_by_default_level_autoload` and preserve stdout/stderr/log refs. Exit code `0` and fixture marker evidence remain useful diagnostics, but they cannot be promoted to runtime execution proof while defaultlevel autoload, AP negotiation, or shader serializer signals remain disqualifying.

Runtime LoadLevel override evidence records a candidate matrix beyond the first autoexec-only `--regremove`. The preserved failed candidate is `settings_registry_regremove_autoexec_loadlevel`; the selected follow-up candidate is `settings_registry_regremove_autoexec_and_deferred_loadlevel`, which adds `--regremove=/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel` to account for `SpawnableLevelSystem` queuing early `LoadLevel` requests. Evidence must include Settings Registry merge-order summary, command-line override order, project registry order, autoexec source/effective state, selected args, expected and actual registry state, expected and actual level loads, AP negotiation status, shader serializer status, exit code, and fixture marker state.

The current live LoadLevel-override run still fails cleanly as evidence rather than proof. It launched the fixture command, exited `0`, and observed the fixture marker, but defaultlevel still autoloaded and stdout reported both regremove targets as missing at parse time. The candidate-specific blocker is `blocked_by_settings_registry_merge_order`; the launch-hygiene blocker remains `blocked_by_default_level_autoload`. Keep `runtime_loadlevel_override_verified=false`, `runtime_exit_fixture_execution_verified=false`, `runtime_execution_verified=false`, and `runtime_character_proof_claimed=false`.

## Golden Project Fixture Evidence

Golden project fixture evidence may be attached as:

- project fixture path, such as `examples/o3de-golden-project/maxine-golden-project.fixture.json`
- local readiness report when the private runner inspected env vars/tool paths
- `live_o3de_execution`, `live_asset_processor_batch_execution`, and `live_editor_execution`
- temp-level policy refs under `Levels/_maxine_smoke`
- evidence/artifact retention roots under `Saved/MaxineEvidence`, `Saved/Logs/Maxine`, and `Saved/Screenshots/Maxine`
- skipped reason and `MXN_VALIDATION_TOOL_UNAVAILABLE` when local project/tooling paths are unavailable

Fixture and skipped readiness reports must not claim project mutation, APB execution, Editor execution, screenshots, or logs that were not actually produced.
