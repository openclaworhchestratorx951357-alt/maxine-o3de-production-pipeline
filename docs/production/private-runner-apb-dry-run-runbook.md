# Private Runner APB Dry-Run Runbook

This runbook prepares a trusted private self-hosted Windows runner for the first live APB-only golden corpus run in a later slice.

It does not run live Asset Processor Batch by default. It does not run Editor, Editor smoke, publication, release packaging, runner registration, or credential handling.

## Prerequisites

- A private self-hosted Windows runner already registered by the operator.
- Runner labels: `self-hosted`, `Windows`, `X64`, `o3de`, `maxine-private`.
- O3DE installed locally.
- A controlled local O3DE project path, not a production project.
- AssetProcessorBatch executable available locally.
- Python available on the runner.
- This repository checked out on the runner.

Do not store runner registration tokens or credentials in repo files.

## Environment Template

Start from:

```text
examples/private-runner/o3de-runner.env.example
```

Use machine-local paths:

```powershell
$env:O3DE_ENGINE_ROOT = "C:\path\to\o3de"
$env:O3DE_PROJECT_PATH = "C:\path\to\MAXINE_GoldenCorpus"
$env:O3DE_EDITOR_EXECUTABLE = "C:\path\to\Editor.exe"
$env:ASSET_PROCESSOR_BATCH_EXECUTABLE = "C:\path\to\AssetProcessorBatch.exe"
$env:MAXINE_ENABLE_O3DE_INTEGRATION = "1"
$env:MAXINE_ENABLE_ASSET_PROCESSOR_BATCH = "1"
$env:MAXINE_ENABLE_O3DE_EDITOR_SMOKE = "0"
$env:MAXINE_ALLOW_LIVE_O3DE_COMMANDS = "0"
$env:MAXINE_GOLDEN_PROJECT_FIXTURE = "examples/o3de-golden-project/maxine-golden-project.fixture.json"
$env:MAXINE_GOLDEN_CORPUS = "examples/golden-corpus"
$env:MAXINE_ARTIFACT_ROOT = "artifacts/o3de-integration"
$env:MAXINE_RUN_MODE = "readiness"
```

Keep `MAXINE_ENABLE_O3DE_EDITOR_SMOKE=0` for the APB-only first live run. Keep `MAXINE_ALLOW_LIVE_O3DE_COMMANDS=0` during dry-run readiness.

For APB-only readiness, `O3DE_EDITOR_EXECUTABLE` may remain unset as long as `MAXINE_ENABLE_O3DE_EDITOR_SMOKE=0`. Editor tooling is required only for a future Editor smoke slice.

## Dry-Run Sequence

Run these from the repository root:

```powershell
python tools/ci/private_runner_apb_dry_run_checklist.py
python tools/ci/private_runner_apb_dry_run_checklist.py --json
python tools/ci/o3de_runner_readiness.py --json
python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness
python tools/ci/run_o3de_integration_suite.py --dry-run
python tools/ci/run_o3de_integration_suite.py --mode fixture
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --check-local-readiness
python tools/o3de/audit_golden_corpus_sources.py --corpus examples/golden-corpus --project $env:O3DE_PROJECT_PATH --json
python tools/o3de/audit_apb_product_evidence.py --project $env:O3DE_PROJECT_PATH --apb-report <asset_processor_batch_live_report.json> --apb-executable $env:ASSET_PROCESSOR_BATCH_EXECUTABLE --json
```

Before any full APB retry, inventory APB candidates and reject mismatched binaries:

```powershell
python tools/o3de/diagnose_asset_processor_batch.py --inventory --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
```

If a candidate is not clearly paired with `MAXINE_GoldenCorpus`, do not use it for live APB. `AssetProcessor.exe` is never an acceptable substitute for `AssetProcessorBatch.exe`.

If no paired APB exists, build only the APB target from the selected engine build tree:

```powershell
$env:CL = "/Zm200"
cmake --build C:\src\o3de\build\windows --target AssetProcessorBatch --config profile --parallel 1 -- /m:1 /nodeReuse:false /p:CL_MPCount=1 /p:UseMultiToolTask=false /v:m
```

Stop and preserve logs if the build repeats C1060 or does not produce APB inside the bounded maintenance window. Do not run the full live golden corpus APB command until inventory selects the project/engine-paired APB and bounded diagnostics pass.

To inspect the build environment without running APB:

```powershell
python tools/o3de/diagnose_o3de_build_environment.py --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus --json
```

When the target is produced, verify it before any full APB run:

```powershell
python tools/o3de/diagnose_asset_processor_batch.py --inventory --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
python tools/o3de/diagnose_asset_processor_batch.py --run-bounded-diagnostics --timeout-seconds 120 --candidate C:\src\o3de\build\windows\bin\profile\AssetProcessorBatch.exe --engine-root C:\src\o3de --project $env:USERPROFILE\O3DE\Projects\MAXINE_GoldenCorpus
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --check-local-readiness --strict
```

For the full APB run, keep a bounded timeout in the session:

```powershell
$env:MAXINE_APB_TIMEOUT_SECONDS = "1800"
```

The APB wrapper records `timed_out`, `timeout_seconds`, and process cleanup status in the live report. A timeout is recorded as `MXN_APB_EXECUTION_STALLED` and is not a pass.

Expected dry-run behavior:

- Missing local tools produce skipped/unavailable reports in non-strict mode.
- Strict mode fails with `MXN_VALIDATION_TOOL_UNAVAILABLE` until paths/tools are configured.
- No live APB report is produced.
- No Editor report is produced in APB-only dry-run.
- No publication artifacts are produced.

Example skipped/unavailable report:

```text
examples/private-runner/apb-dry-run-checklist.unavailable.example.json
```

## Manual Workflow Sequence

1. Open GitHub Actions.
2. Select `O3DE Private Windows Integration`.
3. Use mode `readiness` or `fixture` first.
4. Enter the confirmation string:

```text
I_UNDERSTAND_THIS_REQUIRES_A_PRIVATE_SELF_HOSTED_WINDOWS_RUNNER
```

5. Keep `run_live_o3de_commands` set to `false` during dry-run.
6. Use `apb_live_non_strict` only after readiness and fixture checks pass.
7. Use `apb_live_strict` only when the APB-only path is ready to fail closed.

## Failure Modes

- `O3DE_ENGINE_ROOT` is unset or does not exist.
- `O3DE_PROJECT_PATH` is unset, unsafe, or points at the wrong project.
- `ASSET_PROCESSOR_BATCH_EXECUTABLE` is unset or missing.
- `ASSET_PROCESSOR_BATCH_EXECUTABLE` points at `AssetProcessor.exe` or an APB from a different archived project.
- The golden project fixture is invalid.
- Release proof depends on cache heuristics.
- Workflow confirmation phrase does not match.
- Strict mode fails with `MXN_VALIDATION_TOOL_UNAVAILABLE`.
- Bounded APB diagnostics time out with `MXN_APB_DIAGNOSTIC_STALLED`.
- Full APB execution times out with `MXN_APB_EXECUTION_STALLED`.
- Project-paired APB build does not finish producing `AssetProcessorBatch.exe` inside the bounded window.
- Build environment diagnostics report missing Visual Studio/MSVC, Windows SDK, CMake, or `LY_3RDPARTY_PATH`.
- A help-like APB diagnostic exits nonzero but does not stall; treat it as a responsiveness probe only, not as full APB success.
- APB exits `0` but expected product types are missing from Asset Processor database evidence; this is `MXN_ASSET_PRODUCT_MISSING`, not release success.
- Source settings can be present while product evidence is still missing. For release-rigged APB, `actor`, `motion`, `motionset`, `animgraph`, and physics-enabled `pxmesh` still require actual Asset Processor database evidence or an explicit reviewed waiver policy.
- APB product evidence can be complete while the APB process exits nonzero because a non-golden asset failed. This is `MXN_APB_PROCESS_EXIT_NONZERO`; do not report the APB-only suite as pass until the process failure is fixed or safely scoped.
- If `MAXINE_GoldenCorpus` directly enables an unrelated engine Gem such as `DiffuseProbeGrid`, APB may scan non-golden Gem assets and fail independently of the golden corpus product evidence. Remove only unnecessary Gems from the controlled project with the O3DE CLI, regenerate project-specific CMake registry metadata, and rerun APB; do not suppress APB exit `1` as success.

## Safety Checklist Before First Live APB

- Fixture validation passes.
- Local readiness passes.
- Golden project fixture validates.
- AssetProcessorBatch executable is detected.
- AssetProcessorBatch inventory shows a project-paired or engine-paired APB, not an archived RemoteControlHost binary.
- Build environment diagnostics pass if APB was built locally.
- Bounded APB diagnostics complete without `MXN_APB_DIAGNOSTIC_STALLED`.
- Project path is controlled and non-production.
- Artifact root is safe.
- Editor smoke gates remain off.
- Live publication remains blocked.
- Logs/artifacts contain no secrets.

When every APB-only readiness and live APB check passes with APB exit `0`, the next slice can prepare gated live Editor smoke. Keep publication and release packaging disabled.

## Editor Smoke Readiness Handoff

After the APB-only suite is clean, use the Editor readiness checks before any live Editor execution:

```powershell
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict
```

Editor smoke remains blocked unless a paired `Editor.exe` or `O3DEEditor.exe` exists under the selected engine build output, `EditorPythonBindings` is enabled and built, the APB baseline still passes, and publication/release packaging gates are disabled.

The controlled runner now has a paired profile Editor executable:

```text
C:/src/o3de/build/windows/bin/profile/Editor.exe
```

It was produced by building only the `Editor` target with low-memory settings:

```powershell
cmake --build C:/src/o3de/build/windows --target Editor --config profile --parallel 1 -- /m:1 /nodeReuse:false /p:CL_MPCount=1 /p:UseMultiToolTask=false /v:m
```

Strict readiness should use the explicit Editor path:

```powershell
python tools/o3de/diagnose_editor_smoke_readiness.py --engine-root C:/src/o3de --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --strict --json
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --check-local-readiness --strict --editor-executable C:/src/o3de/build/windows/bin/profile/Editor.exe --project C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --engine-root C:/src/o3de
```

The first live Editor smoke slice did rerun the APB clean baseline and strict Editor readiness in the same session. Editor launched with the paired profile executable and created an approved temp level under `Levels/_maxine_smoke`, but the run exceeded the bounded timeout before the in-Editor report completed and is represented as stalled:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.stalled.example.json
```

Future retries should keep this APB baseline prerequisite, use the same explicit live Editor gates, and continue treating stalled Editor automation as a blocker rather than pass.
