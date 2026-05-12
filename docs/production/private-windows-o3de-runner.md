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
