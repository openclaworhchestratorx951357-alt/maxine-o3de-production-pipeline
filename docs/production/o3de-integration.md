# O3DE Integration Prep

This slice does not run O3DE Editor, Asset Processor Batch, or live runtime smoke.

Future private Windows integration jobs should be explicitly gated and may use commands shaped like:

```powershell
AssetProcessorBatch.exe --project-path <MaxineO3DE project> --platform pc
Editor.exe --project-path <MaxineO3DE project> --runpython <smoke-script.py>
```

Those commands are documentation only unless a future slice admits a safe local query path. `tools/validation/validate_all.py` uses fixture mode by default so local and public CI validation stays credential-free and non-destructive.

To opt into the current local O3DE adapter detection:

```powershell
python tools/validation/validate_all.py --enable-o3de-integration
```

If O3DE tooling is unavailable, the result is reported as skipped with `MXN_VALIDATION_TOOL_UNAVAILABLE`. To require local tooling:

```powershell
python tools/validation/validate_all.py --enable-o3de-integration --strict-integration
```

Strict mode fails when the local integration path is unavailable. Neither mode publishes, runs Editor, runs Asset Processor, contacts external services, or claims live O3DE success.

Asset Processor Batch golden corpus fixture validation is included in the default safe suite:

```powershell
python tools/validation/validate_all.py
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --mode fixture
```

Optional local Asset Processor Batch detection is separate and explicit:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --strict-integration
```

The local APB path requires `O3DE_ENGINE_ROOT`, `O3DE_PROJECT_PATH`, and an AssetProcessorBatch executable. Missing tooling is skipped in non-strict mode and fails in strict mode.

Editor Python package/prefab smoke fixture validation is also included in the default safe suite:

```powershell
python tools/validation/validate_all.py
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode fixture
```

Optional local Editor detection is separate and explicit:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke --strict-integration
```

The local Editor path requires `O3DE_ENGINE_ROOT`, `O3DE_PROJECT_PATH`, and an Editor executable. Missing tooling is skipped in non-strict mode and fails in strict mode. Fixture reports keep `live_editor_execution=false`; screenshots and Editor logs are fixture-labeled unless a future gated run actually captures them.

Private Windows runner wiring is manual-only and self-hosted only:

```powershell
python tools/ci/o3de_runner_readiness.py
python tools/ci/run_o3de_integration_suite.py --dry-run
python tools/ci/run_o3de_integration_suite.py --mode fixture
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration
python tools/ci/run_o3de_integration_suite.py --enable-o3de-integration --strict-integration
```

See `docs/production/private-windows-o3de-runner.md` for the workflow guard phrase, runner labels, and local environment variables. Normal CI remains fixture/offline.

Golden project fixture prep defines the controlled local project contract for future private-runner runs:

```powershell
python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness --strict
```

The fixture maps manifests to project-relative source roots, package/prefab roots, `Levels/_maxine_smoke` temp levels, and `Saved/MaxineEvidence` retention paths. It is validated by default, but local readiness is optional and never mutates the project.
