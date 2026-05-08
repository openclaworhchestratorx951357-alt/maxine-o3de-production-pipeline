"""Metadata/fixture validator for the MAX_BIPED_v1 skeleton contract."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from tools.validation.results import ValidationResult


REQUIRED_BONES = [
    "root",
    "pelvis",
    "spine_01",
    "spine_02",
    "neck",
    "head",
    "clavicle_l",
    "upperarm_l",
    "lowerarm_l",
    "hand_l",
    "clavicle_r",
    "upperarm_r",
    "lowerarm_r",
    "hand_r",
    "thigh_l",
    "calf_l",
    "foot_l",
    "ball_l",
    "thigh_r",
    "calf_r",
    "foot_r",
    "ball_r",
]

REQUIRED_EDGES = {
    "pelvis": "root",
    "spine_01": "pelvis",
    "spine_02": "spine_01",
    "neck": "spine_02",
    "head": "neck",
    "clavicle_l": "spine_02",
    "upperarm_l": "clavicle_l",
    "lowerarm_l": "upperarm_l",
    "hand_l": "lowerarm_l",
    "clavicle_r": "spine_02",
    "upperarm_r": "clavicle_r",
    "lowerarm_r": "upperarm_r",
    "hand_r": "lowerarm_r",
    "thigh_l": "pelvis",
    "calf_l": "thigh_l",
    "foot_l": "calf_l",
    "ball_l": "foot_l",
    "thigh_r": "pelvis",
    "calf_r": "thigh_r",
    "foot_r": "calf_r",
    "ball_r": "foot_r",
}


def _bone_map(skeleton: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    bones = skeleton.get("bones", [])
    if not isinstance(bones, list):
        return {}
    return {str(bone.get("name", "")).strip(): bone for bone in bones if isinstance(bone, dict) and bone.get("name")}


def _is_origin(position: Any) -> bool:
    if not isinstance(position, list) or len(position) != 3:
        return False
    return all(abs(float(value)) <= 0.0001 for value in position)


def validate_skeleton_contract(skeleton: Dict[str, Any], *, character_tier: str = "hero") -> ValidationResult:
    result = ValidationResult()
    bones = _bone_map(skeleton)
    if "root" not in bones:
        result.add_error("MXN_ROOT_BONE_INVALID", "MAX_BIPED_v1 requires a root bone named 'root'.")
    else:
        root = bones["root"]
        if root.get("parent") not in ("", None):
            result.add_error("MXN_ROOT_BONE_INVALID", "MAX_BIPED_v1 root bone must not have a parent.")
        if not _is_origin(root.get("position", [999, 999, 999])):
            result.add_error("MXN_ORIGIN_INVALID", "MAX_BIPED_v1 root bone must be at scene origin.")

    for bone_name in REQUIRED_BONES:
        if bone_name not in bones:
            code = "MXN_ROOT_BONE_INVALID" if bone_name == "root" else "MXN_SKELETON_CONTRACT_FAIL"
            result.add_error(code, f"Required MAX_BIPED_v1 bone is missing: {bone_name}")

    if "pelvis" not in bones:
        result.add_error("MXN_SKELETON_CONTRACT_FAIL", "MAX_BIPED_v1 requires pelvis under root.")
    for child, expected_parent in REQUIRED_EDGES.items():
        if child not in bones:
            continue
        actual_parent = bones[child].get("parent")
        if actual_parent != expected_parent:
            code = "MXN_ROOT_BONE_INVALID" if child == "pelvis" else "MXN_SKELETON_CONTRACT_FAIL"
            result.add_error(code, f"Bone {child} must have parent {expected_parent}; got {actual_parent!r}.")

    coordinate_system = skeleton.get("coordinate_system", {}) if isinstance(skeleton.get("coordinate_system"), dict) else {}
    if coordinate_system.get("up_axis") != "Z":
        result.add_error("MXN_ORIGIN_INVALID", "MAX_BIPED_v1 release export must be Z-up.")
    units = skeleton.get("units", {}) if isinstance(skeleton.get("units"), dict) else {}
    if float(units.get("meters_per_unit", 0)) != 1.0:
        result.add_error("MXN_SCALE_INVALID", "MAX_BIPED_v1 requires 1 meter = 1 O3DE world unit.")

    morphs = skeleton.get("facial_morphs", [])
    has_morphs = isinstance(morphs, list) and bool(morphs)
    tier = str(character_tier or skeleton.get("character_tier", "hero")).strip().lower()
    waiver = skeleton.get("facial_waiver") if isinstance(skeleton.get("facial_waiver"), dict) else {}
    if not has_morphs and tier == "hero":
        result.add_error("MXN_FACIAL_MORPH_MISSING", "Hero MAX_BIPED_v1 characters require facial morph inventory.")
    elif not has_morphs and tier == "npc" and waiver.get("approved") is True:
        result.add_warning("MXN_FACIAL_MORPH_MISSING", "NPC facial morph waiver accepted with warning.")
    elif not has_morphs and tier == "npc":
        result.add_error("MXN_FACIAL_MORPH_MISSING", "NPC missing facial morphs requires an approved waiver.")

    return result
