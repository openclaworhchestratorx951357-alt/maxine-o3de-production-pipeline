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
