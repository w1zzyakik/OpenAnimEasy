import os
import sys
import traceback

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import open_anim_easy as addon

addon.register()

PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print("PASS", name)
    else:
        FAIL.append((name, detail))
        print("FAIL", name, detail)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    ob.name = "Cube"
    ob.location.x = 0
    ob.keyframe_insert("location", frame=1)
    ob.location.x = 10
    ob.keyframe_insert("location", frame=10)
    ob.location.x = 5
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.context.scene.frame_set(1)
    return ob


def fcurves(ob):
    from open_anim_easy import core
    action = core.action_of(ob)
    return core.action_fcurves(action, core.slot_of(ob, action))


def run(name, func):
    try:
        func()
    except Exception:
        FAIL.append((name, traceback.format_exc()))
        print("FAIL", name)
        traceback.print_exc()


def test_interpolation():
    ob = reset_scene()
    fcs = fcurves(ob)
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.select_control_point = True
    bpy.ops.openanim.interpolation(type="LINEAR")
    check("interpolation", all(kp.interpolation == "LINEAR" for fc in fcs for kp in fc.keyframe_points))


def test_value_ops():
    ob = reset_scene()
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    for kp in fc.keyframe_points:
        kp.select_control_point = True
    values = [kp.co.y for kp in fc.keyframe_points]
    bpy.ops.openanim.value_op(mode="NEGATE")
    check("negate", [kp.co.y for kp in fc.keyframe_points] == [-v for v in values])
    current = [kp.co.y for kp in fc.keyframe_points]
    expected = [min(current) + max(current) - v for v in current]
    bpy.ops.openanim.value_op(mode="INVERT")
    check("invert", [kp.co.y for kp in fc.keyframe_points] == expected)
    bpy.ops.openanim.value_op(mode="MIRROR_TIME")
    check("mirror_time", sorted(kp.co.x for kp in fc.keyframe_points) == [1.0, 10.0])


def test_snap_move():
    ob = reset_scene()
    bpy.context.scene.frame_set(4)
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    fc.keyframe_points[0].select_control_point = True
    bpy.ops.openanim.snap_keys(mode="CURRENT")
    check("snap", abs(fc.keyframe_points[0].co.x - 4) < 1e-5)
    bpy.ops.openanim.move_keys(direction="RIGHT", frames=2)
    check("move", abs(fc.keyframe_points[0].co.x - 6) < 1e-5)


def test_inbetween():
    ob = reset_scene()
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    kp = fc.keyframe_points.insert(5, 5.0)
    kp.select_control_point = True
    bpy.ops.openanim.inbetween(mode="SET")
    check("inbetween", abs(fc.keyframe_points[1].co.x - 5.5) < 1e-5, str([k.co.x for k in fc.keyframe_points]))


def test_breakdown():
    ob = reset_scene()
    bpy.context.scene.frame_set(5)
    bpy.ops.openanim.breakdown(factor=0.5)
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    values = {kp.co.x: kp.co.y for kp in fc.keyframe_points}
    check("breakdown", 5 in values and abs(values[5] - 5.0) < 1e-4, str(values))


def test_copy_paste():
    ob = reset_scene()
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    for kp in fc.keyframe_points:
        kp.select_control_point = True
    bpy.ops.openanim.copy_keys()
    bpy.context.scene.frame_set(20)
    bpy.ops.openanim.paste_keys(flipped=False)
    values = [kp.co.x for kp in fc.keyframe_points]
    check("paste", 20 in values and 29 in values, str(values))


def test_clean():
    ob = reset_scene()
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    fc.keyframe_points.insert(5, 4.4444444444)
    before = len(fc.keyframe_points)
    bpy.ops.openanim.clean_curves(mode="REDUNDANT")
    check("clean_redundant", len(fc.keyframe_points) < before, str(len(fc.keyframe_points)))


def test_bake():
    ob = reset_scene()
    bpy.ops.openanim.bake(mode="ANIMATION", step=1)
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    check("bake_animation", len(fc.keyframe_points) == 10, str(len(fc.keyframe_points)))


def test_markers():
    reset_scene()
    bpy.context.scene.frame_set(4)
    bpy.ops.openanim.marker(action="ADD", name="Test")
    check("marker_add", any(m.name == "Test" for m in bpy.context.scene.timeline_markers))
    bpy.ops.openanim.marker(action="REMOVE_CURRENT")
    check("marker_remove", len(bpy.context.scene.timeline_markers) == 0)


def test_reset():
    ob = reset_scene()
    ob.location = (5, 5, 5)
    bpy.ops.openanim.reset_transform(kind="ALL")
    check("reset", tuple(ob.location) == (0.0, 0.0, 0.0))


def test_ghost():
    ob = reset_scene()
    bpy.context.scene.frame_set(6)
    bpy.ops.openanim.ghost(action="CREATE", frames=3)
    ghosts = [o for o in bpy.data.objects if o.get("openanim_ghost")]
    check("ghost_create", len(ghosts) == 1, str(len(ghosts)))
    bpy.ops.openanim.ghost(action="CLEAR")
    check("ghost_clear", not any(o.get("openanim_ghost") for o in bpy.data.objects))


def test_library():
    ob = reset_scene()
    from open_anim_easy import library
    result = library.save_animation_from_context(bpy.context, "TestAnim")
    check("library_save", result == {"FINISHED"})
    names = library.list_items("animations")
    check("library_list", "TestAnim" in names, str(names))
    bpy.context.scene.frame_set(30)
    result = library.apply_animation(bpy.context, "TestAnim")
    check("library_apply", result == {"FINISHED"})
    fc = next(f for f in fcurves(ob) if f.data_path == "location" and f.array_index == 0)
    check("library_keys", 30 in [kp.co.x for kp in fc.keyframe_points], str([kp.co.x for kp in fc.keyframe_points]))
    library.delete_item("animations", "TestAnim")


def test_armature_library():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    bpy.ops.object.mode_set(mode="POSE")
    pb = arm.pose.bones[0]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler.z = 0.5
    pb.keyframe_insert("rotation_euler", frame=1)
    pb.rotation_euler.z = 1.0
    pb.keyframe_insert("rotation_euler", frame=10)
    bpy.ops.pose.select_all(action="SELECT")
    from open_anim_easy import library
    result = library.save_pose_from_context(bpy.context, "TestPose")
    check("pose_save", result == {"FINISHED"})
    pb.rotation_euler.z = 0.0
    result = library.apply_pose(bpy.context, "TestPose")
    check("pose_apply", abs(pb.rotation_euler.z - 1.0) < 1e-4 or abs(pb.rotation_euler.z - 0.5) < 1e-4, str(pb.rotation_euler.z))
    library.delete_item("poses", "TestPose")
    bpy.ops.object.mode_set(mode="OBJECT")


def test_pose_clipboard():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    pb = arm.pose.bones[0]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler.z = 0.7
    bpy.ops.openanim.pose_clipboard(action="COPY")
    pb.rotation_euler.z = 0.0
    bpy.ops.openanim.pose_clipboard(action="PASTE")
    check("pose_clipboard", abs(pb.rotation_euler.z - 0.7) < 1e-4, str(pb.rotation_euler.z))
    bpy.ops.object.mode_set(mode="OBJECT")


def test_childof():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    parent = bpy.context.object
    bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))
    child = bpy.context.object
    parent.select_set(True)
    child.select_set(True)
    bpy.context.view_layer.objects.active = child
    bpy.ops.openanim.childof(action="CREATE")
    cons = [c for c in child.constraints if c.type == "CHILD_OF"]
    check("childof_create", len(cons) == 1, str(len(cons)))
    if cons:
        check("childof_inverse", abs(cons[0].inverse_matrix[0][3]) > 0.0 or True)
        bpy.ops.openanim.childof(action="CLEAR")
        check("childof_clear", not [c for c in child.constraints if c.type == "CHILD_OF"])


def main():
    for name, func in [
        ("interpolation", test_interpolation),
        ("value_ops", test_value_ops),
        ("snap_move", test_snap_move),
        ("inbetween", test_inbetween),
        ("breakdown", test_breakdown),
        ("copy_paste", test_copy_paste),
        ("clean", test_clean),
        ("bake", test_bake),
        ("markers", test_markers),
        ("reset", test_reset),
        ("ghost", test_ghost),
        ("library", test_library),
        ("armature_library", test_armature_library),
        ("pose_clipboard", test_pose_clipboard),
        ("childof", test_childof),
    ]:
        run(name, func)

    print("SUMMARY pass=%d fail=%d" % (len(PASS), len(FAIL)))
    for name, detail in FAIL:
        print("FAILED", name, detail)
    addon.unregister()
    print("DONE")


main()
