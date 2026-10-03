"""Read the untouched static source through Blender MCP; save audit data only.

Open Usu_Static_Approval.blend before running. This never saves that .blend.
The disposable snapshot is input for weight regeneration/rest comparison.
"""
import bpy,json,hashlib
from pathlib import Path
ASSET=Path(r'F:/Programming/Apps/ShittyRandomPhotoScreenSaver/assets/usu')
assert Path(bpy.data.filepath).resolve()==(ASSET/'Usu_Static_Approval.blend').resolve()
assert not any(o.type=='ARMATURE' for o in bpy.context.scene.objects)
output=ASSET.parent.parent/'tmp/Usu_Rig_Validation';output.mkdir(parents=True,exist_ok=True)
data={}
for obj in bpy.context.scene.objects:
 if obj.get('asset_role') not in {'static_character','surface_face_detail'}:continue
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 data[obj.name]={'verts':[list(v.co) for v in obj.data.vertices],
                 'faces':[list(p.vertices) for p in obj.data.polygons],
                 'material_indices':[p.material_index for p in obj.data.polygons],
                 'eval_verts':[list(v.co) for v in mesh.vertices],
                 'eval_faces':[list(p.vertices) for p in mesh.polygons],
                 'matrix_world':[list(row) for row in obj.matrix_world],
                 'modifiers':[[m.name,m.type,getattr(m,'levels',None),getattr(m,'render_levels',None)] for m in obj.modifiers]}
 ev.to_mesh_clear()
(output/'approved_geometry.json').write_text(json.dumps(data))
(output/'static_sha256.txt').write_text(hashlib.sha256((ASSET/'Usu_Static_Approval.blend').read_bytes()).hexdigest()+'\n')
print('Read-only snapshot of',len(data),'approved surfaces. Static blend not saved.')
