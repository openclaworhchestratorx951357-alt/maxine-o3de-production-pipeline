# Evidence Bundles

An evidence bundle is the reviewable index of files that support a manifest and QC report. It records IDs, kinds, paths, and hashes when known.

Evidence bundles in this slice are static and local. They must not claim live O3DE runtime success, Asset Processor success, or external service success unless those systems actually ran under a future admitted integration job.

The example bundle is:

```text
examples/production/evidence_bundle.release_rigged.pass.example.json
```

Strict manifest validation requires referenced evidence files to exist.
