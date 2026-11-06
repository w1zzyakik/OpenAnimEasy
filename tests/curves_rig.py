import os
import sys
import traceback

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import open_anim_easy as addon
from open_anim_easy import core

addon.register()

PASS, FAIL = [], []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print("PASS", name)
    else:
        FAIL.append((name, detail))
        print("FAIL", name, detail)


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    ob.location.x = 0
    ob.keyframe_insert("location", frame=1)
    ob.location.x = 10
    ob.keyframe_insert("location", frame=10)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.context.scene.frame_set(1)
    return ob


def fcs(ob):
    action = core.action_of(ob)
    return core.action_fcurves(action, core.slot_of(ob, action))


def run(name, func):
    try:
        func()
    except Exception:
        FAIL.append((name, traceback.format_exc()))
        print("FAIL", name)
        traceback.print_exc()


def test_delete_crop():
    ob = scene()
    fc = fcs(ob)[0]
    bpy.context.scene.frame_set(5)
    bpy.ops.openanim.key_type(type="BREAKDOWN")
    fc = next(f for f in fcs(ob) if f.data_path == "location" and f.array_index == 0)
    keys = {kp.co.x: kp for kp in fc.keyframe_points}
    check("key_type_insert", 5 in keys and keys[5].type == "BREAKDOWN", str(list(keys)))
    scale_fc = next((f for f in fcs(ob) if f.data_path == "scale"), None)
    check("key_type_scale_default", scale_fc is not None and abs(scale_fc.keyframe_points[0].co.y - 1.0) < 1e-6, str(scale_fc.keyframe_points[0].co.y if scale_fc else None))
    bpy.ops.openanim.delete_keys(mode="CURRENT")
    check("delete_current", 5 not in [kp.co.x for kp in fc.keyframe_points])
    bpy.context.scene.frame_set(1)
    bpy.ops.openanim.delete_keys(mode="CURRENT")
    check("delete_current_2", len(fc.keyframe_points) == 1)
    bpy.ops.openanim.crop_animation()
    check("crop", len(fc.keyframe_points) == 1)


def test_preview():
    ob = scene()
    for fc in fcs(ob):
        for kp in fc.keyframe_points:
            kp.select_control_point = True
    bpy.ops.openanim.frame_view(action="PREVIEW_SET")
    check("preview_set", bpy.context.scene.use_preview_range and bpy.context.scene.frame_preview_start == 1 and bpy.context.scene.frame_preview_end == 10)
    bpy.ops.openanim.frame_view(action="PREVIEW_CLEAR")
    check("preview_clear", not bpy.context.scene.use_preview_range)


def test_handle_blend():
    ob = scene()
    fc = next(f for f in fcs(ob) if f.data_path == "location" and f.array_index == 0)
    kp = fc.keyframe_points.insert(5, 0.0)
    for key in fc.keyframe_points:
        key.select_control_point = True
    bpy.ops.openanim.handle_type(type="VECTOR")
    check("handle", all(k.handle_left_type == "VECTOR" for k in fc.keyframe_points))
    kp = fc.keyframe_points[1]
    kp.select_control_point = True
    for key in fc.keyframe_points:
        if key != kp:
            key.select_control_point = False
    bpy.ops.openanim.blend(mode="NEIGHBOR", factor=0.5)
    check("blend_neighbor", abs(fc.keyframe_points[1].co.y - 2.5) < 1e-4, str(fc.keyframe_points[1].co.y))
    bpy.ops.openanim.blend(mode="PUSH", factor=0.5)
    check("push", abs(fc.keyframe_points[1].co.y - 2.0) < 1e-4, str(fc.keyframe_points[1].co.y))
    bpy.ops.openanim.blend(mode="SMOOTH")
    check("smooth", abs(fc.keyframe_points[1].co.y - 4.0) < 1e-3, str(fc.keyframe_points[1].co.y))
    bpy.ops.openanim.blend(mode="EASE_IN")
    check("ease", fc.keyframe_points[1].easing == "EASE_IN" and fc.keyframe_points[1].interpolation == "SINE")


def test_values():
    ob = scene()
    fc = next(f for f in fcs(ob) if f.data_path == "location" and f.array_index == 0)
    bpy.context.scene.frame_set(5)
    expected = fc.evaluate(5)
    for kp in fc.keyframe_points:
        kp.select_control_point = True
    bpy.ops.openanim.value_op(mode="CURRENT")
    check("current_value", abs(fc.keyframe_points[0].co.y - expected) < 1e-3 and abs(fc.keyframe_points[1].co.y - expected) < 1e-3, "%s vs %s" % ([k.co.y for k in fc.keyframe_points], expected))
    bpy.ops.openanim.value_op(mode="ZERO")
    check("zero", all(abs(kp.co.y) < 1e-9 for kp in fc.keyframe_points))


def test_clean_static_euler():
    ob = scene()
    ob.scale = (1, 1, 1)
    ob.keyframe_insert("scale", frame=1)
    ob.keyframe_insert("scale", frame=10)
    bpy.ops.openanim.clean_curves(mode="STATIC")
    check("clean_static", not any(f.data_path == "scale" for f in fcs(ob)))
    # baked
    ob2 = scene()
    fc = next(f for f in fcs(ob2) if f.data_path == "location" and f.array_index == 0)
    fc.keyframe_points.clear()
    for frame in range(1, 11):
        fc.keyframe_points.insert(frame, frame * 1.0)
    fc.update()
    bpy.ops.openanim.clean_curves(mode="BAKED")
    check("clean_baked", len(fc.keyframe_points) == 2, str([k.co.x for k in fc.keyframe_points]))
    # euler
    ob3 = scene()
    ob3.rotation_mode = "XYZ"
    ob3.rotation_euler = (0, 0, 0)
    ob3.keyframe_insert("rotation_euler", frame=1)
    ob3.rotation_euler = (0, 0, 6.0)
    ob3.keyframe_insert("rotation_euler", frame=10)
    bpy.ops.openanim.clean_curves(mode="EULER")
    efc = next(f for f in fcs(ob3) if f.data_path == "rotation_euler" and f.array_index == 2)
    values = [kp.co.y for kp in efc.keyframe_points]
    check("euler_filter", abs(values[1] - values[0]) < 3.1416, str(values))


def test_copy_flip():
    ob = scene()
    fc = next(f for f in fcs(ob) if f.data_path == "location" and f.array_index == 0)
    for kp in fc.keyframe_points:
        kp.select_control_point = True
    bpy.ops.openanim.copy_keys()
    bpy.context.scene.frame_set(20)
    bpy.ops.openanim.paste_keys(flipped=True)
    values = {kp.co.x: kp.co.y for kp in fc.keyframe_points}
    check("paste_flipped", abs(values[20] - 0.0) < 1e-6 and abs(values[29] + 10.0) < 1e-6, str(values))


def test_bake_curves():
    ob = scene()
    fc = next(f for f in fcs(ob) if f.data_path == "location" and f.array_index == 0)
    bpy.ops.openanim.bake(mode="CURVES", step=1)
    check("bake_curves", len(fc.keyframe_points) == 10, str(len(fc.keyframe_points)))
    # pattern
    ob = scene()
    fc = next(f for f in fcs(ob) if f.data_path == "location" and f.array_index == 0)
    for kp in fc.keyframe_points:
        kp.select_control_point = True
    bpy.ops.openanim.bake(mode="PATTERN")
    check("bake_pattern", len(fc.keyframe_points) == 2, str(len(fc.keyframe_points)))


def test_select_cycle():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    bpy.ops.object.mode_set(mode="POSE")
    pb = arm.pose.bones[0]
    pb.select = True
    bpy.ops.openanim.select_rig(mode="OPPOSITE")
    check("select_opposite", pb.select is False)
    pb.select = True
    active = core.active_bone(bpy.context)
    check("active_bone", active is not None, str(active))
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.openanim.gizmo_size(direction="UP", step=5)
    check("gizmo", bpy.context.preferences.view.gizmo_size > 10)
    before = bpy.context.scene.tool_settings.transform_pivot_point
    bpy.ops.openanim.cycle(what="PIVOT")
    check("pivot", bpy.context.scene.tool_settings.transform_pivot_point != before)
    before = bpy.context.scene.transform_orientation_slots[0].type
    bpy.ops.openanim.cycle(what="ORIENTATION")
    check("orientation", bpy.context.scene.transform_orientation_slots[0].type != before)


def test_childof_toggle_bake():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    parent = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))
    child = bpy.context.object
    child.location.x = 2
    child.keyframe_insert("location", frame=1)
    child.location.x = 3
    child.keyframe_insert("location", frame=10)
    parent.select_set(True)
    child.select_set(True)
    bpy.context.view_layer.objects.active = child
    bpy.ops.openanim.childof(action="CREATE")
    con = next(c for c in child.constraints if c.type == "CHILD_OF")
    bpy.ops.openanim.childof(action="TOGGLE")
    check("childof_toggle", con.mute is True)
    bpy.ops.openanim.childof(action="TOGGLE")
    check("childof_toggle_back", con.mute is False)
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 10
    bpy.ops.openanim.childof(action="BAKE")
    check("childof_bake", not [c for c in child.constraints if c.type == "CHILD_OF"])


def test_space():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    parent = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))
    child = bpy.context.object
    child.parent = parent
    child.location = (1, 0, 0)
    child.keyframe_insert("location", frame=1)
    child.location = (3, 0, 0)
    child.keyframe_insert("location", frame=10)
    bpy.context.view_layer.objects.active = child
    bpy.ops.object.select_all(action="DESELECT")
    child.select_set(True)
    bpy.context.scene.frame_set(5)
    before = child.matrix_world.translation.copy()
    bpy.ops.openanim.space_convert(mode="TO_WORLD")
    bpy.context.scene.frame_set(5)
    after = child.matrix_world.translation.copy()
    check("space_to_world", child.parent is None and (before - after).length < 1e-4, "%s %s" % (before, after))
    bpy.context.scene.frame_set(1)
    bpy.ops.openanim.space_convert(mode="TO_LOCAL")
    check("space_to_local", any(f.data_path == "location" for f in fcs(child)))


def test_motion_paths():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    ob.keyframe_insert("location", frame=1)
    ob.location.x = 5
    ob.keyframe_insert("location", frame=10)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.openanim.motion_paths(action="SHOW")
    check("motion_path_show", ob.motion_path is not None, str(ob.motion_path))
    bpy.ops.openanim.motion_paths(action="CLEAR")
    check("motion_path_clear", ob.motion_path is None)


def test_editable_motion_path():
    from mathutils import Vector
    from open_anim_easy import curves

    ob = scene()
    line, points = curves.motion_path_points(bpy.context, ob, None)
    check(
        "edit_path_line",
        len(line) == 10 and line[0][0] == 1 and line[-1][0] == 10,
        str(len(line)),
    )
    check(
        "edit_path_points",
        [frame for frame, _pos in points] == [1, 10],
        str([frame for frame, _pos in points]),
    )
    state = curves.motion_capture_state(bpy.context, ob, None, 10)
    ok = curves.motion_apply_point(
        bpy.context, ob, None, 10, Vector((0.0, 5.0, 0.0))
    )
    fc_x = next(
        f for f in fcs(ob) if f.data_path == "location" and f.array_index == 0
    )
    fc_y = next(
        f for f in fcs(ob) if f.data_path == "location" and f.array_index == 1
    )
    x_at_10 = next(kp.co.y for kp in fc_x.keyframe_points if kp.co.x == 10)
    y_at_10 = next(kp.co.y for kp in fc_y.keyframe_points if kp.co.x == 10)
    check(
        "edit_path_apply",
        ok and abs(x_at_10) < 1e-4 and abs(y_at_10 - 5.0) < 1e-4,
        "%s %s" % (x_at_10, y_at_10),
    )
    bpy.context.scene.frame_set(10)
    check(
        "edit_path_world",
        (ob.matrix_world.translation - Vector((0.0, 5.0, 0.0))).length < 1e-4,
        str(ob.matrix_world.translation),
    )
    curves.motion_restore_state(bpy.context, ob, None, 10, state)
    bpy.context.scene.frame_set(10)
    check(
        "edit_path_restore",
        abs(ob.matrix_world.translation.x - 10.0) < 1e-4,
        str(ob.matrix_world.translation),
    )


def test_editable_motion_path_bone():
    from mathutils import Vector
    from open_anim_easy import curves

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    bpy.ops.object.mode_set(mode="POSE")
    pb = arm.pose.bones[0]
    pb.location = (0.0, 0.0, 0.0)
    pb.keyframe_insert("location", frame=1)
    pb.location = (1.0, 0.0, 0.0)
    pb.keyframe_insert("location", frame=10)
    pb.select = True
    bpy.context.scene.frame_set(1)
    line, points = curves.motion_path_points(bpy.context, arm, pb)
    check(
        "edit_path_bone_points",
        [frame for frame, _pos in points] == [1, 10],
        str([frame for frame, _pos in points]),
    )
    bpy.context.scene.frame_set(10)
    original = arm.matrix_world @ pb.head.copy()
    target = original + Vector((0.0, 0.0, 1.0))
    state = curves.motion_capture_state(bpy.context, arm, pb, 10)
    ok = curves.motion_apply_point(bpy.context, arm, pb, 10, target)
    bpy.context.scene.frame_set(10)
    check(
        "edit_path_bone_apply",
        ok and (arm.matrix_world @ pb.head - target).length < 1e-4,
        str(arm.matrix_world @ pb.head),
    )
    curves.motion_restore_state(bpy.context, arm, pb, 10, state)
    bpy.context.scene.frame_set(10)
    check(
        "edit_path_bone_restore",
        (arm.matrix_world @ pb.head - original).length < 1e-4,
        str(arm.matrix_world @ pb.head),
    )
    bpy.ops.object.mode_set(mode="OBJECT")


def main():
    for name, func in [
        ("delete_crop", test_delete_crop),
        ("preview", test_preview),
        ("handle_blend", test_handle_blend),
        ("values", test_values),
        ("clean_static_euler", test_clean_static_euler),
        ("copy_flip", test_copy_flip),
        ("bake_curves", test_bake_curves),
        ("select_cycle", test_select_cycle),
        ("childof_toggle_bake", test_childof_toggle_bake),
        ("space", test_space),
        ("motion_paths", test_motion_paths),
        ("editable_motion_path", test_editable_motion_path),
        ("editable_motion_path_bone", test_editable_motion_path_bone),
    ]:
        run(name, func)
    print("SUMMARY pass=%d fail=%d" % (len(PASS), len(FAIL)))
    for name, detail in FAIL:
        print("FAILED", name, detail)
    addon.unregister()
    print("DONE")


main()
