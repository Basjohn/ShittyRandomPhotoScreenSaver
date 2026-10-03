"""Run in Blender MCP from the saved Usu file: validate, render, and save.

The .blend is the modelling source. This script does not rebuild its geometry.
It creates no rig, animation, runtime integration, or engine export.
"""
import bpy
import bmesh
import json
import math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

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
    bm.faces.ensure_lookup_table()
    tree = BVHTree.FromBMesh(bm)
    intersections = sum(a < b and not set(bm.faces[a].verts).intersection(bm.faces[b].verts)
                        for a, b in tree.overlap(tree))
    counts = {
        "vertices": len(bm.verts),
        "faces": len(bm.faces),
        "quads": sum(len(f.verts) == 4 for f in bm.faces),
        "triangles": sum(len(f.verts) == 3 for f in bm.faces),
        "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
        "loose_vertices": sum(not v.link_edges for v in bm.verts),
        "zero_area_faces": sum(f.calc_area() < 1e-10 for f in bm.faces),
        "nonadjacent_cage_self_intersections": intersections,
    }
    bm.free()
    assert counts["nonmanifold_edges"] == 0, (obj.name, counts)
    assert counts["loose_vertices"] == 0, (obj.name, counts)
    assert counts["zero_area_faces"] == 0, (obj.name, counts)
    assert counts["nonadjacent_cage_self_intersections"] == 0, (obj.name, counts)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated_mesh = evaluated.to_mesh()
    faces = [tuple(p.vertices) for p in evaluated_mesh.polygons]
    tree = BVHTree.FromPolygons([v.co.copy() for v in evaluated_mesh.vertices], faces)
    counts["nonadjacent_subdivision_self_intersections"] = sum(
        a < b and not set(faces[a]).intersection(faces[b]) for a, b in tree.overlap(tree))
    evaluated.to_mesh_clear()
    assert counts["nonadjacent_subdivision_self_intersections"] == 0, (obj.name, counts)
    report["surfaces"][obj.name] = counts
report["armatures"] = 0
report["armature_modifiers"] = 0
report["scene_object_actions"] = 0
reference = scene.objects["Approved_Usu_Turnaround_PACKED"].data
report["packed_reference"] = bool(reference and reference.packed_file)
assert report["packed_reference"], "Approved turnaround must be packed"
report["validation_shading"] = "Workbench material colors; fixed paint studio; no shadows, cavity, specular or outline"
(ASSET / "source" / "mesh_validation.json").write_text(json.dumps(report, indent=2) + "\n")

# Shape validation uses ordinary solid shading, independent of scene lighting.
scene.render.engine = "BLENDER_WORKBENCH"
shading = scene.display.shading
for prop, value in (("light", "STUDIO"), ("color_type", "MATERIAL"),
                    ("background_type", "VIEWPORT")):
    assert value in {v.identifier for v in shading.bl_rna.properties[prop].enum_items}
    setattr(shading, prop, value)
assert any(light.name == "paint.sl" for light in bpy.context.preferences.studio_lights)
shading.studio_light = "paint.sl"
shading.background_color = (.26, .26, .26)
shading.show_shadows = False
shading.show_cavity = False
shading.show_specular_highlight = False
shading.show_object_outline = False
scene.objects["Review_Ground"].hide_render = True

settings = scene.render.image_settings
assert "PNG" in {v.identifier for v in settings.bl_rna.properties["file_format"].enum_items}
settings.file_format = "PNG"
scene.render.resolution_x = 1000
scene.render.resolution_y = 1200
scene.render.resolution_percentage = 100
free_angles = (("OBLIQUE_FRONT", -42, 20), ("OBLIQUE_REAR", -140, 18),
               ("HIGH_REAR", 150, 38), ("LOW_FRONT", 35, -6),
               ("HIGH_SIDE", 75, 30))
studio = bpy.data.collections["REVIEW | Neutral studio and orthographic cameras"]
assert "PERSP" in {v.identifier for v in bpy.types.Camera.bl_rna.properties["type"].enum_items}
for name, azimuth, elevation in free_angles:
    camera = scene.objects.get("Review_" + name)
    if camera is None:
        data = bpy.data.cameras.new("Review_" + name)
        camera = bpy.data.objects.new("Review_" + name, data)
        studio.objects.link(camera)
    camera.data.type = "PERSP"
    camera.data.lens = 85
    a, e, distance = math.radians(azimuth), math.radians(elevation), 14
    target = Vector((0, 0, 2.5))
    camera.location = target + Vector((distance * math.sin(a) * math.cos(e),
                                       -distance * math.cos(a) * math.cos(e),
                                       distance * math.sin(e)))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera["asset_role"] = "review_studio"
views = [("FRONT", "front"), ("SIDE", "side"), ("BACK", "back"),
         ("THREE_QUARTER", "three_quarter")]
views.extend((name, name.lower()) for name, _, _ in free_angles)
for camera, stem in views:
    scene.camera = scene.objects["Review_" + camera]
    scene.render.filepath = str(ASSET / "renders" / ("Usu_" + stem + ".png"))
    ground_visibility = [(o, o.hide_render) for o in studio.objects if o.type == "MESH"]
    try:
        if camera == "LOW_FRONT":
            for ground, _ in ground_visibility:
                ground.hide_render = True
        bpy.ops.render.render(write_still=True)
    finally:
        for ground, hidden in ground_visibility:
            ground.hide_render = hidden
scene.camera = scene.objects["Review_THREE_QUARTER"]
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET / "Usu_Static_Approval.blend"), compress=True)
print(json.dumps(report, indent=2))
