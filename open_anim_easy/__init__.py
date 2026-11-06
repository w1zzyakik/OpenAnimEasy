bl_info = {
    "name": "OpenAnimEasy",
    "author": "OpenAnimEasy contributors",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "Animation editor header > OpenAnimEasy, sidebar > AnimEasy",
    "description": "Free and open-source animation workflow tools for Blender",
    "category": "Animation",
    "doc_url": "https://github.com/w1zzyakik/OpenAnimEasy",
    "tracker_url": "https://github.com/w1zzyakik/OpenAnimEasy/issues",
}

from . import core, curves, library, pose, rig, timeline, ui  # noqa: E402

MODULES = (timeline, curves, pose, rig, library, ui)


def register():
    for module in MODULES:
        module.register()


def unregister():
    for module in reversed(MODULES):
        module.unregister()
