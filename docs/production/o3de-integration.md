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
