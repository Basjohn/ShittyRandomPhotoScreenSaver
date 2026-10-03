"""Create the small Usu FK rig in the separate rig-validation .blend.

Run through Blender MCP. Geometry and approved static source are never edited.
Weights are supplied separately by bind_usu.py after the armature is created.
"""
import bpy
from pathlib import Path
from mathutils import Vector

ASSET = Path(r'F:/Programming/Apps/ShittyRandomPhotoScreenSaver/assets/usu')
assert Path(bpy.data.filepath).resolve() == (ASSET/'Usu_Rig_Validation.blend').resolve()
assert not any(o.type == 'ARMATURE' for o in bpy.context.scene.objects)
assert all(tuple(o.scale)==(1,1,1) and tuple(o.rotation_euler)==(0,0,0)
           for o in bpy.context.scene.objects if o.get('asset_role') in {'static_character','surface_face_detail'})

SPECS = [
 ('ROOT',None,(0,0,0),(0,0,.55),False),
 ('BODY_ROOT','ROOT',(0,.08,1.05),(0,.08,1.65),True),
 ('BODY','BODY_ROOT',(0,.08,1.65),(0,.08,2.95),True),
 ('HEAD','BODY',(0,.08,2.95),(0,.08,4.35),True),
]
for side,suffix in [(1,'L'),(-1,'R')]:
 SPECS += [
  ('ARM_'+suffix,'BODY',(side*.48,.17,2.62),(side*.83,.12,1.48),True),
  ('LEG_'+suffix,'BODY_ROOT',(side*.46,.11,.92),(side*.46,.11,.13),True),
  ('EAR_'+suffix+'_ROOT','HEAD',(side*.82,.57,4.40),(side*.95,.68,2.90),True),
  ('EAR_'+suffix+'_MID','EAR_'+suffix+'_ROOT',(side*.95,.68,2.90),(side*1.02,.72,2.40),True),
  ('EAR_'+suffix+'_TIP','EAR_'+suffix+'_MID',(side*1.02,.72,2.40),(side*1.04,.72,2.10),True),
 ]

collection=bpy.data.collections.new('USU | Simple FK rig')
bpy.context.scene.collection.children.link(collection)
data=bpy.data.armatures.new('Usu simple 14-bone FK')
rig=bpy.data.objects.new('Usu_Rig',data)
collection.objects.link(rig)
for o in bpy.context.selected_objects:o.select_set(False)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.object.mode_set(mode='EDIT')
for name,parent,head,tail,deform in SPECS:
 bone=data.edit_bones.new(name);bone.head=head;bone.tail=tail
 bone.use_deform=deform
 bone.align_roll(Vector((0,-1,0)))
 if parent:
  bone.parent=data.edit_bones[parent]
  bone.use_connect=name.endswith('_MID') or name.endswith('_TIP')
bpy.ops.object.mode_set(mode='OBJECT')
data.display_type='STICK'
rig.show_in_front=True
groups={name:data.collections.new(name) for name in ['Placement','Body and head','Limbs','Ears']}
for bone in data.bones:
 bone.inherit_scale='NONE'
 group='Placement' if bone.name=='ROOT' else 'Ears' if bone.name.startswith('EAR_') else 'Limbs' if bone.name.startswith(('ARM_','LEG_')) else 'Body and head'
 groups[group].assign(bone)
 pb=rig.pose.bones[bone.name];pb.rotation_mode='XYZ';pb.lock_scale=(True,True,True)
 pb.lock_location=(True,True,True)
 if bone.name in {'ROOT','BODY_ROOT','HEAD'}:pb.lock_location=(False,False,False)
 if bone.name.endswith('_ROOT') and bone.name.startswith('EAR_'):
  bone['usage']='Keep nearly neutral. Attachment follows HEAD; animate MID and TIP for normal bounce.'
rig['asset_role']='usu_rig'
rig['rig_scope']='Simple FK; validation poses and rough tests only; no polished loops or runtime export'
rig['approved_source']='Usu_Static_Approval.blend'
rig['geometry_changes']='None; no transforms or subdivision modifiers applied'
rig['controls']='ROOT placement; BODY_ROOT lift/pelvis; BODY lean; HEAD tilt/bob; simple arm/leg swing; ear MID/TIP follow-through'
print('Created',len(data.bones),'bones')
print([(b.name,b.parent.name if b.parent else None,b.use_deform) for b in data.bones])
