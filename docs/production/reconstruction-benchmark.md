# Reconstruction Benchmark Harness

The benchmark harness lives in `tools/benchmark/reconstruction_benchmark.py`.

It is local-only:

- detects whether candidates are installed
- skips unavailable candidates with warnings
- never downloads models
- never calls external services
- records model/version/license when available
- records elapsed time, fixture import/product status, metrics, and artifact hashes

Candidate families tracked by the contract include TripoSR, Stable Fast 3D/SF3D, SPAR3D, and InstantMesh. Unit tests use a `fixture://local` candidate so the suite does not need GPUs, credentials, model downloads, or network access.
