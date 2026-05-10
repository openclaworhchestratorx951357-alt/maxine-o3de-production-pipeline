# Editor Smoke Fixture Corpus

This corpus is JSON-only evidence for the O3DE Editor Python package/prefab instantiation bridge.

Default validation is fixture mode and does not run O3DE Editor:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --mode fixture
```

Local Editor detection is opt-in and remains skipped when tooling is unavailable:

```powershell
python tools/o3de/editor_smoke.py --manifest examples/manifests/release_rigged.pass.example.json --enable-editor-smoke
```

The fail fixtures prove missing package/prefab evidence, missing actor/motion products, and release cache heuristics cannot satisfy release smoke evidence.

Live Editor smoke examples are sanitized records from gated private-runner attempts. A stalled live report is not a pass:

```text
examples/editor-smoke/editor-smoke-live.release-rigged.stalled.example.json
```
