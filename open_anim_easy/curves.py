"""Curve, spacing, cleanup, bake and motion path tools."""

import math

import bpy
from bpy_extras.view3d_utils import (
    location_3d_to_region_2d,
    region_2d_to_origin_3d,
    region_2d_to_vector_3d,
)
from mathutils import Vector

from . import core

_CLIP = []


def _lerp(a, b, t):
    return a + (b - a) * t


def _key_at(fc, frame, eps=1e-4):
    for kp in fc.keyframe_points:
        if abs(kp.co.x - frame) < eps:
            return kp
    return None


def _selected_value_points(context):
    return core.selected_keyframes(
        [fc for _ob, fc in core.target_fcurves(context)]
    )


def _curve_subset(context):
    pairs = core.target_fcurves(context)
    selected = [fc for _ob, fc in pairs if core.selected_keyframes([fc])]
    return [fc for fc in (selected or [fc for _ob, fc in pairs])]


def _neighbors(fc, frame):
    prev = next_ = None
    for kp in fc.keyframe_points:
        if kp.co.x < frame - 1e-6:
            prev = kp
        elif kp.co.x > frame + 1e-6:
            next_ = kp
            break
    return prev, next_


# --------------------------------------------------------------------------
# Breakdown / spacing
# --------------------------------------------------------------------------

class OPENANIM_OT_breakdown(bpy.types.Operator):
    bl_idname = "openanim.breakdown"
    bl_label = "Breakdowner"
    bl_description = "Move the mouse to set an inbetween pose, click to confirm"
    bl_options = {"REGISTER", "UNDO"}

    factor: bpy.props.FloatProperty(default=0.5, min=0.0, max=1.0)

    def _build(self, context):
        frame = context.scene.frame_current
        self._items = []
        for _ob, fc in core.target_fcurves(context):
            prev, next_ = _neighbors(fc, frame)
            if not prev or not next_:
                continue
            left = prev.co.y
            right = next_.co.y
            existing = _key_at(fc, frame)
            if existing is not None:
                kp = existing
                existed = True
                original = kp.co.y
            else:
                kp = fc.keyframe_points.insert(frame, fc.evaluate(frame))
                existed = False
                original = kp.co.y
            index = core.key_index(fc, kp)
            self._items.append((fc, index, existed, original, left, right))
        return bool(self._items)

    def _apply(self, factor):
        for fc, index, _existed, _original, left, right in self._items:
            if index >= len(fc.keyframe_points):
                continue
            kp = fc.keyframe_points[index]
            core.move_key_value(kp, _lerp(left, right, factor))
            kp.interpolation = "BEZIER"
        for fc in {item[0] for item in self._items}:
            fc.update()

    def invoke(self, context, event):
        if not self._build(context):
            self.report({"WARNING"}, "No keys on both sides of the current frame")
            return {"CANCELLED"}
        self._apply(self.factor)
        self._anchor = event.mouse_x
        region = core.window_region(context)
        self._width = region.width if region else 500
        if context.area and context.region:
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        return {"FINISHED"}

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            self.factor = max(
                0.0, min(1.0, (event.mouse_x - self._anchor) / max(1, self._width) + 0.5)
            )
            self._apply(self.factor)
            return {"RUNNING_MODAL"}
        if event.type in {"LEFTMOUSE", "RET", "NUMPAD_ENTER"}:
            return {"FINISHED"}
        if event.type in {"RIGHTMOUSE", "ESC"}:
            remove = {}
            restore = []
            for fc, index, existed, original, _left, _right in self._items:
                if existed:
                    restore.append((fc, index, original))
                else:
                    remove.setdefault(fc, []).append(index)
            for fc, index, original in restore:
                if index < len(fc.keyframe_points):
                    core.move_key_value(fc.keyframe_points[index], original)
            for fc, indices in remove.items():
                for index in sorted(indices, reverse=True):
                    if index < len(fc.keyframe_points):
                        fc.keyframe_points.remove(fc.keyframe_points[index])
            for fc in {item[0] for item in self._items}:
                fc.update()
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self._build(context):
            self.report({"WARNING"}, "No keys on both sides of the current frame")
            return {"CANCELLED"}
        self._apply(self.factor)
        return {"FINISHED"}


class OPENANIM_OT_blend(bpy.types.Operator):
    bl_idname = "openanim.blend"
    bl_label = "Blend Keys"
    bl_description = "Blend, ease, smooth or push selected key values"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("NEIGHBOR", "Blend to Neighbor", ""),
            ("DEFAULT", "Blend to Default", ""),
            ("AVERAGE", "Blend Average", ""),
            ("EASE_IN", "Ease In", ""),
            ("EASE_OUT", "Ease Out", ""),
            ("SMOOTH", "Smooth", ""),
            ("PUSH", "Push", ""),
            ("PULL", "Pull", ""),
        ),
        default="NEIGHBOR",
    )
    factor: bpy.props.FloatProperty(default=0.5, min=0.0, max=2.0)

    def execute(self, context):
        points = _selected_value_points(context)
        if not points:
            self.report({"WARNING"}, "No keys selected")
            return {"CANCELLED"}
        by_curve = {}
        for fc, kp in points:
            by_curve.setdefault(fc, []).append(kp)

        for fc, keys in by_curve.items():
            keys.sort(key=lambda kp: kp.co.x)
            if self.mode in {"EASE_IN", "EASE_OUT"}:
                for kp in keys:
                    kp.interpolation = "SINE"
                    kp.easing = "EASE_IN" if self.mode == "EASE_IN" else "EASE_OUT"
                fc.update()
                continue

            average = sum(kp.co.y for kp in keys) / len(keys)
            for kp in keys:
                index = core.key_index(fc, kp)
                prev = fc.keyframe_points[index - 1] if index > 0 else None
                next_ = (
                    fc.keyframe_points[index + 1]
                    if index < len(fc.keyframe_points) - 1
                    else None
                )
                if self.mode == "NEIGHBOR":
                    if prev and next_:
                        target = (prev.co.y + next_.co.y) * 0.5
                    elif prev or next_:
                        target = (prev or next_).co.y
                    else:
                        continue
                    value = _lerp(kp.co.y, target, self.factor)
                elif self.mode == "DEFAULT":
                    value = _lerp(
                        kp.co.y, core.default_value(fc.data_path, fc.array_index), self.factor
                    )
                elif self.mode == "AVERAGE":
                    value = _lerp(kp.co.y, average, self.factor)
                elif self.mode == "SMOOTH":
                    pairs = [k for k in (prev, kp, next_) if k]
                    value = sum(k.co.y for k in pairs) / len(pairs)
                elif self.mode == "PUSH":
                    target = (prev.co.y + next_.co.y) * 0.5 if prev and next_ else average
                    value = target + (kp.co.y - target) * 1.2
                else:  # PULL
                    target = (prev.co.y + next_.co.y) * 0.5 if prev and next_ else average
                    value = target + (kp.co.y - target) * 0.8
                core.move_key_value(kp, value)
            fc.update()
        return {"FINISHED"}


# --------------------------------------------------------------------------
# Ghost curves
# --------------------------------------------------------------------------

_GHOST_PREFIX = "OpenAnimEasy Ghost"


def _ghost_material():
    mat = bpy.data.materials.get("OpenAnimEasy Ghost")
    if mat is None:
        mat = bpy.data.materials.new("OpenAnimEasy Ghost")
        mat.diffuse_color = (1.0, 0.15, 0.05, 1.0)
    return mat


class OPENANIM_OT_ghost(bpy.types.Operator):
    bl_idname = "openanim.ghost"
    bl_label = "Ghost Curve"
    bl_description = "Create or clear a ghost trail of the selected objects / bones"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("CREATE", "Create Ghost Curve", ""), ("CLEAR", "Clear Ghost Curves", "")),
        default="CREATE",
    )
    frames: bpy.props.IntProperty(default=5, min=1, max=120)

    def _targets(self, context):
        ob = context.object
        bones = core.target_bones(context)
        if ob and ob.type == "ARMATURE" and bones:
            return [(ob, pb) for pb in bones]
        return [(o, None) for o in core.target_objects(context)]

    def execute(self, context):
        if self.action == "CLEAR":
            for ob in [o for o in bpy.data.objects if o.get("openanim_ghost")]:
                data = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if data and data.users == 0:
                    try:
                        bpy.data.curves.remove(data)
                    except Exception:
                        pass
            return {"FINISHED"}
        targets = self._targets(context)
        if not targets:
            self.report({"WARNING"}, "Select objects or bones")
            return {"CANCELLED"}
        scene = context.scene
        current = scene.frame_current
        start = max(scene.frame_start, current - self.frames)
        samples = {}
        for index in range(len(targets)):
            samples[index] = []
        for frame in range(start, current + 1):
            scene.frame_set(frame)
            context.view_layer.update()
            for index, (ob, pb) in enumerate(targets):
                if pb is not None:
                    point = ob.matrix_world @ pb.head
                else:
                    point = ob.matrix_world.translation
                samples[index].append(tuple(point))
        scene.frame_set(current)
        curve = bpy.data.curves.new(_GHOST_PREFIX, "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = 0.01
        curve.bevel_resolution = 1
        curve.materials.append(_ghost_material())
        for points in samples.values():
            if len(points) < 2:
                continue
            spline = curve.splines.new("POLY")
            spline.points.add(len(points) - 1)
            for point, co in zip(spline.points, points):
                point.co = (*co, 1.0)
        ob = bpy.data.objects.new(_GHOST_PREFIX, curve)
        context.scene.collection.objects.link(ob)
        ob.show_in_front = True
        ob["openanim_ghost"] = True
        return {"FINISHED"}


# --------------------------------------------------------------------------
# Built-in motion paths
# --------------------------------------------------------------------------

def _pose_paths(context, operation):
    armatures = [o for o in core.target_objects(context) if o.type == "ARMATURE"]
    for ob in armatures:
        if ob.mode != "POSE":
            try:
                bpy.context.view_layer.objects.active = ob
                bpy.ops.object.mode_set(mode="POSE")
            except Exception:
                continue
        temporary = []
        if operation in {"SHOW", "UPDATE"}:
            for pb in ob.pose.bones:
                if not pb.select:
                    pb.select = True
                    temporary.append(pb)
        try:
            with bpy.context.temp_override(
                object=ob, active_object=ob, selected_objects=[ob]
            ):
                if operation == "SHOW":
                    bpy.ops.pose.paths_calculate()
                elif operation == "UPDATE":
                    bpy.ops.pose.paths_update()
                else:
                    bpy.ops.pose.paths_clear(only_selected=False)
        except Exception:
            pass
        for pb in temporary:
            pb.select = False
    return bool(armatures)


class OPENANIM_OT_motion_paths(bpy.types.Operator):
    bl_idname = "openanim.motion_paths"
    bl_label = "Motion Paths"
    bl_description = "Show, update or clear motion paths for the selection"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(("SHOW", "Show Motion Paths", ""), ("UPDATE", "Update All", ""), ("CLEAR", "Clear All", "")),
        default="SHOW",
    )

    def execute(self, context):
        objects = [o for o in core.target_objects(context) if o.type != "ARMATURE"]
        if self.action == "SHOW":
            for ob in objects:
                try:
                    with bpy.context.temp_override(
                        object=ob, active_object=ob, selected_objects=[ob]
                    ):
                        bpy.ops.object.paths_calculate()
                except Exception:
                    pass
            _pose_paths(context, "SHOW")
        elif self.action == "UPDATE":
            try:
                bpy.ops.object.paths_update_visible()
            except Exception:
                for ob in bpy.context.scene.objects:
                    if ob.motion_path:
                        try:
                            with bpy.context.temp_override(
                                object=ob, active_object=ob, selected_objects=[ob]
                            ):
                                bpy.ops.object.paths_update()
                        except Exception:
                            pass
            _pose_paths(context, "UPDATE")
        else:
            for ob in bpy.context.scene.objects:
                if ob.type == "ARMATURE":
                    continue
                if not ob.motion_path:
                    continue
                try:
                    with bpy.context.temp_override(
                        object=ob, active_object=ob, selected_objects=[ob]
                    ):
                        bpy.ops.object.paths_clear()
                except Exception:
                    pass
            for ob in bpy.context.scene.objects:
                if ob.type != "ARMATURE":
                    continue
                if any(pb.motion_path for pb in ob.pose.bones):
                    if ob.mode != "POSE":
                        try:
                            bpy.context.view_layer.objects.active = ob
                            bpy.ops.object.mode_set(mode="POSE")
                        except Exception:
                            continue
                    try:
                        with bpy.context.temp_override(
                            object=ob, active_object=ob, selected_objects=[ob]
                        ):
                            bpy.ops.pose.paths_clear(only_selected=False)
                    except Exception:
                        pass
        return {"FINISHED"}


# --------------------------------------------------------------------------
# Editable 3D motion path
# --------------------------------------------------------------------------

_EDIT = {"handler": None, "points": [], "line": [], "active": -1, "size": 0.05}


def motion_target(context):
    ob = context.object
    if not ob:
        return None, None
    return ob, core.active_bone(context)


def motion_world_position(ob, pb):
    if pb is not None:
        return ob.matrix_world @ pb.head
    return ob.matrix_world.translation.copy()


def _location_data_path(pb):
    return 'pose.bones["%s"].location' % pb.name if pb else "location"


def motion_location_frames(context, ob, pb):
    """Frames that have location keys for the object or pose bone."""
    path = _location_data_path(pb)
    frames = set()
    action = core.action_of(ob)
    if action:
        for fc in core.action_fcurves(action, core.slot_of(ob, action)):
            if fc.data_path == path:
                frames.update(int(round(kp.co.x)) for kp in fc.keyframe_points)
    return sorted(frames or {context.scene.frame_current})


def _sample_position(context, ob, pb, frame):
    scene = context.scene
    current = scene.frame_current
    scene.frame_set(int(frame))
    position = motion_world_position(ob, pb)
    scene.frame_set(current)
    return position


def motion_path_line(context, ob, pb):
    """World-space trajectory sampled over the animation range."""
    start, end = core.smart_range(context)
    start, end = int(start), int(end)
    step = max(1, (end - start) // 1000 + 1)
    scene = context.scene
    current = scene.frame_current
    line = []
    try:
        for frame in range(start, end + 1, step):
            scene.frame_set(frame)
            line.append((frame, motion_world_position(ob, pb).copy()))
    finally:
        scene.frame_set(current)
    return line


def motion_path_points(context, ob, pb):
    """(frame, world position) for every editable location key."""
    line = motion_path_line(context, ob, pb)
    positions = dict(line)
    points = []
    for frame in motion_location_frames(context, ob, pb):
        position = positions.get(frame)
        if position is None:
            position = _sample_position(context, ob, pb, frame)
        points.append((frame, position.copy()))
    return line, points


def _has_location_key(context, ob, pb, frame):
    path = _location_data_path(pb)
    action = core.action_of(ob)
    if not action:
        return False
    for fc in core.action_fcurves(action, core.slot_of(ob, action)):
        if fc.data_path == path and any(
            abs(kp.co.x - frame) < 1e-4 for kp in fc.keyframe_points
        ):
            return True
    return False


def motion_capture_state(context, ob, pb, frame):
    """Location and key presence at frame, for cancelling an edit."""
    context.scene.frame_set(int(frame))
    return {
        "location": (pb.location if pb else ob.location).copy(),
        "key": _has_location_key(context, ob, pb, frame),
    }


def motion_restore_state(context, ob, pb, frame, state):
    context.scene.frame_set(int(frame))
    target = pb or ob
    target.location = state["location"]
    if state["key"]:
        target.keyframe_insert("location", frame=frame)
    else:
        target.keyframe_delete("location", frame=frame)


def motion_apply_point(context, ob, pb, frame, position):
    """Move an object or pose bone to a world position and key it."""
    context.scene.frame_set(int(frame))
    if pb is not None:
        if pb.bone.use_connect:
            return False
        matrix = pb.matrix.copy()
        matrix.translation = ob.matrix_world.inverted() @ position
        pb.matrix = matrix
        pb.keyframe_insert("location", frame=frame)
    else:
        matrix = ob.matrix_world.copy()
        matrix.translation = position
        ob.matrix_world = matrix
        ob.keyframe_insert("location", frame=frame)
    return True


def _draw_motion_path():
    points = _EDIT["points"]
    if not points:
        return
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        size = _EDIT.get("size", 0.05)
        line = _EDIT["line"]
        if len(line) > 1:
            batch = batch_for_shader(
                shader, "LINE_STRIP", {"pos": [p for _f, p in line]}
            )
            shader.bind()
            shader.uniform_float("color", (1.0, 0.55, 0.1, 0.85))
            batch.draw(shader)
        active = _EDIT.get("active", -1)
        idle, hot = [], []
        for index, (_frame, position) in enumerate(points):
            scale = size * (1.6 if index == active else 1.0)
            target = hot if index == active else idle
            for axis in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))):
                target.extend((position + axis * scale, position - axis * scale))
        for coords, color in (
            (idle, (1.0, 0.85, 0.25, 1.0)),
            (hot, (1.0, 1.0, 1.0, 1.0)),
        ):
            if not coords:
                continue
            batch = batch_for_shader(shader, "LINES", {"pos": coords})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
    except Exception:
        pass


class OPENANIM_OT_edit_motion_path(bpy.types.Operator):
    bl_idname = "openanim.edit_motion_path"
    bl_label = "Edit Motion Path"
    bl_description = (
        "Drag motion path points in the 3D Viewport to edit location keys"
    )
    bl_options = {"REGISTER", "UNDO"}

    def _redraw(self, context):
        for area in context.window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def _refresh(self, context):
        line, points = motion_path_points(context, self._ob, self._pb)
        _EDIT["line"] = line
        _EDIT["points"] = points
        _EDIT["active"] = -1
        extent = 0.0
        if len(line) > 1:
            first = line[0][1]
            extent = max((position - first).length for _f, position in line)
        _EDIT["size"] = max(0.01, extent * 0.01)
        self._redraw(context)

    def _point_at(self, event):
        best, best_distance = -1, 14.0
        mouse = Vector(
            (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
        )
        for index, (_frame, position) in enumerate(_EDIT["points"]):
            co = location_3d_to_region_2d(self._region, self._rv3d, position)
            if co is None:
                continue
            distance = (co - mouse).length
            if distance < best_distance:
                best, best_distance = index, distance
        return best

    def _world_on_plane(self, event):
        mouse = (event.mouse_x - self._region.x, event.mouse_y - self._region.y)
        origin = region_2d_to_origin_3d(self._region, self._rv3d, mouse)
        direction = region_2d_to_vector_3d(self._region, self._rv3d, mouse)
        denominator = direction.dot(self._plane_normal)
        if abs(denominator) < 1e-6:
            return None
        distance = (
            (self._plane_point - origin).dot(self._plane_normal) / denominator
        )
        return origin + direction * distance

    def _finish(self, context, cancelled):
        if cancelled:
            for frame, state in self._originals.items():
                motion_restore_state(context, self._ob, self._pb, frame, state)
        if _EDIT["handler"] is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(
                    _EDIT["handler"], "WINDOW"
                )
            except Exception:
                pass
        _EDIT.update(handler=None, points=[], line=[], active=-1)
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        self._redraw(context)
        return {"CANCELLED" if cancelled else "FINISHED"}

    def invoke(self, context, event):
        ob, pb = motion_target(context)
        if ob is None:
            self.report({"WARNING"}, "Select an object or bone")
            return {"CANCELLED"}
        if pb is not None and pb.bone.use_connect:
            self.report(
                {"WARNING"},
                "Connected bones cannot translate; edit the parent bone instead",
            )
            return {"CANCELLED"}
        area = context.area
        if area is None or area.type != "VIEW_3D":
            area = core.find_editor(context, {"VIEW_3D"})
        region = (
            next((r for r in area.regions if r.type == "WINDOW"), None)
            if area
            else None
        )
        if region is None or area.spaces.active.region_3d is None:
            self.report({"WARNING"}, "Run this from the 3D Viewport")
            return {"CANCELLED"}
        self._ob = ob
        self._pb = pb
        self._region = region
        self._rv3d = area.spaces.active.region_3d
        self._drag = -1
        self._originals = {}
        self._plane_point = Vector((0, 0, 0))
        self._plane_normal = self._rv3d.view_rotation @ Vector((0, 0, -1))
        if _EDIT["handler"] is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(
                    _EDIT["handler"], "WINDOW"
                )
            except Exception:
                pass
        _EDIT["handler"] = bpy.types.SpaceView3D.draw_handler_add(
            _draw_motion_path, (), "WINDOW", "POST_VIEW"
        )
        self._refresh(context)
        try:
            context.workspace.status_text_set(
                "Drag a point to edit its location key  |  Enter/RMB: finish  |  Esc: cancel"
            )
        except Exception:
            pass
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            if self._drag >= 0:
                world = self._world_on_plane(event)
                frame = _EDIT["points"][self._drag][0]
                if world is not None and motion_apply_point(
                    context, self._ob, self._pb, frame, world
                ):
                    _EDIT["points"][self._drag] = (frame, world.copy())
                    self._redraw(context)
            else:
                index = self._point_at(event)
                if index != _EDIT["active"]:
                    _EDIT["active"] = index
                    self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            index = self._point_at(event)
            if index >= 0:
                self._drag = index
                frame, position = _EDIT["points"][index]
                self._plane_point = position.copy()
                self._plane_normal = self._rv3d.view_rotation @ Vector((0, 0, -1))
                if int(frame) not in self._originals:
                    self._originals[int(frame)] = motion_capture_state(
                        context, self._ob, self._pb, frame
                    )
                _EDIT["active"] = index
                self._redraw(context)
            return {"RUNNING_MODAL"}
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            if self._drag >= 0:
                self._drag = -1
                self._refresh(context)
            return {"RUNNING_MODAL"}
        if event.type == "ESC":
            return self._finish(context, cancelled=True)
        if event.type in {"RET", "NUMPAD_ENTER", "RIGHTMOUSE"}:
            return self._finish(context, cancelled=False)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        self.report({"WARNING"}, "Run this from the 3D Viewport")
        return {"CANCELLED"}


# --------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------

def _simplify(fc, epsilon):
    points = [(kp.co.x, kp.co.y, kp) for kp in fc.keyframe_points]
    if len(points) < 3:
        return
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        x0, y0, _ = points[first]
        x1, y1, _ = points[last]
        span = x1 - x0
        best = -1.0
        index = -1
        for i in range(first + 1, last):
            x, y, _ = points[i]
            expected = y0 if span == 0 else y0 + (y1 - y0) * (x - x0) / span
            error = abs(y - expected)
            if error > best:
                best = error
                index = i
        if best > epsilon and index >= 0:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    for index in range(len(points) - 1, -1, -1):
        if not keep[index]:
            fc.keyframe_points.remove(fc.keyframe_points[index])
    fc.update()


def _euler_unwrap(context):
    groups = {}
    for ob, fc in core.target_fcurves(context):
        if not fc.data_path.endswith("rotation_euler"):
            continue
        key = (ob.name, core.fcurve_bone(fc.data_path), fc.data_path)
        groups.setdefault(key, {})[fc.array_index] = fc
    for fcurves in groups.values():
        if len(fcurves) < 1:
            continue
        for fc in fcurves.values():
            previous = None
            for kp in fc.keyframe_points:
                angle = kp.co.y
                if previous is not None:
                    while angle - previous > math.pi:
                        angle -= math.pi * 2
                    while angle - previous < -math.pi:
                        angle += math.pi * 2
                core.move_key_value(kp, angle)
                previous = angle
            fc.update()


class OPENANIM_OT_clean_curves(bpy.types.Operator):
    bl_idname = "openanim.clean_curves"
    bl_label = "Clean Curves"
    bl_description = "Remove redundant keys, baked keys, static channels or fix Euler rotations"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("REDUNDANT", "Clean Redundant Keys", ""),
            ("BAKED", "Clean Baked Keys", ""),
            ("STATIC", "Clean Static Channels", ""),
            ("EULER", "Apply Euler Filter", ""),
        ),
        default="REDUNDANT",
    )

    def execute(self, context):
        if self.mode == "EULER":
            _euler_unwrap(context)
            return {"FINISHED"}
        fcurves = _curve_subset(context)
        if not fcurves:
            self.report({"WARNING"}, "No animation in the selection")
            return {"CANCELLED"}
        if self.mode == "STATIC":
            targets = []
            for fc in fcurves:
                values = [kp.co.y for kp in fc.keyframe_points]
                if len(fc.modifiers) == 0 and (
                    len(values) <= 1 or max(values) - min(values) < 1e-6
                ):
                    targets.append((fc.id_data, fc.data_path, fc.array_index))
            for action, path, index in targets:
                core.remove_fcurve_path(action, path, index)
            return {"FINISHED"}
        epsilon = 0.0001 if self.mode == "REDUNDANT" else 0.01
        for fc in fcurves:
            _simplify(fc, epsilon)
        return {"FINISHED"}


# --------------------------------------------------------------------------
# Value operations
# --------------------------------------------------------------------------

def _mirror_value(kp, center):
    kp.co.y = 2 * center - kp.co.y
    kp.handle_left.y = 2 * center - kp.handle_left.y
    kp.handle_right.y = 2 * center - kp.handle_right.y


def _mirror_time(kp, center):
    kp.co.x = 2 * center - kp.co.x
    kp.handle_left.x = 2 * center - kp.handle_left.x
    kp.handle_right.x = 2 * center - kp.handle_right.x


class OPENANIM_OT_value_op(bpy.types.Operator):
    bl_idname = "openanim.value_op"
    bl_label = "Key Values"
    bl_description = "Zero, invert, negate or mirror the selected keys"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("ZERO", "Zero Out", ""),
            ("CURRENT", "Set to Current Value", ""),
            ("NEGATE", "Negate", ""),
            ("INVERT", "Invert", ""),
            ("INVERT_CURSOR", "Invert Over 2D Cursor", ""),
            ("INVERT_CF", "Invert Over Current Value", ""),
            ("MIRROR", "Mirror Values", ""),
            ("MIRROR_TIME", "Mirror Over Timeline Cursor", ""),
        ),
        default="ZERO",
    )

    def execute(self, context):
        points = _selected_value_points(context)
        if not points:
            self.report({"WARNING"}, "No keys selected")
            return {"CANCELLED"}
        frame = context.scene.frame_current
        by_curve = {}
        for fc, kp in points:
            by_curve.setdefault(fc, []).append(kp)
        cursor = core.graph_cursor_y(context)

        if self.mode == "MIRROR_TIME":
            times = [kp.co.x for _fc, kp in points]
            center = (min(times) + max(times)) * 0.5
            for fc, kp in points:
                _mirror_time(kp, center)
        elif self.mode == "INVERT_CURSOR":
            for fc, kp in points:
                _mirror_value(kp, cursor)
        elif self.mode in {"INVERT", "INVERT_CF", "MIRROR"}:
            for fc, keys in by_curve.items():
                if self.mode == "INVERT_CF":
                    center = fc.evaluate(frame)
                    for kp in keys:
                        _mirror_value(kp, center)
                else:
                    values = [kp.co.y for kp in keys]
                    center = (min(values) + max(values)) * 0.5
                    for kp in keys:
                        _mirror_value(kp, center)
        else:
            for fc, keys in by_curve.items():
                current = fc.evaluate(frame)  # before any key moves
                for kp in keys:
                    if self.mode == "ZERO":
                        core.move_key_value(kp, 0.0)
                    elif self.mode == "CURRENT":
                        core.move_key_value(kp, current)
                    else:  # NEGATE
                        core.move_key_value(kp, -kp.co.y)
        for fc in by_curve:
            core.sort_fcurve(fc)
        return {"FINISHED"}


# --------------------------------------------------------------------------
# Copy / paste keys
# --------------------------------------------------------------------------

class OPENANIM_OT_copy_keys(bpy.types.Operator):
    bl_idname = "openanim.copy_keys"
    bl_label = "Copy Keys"
    bl_description = "Copy the selected keys (or all keys) of the selection"
    bl_options = {"REGISTER"}

    def execute(self, context):
        global _CLIP
        _CLIP = []
        pairs = core.target_fcurves(context)
        if not pairs:
            self.report({"WARNING"}, "Nothing to copy")
            return {"CANCELLED"}
        selected = core.selected_keyframes([fc for _ob, fc in pairs])
        selected_curves = {fc.as_pointer() for fc, _kp in selected}
        for _ob, fc in pairs:
            keys = [
                kp
                for kp in fc.keyframe_points
                if not selected_curves or fc.as_pointer() in selected_curves
            ]
            if not keys:
                continue
            _CLIP.append(
                {
                    "path": fc.data_path,
                    "index": fc.array_index,
                    "keys": [
                        (kp.co.x, kp.co.y, kp.interpolation, kp.type) for kp in keys
                    ],
                }
            )
        if not _CLIP:
            self.report({"WARNING"}, "No keys to copy")
            return {"CANCELLED"}
        self.report({"INFO"}, "Copied %d channels" % len(_CLIP))
        return {"FINISHED"}


def _flip_value(path, index, value):
    if path.endswith("location") and index == 0:
        return -value
    if path.endswith("rotation_euler") and index in (1, 2):
        return -value
    if path.endswith("rotation_quaternion") and index in (1, 2, 3):
        return -value
    return value


class OPENANIM_OT_paste_keys(bpy.types.Operator):
    bl_idname = "openanim.paste_keys"
    bl_label = "Paste Keys"
    bl_description = "Paste the copied keys at the current frame"
    bl_options = {"REGISTER", "UNDO"}

    flipped: bpy.props.BoolProperty(default=False)
    offset: bpy.props.IntProperty(default=0)

    def execute(self, context):
        if not _CLIP:
            self.report({"WARNING"}, "Clipboard is empty - copy keys first")
            return {"CANCELLED"}
        target = context.object
        if target is None:
            self.report({"WARNING"}, "Select a target object")
            return {"CANCELLED"}
        scene_frame = context.scene.frame_current
        first = min(k[0] for entry in _CLIP for k in entry["keys"])
        for entry in _CLIP:
            path = entry["path"]
            if self.flipped:
                bone = core.fcurve_bone(path)
                if bone:
                    path = path.replace(
                        'pose.bones["%s"]' % bone,
                        'pose.bones["%s"]' % core.flip_bone_name(bone),
                        1,
                    )
            fc = core.ensure_fcurve(target, path, entry["index"])
            for frame, value, interpolation, key_type in entry["keys"]:
                new_frame = scene_frame + self.offset + (frame - first)
                new_value = _flip_value(path, entry["index"], value) if self.flipped else value
                kp = fc.keyframe_points.insert(new_frame, new_value)
                kp.interpolation = interpolation
                kp.type = key_type
            core.sort_fcurve(fc)
            core.dedupe_fcurve(fc)
        return {"FINISHED"}


# --------------------------------------------------------------------------
# Bake
# --------------------------------------------------------------------------

def _visual_local(ob, pb):
    if pb is not None:
        return ob.convert_space(
            pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL"
        )
    matrix = ob.matrix_world
    if ob.parent:
        matrix = (
            ob.matrix_parent_inverse.inverted()
            @ ob.parent.matrix_world.inverted()
            @ matrix
        )
    return matrix


def _rotation_values(rotation, mode, previous=None):
    if mode == "QUATERNION":
        quat = rotation.copy()
        if previous is not None and quat.dot(previous) < 0:
            quat.negate()
        return [quat.w, quat.x, quat.y, quat.z], quat
    if mode == "AXIS_ANGLE":
        axis, angle = rotation.to_axis_angle()
        return [angle, axis.x, axis.y, axis.z], None
    euler = rotation.to_euler(mode)
    return [euler.x, euler.y, euler.z], None


def _bake_targets(context):
    ob = context.object
    bones = core.target_bones(context)
    if ob and ob.type == "ARMATURE" and bones:
        return [(ob, pb) for pb in bones]
    return [(o, None) for o in core.target_objects(context)]


def _bake_animation(context, start, end, step):
    targets = _bake_targets(context)
    if not targets:
        return False
    scene = context.scene
    original = scene.frame_current
    collected = []
    for ob, pb in targets:
        frames = []
        previous_quat = None
        for frame in range(int(start), int(end) + 1, max(1, step)):
            scene.frame_set(frame)
            context.view_layer.update()
            matrix = _visual_local(ob, pb)
            location, rotation, scale = matrix.decompose()
            mode = pb.rotation_mode if pb else ob.rotation_mode
            rot_values, previous_quat = _rotation_values(rotation, mode, previous_quat)
            frames.append((frame, location, rot_values, scale))
        collected.append((ob, pb, mode, frames))
    scene.frame_set(original)

    for ob, pb, mode, frames in collected:
        channels, _ = core.transform_channels(ob, pb)
        if mode == "QUATERNION":
            rot_path, rot_count = channels[1]
        elif mode == "AXIS_ANGLE":
            rot_path, rot_count = channels[1]
        else:
            rot_path, rot_count = channels[1]
        data = {
            channels[0][0]: (3, [f[1] for f in frames]),
            rot_path: (rot_count, [f[2] for f in frames]),
            channels[2][0]: (3, [f[3] for f in frames]),
        }
        for path, (count, values) in data.items():
            for index in range(count):
                fc = core.ensure_fcurve(ob, path, index)
                fc.keyframe_points.clear()
                for frame_data, vector in zip(frames, values):
                    fc.keyframe_points.insert(
                        frame_data[0], vector[index] if hasattr(vector, "__len__") else vector
                    ).interpolation = "LINEAR"
                fc.update()
    return True


class OPENANIM_OT_bake(bpy.types.Operator):
    bl_idname = "openanim.bake"
    bl_label = "Bake"
    bl_description = "Bake transforms, selected curves or a curve to a timing pattern"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("ANIMATION", "Bake Animation", ""),
            ("CURVES", "Bake Selected Curves", ""),
            ("PATTERN", "Bake to Timing Pattern", ""),
        ),
        default="ANIMATION",
    )
    step: bpy.props.IntProperty(default=1, min=1, max=100)

    def execute(self, context):
        start, end = core.smart_range(context)
        if self.mode == "ANIMATION":
            if not _bake_animation(context, start, end, self.step):
                self.report({"WARNING"}, "Select objects or bones to bake")
                return {"CANCELLED"}
            return {"FINISHED"}

        fcurves = _curve_subset(context)
        if not fcurves:
            self.report({"WARNING"}, "No curves to bake")
            return {"CANCELLED"}
        if self.mode == "CURVES":
            for fc in fcurves:
                frames = [kp.co.x for kp in fc.keyframe_points]
                if len(frames) < 2:
                    continue
                samples = [
                    (frame, fc.evaluate(frame))
                    for frame in range(int(start), int(end) + 1, self.step)
                ]
                fc.keyframe_points.clear()
                for frame, value in samples:
                    fc.keyframe_points.insert(frame, value).interpolation = "LINEAR"
                fc.update()
            return {"FINISHED"}

        selected = _selected_value_points(context)
        if not selected:
            self.report({"WARNING"}, "Select the keys that define the timing pattern")
            return {"CANCELLED"}
        pattern = sorted({kp.co.x for _fc, kp in selected})
        for fc in fcurves:
            samples = [(frame, fc.evaluate(frame)) for frame in pattern]
            fc.keyframe_points.clear()
            for frame, value in samples:
                fc.keyframe_points.insert(frame, value)
            fc.update()
        return {"FINISHED"}


CLASSES = (
    OPENANIM_OT_breakdown,
    OPENANIM_OT_blend,
    OPENANIM_OT_ghost,
    OPENANIM_OT_motion_paths,
    OPENANIM_OT_edit_motion_path,
    OPENANIM_OT_clean_curves,
    OPENANIM_OT_value_op,
    OPENANIM_OT_copy_keys,
    OPENANIM_OT_paste_keys,
    OPENANIM_OT_bake,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    if _EDIT["handler"] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_EDIT["handler"], "WINDOW")
        except Exception:
            pass
        _EDIT["handler"] = None
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
