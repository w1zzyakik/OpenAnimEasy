"""Portable JSON pose and animation library."""

import json
import os
import re
import time

import bpy
from mathutils import Matrix

from . import core


def _root(kind=None):
    base = os.path.join(bpy.utils.user_resource("CONFIG"), "OpenAnimEasy")
    if kind:
        base = os.path.join(base, kind)
    os.makedirs(base, exist_ok=True)
    return base


def _safe(name):
    name = os.path.basename(name.strip()) or "Untitled"
    return re.sub(r"[^A-Za-z0-9 _\-\.]", "_", name)


def _unique_path(folder, name):
    path = os.path.join(folder, name + ".json")
    index = 1
    while os.path.exists(path):
        path = os.path.join(folder, "%s.%03d.json" % (name, index))
        index += 1
    return path


def list_items(kind):
    try:
        return sorted(
            os.path.splitext(entry)[0]
            for entry in os.listdir(_root(kind))
            if entry.lower().endswith(".json")
        )
    except Exception:
        return []


def _write(kind, name, payload):
    path = _unique_path(_root(kind), _safe(name))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    return os.path.splitext(os.path.basename(path))[0]


def _read(kind, name):
    path = os.path.join(_root(kind), os.path.basename(name) + ".json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _fail(operator, message):
    if operator:
        operator.report({"WARNING"}, message)
    return {"CANCELLED"}


def save_pose_from_context(context, name, operator=None):
    ob = context.object
    if not ob or ob.type != "ARMATURE":
        return _fail(operator, "Select an armature")
    bones = core.target_bones(context) or list(ob.pose.bones)
    payload = {
        "version": 1,
        "created": time.time(),
        "bones": {
            pb.name: {
                "mode": pb.rotation_mode,
                "matrix": [list(row) for row in pb.matrix_basis],
            }
            for pb in bones
        },
    }
    saved = _write("poses", name or "Pose", payload)
    if operator:
        operator.report({"INFO"}, "Saved pose '%s'" % saved)
    return {"FINISHED"}


def save_animation_from_context(context, name, operator=None):
    ob = context.object
    if not ob:
        return _fail(operator, "Select an object")
    action = core.action_of(ob)
    if not action:
        return _fail(operator, "The active object has no animation")
    fcurves = core.action_fcurves(action, core.slot_of(ob, action))
    entries = []
    for fc in fcurves:
        if not len(fc.keyframe_points):
            continue
        entries.append(
            {
                "path": fc.data_path,
                "index": fc.array_index,
                "keys": [
                    [kp.co.x, kp.co.y, kp.interpolation, kp.type]
                    for kp in fc.keyframe_points
                ],
            }
        )
    if not entries:
        return _fail(operator, "No keys to store")
    payload = {
        "version": 1,
        "created": time.time(),
        "object_type": ob.type,
        "entries": entries,
    }
    saved = _write("animations", name or "Animation", payload)
    if operator:
        operator.report({"INFO"}, "Saved animation '%s'" % saved)
    return {"FINISHED"}


def apply_pose(context, name, operator=None):
    ob = context.object
    if not ob or ob.type != "ARMATURE":
        return _fail(operator, "Select an armature")
    payload = _read("poses", name)
    if not payload:
        return _fail(operator, "Pose not found")
    applied = 0
    for bone_name, data in payload.get("bones", {}).items():
        pb = ob.pose.bones.get(bone_name)
        if not pb:
            continue
        pb.rotation_mode = data.get("mode", pb.rotation_mode)
        pb.matrix_basis = Matrix(data["matrix"])
        applied += 1
    context.view_layer.update()
    if operator:
        operator.report({"INFO"}, "Applied pose to %d bones" % applied)
    return {"FINISHED"}


def apply_animation(context, name, operator=None):
    ob = context.object
    if not ob:
        return _fail(operator, "Select an object")
    payload = _read("animations", name)
    if not payload:
        return _fail(operator, "Animation not found")
    entries = payload.get("entries", [])
    if not entries:
        return _fail(operator, "Empty animation")
    frames = [key[0] for entry in entries for key in entry["keys"]]
    if not frames:
        return _fail(operator, "Empty animation")
    first = min(frames)
    offset = context.scene.frame_current
    for entry in entries:
        if entry["path"].startswith("pose.bones") and ob.type != "ARMATURE":
            continue
        fc = core.ensure_fcurve(ob, entry["path"], entry["index"])
        for frame, value, interpolation, key_type in entry["keys"]:
            kp = fc.keyframe_points.insert(offset + frame - first, value)
            kp.interpolation = interpolation
            kp.type = key_type
        core.sort_fcurve(fc)
        core.dedupe_fcurve(fc)
    if operator:
        operator.report({"INFO"}, "Applied animation '%s'" % name)
    return {"FINISHED"}


def delete_item(kind, name):
    path = os.path.join(_root(kind), os.path.basename(name) + ".json")
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


class OPENANIM_OT_library_save(bpy.types.Operator):
    bl_idname = "openanim.library_save"
    bl_label = "Save to Library"
    bl_description = "Store the current pose or animation in the portable library"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(
        items=(("animations", "Animation", ""), ("poses", "Pose", "")),
        default="animations",
    )
    name: bpy.props.StringProperty(default="")

    def invoke(self, context, event):
        if not self.name:
            self.name = "Pose" if self.kind == "poses" else "Animation"
        return context.window_manager.invoke_props_dialog(self, width=320)

    def execute(self, context):
        if self.kind == "poses":
            return save_pose_from_context(context, self.name, self)
        return save_animation_from_context(context, self.name, self)


class OPENANIM_OT_library_apply(bpy.types.Operator):
    bl_idname = "openanim.library_apply"
    bl_label = "Apply from Library"
    bl_description = "Apply a stored pose or animation"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(
        items=(("animations", "Animation", ""), ("poses", "Pose", "")),
        default="animations",
    )
    name: bpy.props.StringProperty(default="")

    def execute(self, context):
        if not self.name:
            self.report({"WARNING"}, "Pick a library item")
            return {"CANCELLED"}
        if self.kind == "poses":
            return apply_pose(context, self.name, self)
        return apply_animation(context, self.name, self)


class OPENANIM_OT_library_delete(bpy.types.Operator):
    bl_idname = "openanim.library_delete"
    bl_label = "Delete Library Item"
    bl_description = "Delete a stored pose or animation"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(
        items=(("animations", "Animation", ""), ("poses", "Pose", "")),
        default="animations",
    )
    name: bpy.props.StringProperty(default="")

    def execute(self, context):
        if not self.name:
            return {"CANCELLED"}
        if delete_item(self.kind, self.name):
            self.report({"INFO"}, "Deleted '%s'" % self.name)
            return {"FINISHED"}
        self.report({"WARNING"}, "Item not found")
        return {"CANCELLED"}


CLASSES = (
    OPENANIM_OT_library_save,
    OPENANIM_OT_library_apply,
    OPENANIM_OT_library_delete,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
