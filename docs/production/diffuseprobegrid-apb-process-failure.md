# DiffuseProbeGrid APB Process Failure

## Scope

This note records the APB-only golden corpus fix for the non-golden engine/Gem asset failure:

```text
C:/src/o3de/Gems/DiffuseProbeGrid/Assets/Passes/DiffuseProbeGridQueryFullscreenWithAlbedo.pass
```

The fix applies only to the controlled local `MAXINE_GoldenCorpus` project. It does not mutate production projects, does not patch O3DE engine source assets, and does not treat APB exit `1` as success.

## Diagnosis

The release-rigged product evidence was already complete after the pxmesh slice:

- `azmodel`
- `actor`
- `procprefab`
- `motion`
- `motionset`
- `animgraph`
- `pxmesh`
- `azmaterial`

APB still exited `1` because `DiffuseProbeGrid` was directly enabled in:

```text
%USERPROFILE%/O3DE/Projects/MAXINE_GoldenCorpus/project.json
```

That caused APB to scan the DiffuseProbeGrid Gem assets. The failing pass asset reported:

```text
PassBuilder: Loading issues: Unable to resolve provided type: DiffuseProbeGridQueryFullscreenPassData. '/PassTemplate/PassData'
```

`DiffuseProbeGrid` is not required for the controlled release-rigged character/product-evidence fixture, so the smallest safe fix was to remove that Gem from the controlled project rather than patching engine Gem content or suppressing APB process failures.

## Fix

The controlled project was changed with the O3DE CLI:

```powershell
C:/src/o3de/scripts/o3de.bat disable-gem --project-path C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus --gem-name DiffuseProbeGrid
```

Project-specific registry metadata was then regenerated:

```powershell
cmake -S C:/src/o3de -B C:/src/o3de/build/windows -DLY_PROJECTS=C:/Users/topgu/O3DE/Projects/MAXINE_GoldenCorpus
```

After reconfiguration, `cmake_dependencies.maxine_goldencorpus*.setreg` no longer referenced `DiffuseProbeGrid`.

## Result

The APB-only command now exits cleanly:

```powershell
python tools/o3de/asset_processor_batch.py --corpus examples/golden-corpus --enable-asset-processor-batch --golden-project-fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --strict-integration
```

Observed result:

- APB process exit code: `0`
- wrapper exit code: `0`
- APB-only suite exit code: `0`
- product matrix status: `pass`
- missing products: none
- pending products: none
- `cache_heuristic_used=false`
- `live_asset_processor_batch_execution=true`
- `live_editor_execution=false`
- `live_publication=false`
- `release_packaging=false`

Sanitized evidence:

```text
examples/private-runner/apb-live-full-golden-corpus.release-rigged.apb-clean.pass.example.json
```

Raw local artifacts remain gitignored under:

```text
artifacts/o3de-integration/apb/
artifacts/o3de-integration/setup/diffuseprobegrid/
```

## Follow-Up

The next slice can prepare gated live Editor smoke on the private runner. Keep Editor smoke non-publishing, keep release packaging disabled, and keep `DiffuseProbeGrid` out of `MAXINE_GoldenCorpus` unless a future fixture explicitly needs diffuse probe grid assets.
