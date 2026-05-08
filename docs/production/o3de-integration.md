# O3DE Integration Prep

This slice does not run O3DE Editor, Asset Processor Batch, or live runtime smoke.

Future private Windows integration jobs should be explicitly gated and may use commands shaped like:

```powershell
AssetProcessorBatch.exe --project-path <MaxineO3DE project> --platform pc
Editor.exe --project-path <MaxineO3DE project> --runpython <smoke-script.py>
```

Those commands are documentation only in this slice. `tools/validation/validate_all.py` reports O3DE Editor and Asset Processor checks as skipped so local and public CI validation stays credential-free and non-destructive.
