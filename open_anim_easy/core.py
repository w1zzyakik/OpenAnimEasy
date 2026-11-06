"""Shared helpers for OpenAnimEasy.

Blender 4.4+ stores F-Curves inside layered actions. 5.x removed
Action.fcurves entirely, so every access goes through this module.
"""

import bpy


# --------------------------------------------------------------------------
# Actions / F-Curves
# --------------------------------------------------------------------------

def action_of(id_data):
    ad = id_data.animation_data
    return ad.action if ad and ad.action else None


def slot_of(id_data, action=None):
    ad = id_data.animation_data
    if not ad:
        return None
    slot = getattr(ad, "action_slot", None)
    action = action or ad.action
    if slot is None and action is not None:
        slots = getattr(action, "slots", None)
        if slots:
            slot = slots[0]
    return slot


def action_fcurves(action, slot=None):
    """All F-Curves of an action for one slot (or every slot)."""
    if action is None:
        return []
    layers = getattr(action, "layers", None)
    if layers is not None:
        result = []
        for layer in layers:
            for strip in layer.strips:
                bags = []
                if slot is not None:
                    bag = strip.channelbag(slot)
                    if bag:
                        bags.append(bag)
                if not bags:
                    bags.extend(strip.channelbags)
                for bag in bags:
                    result.extend(bag.fcurves)
        if result:
            return result
    legacy = getattr(action, "fcurves", None)
    return list(legacy) if legacy is not None else []


def ensure_action(id_data):
    action = action_of(id_data)
    if action:
        return action, slot_of(id_data, action)
    ad = id_data.animation_data_create()
    action = bpy.data.actions.new(id_data.name + "Action")
    ad.action = action
    slot = None
    if hasattr(action, "slots"):
        slot = action.slots.new(id_type="OBJECT", name=id_data.name)
        ad.action_slot = slot
    return action, slot


def ensure_fcurve(id_data, data_path, index=0):
    action, slot = ensure_action(id_data)
    if hasattr(action, "layers"):
        layer = action.layers[0] if len(action.layers) else action.layers.new("Layer")
        strip = layer.strips[0] if len(layer.strips) else layer.strips.new(type="KEYFRAME")
        bag = strip.channelbag(slot, ensure=True)
        fc = bag.fcurves.find(data_path, index=index)
        return fc or bag.fcurves.new(data_path, index=index)
    return action.fcurves.find(data_path, index=index) or action.fcurves.new(
        data_path, index=index
    )


def remove_fcurve(fc):
    action = fc.id_data
    return remove_fcurve_path(action, fc.data_path, fc.array_index)


def remove_fcurve_path(action, path, index):
    if action is None:
        return False
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    candidate = bag.fcurves.find(path, index=index)
                    if candidate:
                        bag.fcurves.remove(candidate)
                        return True
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        candidate = legacy.find(path, index=index)
        if candidate:
            legacy.remove(candidate)
            return True
    return False


def fcurve_bone(path):
    if path.startswith('pose.bones["'):
        end = path.find('"]', 12)
        if end != -1:
            return path[12:end]
    return None


def default_value(path, index):
    if path.endswith("scale"):
        return 1.0
    if path.endswith("rotation_quaternion") and index == 0:
        return 1.0
    if path.endswith("rotation_axis_angle") and index == 0:
        return 1.0
    return 0.0


# --------------------------------------------------------------------------
# Selection targets
# --------------------------------------------------------------------------

def target_objects(context):
    objects = [ob for ob in context.selected_objects]
    active = context.object
    if active and active not in objects:
        objects.append(active)
    return objects


def _bone_filter(ob):
    if ob.type != "ARMATURE" or ob.mode != "POSE":
        return None
    names = {pb.name for pb in ob.pose.bones if pb.select}
    return names or None


def target_fcurves(context):
    """(object, fcurve) for selected objects and selected pose bones."""
    result = []
    seen = set()
    for ob in target_objects(context):
        action = action_of(ob)
        if not action:
            continue
        slot = slot_of(ob, action)
        bones = _bone_filter(ob)
        pose_only = ob.type == "ARMATURE" and ob.mode == "POSE"
        for fc in action_fcurves(action, slot):
            if pose_only:
                bone = fcurve_bone(fc.data_path)
                if bone is None:
                    continue
                if bones is not None and bone not in bones:
                    continue
            key = fc.as_pointer()
            if key in seen:
                continue
            seen.add(key)
            result.append((ob, fc))
    return result


def target_bones(context):
    ob = context.object
    if not ob or ob.type != "ARMATURE" or ob.mode != "POSE":
        return []
    return [pb for pb in ob.pose.bones if pb.select]


def active_bone(context):
    ob = context.object
    if not ob or ob.type != "ARMATURE" or ob.mode != "POSE":
        return None
    pose_bone = getattr(context, "active_pose_bone", None)
    if pose_bone is not None and pose_bone.id_data == ob:
        return pose_bone
    active = ob.data.bones.active
    return ob.pose.bones.get(active.name) if active else None


def selected_keyframes(fcurves):
    points = []
    for fc in fcurves:
        for kp in fc.keyframe_points:
            if kp.select_control_point:
                points.append((fc, kp))
    return points


def fcurves_with_selection(context):
    result = []
    for _ob, fc in target_fcurves(context):
        if any(kp.select_control_point for kp in fc.keyframe_points):
            result.append(fc)
    return result or [fc for _ob, fc in target_fcurves(context)]


def all_keyframes(fcurves):
    return [(fc, kp) for fc in fcurves for kp in fc.keyframe_points]


def key_range(fcurves):
    frames = [
        kp.co.x for fc in fcurves for kp in fc.keyframe_points if kp.co.x is not None
    ]
    if not frames:
        return None
    return min(frames), max(frames)


def current_frame(context):
    return context.scene.frame_current


# --------------------------------------------------------------------------
# Keyframe primitives
# --------------------------------------------------------------------------

def insert_key(fc, frame, value=None, interpolation=None, key_type=None):
    if value is None:
        if len(fc.keyframe_points):
            value = fc.evaluate(frame)
        else:
            value = default_value(fc.data_path, fc.array_index)
    kp = fc.keyframe_points.insert(frame, value)
    if interpolation:
        kp.interpolation = interpolation
    if key_type:
        kp.type = key_type
    fc.update()
    return kp


def move_key_time(kp, frame):
    delta = frame - kp.co.x
    kp.co.x = frame
    kp.handle_left.x += delta
    kp.handle_right.x += delta


def move_key_value(kp, value):
    delta = value - kp.co.y
    kp.co.y = value
    kp.handle_left.y += delta
    kp.handle_right.y += delta


def sort_fcurve(fc):
    fc.keyframe_points.sort()
    fc.update()


def key_index(fc, key):
    pointer = key.as_pointer()
    for index, candidate in enumerate(fc.keyframe_points):
        if candidate.as_pointer() == pointer:
            return index
    return -1


def dedupe_fcurve(fc):
    try:
        fc.keyframe_points.deduplicate()
    except Exception:
        pass


def transform_channels(ob, pb=None):
    """(data_path, indices, rotation_mode) for object or pose bone."""
    if pb is not None:
        mode = pb.rotation_mode
    else:
        mode = ob.rotation_mode
    if mode == "QUATERNION":
        channels = [("location", 3), ("rotation_quaternion", 4), ("scale", 3)]
    elif mode == "AXIS_ANGLE":
        channels = [("location", 3), ("rotation_axis_angle", 4), ("scale", 3)]
    else:
        channels = [("location", 3), ("rotation_euler", 3), ("scale", 3)]
    if pb is not None:
        prefix = 'pose.bones["%s"].' % pb.name
        channels = [(prefix + path, count) for path, count in channels]
    return channels, mode


def insert_transform_keys(ob, pb, frame, key_type=None):
    channels, _mode = transform_channels(ob, pb)
    for path, count in channels:
        for index in range(count):
            fc = ensure_fcurve(ob, path, index)
            value = (
                fc.evaluate(frame)
                if len(fc.keyframe_points)
                else default_value(path, index)
            )
            fc.keyframe_points.insert(frame, value).type = key_type or "KEYFRAME"
            fc.update()


# --------------------------------------------------------------------------
# Editor / view utilities
# --------------------------------------------------------------------------

def find_editor(context, types):
    types = set(types)
    area = getattr(context, "area", None)
    if area and area.type in types:
        return area
    screen = getattr(context, "screen", None) or (
        context.window.screen if context.window else None
    )
    if not screen:
        return None
    candidates = [a for a in screen.areas if a.type in types]
    return max(candidates, key=lambda a: a.width * a.height) if candidates else None


def area_override(area):
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    space = area.spaces.active
    return bpy.context.temp_override(area=area, region=region, space_data=space)


def call_view_op(context, group, name, editor_types):
    area = find_editor(context, editor_types)
    if not area:
        return False
    try:
        with area_override(area):
            getattr(getattr(bpy.ops, group), name)()
        return True
    except Exception:
        return False


def graph_cursor_y(context):
    for area in getattr(context.screen, "areas", []):
        if area.type == "GRAPH_EDITOR":
            return area.spaces.active.cursor_position_y
    return 0.0


def mouse_frame(context, event):
    region = context.region
    view = getattr(region, "data", None)
    if view is None or not hasattr(view, "region_to_view"):
        return float(context.scene.frame_current)
    x, y = event.mouse_x - region.x, event.mouse_y - region.y
    return view.region_to_view(x, y)[0]


def window_region(context):
    """The View2D window region, even when invoked from a header/sidebar."""
    area = getattr(context, "area", None)
    candidates = []
    if area:
        candidates.append(area)
    editor = find_editor(
        context, {"DOPESHEET_EDITOR", "GRAPH_EDITOR", "NLA_EDITOR"}
    )
    if editor and editor not in candidates:
        candidates.append(editor)
    for candidate in candidates:
        for region in candidate.regions:
            if region.type == "WINDOW" and hasattr(region.data, "region_to_view"):
                return region
    region = getattr(context, "region", None)
    if region and hasattr(region.data, "region_to_view"):
        return region
    return None


def frame_from_event(context, event):
    region = window_region(context)
    if region is None:
        return float(context.scene.frame_current)
    x = event.mouse_x - region.x
    return region.data.region_to_view(x, 0)[0]


def smart_range(context, fcurves=None, selected_only=False):
    """Preview range when enabled, otherwise selected keys or action range."""
    scene = context.scene
    if scene.use_preview_range:
        return scene.frame_preview_start, scene.frame_preview_end
    fcurves = fcurves or [fc for _ob, fc in target_fcurves(context)]
    if selected_only:
        frames = [
            kp.co.x
            for fc in fcurves
            for kp in fc.keyframe_points
            if kp.select_control_point
        ]
        if frames:
            return int(min(frames)), int(max(frames))
    bounds = key_range(fcurves)
    if bounds:
        return int(bounds[0]), int(bounds[1])
    return scene.frame_start, scene.frame_end


# --------------------------------------------------------------------------
# Bone name mirroring (for flipped pose / keys)
# --------------------------------------------------------------------------

def flip_bone_name(name):
    for a, b in ((".L", ".R"), (".R", ".L"), ("_L", "_R"), ("_R", "_L"),
                 (".l", ".r"), (".r", ".l")):
        if name.endswith(a):
            return name[: -len(a)] + b
    for a, b in (("Left", "Right"), ("Right", "Left"),
                 ("left", "right"), ("right", "left")):
        if name.startswith(a):
            return b + name[len(a):]
        if name.endswith(a):
            return name[: -len(a)] + b
    return name
