"""Plain-shaded rig proofs, executed through Blender MCP in the rig copy only.

Definitions do not render or save automatically. Call audit_rest(), pose(),
render_views(), and make_actions() explicitly. Tests are deliberately rough.
"""
import bpy, json, math, hashlib
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix
from mathutils.bvhtree import BVHTree

ASSET=Path(r'F:/Programming/Apps/ShittyRandomPhotoScreenSaver/assets/usu')
OUTPUT=ASSET/'renders/rig_validation'
OUTPUT.mkdir(parents=True,exist_ok=True)
assert Path(bpy.data.filepath).resolve()==(ASSET/'Usu_Rig_Validation.blend').resolve()
scene=bpy.context.scene
rig=bpy.data.objects['Usu_Rig']
character=[o for o in scene.objects if o.get('asset_role') in {'static_character','surface_face_detail'}]
VIEWS=['FRONT','SIDE','BACK','THREE_QUARTER','HIGH_REAR','HIGH_SIDE']

def reset():
 if rig.animation_data:rig.animation_data.action=None
 for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
 bpy.context.view_layer.update()

def rotate(name,degrees,axis=(1,0,0)):
 pb=rig.pose.bones[name]
 local=pb.bone.matrix_local.to_3x3().inverted()@Vector(axis)
 pb.rotation_euler=Quaternion(local,math.radians(degrees)).to_euler('XYZ')

def translate(name,vector):
 pb=rig.pose.bones[name]
 pb.location=pb.bone.matrix_local.to_3x3().inverted()@Vector(vector)

def pose(name):
 reset()
 if name=='head_tilt':rotate('HEAD',12,(0,1,0))
 elif name=='head_bob':translate('HEAD',(0,0,.10))
 elif name=='arm_swing':rotate('ARM_L',25);rotate('ARM_R',-25)
 elif name=='leg_left':rotate('LEG_L',25)
 elif name=='leg_right':rotate('LEG_R',-25)
 elif name=='ears_backward':
  for suffix in ['L','R']:rotate('EAR_'+suffix+'_MID',20);rotate('EAR_'+suffix+'_TIP',12)
 elif name=='ear_mid_left':rotate('EAR_L_MID',22)
 elif name=='ear_tip_right':rotate('EAR_R_TIP',25)
 elif name=='body_lean':rotate('BODY',12)
 elif name=='collapsed':
  translate('ROOT',(0,.65,.151));translate('BODY_ROOT',(0,0,-.65));rotate('BODY',45);rotate('HEAD',20)
  rotate('LEG_L',-80);rotate('LEG_R',-80)
  rotate('ARM_L',-32);rotate('ARM_R',-32)
  for suffix in ['L','R']:rotate('EAR_'+suffix+'_MID',-15);rotate('EAR_'+suffix+'_TIP',-10)
 elif name!='neutral':raise ValueError(name)
 bpy.context.view_layer.update()

def plain_shading(width=600,height=720):
 scene.render.engine='BLENDER_WORKBENCH'
 sh=scene.display.shading
 sh.light='STUDIO';sh.studio_light='paint.sl';sh.color_type='MATERIAL'
 sh.background_type='VIEWPORT';sh.background_color=(.26,.26,.26)
 sh.show_shadows=False;sh.show_cavity=False;sh.show_specular_highlight=False;sh.show_object_outline=False
 scene.objects['Review_Ground'].hide_render=True
 scene.render.image_settings.file_format='PNG'
 scene.render.resolution_x=width;scene.render.resolution_y=height;scene.render.resolution_percentage=100

def render_views(label,views=VIEWS):
 plain_shading()
 directory=OUTPUT/label;directory.mkdir(parents=True,exist_ok=True)
 for name in views:
  scene.camera=scene.objects['Review_'+name]
  scene.render.filepath=str(directory/(name.lower()+'.png'))
  bpy.ops.render.render(write_still=True)
 print('Rendered',label,list(views))

def audit_rest():
 reset()
 baseline=json.loads((ASSET.parent.parent/'tmp/Usu_Rig_Validation/approved_geometry.json').read_text())
 report={'approved_static_sha256':hashlib.sha256((ASSET/'Usu_Static_Approval.blend').read_bytes()).hexdigest(),'geometry_changes':False,'surfaces':{},'hierarchy':[]}
 for name,old in baseline.items():
  obj=scene.objects[name]
  verts=[list(v.co) for v in obj.data.vertices]
  faces=[list(p.vertices) for p in obj.data.polygons]
  assert verts==old['verts'] and faces==old['faces'],name
  assert [p.material_index for p in obj.data.polygons]==old['material_indices'],name
  assert [list(row) for row in obj.matrix_world]==old['matrix_world'],name
  ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
  assert len(mesh.vertices)==len(old['eval_verts']) and [list(p.vertices) for p in mesh.polygons]==old['eval_faces'],name
  deviation=max((v.co-Vector(old['eval_verts'][i])).length for i,v in enumerate(mesh.vertices))
  # Float32 armature matrix arithmetic permits subpixel numerical drift.
  ev.to_mesh_clear();assert deviation<1e-5,(name,deviation)
  sums=[sum(g.weight for g in v.groups) for v in obj.data.vertices]
  assert min(sums)>.99999 and max(sums)<1.00001
  report['surfaces'][name]={'cage_geometry_identical':True,'evaluated_rest_max_deviation':deviation,'weight_sum_range':[min(sums),max(sums)]}
 for bone in rig.data.bones:report['hierarchy'].append({'bone':bone.name,'parent':bone.parent.name if bone.parent else None,'deform':bone.use_deform,'head':list(bone.head_local),'tail':list(bone.tail_local)})
 assert len(rig.data.bones)==14 and not rig.data.bones['ROOT'].use_deform
 assert not rig.constraints and not any(pb.constraints for pb in rig.pose.bones)
 assert not (rig.animation_data and rig.animation_data.drivers)
 report['transforms_or_modifiers_applied']=False
 (ASSET/'source/rig_validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Rest mesh verified',len(baseline),'surfaces; max evaluated deviation',max(o['evaluated_rest_max_deviation'] for o in report['surfaces'].values()))
 return report

def cage_metrics(label):
 """Evaluate armature without subdivision; test folds and protected regions."""
 report={}
 for obj in character:
  if obj.get('asset_role')!='static_character':continue
  mods=[m for m in obj.modifiers if m.type=='SUBSURF'];enabled=[m.show_viewport for m in mods]
  try:
   for m in mods:m.show_viewport=False
   bpy.context.view_layer.update()
   ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
   points=[v.co.copy() for v in mesh.vertices];faces=[tuple(p.vertices) for p in mesh.polygons]
   tree=BVHTree.FromPolygons(points,faces)
   crossings=[(a,b) for a,b in tree.overlap(tree) if a<b and not set(faces[a]).intersection(faces[b])]
   min_area=min(p.area for p in mesh.polygons)
   data={'nonadjacent_cage_self_intersections':len(crossings),'minimum_face_area':min_area}
   if obj.name=='Usu_Head_And_Ears':
    head_matrix=rig.pose.bones['HEAD'].matrix@rig.data.bones['HEAD'].matrix_local.inverted()
    protected=[i for i,v in enumerate(obj.data.vertices) if v.co.z>=3.42 or v.co.y<=.08 or abs(v.co.x)<.52]
    data['rigid_skull_max_deviation']=max((points[i]-head_matrix@obj.data.vertices[i].co).length for i in protected)
    if label.startswith('ear'):
     data['upper_attachment_max_displacement']=max((points[i]-obj.data.vertices[i].co).length for i,v in enumerate(obj.data.vertices) if v.co.z>=3.42)
   report[obj.name]=data
   ev.to_mesh_clear()
  finally:
   for m,value in zip(mods,enabled):m.show_viewport=value
   bpy.context.view_layer.update()
 path=OUTPUT/'pose_metrics.json'
 results=json.loads(path.read_text()) if path.exists() else {}
 results[label]=report;path.write_text(json.dumps(results,indent=2)+'\n')
 print(label,json.dumps(report))
 return report

def key_all(frame):
 for pb in rig.pose.bones:
  pb.keyframe_insert(data_path='rotation_euler',frame=frame,group=pb.name)
  pb.keyframe_insert(data_path='location',frame=frame,group=pb.name)

def new_action(name,last):
 reset();rig.animation_data_create()
 old=bpy.data.actions.get(name)
 if old:bpy.data.actions.remove(old)
 action=bpy.data.actions.new(name);action.use_fake_user=True
 action['scope']='Rough rig validation only; not approved final animation'
 action.use_frame_range=True;action.frame_start=1;action.frame_end=last
 rig.animation_data.action=action
 return action

def motion(kind,frame):
 """Deterministic simple FK test. Keep ear ROOT channels neutral."""
 for pb in rig.pose.bones:pb.matrix_basis=Matrix.Identity(4)
 if kind=='rest':
  translate('ROOT',(0,.65,.151));translate('BODY_ROOT',(0,0,-.65));rotate('BODY',45);rotate('HEAD',20+2*math.sin((frame-1)*math.tau/48))
  rotate('LEG_L',-80);rotate('LEG_R',-80);rotate('ARM_L',-32);rotate('ARM_R',-32)
  for s in ['L','R']:rotate('EAR_'+s+'_MID',-15);rotate('EAR_'+s+'_TIP',-10)
 elif kind in {'walk','run'}:
  run=kind=='run';period=24 if run else 48;t=(frame-1)*math.tau/period
  leg=32 if run else 19;arm=30 if run else 16
  bob=(.09 if run else .035)*(1-math.cos(2*t))
  translate('BODY_ROOT',(0,0,bob));rotate('BODY',9 if run else 3)
  rotate('HEAD',3*math.sin(t+.5));translate('HEAD',(0,0,.015*math.sin(2*t+.3)))
  for side,s in [(1,'L'),(-1,'R')]:
   rotate('LEG_'+s,side*leg*math.sin(t));rotate('ARM_'+s,-side*arm*math.sin(t))
   rotate('EAR_'+s+'_MID',(6 if run else 2)+(9 if run else 4)*math.sin(2*t-.8+side*.12))
   rotate('EAR_'+s+'_TIP',(13 if run else 6)*math.sin(2*t-1.45+side*.15))
 elif kind=='ears':
  t=(frame-1)/47
  # One authored impulse followed by a decaying overshoot and settle.
  wave=math.sin(t*math.tau*2)*math.exp(-t*2.2)
  rotate('HEAD',4*wave)
  for s in ['L','R']:
   rotate('EAR_'+s+'_MID',-20*wave)
   rotate('EAR_'+s+'_TIP',-27*math.sin(t*math.tau*2-.5)*math.exp(-t*2.2))
 else:raise ValueError(kind)
 bpy.context.view_layer.update()

def make_actions():
 scene.render.fps=24
 action=new_action('Usu_TEST_Poses',100)
 labels=['neutral','head_tilt','head_bob','arm_swing','leg_left','leg_right','ears_backward','ear_mid_left','ear_tip_right','body_lean','collapsed']
 for index,label in enumerate(labels):
  # pose() resets action; restore it after assigning each test.
  pose(label);rig.animation_data.action=action;frame=1+index*9;key_all(frame)
  action.pose_markers.new(label).frame=frame
 for kind,name,last in [('rest','Usu_TEST_RestCollapsed',49),('walk','Usu_TEST_Walk',49),('run','Usu_TEST_Run',49),('ears','Usu_TEST_EarFollowThrough',48)]:
  action=new_action(name,last)
  for frame in range(1,last+1):motion(kind,frame);key_all(frame)
 reset();scene.frame_start=1;scene.frame_end=49;scene.frame_set(1)
 print('Created rough test actions:',[a.name for a in bpy.data.actions])

def render_motion(kind,frames,view='THREE_QUARTER'):
 names={'rest':'Usu_TEST_RestCollapsed','walk':'Usu_TEST_Walk','run':'Usu_TEST_Run','ears':'Usu_TEST_EarFollowThrough'}
 rig.animation_data.action=bpy.data.actions[names[kind]]
 plain_shading(400,480);scene.camera=scene.objects['Review_'+view]
 directory=OUTPUT/'motion_frames'/kind/view.lower();directory.mkdir(parents=True,exist_ok=True)
 for frame in frames:
  scene.frame_set(frame);scene.render.filepath=str(directory/(f'{frame:03d}.png'))
  bpy.ops.render.render(write_still=True)
 print('Rendered',kind,view,len(frames),'frames')

def save_neutral():
 reset();scene.frame_set(1);scene.camera=scene.objects['Review_THREE_QUARTER'];plain_shading(1000,1200)
 scene.name='Usu_RIG_Validation'
 for o in bpy.context.selected_objects:o.select_set(False)
 rig.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/'Usu_Rig_Validation.blend'),compress=True)

def audit_subdivision():
 """Inspect visible smooth surfaces at every required pose and motion peaks."""
 results={}
 def inspect(label):
  entry={}
  for obj in character:
   if obj.get('asset_role')!='static_character':continue
   ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
   vs=[v.co.copy() for v in mesh.vertices];fs=[tuple(p.vertices) for p in mesh.polygons]
   tree=BVHTree.FromPolygons(vs,fs)
   crossings=sum(a<b and not set(fs[a]).intersection(fs[b]) for a,b in tree.overlap(tree))
   minimum=min(p.area for p in mesh.polygons)
   entry[obj.name]={'nonadjacent_subdivision_self_intersections':crossings,'minimum_face_area':minimum}
   ev.to_mesh_clear()
  results[label]=entry
 for label in ['neutral','head_tilt','head_bob','arm_swing','leg_left','leg_right','ears_backward','ear_mid_left','ear_tip_right','body_lean','collapsed']:
  pose(label);inspect(label)
 for kind,name in [('rest','Usu_TEST_RestCollapsed'),('walk','Usu_TEST_Walk'),('run','Usu_TEST_Run'),('ears','Usu_TEST_EarFollowThrough')]:
  rig.animation_data.action=bpy.data.actions[name]
  for frame in [3,7,13,19,25,37,47]:
   scene.frame_set(frame);inspect(kind+'_'+str(frame))
 failures={name:entry for name,entry in results.items() if any(v['nonadjacent_subdivision_self_intersections'] or v['minimum_face_area']<1e-12 for v in entry.values())}
 (OUTPUT/'subdivision_metrics.json').write_text(json.dumps(results,indent=2)+'\n')
 reset();scene.frame_set(1)
 print('Smooth-surface audits:',len(results),'states. Failures:',json.dumps(failures))
 return failures

def audit_isolation():
 reset()
 for obj in character:
  names={g.index:g.name for g in obj.vertex_groups}
  if obj.get('asset_role')=='surface_face_detail':
   assert all(len(v.groups)==1 and names[v.groups[0].group]=='HEAD' and v.groups[0].weight==1 for v in obj.data.vertices)
  for v in obj.data.vertices:
   assert not any(names[g.group]=='ROOT' for g in v.groups)
   assert not any((v.co.x<0 and names[g.group] in {'EAR_L_ROOT','EAR_L_MID','EAR_L_TIP','ARM_L'}) or
                  (v.co.x>0 and names[g.group] in {'EAR_R_ROOT','EAR_R_MID','EAR_R_TIP','ARM_R'}) for g in v.groups)
 obj=scene.objects['Usu_Head_And_Ears'];sub=next(m for m in obj.modifiers if m.type=='SUBSURF')
 sub.show_viewport=False;bpy.context.view_layer.update()
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 neutral=[v.co.copy() for v in mesh.vertices];ev.to_mesh_clear()
 pose('ear_mid_left')
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
 opposite=max((mesh.vertices[i].co-neutral[i]).length for i,v in enumerate(obj.data.vertices) if v.co.x<=0)
 upper=max((mesh.vertices[i].co-neutral[i]).length for i,v in enumerate(obj.data.vertices) if v.co.z>=3.42)
 ev.to_mesh_clear();sub.show_viewport=True;reset()
 translate('ROOT',(.1,.1,.2));rotate('ROOT',18,(0,0,1));bpy.context.view_layer.update()
 matrix=rig.pose.bones['ROOT'].matrix@rig.data.bones['ROOT'].matrix_local.inverted()
 baseline=json.loads((ASSET.parent.parent/'tmp/Usu_Rig_Validation/approved_geometry.json').read_text())
 error=0
 for obj in character:
  ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
  error=max(error,max((v.co-matrix@Vector(baseline[obj.name]['eval_verts'][i])).length for i,v in enumerate(mesh.vertices)))
  ev.to_mesh_clear()
 assert opposite<1e-6 and upper<1e-6 and error<1e-5,(opposite,upper,error)
 report={'facial_details_HEAD_only':True,'ROOT_non_deforming':True,'opposite_side_weight_leakage':0,
         'opposite_ear_displacement_with_left_MID':opposite,'upper_attachment_displacement_with_left_MID':upper,
         'master_placement_max_evaluated_error':error}
 (OUTPUT/'weight_isolation.json').write_text(json.dumps(report,indent=2)+'\n')
 reset();print(json.dumps(report))
 return report
