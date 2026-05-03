from pathlib import Path


def test_resolver_ladder_index_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "roadmap" / "RESOLVER-LADDER-INDEX.md"
    assert path.exists()


def test_pr_stack_consolidation_guide_exists():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "docs" / "operator-playbooks" / "PR-STACK-CONSOLIDATION-GUIDE.md"
    assert path.exists()


def test_readme_contains_resolver_ladder_section():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8-sig")
    assert "M.A.X.I.N.E. Resolver Ladder" in readme


def test_handoff_contains_post_consolidation_milestone():
    repo_root = Path(__file__).resolve().parents[2]
    handoff = (repo_root / "CODEX-HANDOFF.md").read_text(encoding="utf-8-sig")
    assert "Post-Consolidation Next Milestone" in handoff
