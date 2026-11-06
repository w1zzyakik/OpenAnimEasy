"""Timing, interpolation and editor tools."""

import bpy

from . import core

I18N = "OpenAnimEasy"


class OPENANIM_OT_toggle_editor(bpy.types.Operator):
    bl_idname = "openanim.toggle_editor"
    bl_label = "Toggle Timeline / Graph Editor"
    bl_description = "Switch the active animation editor between Timeline and Graph Editor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        area = core.find_editor(context, {"DOPESHEET_EDITOR", "GRAPH_EDITOR"})
        if not area:
            self.report({"WARNING"}, "No Timeline or Graph Editor found")
            return {"CANCELLED"}
        space = area.spaces.active
        if area.type == "DOPESHEET_EDITOR":
            area.type = "GRAPH_EDITOR"
            space.mode = "FCURVES"
        else:
            area.type = "DOPESHEET_EDITOR"
            space.mode = "TIMELINE"
        return {"FINISHED"}


class OPENANIM_OT_fast_frame_range(bpy.types.Operator):
    bl_idname = "openanim.fast_frame_range"
    bl_label = "Fast Frame Range"
    bl_description = "Drag in the timeline to set the scene frame range"
    bl_options = {"REGISTER", "UNDO"}

    def _set(self, context, event):
        frame = int(round(core.frame_from_event(context, event)))
        start, end = sorted((self._anchor, frame))
        context.scene.frame_start = start
        context.scene.frame_end = max(start, end)

    def invoke(self, context, event):
        area = core.find_editor(context, {"DOPESHEET_EDITOR", "GRAPH_EDITOR"})
        if not area or core.window_region(context) is None:
            self.report({"WARNING"}, "Run this from the Timeline")
            return {"CANCELLED"}
        self._area = area
        self._anchor = int(round(core.frame_from_event(context, event)))
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            self._set(context, event)
            return {"RUNNING_MODAL"}
        if event.type in {"LEFTMOUSE", "RET", "NUMPAD_ENTER"}:
            self._set(context, event)
            return {"FINISHED"}
        if event.type in {"RIGHTMOUSE", "ESC"}:
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        start, end = core.smart_range(context, selected_only=True)
        context.scene.frame_start = int(start)
        context.scene.frame_end = int(end)
        return {"FINISHED"}


class OPENANIM_OT_frame_view(bpy.types.Operator):
    bl_idname = "openanim.frame_view"
    bl_label = "Frame View"
    bl_description = "Frame animation, show animated channels or manage the preview range"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("ALL", "Frame All", "Frame the whole keyframe range"),
            ("ANIMATED", "Show Animated", "Show only animated F-Curves"),
            ("SELECTED", "Show Selected", "Show only F-Curves of the selection"),
            ("PREVIEW_SET", "Set Preview Range", "Set preview range to the selected keys"),
            ("PREVIEW_CLEAR", "Clear Preview Range", "Disable the preview range"),
        ),
        default="ALL",
    )

    def execute(self, context):
        scene = context.scene
        if self.action == "PREVIEW_CLEAR":
            scene.use_preview_range = False
            return {"FINISHED"}
        if self.action == "PREVIEW_SET":
            start, end = core.smart_range(context, selected_only=True)
            scene.use_preview_range = True
            scene.frame_preview_start = int(start)
            scene.frame_preview_end = int(end)
            return {"FINISHED"}
        if self.action in {"ANIMATED", "SELECTED"}:
            pairs = core.target_fcurves(context)
            if not pairs:
                self.report({"WARNING"}, "Nothing animated in the selection")
                return {"CANCELLED"}
            selected = {fc.as_pointer() for _ob, fc in pairs}
            everything = []
            for ob in core.target_objects(context):
                action = core.action_of(ob)
                if action:
                    everything.extend(
                        core.action_fcurves(action, core.slot_of(ob, action))
                    )
            for fc in everything:
                if self.action == "ANIMATED":
                    show = len(fc.keyframe_points) > 0
                else:
                    show = fc.as_pointer() in selected
                fc.hide = not show
                fc.select = show
            core.call_view_op(
                context, "graph", "view_selected", {"GRAPH_EDITOR"}
            )
            return {"FINISHED"}
        area = core.find_editor(context, {"DOPESHEET_EDITOR", "GRAPH_EDITOR"})
        if not area:
            self.report({"WARNING"}, "No animation editor found")
            return {"CANCELLED"}
        if area.type == "GRAPH_EDITOR":
            ok = core.call_view_op(context, "graph", "view_all", {"GRAPH_EDITOR"})
        else:
            ok = core.call_view_op(
                context, "action", "view_all", {"DOPESHEET_EDITOR"}
            )
        if not ok:
            self.report({"WARNING"}, "Could not frame the view")
            return {"CANCELLED"}
        return {"FINISHED"}


class OPENANIM_OT_select_keys_side(bpy.types.Operator):
    bl_idname = "openanim.select_keys_side"
    bl_label = "Select Keys Left / Right"
    bl_description = "Select keys before or after the current frame"
    bl_options = {"REGISTER", "UNDO"}

    side: bpy.props.EnumProperty(items=(("LEFT", "Left", ""), ("RIGHT", "Right", "")))

    def execute(self, context):
        frame = context.scene.frame_current
        pairs = core.target_fcurves(context)
        if not pairs:
            return {"CANCELLED"}
        for _ob, fc in pairs:
            for kp in fc.keyframe_points:
                kp.select_control_point = (
                    kp.co.x < frame if self.side == "LEFT" else kp.co.x > frame
                )
        return {"FINISHED"}


class OPENANIM_OT_snap_keys(bpy.types.Operator):
    bl_idname = "openanim.snap_keys"
    bl_label = "Snap Keys"
    bl_description = "Snap selected keys to the current frame"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("CURRENT", "To Current Frame", "Move each selected key to the current frame"),
            ("FIRST", "From First", "Align the first selected key to the current frame"),
            ("LAST", "From Last", "Align the last selected key to the current frame"),
        ),
        default="CURRENT",
    )

    def execute(self, context):
        frame = context.scene.frame_current
        points = core.selected_keyframes(
            [fc for _ob, fc in core.target_fcurves(context)]
        )
        if not points:
            self.report({"WARNING"}, "No keys selected")
            return {"CANCELLED"}
        if self.mode == "CURRENT":
            for fc, kp in points:
                core.move_key_time(kp, frame)
        else:
            anchor = min(kp.co.x for _fc, kp in points) if self.mode == "FIRST" else max(
                kp.co.x for _fc, kp in points
            )
            delta = frame - anchor
            for fc, kp in points:
                core.move_key_time(kp, kp.co.x + delta)
        for fc in {fc for fc, _kp in points}:
            core.sort_fcurve(fc)
        return {"FINISHED"}


class OPENANIM_OT_move_keys(bpy.types.Operator):
    bl_idname = "openanim.move_keys"
    bl_label = "Move Keys"
    bl_description = "Move selected keys by whole frames"
    bl_options = {"REGISTER", "UNDO"}

    direction: bpy.props.EnumProperty(items=(("LEFT", "Left", ""), ("RIGHT", "Right", "")))
    frames: bpy.props.IntProperty(default=1, min=1)

    def execute(self, context):
        delta = -self.frames if self.direction == "LEFT" else self.frames
        points = core.selected_keyframes(
            [fc for _ob, fc in core.target_fcurves(context)]
        )
        if not points:
            self.report({"WARNING"}, "No keys selected")
            return {"CANCELLED"}
        for fc, kp in points:
            core.move_key_time(kp, kp.co.x + delta)
        for fc in {fc for fc, _kp in points}:
            core.sort_fcurve(fc)
        return {"FINISHED"}


class OPENANIM_OT_inbetween(bpy.types.Operator):
    bl_idname = "openanim.inbetween"
    bl_label = "Inbetween"
    bl_description = "Set an even inbetween, or add / remove an empty frame between keys"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("SET", "Set Even Inbetween", ""),
            ("ADD", "Add Inbetween", ""),
            ("REMOVE", "Remove Inbetween", ""),
        ),
        default="SET",
    )
    frames: bpy.props.IntProperty(default=1, min=1)

    def execute(self, context):
        pairs = core.target_fcurves(context)
        if not pairs:
            self.report({"WARNING"}, "No animation in the selection")
            return {"CANCELLED"}
        frame = context.scene.frame_current
        if self.mode == "SET":
            points = core.selected_keyframes([fc for _ob, fc in pairs])
            if not points:
                self.report({"WARNING"}, "Select the inbetween keys first")
                return {"CANCELLED"}
            for fc, kp in points:
                index = core.key_index(fc, kp)
                if index <= 0 or index >= len(fc.keyframe_points) - 1:
                    continue
                left = fc.keyframe_points[index - 1].co.x
                right = fc.keyframe_points[index + 1].co.x
                core.move_key_time(kp, (left + right) * 0.5)
            for fc in {fc for fc, _kp in points}:
                core.sort_fcurve(fc)
            return {"FINISHED"}
        delta = self.frames if self.mode == "ADD" else -self.frames
        for _ob, fc in pairs:
            for kp in fc.keyframe_points:
                if kp.co.x >= frame:
                    core.move_key_time(kp, kp.co.x + delta)
            core.sort_fcurve(fc)
        return {"FINISHED"}


class OPENANIM_OT_key_type(bpy.types.Operator):
    bl_idname = "openanim.key_type"
    bl_label = "Add Keyframe Type"
    bl_description = "Insert a keyframe of the chosen type at the current frame"
    bl_options = {"REGISTER", "UNDO"}

    type: bpy.props.EnumProperty(
        items=(
            ("KEYFRAME", "Keyframe", ""),
            ("BREAKDOWN", "Breakdown", ""),
            ("MOVING_HOLD", "Moving Hold", ""),
            ("EXTREME", "Extreme", ""),
            ("JITTER", "Jitter", ""),
        ),
        default="KEYFRAME",
    )

    def execute(self, context):
        frame = context.scene.frame_current
        bones = core.target_bones(context)
        if bones:
            ob = context.object
            for pb in bones:
                existing = {
                    (fc.data_path, fc.array_index): fc
                    for _o, fc in core.target_fcurves(context)
                    if core.fcurve_bone(fc.data_path) == pb.name
                }
                for path, count in core.transform_channels(ob, pb)[0]:
                    for index in range(count):
                        key = (path, index)
                        fc = existing.get(key)
                        if fc is None:
                            fc = core.ensure_fcurve(ob, path, index)
                        core.insert_key(fc, frame, key_type=self.type)
            return {"FINISHED"}
        objects = core.target_objects(context)
        if not objects:
            self.report({"WARNING"}, "Select an object or bone")
            return {"CANCELLED"}
        for ob in objects:
            core.insert_transform_keys(ob, None, frame, self.type)
        return {"FINISHED"}


class OPENANIM_OT_delete_keys(bpy.types.Operator):
    bl_idname = "openanim.delete_keys"
    bl_label = "Delete Keys"
    bl_description = "Delete keys at the current frame or the selected keys"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(
            ("CURRENT", "Current Frame", ""),
            ("SELECTED", "Selected", ""),
            ("ALL", "All Keys", ""),
        ),
        default="SELECTED",
    )

    def execute(self, context):
        frame = context.scene.frame_current
        pairs = core.target_fcurves(context)
        if not pairs:
            self.report({"WARNING"}, "No animation in the selection")
            return {"CANCELLED"}
        for _ob, fc in pairs:
            doomed = []
            for kp in fc.keyframe_points:
                if (
                    self.mode == "ALL"
                    or (self.mode == "CURRENT" and abs(kp.co.x - frame) < 1e-4)
                    or (self.mode == "SELECTED" and kp.select_control_point)
                ):
                    doomed.append(core.key_index(fc, kp))
            for index in sorted(doomed, reverse=True):
                fc.keyframe_points.remove(fc.keyframe_points[index])
            fc.update()
        return {"FINISHED"}


class OPENANIM_OT_clean_animation(bpy.types.Operator):
    bl_idname = "openanim.clean_animation"
    bl_label = "Clean Animation"
    bl_description = "Remove every animated channel from the selected objects or bones"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        pairs = core.target_fcurves(context)
        if not pairs:
            self.report({"WARNING"}, "Nothing to clean")
            return {"CANCELLED"}
        targets = [(fc.id_data, fc.data_path, fc.array_index) for _ob, fc in pairs]
        for action, path, index in targets:
            core.remove_fcurve_path(action, path, index)
        return {"FINISHED"}

class OPENANIM_OT_crop_animation(bpy.types.Operator):
    bl_idname = "openanim.crop_animation"
    bl_label = "Crop Animation"
    bl_description = "Remove keys outside the scene or preview frame range"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        if scene.use_preview_range:
            start, end = scene.frame_preview_start, scene.frame_preview_end
        else:
            start, end = scene.frame_start, scene.frame_end
        pairs = core.target_fcurves(context)
        if not pairs:
            return {"CANCELLED"}
        for _ob, fc in pairs:
            doomed = [
                core.key_index(fc, kp)
                for kp in fc.keyframe_points
                if kp.co.x < start or kp.co.x > end
            ]
            for index in sorted(doomed, reverse=True):
                fc.keyframe_points.remove(fc.keyframe_points[index])
            fc.update()
        return {"FINISHED"}


class OPENANIM_OT_share_times(bpy.types.Operator):
    bl_idname = "openanim.share_times"
    bl_label = "Share Key Times"
    bl_description = "Copy key timing from the active object / bone to the other selected ones"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        items=(("FIRST", "From First Selected", ""), ("LAST", "From Last Selected", "")),
        default="LAST",
    )

    def _groups(self, context):
        groups = {}
        for ob, fc in core.target_fcurves(context):
            key = (ob.name, core.fcurve_bone(fc.data_path))
            groups.setdefault(key, []).append(fc)
        return groups

    def execute(self, context):
        groups = self._groups(context)
        if len(groups) < 2:
            self.report({"WARNING"}, "Select at least two animated objects or bones")
            return {"CANCELLED"}
        active = context.object
        active_bone = core.active_bone(context)
        def score(item):
            key, fcurves = item
            pts = [kp.co.x for fc in fcurves for kp in fc.keyframe_points]
            if not pts:
                return (9, 0)
            is_active = key[0] == (active.name if active else "") and key[1] == (
                active_bone.name if active_bone else None
            )
            return (0 if is_active else 1, min(pts))
        ordered = sorted(groups.items(), key=score)
        leader = ordered[0] if self.mode == "LAST" else (ordered[-1] if len(ordered) > 1 else ordered[0])
        leader_times = sorted({kp.co.x for fc in leader[1] for kp in fc.keyframe_points})
        if not leader_times:
            self.report({"WARNING"}, "The leader has no keys")
            return {"CANCELLED"}
        for key, fcurves in groups.items():
            if key == leader[0]:
                continue
            times = sorted({kp.co.x for fc in fcurves for kp in fc.keyframe_points})
            if len(times) == len(leader_times):
                mapping = dict(zip(times, leader_times))
            else:
                mapping = {}
                for index, time in enumerate(times):
                    mapped = leader_times[min(index, len(leader_times) - 1)]
                    mapping[time] = mapped
            for fc in fcurves:
                for kp in fc.keyframe_points:
                    if kp.co.x in mapping:
                        core.move_key_time(kp, mapping[kp.co.x])
                core.sort_fcurve(fc)
                core.dedupe_fcurve(fc)
        return {"FINISHED"}


class OPENANIM_OT_time_offset(bpy.types.Operator):
    bl_idname = "openanim.time_offset"
    bl_label = "Time Offset"
    bl_description = "Drag horizontally to offset the selected keys in time"
    bl_options = {"REGISTER", "UNDO"}

    frame_offset: bpy.props.IntProperty(default=1)

    def _points(self, context):
        pairs = core.target_fcurves(context)
        points = core.selected_keyframes([fc for _ob, fc in pairs])
        if not points:
            points = core.all_keyframes([fc for _ob, fc in pairs])
        return points

    def _apply(self, delta):
        for fc, index, original in self._orig:
            if index < len(fc.keyframe_points):
                core.move_key_time(fc.keyframe_points[index], original + delta)
        for fc in {fc for fc, _index, _original in self._orig}:
            fc.update()

    def _finish(self):
        for fc in {fc for fc, _index, _original in self._orig}:
            core.sort_fcurve(fc)
            core.dedupe_fcurve(fc)

    def invoke(self, context, event):
        if context.area is None or context.region is None:
            return self.execute(context)
        points = self._points(context)
        if not points:
            self.report({"WARNING"}, "No keys to offset")
            return {"CANCELLED"}
        self._orig = [
            (fc, core.key_index(fc, kp), kp.co.x) for fc, kp in points
        ]
        self._anchor = core.frame_from_event(context, event)
        self._delta = 0
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "MOUSEMOVE":
            delta = int(round(core.frame_from_event(context, event) - self._anchor))
            if delta != self._delta:
                self._apply(delta)
                self._delta = delta
            return {"RUNNING_MODAL"}
        if event.type in {"LEFTMOUSE", "RET", "NUMPAD_ENTER"}:
            self._finish()
            return {"FINISHED"}
        if event.type in {"RIGHTMOUSE", "ESC"}:
            self._apply(0)
            self._finish()
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def execute(self, context):
        points = self._points(context)
        if not points:
            self.report({"WARNING"}, "No keys to offset")
            return {"CANCELLED"}
        for fc, kp in points:
            core.move_key_time(kp, kp.co.x + self.frame_offset)
        for fc in {fc for fc, _kp in points}:
            core.sort_fcurve(fc)
        return {"FINISHED"}


class OPENANIM_OT_interpolation(bpy.types.Operator):
    bl_idname = "openanim.interpolation"
    bl_label = "Set Interpolation"
    bl_description = "Set the interpolation of the selected keys"
    bl_options = {"REGISTER", "UNDO"}

    type: bpy.props.EnumProperty(
        items=(
            ("CONSTANT", "Constant", ""),
            ("LINEAR", "Linear", ""),
            ("BEZIER", "Bezier", ""),
            ("SINE", "Sine", ""),
            ("QUAD", "Quad", ""),
            ("CUBIC", "Cubic", ""),
            ("QUART", "Quart", ""),
            ("QUINT", "Quint", ""),
            ("EXPO", "Expo", ""),
            ("CIRC", "Circ", ""),
            ("BACK", "Back", ""),
            ("BOUNCE", "Bounce", ""),
            ("ELASTIC", "Elastic", ""),
        ),
        default="BEZIER",
    )

    def execute(self, context):
        points = core.selected_keyframes(
            [fc for _ob, fc in core.target_fcurves(context)]
        )
        if not points:
            self.report({"WARNING"}, "No keys selected")
            return {"CANCELLED"}
        for fc, kp in points:
            kp.interpolation = self.type
        for fc in {fc for fc, _kp in points}:
            fc.update()
        return {"FINISHED"}


class OPENANIM_OT_handle_type(bpy.types.Operator):
    bl_idname = "openanim.handle_type"
    bl_label = "Set Handle Type"
    bl_description = "Set the handle type of the selected keys"
    bl_options = {"REGISTER", "UNDO"}

    type: bpy.props.EnumProperty(
        items=(
            ("AUTO", "Auto", ""),
            ("AUTO_CLAMPED", "Auto Clamped", ""),
            ("VECTOR", "Vector", ""),
            ("FREE", "Free", ""),
            ("ALIGNED", "Aligned", ""),
        ),
        default="AUTO_CLAMPED",
    )

    def execute(self, context):
        points = core.selected_keyframes(
            [fc for _ob, fc in core.target_fcurves(context)]
        )
        if not points:
            self.report({"WARNING"}, "No keys selected")
            return {"CANCELLED"}
        for fc, kp in points:
            kp.handle_left_type = self.type
            kp.handle_right_type = self.type
        for fc in {fc for fc, _kp in points}:
            fc.keyframe_points.handles_recalc()
            fc.update()
        return {"FINISHED"}


class OPENANIM_OT_nudge_value(bpy.types.Operator):
    bl_idname = "openanim.nudge_value"
    bl_label = "Nudge Key Value"
    bl_description = "Increase or decrease selected key values by a small amount"
    bl_options = {"REGISTER", "UNDO"}

    direction: bpy.props.EnumProperty(items=(("UP", "Increase", ""), ("DOWN", "Decrease", "")))
    amount: bpy.props.FloatProperty(default=0.01)

    def execute(self, context):
        points = core.selected_keyframes(
            [fc for _ob, fc in core.target_fcurves(context)]
        )
        if not points:
            self.report({"WARNING"}, "No keys selected")
            return {"CANCELLED"}
        delta = self.amount if self.direction == "UP" else -self.amount
        for fc, kp in points:
            core.move_key_value(kp, kp.co.y + delta)
        for fc in {fc for fc, _kp in points}:
            fc.update()
        return {"FINISHED"}


class OPENANIM_OT_marker(bpy.types.Operator):
    bl_idname = "openanim.marker"
    bl_label = "Timeline Marker"
    bl_description = "Add or remove timeline markers"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("ADD", "Add Marker", ""),
            ("REMOVE_CURRENT", "Remove Current Marker", ""),
            ("REMOVE_SELECTED", "Remove Selected Markers", ""),
            ("REMOVE_ALL", "Remove All Markers", ""),
        ),
        default="ADD",
    )
    name: bpy.props.StringProperty(default="")

    def execute(self, context):
        markers = context.scene.timeline_markers
        frame = context.scene.frame_current
        if self.action == "ADD":
            if any(abs(m.frame - frame) < 1e-4 for m in markers):
                self.report({"WARNING"}, "A marker already exists at this frame")
                return {"CANCELLED"}
            name = self.name or "Marker"
            markers.new(name, frame=frame)
        elif self.action == "REMOVE_CURRENT":
            for marker in [m for m in markers if abs(m.frame - frame) < 1e-4]:
                markers.remove(marker)
        elif self.action == "REMOVE_SELECTED":
            for marker in [m for m in markers if m.select]:
                markers.remove(marker)
        else:
            markers.clear()
        return {"FINISHED"}


CLASSES = (
    OPENANIM_OT_toggle_editor,
    OPENANIM_OT_fast_frame_range,
    OPENANIM_OT_frame_view,
    OPENANIM_OT_select_keys_side,
    OPENANIM_OT_snap_keys,
    OPENANIM_OT_move_keys,
    OPENANIM_OT_inbetween,
    OPENANIM_OT_key_type,
    OPENANIM_OT_delete_keys,
    OPENANIM_OT_clean_animation,
    OPENANIM_OT_crop_animation,
    OPENANIM_OT_share_times,
    OPENANIM_OT_time_offset,
    OPENANIM_OT_interpolation,
    OPENANIM_OT_handle_type,
    OPENANIM_OT_nudge_value,
    OPENANIM_OT_marker,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
