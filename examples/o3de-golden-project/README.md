# O3DE Golden Project Fixture

This directory contains fixtures and reviewed source inputs for the future private-runner O3DE golden project.

The fixture contract defines safe project-relative roots, temporary smoke-test level policy, expected artifact retention paths, product expectations by lane, and evidence links between manifests, product resolution, Asset Processor Batch proof, Editor smoke, QC, and evidence bundles.

Most files do not create an O3DE project, do not contain model assets, and do not run O3DE. The `source/Assets/Characters/MAXINE_GoldenCorpus/prefabs/release_rigged.prefab` file is a repo-owned reviewed source prefab intended to be staged into the live project scanfolder under an explicit gate so APB can produce a character-specific `.spawnable`. It is source input only; generated `.spawnable` products and Asset Cache files must not be committed.

Useful commands:

```powershell
python tools/o3de/golden_project_fixture.py --fixtures examples/o3de-golden-project
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness
python tools/o3de/golden_project_fixture.py --fixture examples/o3de-golden-project/maxine-golden-project.fixture.json --check-local-readiness --strict
```
