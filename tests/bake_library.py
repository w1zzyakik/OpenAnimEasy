import os
import sys
import traceback

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import open_anim_easy as addon
from open_anim_easy import core, library

addon.register()

PASS, FAIL = [], []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print("PASS", name)
    else:
        FAIL.append((name, detail))
        print("FAIL", name, detail)


def run(name, func):
    try:
        func()
    except Exception:
        FAIL.append((name, traceback.format_exc()))
        print("FAIL", name)
        traceback.print_exc()


def armature():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    bpy.ops.object.mode_set(mode="POSE")
    return arm


def fcs(ob):
    action = core.action_of(ob)
    return core.action_fcurves(action, core.slot_of(ob, action))


def test_bake_bones():
    arm = armature()
    pb = arm.pose.bones[0]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = (1, 0, 0, 0)
    pb.keyframe_insert("rotation_quaternion", frame=1)
    pb.rotation_quaternion = (0.7, 0.7, 0, 0)
    pb.keyframe_insert("rotation_quaternion", frame=10)
    pb.select = True
    bpy.context.scene.frame_set(1)
    bpy.ops.openanim.bake(mode="ANIMATION", step=1)
    path = 'pose.bones["%s"].rotation_quaternion' % pb.name
    curves = [fc for fc in fcs(arm) if fc.data_path == path]
    frames = sorted({kp.co.x for fc in curves for kp in fc.keyframe_points})
    check(
        "bake_bones",
        len(curves) == 4 and frames == list(range(1, 11)),
        "%s %s" % (len(curves), frames),
    )
    check(
        "bake_bones_value",
        abs(curves[0].evaluate(10) - 0.7071068) < 1e-3
        and abs(curves[1].evaluate(10) - 0.7071068) < 1e-3,
        str([fc.evaluate(10) for fc in curves]),
    )
    bpy.ops.object.mode_set(mode="OBJECT")


def test_bake_object_euler():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    ob.rotation_mode = "XYZ"
    ob.rotation_euler = (0, 0, 0)
    ob.keyframe_insert("rotation_euler", frame=1)
    ob.rotation_euler = (0, 0, 1.0)
    ob.keyframe_insert("rotation_euler", frame=10)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.context.scene.frame_set(1)
    bpy.ops.openanim.bake(mode="ANIMATION", step=1)
    curves = [fc for fc in fcs(ob) if fc.data_path == "rotation_euler"]
    check("bake_object_euler", len(curves) == 3, str(len(curves)))
    z = next(fc for fc in curves if fc.array_index == 2)
    frames = [kp.co.x for kp in z.keyframe_points]
    check(
        "bake_object_euler_value",
        frames == list(range(1, 11)) and abs(z.evaluate(10) - 1.0) < 1e-3,
        "%s %s" % (frames, z.evaluate(10)),
    )


def test_pose_motion_paths():
    arm = armature()
    pb = arm.pose.bones[0]
    pb.rotation_mode = "QUATERNION"
    pb.keyframe_insert("rotation_quaternion", frame=1)
    pb.rotation_quaternion = (0.7, 0.7, 0, 0)
    pb.keyframe_insert("rotation_quaternion", frame=10)
    pb.select = True
    bpy.context.scene.frame_set(1)
    bpy.ops.openanim.motion_paths(action="SHOW")
    check(
        "pose_motion_path_show",
        any(p.motion_path is not None for p in arm.pose.bones),
        str([p.motion_path for p in arm.pose.bones]),
    )
    bpy.ops.openanim.motion_paths(action="CLEAR")
    check(
        "pose_motion_path_clear",
        not any(p.motion_path for p in arm.pose.bones),
    )
    bpy.ops.object.mode_set(mode="OBJECT")


def test_pivot_offset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(location=(2, 3, 4))
    ob = bpy.context.object
    bpy.ops.object.transform_apply(location=False)
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.context.scene.tool_settings.transform_pivot_point = "MEDIAN_POINT"
    bpy.ops.openanim.pivot_offset()
    check(
        "pivot_offset_on",
        bpy.context.scene.tool_settings.transform_pivot_point == "CURSOR"
        and (bpy.context.scene.cursor.location - ob.matrix_world.translation).length < 1e-5,
        str(bpy.context.scene.cursor.location),
    )
    bpy.ops.openanim.pivot_offset()
    check(
        "pivot_offset_off",
        bpy.context.scene.tool_settings.transform_pivot_point == "MEDIAN_POINT",
        bpy.context.scene.tool_settings.transform_pivot_point,
    )


def test_library_pose():
    for name in library.list_items("poses"):
        if name.startswith("SmokePose"):
            library.delete_item("poses", name)
    arm = armature()
    pb = arm.pose.bones[0]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = (0.5, 0.5, 0.5, 0.5)
    pb.select = True
    bpy.ops.openanim.library_save(kind="poses", name="SmokePose")
    saved = [n for n in library.list_items("poses") if n.startswith("SmokePose")]
    check("pose_lib_save", bool(saved), str(library.list_items("poses")))
    pb.rotation_quaternion = (1, 0, 0, 0)
    bpy.ops.openanim.library_apply(kind="poses", name=saved[0])
    check(
        "pose_lib_apply",
        abs(pb.rotation_quaternion.w - 0.5) < 1e-4
        and abs(pb.rotation_quaternion.y - 0.5) < 1e-4,
        str(tuple(pb.rotation_quaternion)),
    )
    pb.rotation_quaternion = (1, 0, 0, 0)
    bpy.ops.openanim.library_apply(kind="poses", name="does-not-exist")
    check(
        "pose_lib_missing",
        abs(pb.rotation_quaternion.w - 1.0) < 1e-4,
        str(tuple(pb.rotation_quaternion)),
    )
    library.delete_item("poses", saved[0])
    check("pose_lib_delete", not [n for n in library.list_items("poses") if n.startswith("SmokePose")])
    bpy.ops.object.mode_set(mode="OBJECT")


def test_library_animation():
    for name in library.list_items("animations"):
        if name.startswith("SmokeAnim"):
            library.delete_item("animations", name)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    ob.location.x = 0
    ob.keyframe_insert("location", frame=1)
    ob.location.x = 10
    ob.keyframe_insert("location", frame=10)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.openanim.library_save(kind="animations", name="SmokeAnim")
    saved = [n for n in library.list_items("animations") if n.startswith("SmokeAnim")]
    check("anim_lib_save", bool(saved), str(library.list_items("animations")))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    other = bpy.context.object
    other.select_set(True)
    bpy.context.view_layer.objects.active = other
    bpy.context.scene.frame_set(5)
    bpy.ops.openanim.library_apply(kind="animations", name=saved[0])
    curves = [fc for fc in fcs(other) if fc.data_path == "location" and fc.array_index == 0]
    times = [kp.co.x for kp in curves[0].keyframe_points] if curves else []
    check(
        "anim_lib_apply",
        len(curves) == 1 and times == [5, 14],
        str(times),
    )
    library.delete_item("animations", saved[0])
    check("anim_lib_delete", not [n for n in library.list_items("animations") if n.startswith("SmokeAnim")])


def main():
    for name, func in [
        ("bake_bones", test_bake_bones),
        ("bake_object_euler", test_bake_object_euler),
        ("pose_motion_paths", test_pose_motion_paths),
        ("pivot_offset", test_pivot_offset),
        ("library_pose", test_library_pose),
        ("library_animation", test_library_animation),
    ]:
        run(name, func)
    print("SUMMARY pass=%d fail=%d" % (len(PASS), len(FAIL)))
    for name, detail in FAIL:
        print("FAILED", name, detail)
    addon.unregister()
    print("DONE")


main()
