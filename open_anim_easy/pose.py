"""Posing, selection and viewport tools."""

import bpy
from mathutils import Matrix

from . import core

_POSE_CLIP = {}
_SILHOUETTE = {}


class OPENANIM_OT_gizmo_size(bpy.types.Operator):
    bl_idname = "openanim.gizmo_size"
    bl_label = "Gizmo Size"
    bl_description = "Increase or decrease the viewport gizmo size"
    bl_options = {"REGISTER", "UNDO"}

    direction: bpy.props.EnumProperty(items=(("UP", "Increase", ""), ("DOWN", "Decrease", "")))
    step: bpy.props.IntProperty(default=5, min=1, max=50)

    def execute(self, context):
        view = context.preferences.view
        delta = self.step if self.direction == "UP" else -self.step
        view.gizmo_size = max(10, min(200, view.gizmo_size + delta))
        return {"FINISHED"}


class OPENANIM_OT_cycle(bpy.types.Operator):
    bl_idname = "openanim.cycle"
    bl_label = "Cycle Transform Settings"
    bl_description = "Cycle the transform orientation or the pivot point"
    bl_options = {"REGISTER", "UNDO"}

    what: bpy.props.EnumProperty(
        items=(("ORIENTATION", "Orientation", ""), ("PIVOT", "Pivot", "")),
        default="ORIENTATION",
    )

    ORIENTATIONS = ("GLOBAL", "LOCAL", "NORMAL", "VIEW", "CURSOR")
    PIVOTS = (
        "MEDIAN_POINT",
        "INDIVIDUAL_ORIGINS",
        "CURSOR",
        "ACTIVE_ELEMENT",
        "BOUNDING_BOX_CENTER",
    )

    def execute(self, context):
        scene = context.scene
        if self.what == "PIVOT":
            values = self.PIVOTS
            current = scene.tool_settings.transform_pivot_point
            scene.tool_settings.transform_pivot_point = values[
                (values.index(current) + 1) % len(values)
            ]
        else:
            values = self.ORIENTATIONS
            slot = scene.transform_orientation_slots[0]
            current = slot.type
            try:
                slot.type = values[(values.index(current) + 1) % len(values)]
            except Exception:
                slot.type = "GLOBAL"
        return {"FINISHED"}


class OPENANIM_OT_select_rig(bpy.types.Operator):
    bl_idname = "openanim.select_rig"
    bl_label = "Select Rig Elements"
    bl_description = "Select opposite, parent or child bones / objects"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("OPPOSITE", "Select Opposite", ""),
            ("PARENT", "Select Parent", ""),
            ("CHILD", "Select Children", ""),
        ),
        default="OPPOSITE",
    )

    def execute(self, context):
        ob = context.object
        bones = core.target_bones(context)
        if ob and ob.type == "ARMATURE" and ob.mode == "POSE" and bones:
            if self.mode == "OPPOSITE":
                for pb in ob.pose.bones:
                    pb.select = not pb.select
            elif self.mode == "PARENT":
                parents = [pb.parent for pb in bones if pb.parent]
                for pb in ob.pose.bones:
                    pb.select = False
                for pb in parents:
                    pb.select = True
                if parents:
                    ob.data.bones.active = parents[0].bone
            else:
                children = [child for pb in bones for child in pb.children]
                for pb in ob.pose.bones:
                    pb.select = False
                for pb in children:
                    pb.select = True
                if children:
                    ob.data.bones.active = children[0].bone
            return {"FINISHED"}

        objects = list(context.selected_objects)
        if self.mode == "OPPOSITE":
            for other in context.view_layer.objects:
                if other.hide_select:
                    continue
                other.select_set(not other.select_get())
        elif self.mode == "PARENT":
            parents = {o.parent for o in objects if o.parent}
            for other in context.view_layer.objects:
                other.select_set(False)
            for parent in parents:
                parent.select_set(True)
            if parents:
                context.view_layer.objects.active = next(iter(parents))
        else:
            children = [c for o in objects for c in o.children]
            for other in context.view_layer.objects:
                other.select_set(False)
            for child in children:
                child.select_set(True)
            if children:
                context.view_layer.objects.active = children[0]
        return {"FINISHED"}


class OPENANIM_OT_pose_clipboard(bpy.types.Operator):
    bl_idname = "openanim.pose_clipboard"
    bl_label = "Pose Clipboard"
    bl_description = "Copy, paste or flip the pose of the selected bones"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("COPY", "Copy Pose", ""),
            ("PASTE", "Paste Pose", ""),
            ("PASTE_FLIPPED", "Paste Pose Flipped", ""),
            ("SAVE", "Add Pose to Library", ""),
        ),
        default="COPY",
    )
    name: bpy.props.StringProperty(default="")

    def execute(self, context):
        global _POSE_CLIP
        ob = context.object
        if self.action == "SAVE":
            from . import library

            return library.save_pose_from_context(context, self.name)
        if not ob or ob.type != "ARMATURE":
            self.report({"WARNING"}, "Select an armature")
            return {"CANCELLED"}
        bones = core.target_bones(context)
        if self.action == "COPY":
            if not bones:
                self.report({"WARNING"}, "Select pose bones")
                return {"CANCELLED"}
            _POSE_CLIP = {
                pb.name: {
                    "mode": pb.rotation_mode,
                    "matrix": [list(row) for row in pb.matrix_basis],
                }
                for pb in bones
            }
            self.report({"INFO"}, "Copied %d bones" % len(_POSE_CLIP))
            return {"FINISHED"}
        if not _POSE_CLIP:
            self.report({"WARNING"}, "Pose clipboard is empty")
            return {"CANCELLED"}
        flipped = self.action == "PASTE_FLIPPED"
        mirror = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0))
        targets = bones or list(ob.pose.bones)
        for pb in targets:
            source_name = core.flip_bone_name(pb.name) if flipped else pb.name
            data = _POSE_CLIP.get(source_name)
            if not data:
                continue
            matrix = Matrix(data["matrix"])
            if flipped:
                matrix = mirror @ matrix @ mirror
            pb.rotation_mode = data["mode"]
            pb.matrix_basis = matrix
        context.view_layer.update()
        return {"FINISHED"}


class OPENANIM_OT_reset_transform(bpy.types.Operator):
    bl_idname = "openanim.reset_transform"
    bl_label = "Reset Transforms"
    bl_description = "Reset location, rotation, scale or all transforms"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(
        items=(
            ("ALL", "All Transforms", ""),
            ("LOCATION", "Location", ""),
            ("ROTATION", "Rotation", ""),
            ("SCALE", "Scale", ""),
        ),
        default="ALL",
    )

    def _reset(self, target):
        if self.kind in {"ALL", "LOCATION"}:
            target.location = (0.0, 0.0, 0.0)
        if self.kind in {"ALL", "ROTATION"}:
            mode = target.rotation_mode
            if mode == "QUATERNION":
                target.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            elif mode == "AXIS_ANGLE":
                target.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
            else:
                target.rotation_euler = (0.0, 0.0, 0.0)
        if self.kind in {"ALL", "SCALE"}:
            target.scale = (1.0, 1.0, 1.0)

    def execute(self, context):
        bones = core.target_bones(context)
        if bones:
            for pb in bones:
                if self.kind == "ALL":
                    pb.matrix_basis = Matrix.Identity(4)
                else:
                    self._reset(pb)
            context.view_layer.update()
            return {"FINISHED"}
        objects = core.target_objects(context)
        if not objects:
            self.report({"WARNING"}, "Select objects or bones")
            return {"CANCELLED"}
        for ob in objects:
            self._reset(ob)
        return {"FINISHED"}


class OPENANIM_OT_pivot_offset(bpy.types.Operator):
    bl_idname = "openanim.pivot_offset"
    bl_label = "Pivot Offset"
    bl_description = "Move the 3D cursor to the active bone / object and use it as pivot"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ob = context.object
        if not ob:
            self.report({"WARNING"}, "Select an object or bone")
            return {"CANCELLED"}
        scene = context.scene
        pb = core.active_bone(context)
        if pb is not None:
            position = ob.matrix_world @ pb.head
        else:
            position = ob.matrix_world.translation
        if (
            scene.tool_settings.transform_pivot_point == "CURSOR"
            and "openanim_previous_pivot" in scene
        ):
            scene.tool_settings.transform_pivot_point = scene[
                "openanim_previous_pivot"
            ]
            del scene["openanim_previous_pivot"]
        else:
            scene["openanim_previous_pivot"] = (
                scene.tool_settings.transform_pivot_point
            )
            scene.cursor.location = position
            scene.tool_settings.transform_pivot_point = "CURSOR"
        return {"FINISHED"}


class OPENANIM_OT_silhouette(bpy.types.Operator):
    bl_idname = "openanim.silhouette"
    bl_label = "Silhouette Toggle"
    bl_description = "Toggle a flat silhouette shading for the 3D viewports"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        screen = getattr(context, "screen", None)
        if screen is None:
            self.report({"WARNING"}, "No 3D Viewport found")
            return {"CANCELLED"}
        areas = [a for a in screen.areas if a.type == "VIEW_3D"]
        if not areas:
            self.report({"WARNING"}, "No 3D Viewport found")
            return {"CANCELLED"}
        for area in areas:
            key = area.as_pointer()
            shading = area.spaces.active.shading
            if key in _SILHOUETTE:
                state = _SILHOUETTE.pop(key)
                shading.light = state["light"]
                shading.color_type = state["color_type"]
                shading.background_type = state["background_type"]
                shading.show_shadows = state["shadows"]
                shading.show_cavity = state["cavity"]
                shading.show_object_outline = state["outline"]
            else:
                _SILHOUETTE[key] = {
                    "light": shading.light,
                    "color_type": shading.color_type,
                    "background_type": shading.background_type,
                    "shadows": shading.show_shadows,
                    "cavity": shading.show_cavity,
                    "outline": shading.show_object_outline,
                }
                shading.light = "FLAT"
                shading.color_type = "SINGLE"
                shading.single_color = (0.02, 0.02, 0.02)
                shading.background_type = "VIEWPORT"
                shading.background_color = (0.78, 0.78, 0.78)
                shading.show_shadows = False
                shading.show_cavity = False
                shading.show_object_outline = False
        return {"FINISHED"}


CLASSES = (
    OPENANIM_OT_gizmo_size,
    OPENANIM_OT_cycle,
    OPENANIM_OT_select_rig,
    OPENANIM_OT_pose_clipboard,
    OPENANIM_OT_reset_transform,
    OPENANIM_OT_pivot_offset,
    OPENANIM_OT_silhouette,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
