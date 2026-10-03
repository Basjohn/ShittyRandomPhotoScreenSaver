"""Run in Blender MCP from the saved Usu file: validate, render, and save.

The .blend is the modelling source. This script does not rebuild its geometry.
It creates no rig, animation, runtime integration, or engine export.
"""
import bpy
import bmesh
import json
from pathlib import Path

ASSET = Path(r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\assets\usu")
scene = bpy.data.scenes["Usu_STATIC_Approval"]
bpy.context.window.scene = scene
principal = [o for o in scene.objects if o.get("asset_role") == "static_character"]
assert principal, "No principal Usu surfaces tagged for validation"
assert not any(o.type == "ARMATURE" for o in scene.objects)
assert not any(m.type == "ARMATURE" for o in scene.objects for m in o.modifiers)
assert not any(o.animation_data and o.animation_data.action for o in scene.objects)
assert len(bpy.data.actions) == 0

report = {"scope": "Static authoring only; visual approval pending", "surfaces": {}}
for obj in principal:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    counts = {
        "vertices": len(bm.verts),
        "faces": len(bm.faces),
        "quads": sum(len(f.verts) == 4 for f in bm.faces),
        "triangles": sum(len(f.verts) == 3 for f in bm.faces),
        "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
        "loose_vertices": sum(not v.link_edges for v in bm.verts),
        "zero_area_faces": sum(f.calc_area() < 1e-10 for f in bm.faces),
    }
    bm.free()
    assert counts["nonmanifold_edges"] == 0, (obj.name, counts)
    assert counts["loose_vertices"] == 0, (obj.name, counts)
    assert counts["zero_area_faces"] == 0, (obj.name, counts)
    report["surfaces"][obj.name] = counts
report["armatures"] = 0
report["armature_modifiers"] = 0
report["scene_object_actions"] = 0
reference = scene.objects["Approved_Usu_Turnaround_PACKED"].data
report["packed_reference"] = bool(reference and reference.packed_file)
assert report["packed_reference"], "Approved turnaround must be packed"
(ASSET / "source" / "mesh_validation.json").write_text(json.dumps(report, indent=2) + "\n")

settings = scene.render.image_settings
assert "PNG" in {v.identifier for v in settings.bl_rna.properties["file_format"].enum_items}
settings.file_format = "PNG"
scene.render.resolution_x = 1000
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
for camera, stem in (("FRONT", "front"), ("SIDE", "side"),
                     ("BACK", "back"), ("THREE_QUARTER", "three_quarter")):
    scene.camera = scene.objects["Review_" + camera]
    scene.render.filepath = str(ASSET / "renders" / ("Usu_" + stem + ".png"))
    bpy.ops.render.render(write_still=True)
scene.camera = scene.objects["Review_THREE_QUARTER"]
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET / "Usu_Static_Approval.blend"), compress=True)
print(json.dumps(report, indent=2))
