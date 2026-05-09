# O3DE Golden Project Fixture

This directory contains JSON-only fixtures for the future private-runner O3DE golden project.

The fixture contract defines safe project-relative roots, temporary smoke-test level policy, expected artifact retention paths, product expectations by lane, and evidence links between manifests, product resolution, Asset Processor Batch proof, Editor smoke, QC, and evidence bundles.

These files do not create an O3DE project, do not contain model assets, and do not run O3DE. They are intended for default offline validation and for future private Windows runner readiness checks.

Useful commands:

```powershell
python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness --strict
```
