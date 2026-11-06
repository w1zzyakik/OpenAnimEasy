"""Menus, side panels and preferences."""

import bpy

from . import library

ADDON_KEY = __package__


def get_prefs(context):
    addon = context.preferences.addons.get(ADDON_KEY)
    return addon.preferences if addon else None


class OPENANIM_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_KEY

    show_headers: bpy.props.BoolProperty(
        name="Header menu", default=True,
        description="Add the OpenAnimEasy menu to animation editor headers",
    )
    show_timing: bpy.props.BoolProperty(name="Timing", default=True)
    show_curves: bpy.props.BoolProperty(name="Curves", default=True)
    show_spacing: bpy.props.BoolProperty(name="Spacing", default=True)
    show_pose: bpy.props.BoolProperty(name="Posing", default=True)
    show_scene: bpy.props.BoolProperty(name="Markers / Constraints / Space", default=True)
    show_library: bpy.props.BoolProperty(name="Library", default=True)
    gizmo_step: bpy.props.IntProperty(name="Gizmo Step", default=5, min=1, max=50)
    ghost_frames: bpy.props.IntProperty(name="Ghost Frames", default=5, min=1, max=120)
    bake_step: bpy.props.IntProperty(name="Bake Step", default=1, min=1, max=100)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Toolbar sections")
        col.prop(self, "show_headers")
        grid = col.grid_flow(row_major=True, columns=2, even_columns=True)
        grid.prop(self, "show_timing")
        grid.prop(self, "show_curves")
        grid.prop(self, "show_spacing")
        grid.prop(self, "show_pose")
        grid.prop(self, "show_scene")
        grid.prop(self, "show_library")
        row = layout.row()
        row.prop(self, "gizmo_step")
        row.prop(self, "ghost_frames")
        layout.prop(self, "bake_step")
        layout.label(text="Library: " + library._root(), icon="FILE_FOLDER")


# --------------------------------------------------------------------------
# Menus
# --------------------------------------------------------------------------

class OPENANIM_MT_snap(bpy.types.Menu):
    bl_label = "Snap Keys"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.snap_keys", text="To Current Frame").mode = "CURRENT"
        col.operator("openanim.snap_keys", text="From First Selected").mode = "FIRST"
        col.operator("openanim.snap_keys", text="From Last Selected").mode = "LAST"


class OPENANIM_MT_inbetween(bpy.types.Menu):
    bl_label = "Inbetween"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.inbetween", text="Set Even Inbetween").mode = "SET"
        col.operator("openanim.inbetween", text="Add Empty Frame").mode = "ADD"
        col.operator("openanim.inbetween", text="Remove Empty Frame").mode = "REMOVE"


class OPENANIM_MT_keytype(bpy.types.Menu):
    bl_label = "Add Key Type"

    def draw(self, context):
        for key_type, label in (
            ("KEYFRAME", "Keyframe"),
            ("BREAKDOWN", "Breakdown"),
            ("MOVING_HOLD", "Moving Hold"),
            ("EXTREME", "Extreme"),
            ("JITTER", "Jitter"),
        ):
            self.layout.operator("openanim.key_type", text=label).type = key_type


class OPENANIM_MT_delete(bpy.types.Menu):
    bl_label = "Delete Keys"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.delete_keys", text="Delete Current Key").mode = "CURRENT"
        col.operator("openanim.delete_keys", text="Delete Selected Keys").mode = "SELECTED"
        col.operator("openanim.delete_keys", text="Delete All Keys").mode = "ALL"


class OPENANIM_MT_interp(bpy.types.Menu):
    bl_label = "Interpolation"

    def draw(self, context):
        col = self.layout.column()
        for value, label in (
            ("CONSTANT", "Constant"),
            ("LINEAR", "Linear"),
            ("BEZIER", "Bezier"),
            ("SINE", "Sine"),
            ("QUAD", "Quad"),
            ("CUBIC", "Cubic"),
            ("EXPO", "Expo"),
            ("BACK", "Back"),
            ("BOUNCE", "Bounce"),
            ("ELASTIC", "Elastic"),
        ):
            col.operator("openanim.interpolation", text=label).type = value


class OPENANIM_MT_handle(bpy.types.Menu):
    bl_label = "Handles"

    def draw(self, context):
        col = self.layout.column()
        for value, label in (
            ("AUTO", "Auto"),
            ("AUTO_CLAMPED", "Auto Clamped"),
            ("VECTOR", "Vector"),
            ("FREE", "Free"),
            ("ALIGNED", "Aligned"),
        ):
            col.operator("openanim.handle_type", text=label).type = value


class OPENANIM_MT_values(bpy.types.Menu):
    bl_label = "Key Values"

    def draw(self, context):
        col = self.layout.column()
        for value, label in (
            ("ZERO", "Zero Out"),
            ("CURRENT", "Set to Current Value"),
            ("NEGATE", "Negate"),
            ("INVERT", "Invert"),
            ("INVERT_CURSOR", "Invert Over 2D Cursor"),
            ("INVERT_CF", "Invert Over Current Value"),
            ("MIRROR", "Mirror Values"),
            ("MIRROR_TIME", "Mirror Over Timeline Cursor"),
        ):
            col.operator("openanim.value_op", text=label).mode = value


class OPENANIM_MT_clean(bpy.types.Menu):
    bl_label = "Clean Up"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.clean_curves", text="Clean Redundant Keys").mode = "REDUNDANT"
        col.operator("openanim.clean_curves", text="Clean Baked Keys").mode = "BAKED"
        col.operator("openanim.clean_curves", text="Clean Static Channels").mode = "STATIC"
        col.operator("openanim.clean_curves", text="Apply Euler Filter").mode = "EULER"
        col.separator()
        col.operator("openanim.clean_animation", text="Clean Animation")


class OPENANIM_MT_bake(bpy.types.Menu):
    bl_label = "Bake"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.bake", text="Bake Animation").mode = "ANIMATION"
        col.operator("openanim.bake", text="Bake Selected Curves").mode = "CURVES"
        col.operator("openanim.bake", text="Bake to Timing Pattern").mode = "PATTERN"


class OPENANIM_MT_blend(bpy.types.Menu):
    bl_label = "Blend / Spacing"

    def draw(self, context):
        col = self.layout.column()
        for value, label in (
            ("NEIGHBOR", "Blend to Neighbor"),
            ("DEFAULT", "Blend to Default"),
            ("AVERAGE", "Blend Average"),
            ("EASE_IN", "Ease In"),
            ("EASE_OUT", "Ease Out"),
            ("SMOOTH", "Smooth"),
            ("PUSH", "Push"),
            ("PULL", "Pull"),
        ):
            col.operator("openanim.blend", text=label).mode = value


class OPENANIM_MT_marker(bpy.types.Menu):
    bl_label = "Markers"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.marker", text="Add Marker", icon="MARKER").action = "ADD"
        col.operator("openanim.marker", text="Remove Current Marker").action = "REMOVE_CURRENT"
        col.operator("openanim.marker", text="Remove Selected Markers").action = "REMOVE_SELECTED"
        col.operator("openanim.marker", text="Remove All Markers").action = "REMOVE_ALL"


class OPENANIM_MT_childof(bpy.types.Menu):
    bl_label = "Child Of"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.childof", text="Create Child Of").action = "CREATE"
        col.operator("openanim.childof", text="Toggle Child Of").action = "TOGGLE"
        col.operator("openanim.childof", text="Bake Child Of").action = "BAKE"
        col.operator("openanim.childof", text="Clear Child Of").action = "CLEAR"


class OPENANIM_MT_space(bpy.types.Menu):
    bl_label = "Space Conversion"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.space_convert", text="Local to World").mode = "TO_WORLD"
        col.operator("openanim.space_convert", text="World to Local (Bake)").mode = "TO_LOCAL"


class OPENANIM_MT_motion(bpy.types.Menu):
    bl_label = "Motion Paths"

    def draw(self, context):
        col = self.layout.column()
        col.operator("openanim.motion_paths", text="Show Motion Paths").action = "SHOW"
        col.operator("openanim.motion_paths", text="Update All Motion Paths").action = "UPDATE"
        col.operator("openanim.motion_paths", text="Clear All Motion Paths").action = "CLEAR"
        col.separator()
        col.operator(
            "openanim.edit_motion_path",
            text="Edit Motion Path (Drag)",
            icon="CURVE_PATH",
        )


class OPENANIM_MT_root(bpy.types.Menu):
    bl_label = "OpenAnimEasy"

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.operator("openanim.toggle_editor", text="Toggle Timeline / Graph", icon="GRAPH")
        col.separator()
        col.menu("OPENANIM_MT_snap", text="Snap Keys", icon="SNAP_ON")
        col.menu("OPENANIM_MT_inbetween", text="Inbetween", icon="SORTTIME")
        col.menu("OPENANIM_MT_keytype", text="Add Key Type", icon="KEYFRAME")
        col.menu("OPENANIM_MT_delete", text="Delete Keys", icon="X")
        col.separator()
        col.menu("OPENANIM_MT_interp", text="Interpolation", icon="IPO_BEZIER")
        col.menu("OPENANIM_MT_handle", text="Handles", icon="HANDLE_AUTO")
        col.menu("OPENANIM_MT_values", text="Key Values", icon="MOD_MIRROR")
        col.menu("OPENANIM_MT_clean", text="Clean Up", icon="BRUSH_DATA")
        col.menu("OPENANIM_MT_bake", text="Bake", icon="FILE_TICK")
        col.separator()
        col.menu("OPENANIM_MT_blend", text="Blend / Spacing", icon="ARROW_LEFTRIGHT")
        col.operator("openanim.breakdown", text="Breakdowner", icon="KEYFRAME")
        col.operator("openanim.ghost", text="Create Ghost Curve", icon="GHOST_ENABLED").action = "CREATE"
        col.operator("openanim.ghost", text="Clear Ghost Curves", icon="GHOST_DISABLED").action = "CLEAR"
        col.separator()
        col.menu("OPENANIM_MT_marker", text="Markers", icon="MARKER")
        col.menu("OPENANIM_MT_childof", text="Child Of", icon="CONSTRAINT")
        col.menu("OPENANIM_MT_space", text="Space Conversion", icon="WORLD")
        col.menu("OPENANIM_MT_motion", text="Motion Paths", icon="CURVE_PATH")
        col.separator()
        col.operator("openanim.pose_clipboard", text="Copy Pose", icon="COPYDOWN").action = "COPY"
        col.operator("openanim.pose_clipboard", text="Paste Pose", icon="PASTEDOWN").action = "PASTE"
        col.operator("openanim.pose_clipboard", text="Paste Pose Flipped", icon="MOD_MIRROR").action = "PASTE_FLIPPED"
        col.operator("openanim.library_save", text="Save Animation", icon="FILE_TICK").kind = "animations"


def _menu_button(self, context):
    prefs = get_prefs(context)
    if prefs and not prefs.show_headers:
        return
    layout = self.layout
    layout.menu("OPENANIM_MT_root", text="OpenAnimEasy", icon="ANIM")
    if context.area and context.area.type in {"DOPESHEET_EDITOR", "GRAPH_EDITOR"}:
        layout.operator("openanim.frame_view", text="", icon="VIEWZOOM").action = "ALL"
        layout.operator("openanim.breakdown", text="", icon="KEYFRAME")
        layout.operator("openanim.marker", text="", icon="MARKER").action = "ADD"


# --------------------------------------------------------------------------
# Side panel
# --------------------------------------------------------------------------

def draw_pose_tools(layout, context):
    prefs = get_prefs(context)
    pose_box = layout.box()
    pose_box.label(text="Posing", icon="POSE_HLT")
    grid = pose_box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    grid.operator("openanim.select_rig", text="Opposite", icon="SELECT_DIFFERENCE").mode = "OPPOSITE"
    grid.operator("openanim.select_rig", text="Parent", icon="TRIA_UP").mode = "PARENT"
    grid.operator("openanim.select_rig", text="Children", icon="TRIA_DOWN").mode = "CHILD"
    grid.operator("openanim.pose_clipboard", text="Copy Pose", icon="COPYDOWN").action = "COPY"
    grid.operator("openanim.pose_clipboard", text="Paste Pose", icon="PASTEDOWN").action = "PASTE"
    grid.operator("openanim.pose_clipboard", text="Paste Flip", icon="MOD_MIRROR").action = "PASTE_FLIPPED"
    grid.operator("openanim.pose_clipboard", text="Save Pose", icon="FILE_TICK").action = "SAVE"
    row = pose_box.row(align=True)
    row.operator("openanim.reset_transform", text="All").kind = "ALL"
    row.operator("openanim.reset_transform", text="Loc").kind = "LOCATION"
    row.operator("openanim.reset_transform", text="Rot").kind = "ROTATION"
    row.operator("openanim.reset_transform", text="Scale").kind = "SCALE"
    row = pose_box.row(align=True)
    row.operator("openanim.gizmo_size", text="Gizmo +", icon="ADD").step = prefs.gizmo_step if prefs else 5
    row.operator("openanim.gizmo_size", text="Gizmo -", icon="REMOVE").direction = "DOWN"
    pose_box.operator("openanim.cycle", text="Cycle Orientation", icon="ORIENTATION_GLOBAL").what = "ORIENTATION"
    pose_box.operator("openanim.cycle", text="Cycle Pivot", icon="PIVOT_CURSOR").what = "PIVOT"
    pose_box.operator("openanim.pivot_offset", text="Pivot Offset", icon="PIVOT_CURSOR")
    pose_box.operator("openanim.silhouette", text="Silhouette Toggle", icon="LIGHT")


def draw_main(layout, context):
    prefs = get_prefs(context)
    if prefs is None:
        return
    layout.operator("openanim.toggle_editor", text="Toggle Timeline / Graph", icon="GRAPH")

    if prefs.show_timing:
        box = layout.box()
        box.label(text="Timing", icon="TIME")
        row = box.row(align=True)
        row.operator("openanim.frame_view", text="Frame All", icon="VIEWZOOM").action = "ALL"
        row.operator("openanim.frame_view", text="Set Preview", icon="PREVIEW_RANGE").action = "PREVIEW_SET"
        row = box.row(align=True)
        row.operator("openanim.frame_view", text="Clear Preview", icon="X").action = "PREVIEW_CLEAR"
        row.operator("openanim.select_keys_side", text="Keys <", icon="BACK").side = "LEFT"
        row.operator("openanim.select_keys_side", text="Keys >", icon="FORWARD").side = "RIGHT"
        box.menu("OPENANIM_MT_snap", text="Snap Selected Keys", icon="SNAP_ON")
        row = box.row(align=True)
        row.operator("openanim.move_keys", text="Move <", icon="TRIA_LEFT").direction = "LEFT"
        row.operator("openanim.move_keys", text="Move >", icon="TRIA_RIGHT").direction = "RIGHT"
        box.menu("OPENANIM_MT_inbetween", text="Inbetween", icon="SORTTIME")
        box.menu("OPENANIM_MT_keytype", text="Add Key Type", icon="KEYFRAME")
        box.menu("OPENANIM_MT_delete", text="Delete Keys", icon="X")
        row = box.row(align=True)
        row.operator("openanim.crop_animation", text="Crop", icon="ARROW_LEFTRIGHT")
        row.operator("openanim.time_offset", text="Offset", icon="ARROW_LEFTRIGHT")
        row.operator("openanim.fast_frame_range", text="Fast Range", icon="PREVIEW_RANGE")
        box.operator("openanim.share_times", text="Share Key Times", icon="SORTTIME")

    if prefs.show_curves:
        box = layout.box()
        box.label(text="Curves", icon="CURVE_DATA")
        row = box.row(align=True)
        row.menu("OPENANIM_MT_interp", text="Interpolation", icon="IPO_BEZIER")
        row.menu("OPENANIM_MT_handle", text="Handles", icon="HANDLE_AUTO")
        row = box.row(align=True)
        row.operator("openanim.nudge_value", text="Value +", icon="ADD").direction = "UP"
        row.operator("openanim.nudge_value", text="Value -", icon="REMOVE").direction = "DOWN"
        box.menu("OPENANIM_MT_values", text="Key Values", icon="MOD_MIRROR")
        row = box.row(align=True)
        row.operator("openanim.copy_keys", text="Copy", icon="COPYDOWN")
        row.operator("openanim.paste_keys", text="Paste", icon="PASTEDOWN")
        row.operator("openanim.paste_keys", text="Flip", icon="MOD_MIRROR").flipped = True
        box.menu("OPENANIM_MT_clean", text="Clean Up", icon="BRUSH_DATA")
        box.menu("OPENANIM_MT_bake", text="Bake", icon="FILE_TICK")

    if prefs.show_spacing:
        box = layout.box()
        box.label(text="Spacing", icon="ARROW_LEFTRIGHT")
        box.operator("openanim.breakdown", text="Breakdowner", icon="KEYFRAME")
        box.menu("OPENANIM_MT_blend", text="Blend / Ease / Smooth", icon="ARROW_LEFTRIGHT")
        box.operator("openanim.ghost", text="Create Ghost Curve", icon="GHOST_ENABLED").action = "CREATE"
        box.operator("openanim.ghost", text="Clear Ghost Curves", icon="GHOST_DISABLED").action = "CLEAR"

    if prefs.show_pose:
        draw_pose_tools(layout, context)

    if prefs.show_scene:
        box = layout.box()
        box.label(text="Scene & Rig", icon="CONSTRAINT")
        box.menu("OPENANIM_MT_marker", text="Markers", icon="MARKER")
        box.menu("OPENANIM_MT_childof", text="Child Of", icon="CONSTRAINT")
        box.menu("OPENANIM_MT_space", text="Space Conversion", icon="WORLD")
        box.menu("OPENANIM_MT_motion", text="Motion Paths", icon="CURVE_PATH")
        box.operator(
            "openanim.edit_motion_path",
            text="Edit Motion Path (Drag)",
            icon="CURVE_PATH",
        )

    if prefs.show_library:
        box = layout.box()
        box.label(text="Library", icon="FILE_FOLDER")
        row = box.row(align=True)
        row.operator("openanim.library_save", text="Save Animation", icon="FILE_TICK").kind = "animations"
        row.operator("openanim.library_save", text="Save Pose", icon="POSE_HLT").kind = "poses"
        for kind, label in (("animations", "Animations"), ("poses", "Poses")):
            items = library.list_items(kind)
            if not items:
                continue
            box.label(text=label)
            for item in items:
                row = box.row(align=True)
                op = row.operator("openanim.library_apply", text=item, icon="IMPORT")
                op.name = item
                op.kind = kind
                op = row.operator("openanim.library_delete", text="", icon="X")
                op.name = item
                op.kind = kind


class OPENANIM_PT_graph(bpy.types.Panel):
    bl_label = "OpenAnimEasy"
    bl_idname = "OPENANIM_PT_graph"
    bl_space_type = "GRAPH_EDITOR"
    bl_region_type = "UI"
    bl_category = "AnimEasy"

    def draw(self, context):
        draw_main(self.layout, context)


class OPENANIM_PT_dopesheet(bpy.types.Panel):
    bl_label = "OpenAnimEasy"
    bl_idname = "OPENANIM_PT_dopesheet"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "UI"
    bl_category = "AnimEasy"

    def draw(self, context):
        draw_main(self.layout, context)


class OPENANIM_PT_view3d(bpy.types.Panel):
    bl_label = "OpenAnimEasy"
    bl_idname = "OPENANIM_PT_view3d"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AnimEasy"

    def draw(self, context):
        draw_pose_tools(self.layout, context)
        layout = self.layout
        box = layout.box()
        box.label(text="Scene", icon="CONSTRAINT")
        box.menu("OPENANIM_MT_marker", text="Markers", icon="MARKER")
        box.menu("OPENANIM_MT_childof", text="Child Of", icon="CONSTRAINT")
        box.menu("OPENANIM_MT_space", text="Space Conversion", icon="WORLD")
        box.menu("OPENANIM_MT_motion", text="Motion Paths", icon="CURVE_PATH")
        box.operator(
            "openanim.edit_motion_path",
            text="Edit Motion Path (Drag)",
            icon="CURVE_PATH",
        )


MENUS = (
    OPENANIM_MT_snap,
    OPENANIM_MT_inbetween,
    OPENANIM_MT_keytype,
    OPENANIM_MT_delete,
    OPENANIM_MT_interp,
    OPENANIM_MT_handle,
    OPENANIM_MT_values,
    OPENANIM_MT_clean,
    OPENANIM_MT_bake,
    OPENANIM_MT_blend,
    OPENANIM_MT_marker,
    OPENANIM_MT_childof,
    OPENANIM_MT_space,
    OPENANIM_MT_motion,
    OPENANIM_MT_root,
)

PANELS = (
    OPENANIM_AddonPreferences,
    OPENANIM_PT_graph,
    OPENANIM_PT_dopesheet,
    OPENANIM_PT_view3d,
)

MENU_TARGETS = (
    "DOPESHEET_MT_editor_menus",
    "GRAPH_MT_editor_menus",
    "NLA_MT_editor_menus",
    "VIEW3D_MT_editor_menus",
)


def register():
    for cls in PANELS:
        bpy.utils.register_class(cls)
    for cls in MENUS:
        bpy.utils.register_class(cls)
    for target in MENU_TARGETS:
        menu = getattr(bpy.types, target, None)
        if menu is not None:
            menu.append(_menu_button)


def unregister():
    for target in MENU_TARGETS:
        menu = getattr(bpy.types, target, None)
        if menu is not None:
            try:
                menu.remove(_menu_button)
            except Exception:
                pass
    for cls in reversed(MENUS):
        bpy.utils.unregister_class(cls)
    for cls in reversed(PANELS):
        bpy.utils.unregister_class(cls)
