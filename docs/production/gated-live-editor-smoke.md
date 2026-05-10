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

## Current Blocker

`EditorPythonBindings.Editor.dll` exists in the paired profile bin and the controlled project enables `EditorPythonBindings`, but no paired `Editor.exe` or `O3DEEditor.exe` exists under `C:/src/o3de/build/windows/bin/profile`.

A bounded low-memory `Editor` target build was attempted and exceeded the one-hour command window without producing the executable. The build process tree was stopped, raw logs remain gitignored under `artifacts/o3de-integration/setup/editor/`, and live Editor execution was not attempted.
