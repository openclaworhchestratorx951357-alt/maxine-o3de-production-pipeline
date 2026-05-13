# Editor Smoke Stall Diagnostics

The gated Editor smoke supports split live diagnostic modes so a private runner can isolate stalls without broadening publication or packaging authority.

Run modes in order:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode hello --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode product-evidence --timeout-seconds 180 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode temp-level --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode entity-minimal --timeout-seconds 240 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration --diagnostic-mode full --timeout-seconds 300 --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

Stop at the first failing or stalled mode. Each run writes `progress.jsonl` beside `editor_smoke_live_report.json`, `stdout.txt`, and `stderr.txt`.

The PR #116 blocker was classified as `idle_wait_stall`: `create_level_no_prompt` returned, the approved temp level was written under `Levels/_maxine_smoke`, and then `azlmbr.legacy.general.idle_wait_frames(5)` did not return while the Editor log was loading the temp map. The smoke skips that idle wait by default and records `idle_wait_skipped`. Set `MAXINE_EDITOR_SMOKE_ENABLE_IDLE_WAIT=1` only to reproduce or diagnose the old path.

Expected safety posture is unchanged:

- `live_publication=false`
- `release_packaging=false`
- `production_level_mutation=false`
- no Asset Cache deletion
- no production levels
- no external service calls
- no fake pass on timeout, missing report, or nonzero Editor exit

The first fixed full pass is represented by:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.pass.example.json
```

Later binding/content hardening slices add more targeted live modes after APB product evidence is complete. Use `component-binding`, `actor-asset-assignment`, `prefab-instantiation`, `procprefab-product-instantiation`, `procprefab-content-assertions`, `procprefab-character-component-assertions`, and `runtime-spawnable-proof-surface` to isolate stalls in the component, Actor assignment, source-prefab, direct product, structural content, character-specific assertion, and runtime/spawnable proof-surface phases. The character-specific mode records `procprefab_character_assertions` and may report typed unavailable evidence when the current Editor binding surface does not expose Actor/Mesh/Material/Animation/PhysX components on direct `.procprefab` product instances; that state is not a pass for character component presence. The runtime/spawnable mode records `runtime_spawnable_proof` and classifies stalls with `runtime_spawnable_proof_stall`; it does not launch runtime unless a future bounded harness is explicitly pinned.

Runtime harness diagnostics are separate from Editor stall diagnostics. A gated runtime command that exits `3221225477` is rendered as `0xC0000005` and classified as crash-like runtime failure, with stdout/stderr/runtime-log summaries captured by `tools/o3de/runtime_harness.py`. That classification must not be folded into Editor pass/fail proof or counted as runtime character proof.

Runtime quit-variant diagnostics are also separate from Editor stalls. Variant reports may show clean exit, nonzero exit, timeout/kill, AssetManager shutdown asserts, shader serializer errors, or Asset Processor negotiation failures, but those signals belong to `runtime_command_variant_matrix` and `runtime_quit_variant_diagnostic_status`; they do not change Editor smoke progress markers or temp-level policy.

Runtime exit-strategy and exit-fixture diagnostics remain separate as well. Exit-strategy reports explain why externally pinnable launcher exits are accepted or rejected; exit-fixture reports explain whether a harness-side, non-shipping after-initialization exit hook exists. The preserved #129 fixture status `blocked_by_fixture_requires_project_code_rebuild` is a typed runtime-harness blocker, not an Editor stall and not runtime character evidence. The repo-owned fixture source/rebuild checks add `runtime_exit_fixture_source_ready` and `runtime_exit_fixture_rebuild_gate_pass` evidence, but those readiness states still do not launch runtime and do not alter Editor smoke progress markers.

Registration, enablement, rebuild, and fixture runtime execution are also not Editor stall evidence. Registration/enablement reports may mutate only live project Gem metadata under `MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION=1`; rebuild reports may build only the scoped launcher target under `MAXINE_ALLOW_RUNTIME_FIXTURE_REBUILD=1`. A fixture runtime command may exit with code `0` and still fail verification if it emits disqualifying runtime signals or auto-loads a default/production level. Such a failure is reported as runtime fixture evidence, not as an Editor smoke timeout or progress-marker failure.

Runtime launch-hygiene diagnostics add the no-default-level layer without changing Editor stall semantics. The paired project's defaultlevel autoload is sourced to `Registry/load_level.setreg` and `/O3DE/Autoexec/ConsoleCommands/LoadLevel=defaultlevel`; the harness source-validates `--regremove=/O3DE/Autoexec/ConsoleCommands/LoadLevel` as a per-process prevention strategy. A no-default-level fixture run can still fail on Asset Processor negotiation or shader serializer signals, and those failures remain runtime-harness evidence rather than Editor progress-marker evidence.

Runtime LoadLevel override diagnostics also remain outside Editor stall semantics. They record Settings Registry merge-order evidence and a candidate matrix for removing both `/O3DE/Autoexec/ConsoleCommands/LoadLevel` and `/O3DE/Runtime/SpawnableLevelSystem/DeferredLoadLevel`. The current bounded fixture run still loads `Levels/defaultlevel/defaultlevel.spawnable`, so the candidate is blocked by settings-registry timing and the launch remains blocked by defaultlevel autoload. That does not change Editor progress markers, temp-level-only Editor execution, or the direct `.procprefab` Editor proof contract.

Runtime later-precedence registry patch diagnostics are also runtime-harness evidence, not Editor stall evidence. They source-validate final command-line `--regset-file` registry-file merging after project registry files and may generate a temporary artifact `.setreg` merge patch only when `MAXINE_ALLOW_RUNTIME_FIXTURE_TEMP_REGISTRY_PATCH=1` is set. Patch generation, fixture marker, or exit code `0` still do not alter Editor progress markers and do not claim runtime execution if defaultlevel autoload or disqualifying AP/shader/runtime signals remain.

Runtime pre-autoexec LoadLevel suppression diagnostics remain outside Editor stall semantics as well. They source-validate Settings Registry merge order, project-user registry order, console autoexec notification timing, and `SpawnableLevelSystem` deferred-load timing before selecting any fixture strategy. The gated fixture mode may temporarily rename the live project `Registry/load_level.setreg` under `MAXINE_ALLOW_RUNTIME_FIXTURE_PROJECT_MUTATION=1`, then restore it after the bounded process exits. If generated `Cache/pc/bootstrap*.setreg` files still contain `LoadLevel=defaultlevel`, the runtime blocker is recorded as cache-bootstrap evidence, not an Editor stall. That reversible registry suppression can affect only runtime harness launch hygiene; it must not change Editor smoke temp-level progress markers, mutate `Levels/defaultlevel`, edit Asset Cache, or be counted as runtime character proof.

Runtime cache-bootstrap LoadLevel source diagnostics are likewise separate from Editor stall evidence. They inventory generated `Cache/pc/bootstrap*.setreg` files and source-validate Asset Processor bootstrap generation and GameApplication bootstrap loading. A gated fixture attempt may temporarily neutralize those generated keys only with backup, restore, and hash verification under `MAXINE_ALLOW_RUNTIME_FIXTURE_CACHE_BOOTSTRAP_MUTATION=1`; `asset_cache_deleted` must remain false. Even if that runtime fixture exits `0`, it does not change Editor progress markers and cannot become runtime proof while defaultlevel autoload or disqualifying AP/shader/runtime signals remain.

Runtime AP/shader signal classification remains a runtime-harness concern, not an Editor stall concern. It can source-classify the bounded no-defaultlevel fixture AP negotiation warning and known Atom serializer signatures, but those classifications do not change Editor smoke progress markers, temp-level policy, direct `.procprefab` Editor evidence, or runtime character proof. Any unclassified AP/shader/assert/load-error signal must stay in the runtime harness report as a blocker.

Runtime character product-load evidence is also runtime-harness evidence, not Editor stall evidence. The product-load fixture probe uses the repo-owned `MaxineRuntimeExitFixture` component, Settings Registry product-list keys, and `MAXINE_RUNTIME_PRODUCT_LOAD_*` markers to resolve and load approved character products in a bounded no-defaultlevel command envelope. Product-load success can prove only runtime product resolution/load readiness. It must not change Editor progress markers, imply direct product Editor component inventory, or claim runtime instantiation, spawn, animation, full character proof, or production-ready release status.

Runtime `.procprefab` handler/surface diagnostics remain outside Editor stall semantics too. The diagnostic records whether direct runtime `.procprefab` AssetManager load is supported, whether its handler is runtime-available, and whether a spawnable or prefab-equivalent runtime surface exists. The current source-validated direct handler is builder/tools-only, so the PR #138 `asset_handler_missing` blocker remains preserved. This diagnostic must not change Editor temp-level behavior, direct Editor `.procprefab` proof, product-load proof, spawn proof, animation proof, or full runtime character proof.

Runtime approved character spawnable-surface diagnostics are also runtime-harness evidence, not Editor stall evidence. The diagnostic source-validates the `*.prefab` to `.spawnable` product path and runtime `AzFramework::Spawnable` handler, then searches APB/AP DB evidence for approved release-rigged character spawnables. Missing approved surfaces, rejected defaultlevel/level/temp/generic spawnables, or generation-required blockers do not change Editor progress markers, direct `.procprefab` Editor proof, or temp-level policy, and they must not be reported as runtime product-load, spawn, animation, or full character proof.

Runtime exit-strategy diagnostics add a further non-Editor layer. They source-classify candidate exit mechanisms in `runtime_exit_strategy_candidate_matrix` and may stop with `blocked_by_missing_source_validated_runtime_exit_strategy` without launching runtime when no bounded no-production-level exit path is validated. That blocker is not an Editor stall and does not weaken the existing temp-level-only smoke contract.
