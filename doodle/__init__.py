"""3d_doodle toolkit: headless Blender helpers for building game-ready models.

Every model script in models/ imports from here. The pipeline is:
    scene.reset() -> build geometry/materials -> render previews -> bake + export
"""

from . import scene, geo, materials, lighting, render, export  # noqa: F401
