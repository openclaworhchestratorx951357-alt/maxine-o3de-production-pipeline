import json
from pathlib import Path

from tools.qc.skeleton_contract import validate_skeleton_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
SKELETON = REPO_ROOT / "examples" / "production" / "MAX_BIPED_v1.skeleton.json"


def _load() -> dict:
    return json.loads(SKELETON.read_text(encoding="utf-8-sig"))


def test_valid_skeleton_passes():
    result = validate_skeleton_contract(_load(), character_tier="hero")

    assert result.status == "pass"


def test_missing_root_fails():
    skeleton = _load()
    skeleton["bones"] = [bone for bone in skeleton["bones"] if bone["name"] != "root"]

    result = validate_skeleton_contract(skeleton)

    assert result.status == "fail"
    assert "MXN_ROOT_BONE_INVALID" in result.error_codes


def test_root_not_origin_flagged():
    skeleton = _load()
    for bone in skeleton["bones"]:
        if bone["name"] == "root":
            bone["position"] = [0, 0, 0.1]

    result = validate_skeleton_contract(skeleton)

    assert result.status == "fail"
    assert "origin" in " ".join(result.messages)


def test_missing_pelvis_fails():
    skeleton = _load()
    skeleton["bones"] = [bone for bone in skeleton["bones"] if bone["name"] != "pelvis"]

    result = validate_skeleton_contract(skeleton)

    assert result.status == "fail"
    assert "pelvis" in " ".join(result.messages)


def test_renamed_required_bone_fails():
    skeleton = _load()
    for bone in skeleton["bones"]:
        if bone["name"] == "spine_01":
            bone["name"] = "spine_a"

    result = validate_skeleton_contract(skeleton)

    assert result.status == "fail"
    assert "spine_01" in " ".join(result.messages)


def test_npc_facial_waiver_warns_and_is_accepted():
    skeleton = _load()
    skeleton["facial_morphs"] = []
    skeleton["facial_waiver"] = {"approved": True, "reason": "background NPC"}

    result = validate_skeleton_contract(skeleton, character_tier="npc")

    assert result.status == "warn"
    assert "MXN_FACIAL_MORPH_MISSING" in result.warning_codes


def test_hero_missing_facial_morphs_fails():
    skeleton = _load()
    skeleton["facial_morphs"] = []

    result = validate_skeleton_contract(skeleton, character_tier="hero")

    assert result.status == "fail"
    assert "MXN_FACIAL_MORPH_MISSING" in result.error_codes
