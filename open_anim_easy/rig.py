"""Constraints and space conversion tools."""

import bpy

from . import core
from .curves import _bake_animation, _rotation_values


def _owner(context):
    ob = context.object
    if not ob:
        return None, None
    pb = core.active_bone(context)
    return ob, pb


def _childof_constraints(ob, pb):
    owner = pb.constraints if pb is not None else ob.constraints
    return [con for con in owner if con.type == "CHILD_OF"]


class OPENANIM_OT_childof(bpy.types.Operator):
    bl_idname = "openanim.childof"
    bl_label = "Child Of Constraint"
    bl_description = "Create, toggle, bake or clear a Child Of constraint"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("CREATE", "Create Child Of", ""),
            ("TOGGLE", "Toggle Child Of", ""),
            ("BAKE", "Bake Child Of", ""),
            ("CLEAR", "Clear Child Of", ""),
        ),
        default="CREATE",
    )

    def execute(self, context):
        ob, pb = _owner(context)
        if not ob:
            self.report({"WARNING"}, "Select an object or bone")
            return {"CANCELLED"}

        if self.action == "CREATE":
            parent_ob = None
            parent_pb = None
            if pb is not None:
                candidates = [
                    other
                    for other in core.target_bones(context)
                    if other.name != pb.name
                ]
                parent_pb = candidates[0] if candidates else None
                if parent_pb is not None:
                    parent_ob = parent_pb.id_data
                else:
                    others = [o for o in context.selected_objects if o != ob]
                    parent_ob = others[0] if others else None
            else:
                others = [o for o in context.selected_objects if o != ob]
                parent_ob = others[0] if others else None
            if parent_ob is None:
                self.report(
                    {"WARNING"}, "Select the parent first, then the child"
                )
                return {"CANCELLED"}

            context.view_layer.update()
            if parent_pb is not None:
                target_matrix = parent_ob.matrix_world @ parent_pb.matrix
            else:
                target_matrix = parent_ob.matrix_world
            if pb is not None:
                child_matrix = ob.matrix_world @ pb.matrix
            else:
                child_matrix = ob.matrix_world

            owner = pb.constraints if pb is not None else ob.constraints
            constraint = owner.new("CHILD_OF")
            constraint.name = "Child Of"
            constraint.target = parent_ob
            if parent_pb is not None:
                constraint.subtarget = parent_pb.name
            constraint.inverse_matrix = target_matrix.inverted() @ child_matrix
            return {"FINISHED"}

        constraints = _childof_constraints(ob, pb)
        if not constraints and self.action != "TOGGLE":
            self.report({"WARNING"}, "No Child Of constraint on the active element")
            return {"CANCELLED"}

        if self.action == "TOGGLE":
            for constraint in constraints:
                constraint.mute = not constraint.mute
            return {"FINISHED"}
        if self.action == "CLEAR":
            for constraint in constraints:
                if pb is not None:
                    pb.constraints.remove(constraint)
                else:
                    ob.constraints.remove(constraint)
            return {"FINISHED"}

        start, end = core.smart_range(context)
        if not _bake_animation(context, start, end, 1):
            self.report({"WARNING"}, "Nothing to bake")
            return {"CANCELLED"}
        for target_pb in core.target_bones(context):
            for constraint in _childof_constraints(ob, target_pb):
                target_pb.constraints.remove(constraint)
        if pb is None:
            for constraint in _childof_constraints(ob, None):
                ob.constraints.remove(constraint)
        return {"FINISHED"}


def _write_object_world(ob, matrices):
    mode = ob.rotation_mode
    previous_quat = None
    samples = []
    for frame, matrix in matrices:
        location, rotation, scale = matrix.decompose()
        rotation_values, previous_quat = _rotation_values(
            rotation, mode, previous_quat
        )
        samples.append((frame, location, rotation_values, scale))
    channels = [("location", 3), ("scale", 3)]
    if mode == "QUATERNION":
        channels.insert(1, ("rotation_quaternion", 4))
    elif mode == "AXIS_ANGLE":
        channels.insert(1, ("rotation_axis_angle", 4))
    else:
        channels.insert(1, ("rotation_euler", 3))
    for path, count in channels:
        for index in range(count):
            fc = core.ensure_fcurve(ob, path, index)
            fc.keyframe_points.clear()
            for frame, location, rotation_values, scale in samples:
                if path == "location":
                    value = location[index]
                elif path == "scale":
                    value = scale[index]
                else:
                    value = rotation_values[index]
                fc.keyframe_points.insert(frame, value).interpolation = "LINEAR"
            fc.update()


def _world_matrices(context, ob, start, end, step):
    scene = context.scene
    original = scene.frame_current
    matrices = []
    for frame in range(int(start), int(end) + 1, max(1, step)):
        scene.frame_set(frame)
        context.view_layer.update()
        matrices.append((frame, ob.matrix_world.copy()))
    scene.frame_set(original)
    return matrices


class OPENANIM_OT_space_convert(bpy.types.Operator):
    bl_idname = "openanim.space_convert"
    bl_label = "Space Conversion"
    bl_description = "Convert animation between local and world space"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("TO_WORLD", "Local to World", ""),
            ("TO_LOCAL", "World to Local (Bake)", ""),
        ),
        default="TO_WORLD",
    )
    step: bpy.props.IntProperty(default=1, min=1, max=100)

    def execute(self, context):
        start, end = core.smart_range(context)
        objects = core.target_objects(context)
        if not objects:
            self.report({"WARNING"}, "Select objects or bones")
            return {"CANCELLED"}

        if self.mode == "TO_LOCAL":
            bones = core.target_bones(context)
            if not _bake_animation(context, start, end, self.step):
                return {"CANCELLED"}
            for pb in bones:
                for constraint in list(pb.constraints):
                    pb.constraints.remove(constraint)
            for ob in objects:
                for constraint in list(ob.constraints):
                    ob.constraints.remove(constraint)
            self.report({"INFO"}, "Baked visual transforms into local space")
            return {"FINISHED"}

        for ob in objects:
            if ob.type == "ARMATURE":
                continue
            matrices = _world_matrices(context, ob, start, end, self.step)
            ob.parent = None
            ob.matrix_parent_inverse.identity()
            for constraint in list(ob.constraints):
                ob.constraints.remove(constraint)
            _write_object_world(ob, matrices)
        if core.target_bones(context):
            _bake_animation(context, start, end, self.step)
            self.report(
                {"INFO"},
                "Bones are baked in local space (hierarchy cannot be flattened)",
            )
        return {"FINISHED"}


CLASSES = (
    OPENANIM_OT_childof,
    OPENANIM_OT_space_convert,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
