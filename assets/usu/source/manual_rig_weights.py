"""Build reviewable, geometry-specific Usu rig weights without Blender.

Input is the approved static geometry snapshot.  Output is data only; it does
not create or modify mesh geometry, a blend, actions, or bones.
"""

import json
import hashlib
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "tmp" / "Usu_Rig_Validation" / "approved_geometry.json"
OUTPUT = Path(__file__).with_name("manual_weights.json")
DATA = json.loads(SOURCE.read_text())


def smoothstep(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def continuous_arm_weights(vertices):
    """Use a smooth lateral ownership field across Usu's welded arm/hip web.

    The dark hand material crosses the medial welded web, so it cannot be a
    rigid arm anchor: during an X-axis swing that folds the hip through the
    body.  This field keeps the inner web torso-owned and reaches full arm
    ownership only at the outer hand.  Usu's handedness is L=+X, R=-X.
    """
    x, _, z = vertices.T
    lateral = smoothstep((np.abs(x) - 0.55) / 0.40)  # 0 at .55, 1 at .95
    shoulder = 1.0 - smoothstep((z - 2.62) / 0.25)   # 1 through 2.62, 0 by 2.87
    shared = lateral * shoulder
    left = shared * (x > 0.0)
    right = shared * (x < 0.0)
    torso = 1.0 - left - right
    return left, right, torso, {
        "arm_weighting": "continuous lateral welded-web transition",
        "lateral_transition_abs_x": [0.55, 0.95],
        "shoulder_transition_z": [2.62, 2.87],
        "ARM_L_max": float(left.max()),
        "ARM_R_max": float(right.max()),
        "torso_min": float(torso.min()),
    }


# Head and fused ears.  The lower lobe is the only animated region.  The
# fused web fades into HEAD before z=3.42; upper root z>=3.8 is therefore
# unconditionally rigid even if an animator poses EAR_MID/TIP.
head = DATA["Usu_Head_And_Ears"]
hv = np.asarray(head["verts"], dtype=float)
x, y, z = hv.T
side = np.sign(x)
x_cut = 0.55 + 0.10 * np.clip(z - 2.80, 0.0, 0.62) / 0.62
outer_lower_lobe = (np.abs(x) > x_cut) & (y > 0.08) & (z < 3.42)
web_fade = np.where(z > 3.22, 1.0 - smoothstep((z - 3.22) / 0.20), 1.0)
lateral_fade = smoothstep((np.abs(x) - x_cut) / 0.12)
ear = outer_lower_lobe.astype(float) * web_fade * lateral_fade

# Matches the live bone pivots: MID at z=2.90 and TIP at z=2.40.  These broad
# transitions preserve the simple ear volume instead of forming hinge rings.
mid_progress = smoothstep((3.02 - z) / 0.40)       # 3.02 -> 2.62
tip_progress = smoothstep((2.62 - z) / 0.42)       # 2.62 -> 2.20
tip = ear * tip_progress
mid = ear * mid_progress * (1.0 - tip_progress)
ear_root = ear - mid - tip
head_weight = 1.0 - ear

head_weights = {
    "HEAD": head_weight,
    "EAR_L_ROOT": ear_root * (side > 0),
    "EAR_L_MID": mid * (side > 0),
    "EAR_L_TIP": tip * (side > 0),
    "EAR_R_ROOT": ear_root * (side < 0),
    "EAR_R_MID": mid * (side < 0),
    "EAR_R_TIP": tip * (side < 0),
}


# Torso and arms.  BODY_ROOT owns the lower belly, BODY takes the main torso,
# and HEAD owns only the neck cap.  The continuous arm share is subtracted
# first, then the residual distributes across that three-bone torso chain.
body = DATA["Usu_Body_And_Arms"]
bv = np.asarray(body["verts"], dtype=float)
arm_l, arm_r, torso, arm_report = continuous_arm_weights(bv)
bz = bv[:, 2]
body_progress = smoothstep((bz - 1.15) / (2.30 - 1.15))
head_progress = smoothstep((bz - 2.80) / (3.13 - 2.80))
body_weight = torso * body_progress * (1.0 - head_progress)
head_neck = torso * head_progress
body_root = torso - body_weight - head_neck


def rigid_head_group(name):
    return {"HEAD": [1.0] * len(DATA[name]["verts"])}


result = {
    "mesh_fingerprints": {
        name: hashlib.sha256(json.dumps([data['verts'], data['faces']], separators=(',', ':')).encode()).hexdigest()
        for name, data in DATA.items()
    },
    "contract": {
        "ROOT": "non-deforming master",
        "BODY_ROOT": "lower torso residual; receives all torso residual below z=1.15",
        "BODY": "torso residual transition z=1.15 to 2.30",
        "HEAD": "rigid skull and face; neck residual transition z=2.80 to 3.13",
        "handedness": "L is +X (Usu_Foot_L); R is -X (Usu_Foot_R)",
        "arm_weighting": "continuous lateral welded-web transition; no material or topology anchors",
        "ear_lock": "all EAR weights are zero for z>=3.42, y<=0.08, and abs(x)<=0.52",
    },
    "Usu_Head_And_Ears": {name: values.round(8).tolist() for name, values in head_weights.items()},
    "Usu_Body_And_Arms": {
        "BODY_ROOT": body_root.round(8).tolist(),
        "BODY": body_weight.round(8).tolist(),
        "HEAD": head_neck.round(8).tolist(),
        "ARM_L": arm_l.round(8).tolist(),
        "ARM_R": arm_r.round(8).tolist(),
    },
    "Usu_Foot_L": {"LEG_L": [1.0] * len(DATA["Usu_Foot_L"]["verts"])},
    "Usu_Foot_R": {"LEG_R": [1.0] * len(DATA["Usu_Foot_R"]["verts"])},
    "Usu_Eye_Outline_L": rigid_head_group("Usu_Eye_Outline_L"),
    "Usu_Eye_Iris_Rim_L": rigid_head_group("Usu_Eye_Iris_Rim_L"),
    "Usu_Eye_Iris_L": rigid_head_group("Usu_Eye_Iris_L"),
    "Usu_Eye_Glint_L": rigid_head_group("Usu_Eye_Glint_L"),
    "Usu_Brow_L": rigid_head_group("Usu_Brow_L"),
    "Usu_Eye_Outline_R": rigid_head_group("Usu_Eye_Outline_R"),
    "Usu_Eye_Iris_Rim_R": rigid_head_group("Usu_Eye_Iris_Rim_R"),
    "Usu_Eye_Iris_R": rigid_head_group("Usu_Eye_Iris_R"),
    "Usu_Eye_Glint_R": rigid_head_group("Usu_Eye_Glint_R"),
    "Usu_Brow_R": rigid_head_group("Usu_Brow_R"),
    "report": {
        "head_sum_range": [float((head_weight + ear_root + mid + tip).min()), float((head_weight + ear_root + mid + tip).max())],
        "body_sum_range": [float((body_root + body_weight + head_neck + arm_l + arm_r).min()), float((body_root + body_weight + head_neck + arm_l + arm_r).max())],
        "ear_moving_mass": float(ear.sum()),
        **arm_report,
    },
}
OUTPUT.write_text(json.dumps(result))
print(json.dumps(result["report"], indent=2))
