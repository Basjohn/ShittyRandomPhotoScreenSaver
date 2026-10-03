"""Bind controlled weights in the separate rig copy. Never alter mesh data."""
import bpy
import json
import hashlib
from pathlib import Path
from mathutils import Matrix

ASSET = Path(r'F:/Programming/Apps/ShittyRandomPhotoScreenSaver/assets/usu')
assert Path(bpy.data.filepath).resolve() == (ASSET/'Usu_Rig_Validation.blend').resolve()
rig=bpy.data.objects['Usu_Rig']
weights=json.loads((ASSET/'source/manual_weights.json').read_text())
if rig.animation_data:rig.animation_data.action=None
for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
for obj in list(bpy.context.scene.objects):
 if obj.get('asset_role') not in {'static_character','surface_face_detail'}:continue
 fingerprint=hashlib.sha256(json.dumps([[list(v.co) for v in obj.data.vertices],
                                      [list(p.vertices) for p in obj.data.polygons]],separators=(',',':')).encode()).hexdigest()
 assert fingerprint==weights['mesh_fingerprints'][obj.name],('Approved topology/coordinates differ',obj.name)
 data=weights.get(obj.name,{'HEAD':[1.0]*len(obj.data.vertices)})
 totals=[sum(values[i] for values in data.values()) for i in range(len(obj.data.vertices))]
 assert min(totals)>.99999 and max(totals)<1.00001,(obj.name,min(totals),max(totals))
 for group in list(obj.vertex_groups):obj.vertex_groups.remove(group)
 for name,values in data.items():
  assert name in rig.data.bones
  group=obj.vertex_groups.new(name=name)
  for i,w in enumerate(values):
   if w>0:group.add([i],w/totals[i],'REPLACE')
 for mod in list(obj.modifiers):
  if mod.type=='ARMATURE':obj.modifiers.remove(mod)
 mod=obj.modifiers.new('Usu controlled skin','ARMATURE')
 mod.object=rig;mod.use_vertex_groups=True;mod.use_bone_envelopes=False
 mod.use_deform_preserve_volume=True
 obj.modifiers.move(len(obj.modifiers)-1,0)
 matrix=obj.matrix_world.copy();obj.parent=rig;obj.matrix_parent_inverse=rig.matrix_world.inverted();obj.matrix_world=matrix
 obj['rig_binding']='Manual regional weights; armature before retained subdivision; preserve volume'
bpy.context.view_layer.update()
print('Bound fourteen approved surfaces; no geometry edits or applied modifiers.')
