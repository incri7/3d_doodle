"""Cameras and Cycles rendering (CPU; EEVEE needs a GPU the sandbox lacks).

Every model gets:
  hero.png      3/4 view, high quality
  views.png     front / right / back / top contact sheet (proportion check)
  turntable.mp4 optional 360 loop
"""

import math
import os
import subprocess

import bpy
from mathutils import Vector

from . import scene as sc


def setup_cycles(samples=128, res=(1600, 1200), transparent=False):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 12
    s.cycles.transmission_bounces = 16
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.film_transparent = transparent
    s.render.image_settings.file_format = "PNG"
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"
    return s


def camera(name="CAM-main", lens=60):
    cam = bpy.data.objects.get(name)
    if cam is None:
        data = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, data)
        sc.collection("Studio").objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.01
    cam.data.clip_end = 1000
    bpy.context.scene.camera = cam
    return cam


def frame(cam, azimuth=-35, elevation=20, margin=1.15):
    """Place camera on a sphere around the model so it fills the frame.
    azimuth 0 = looking from -Y (front), positive rotates toward +X."""
    lo, hi = sc.bounds()
    center = (lo + hi) / 2
    radius = (hi - lo).length / 2
    s = bpy.context.scene
    aspect = s.render.resolution_x / s.render.resolution_y
    # Sensor fit AUTO: cam.data.angle spans the longer image side; use the shorter.
    fov = cam.data.angle
    if aspect >= 1:
        fov = 2 * math.atan(math.tan(fov / 2) / aspect)
    dist = radius * margin / math.sin(fov / 2)
    az, el = math.radians(azimuth), math.radians(elevation)
    offset = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    cam.location = center + offset * dist
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    return cam


def still(path, cam=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s = bpy.context.scene
    if cam is not None:
        s.camera = cam
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def hero(out_dir, samples=128, res=(1600, 1200), azimuth=-35, elevation=18):
    setup_cycles(samples, res)
    cam = frame(camera(), azimuth, elevation)
    return still(os.path.join(out_dir, "hero.png"), cam)


def views(out_dir, samples=48, res=(800, 600)):
    """Front/right/back/top renders tiled into one image."""
    setup_cycles(samples, res)
    cam = camera("CAM-views", lens=50)
    backdrop = bpy.data.objects.get("Backdrop")
    if backdrop:  # orthographic-style checks: cameras would sit inside the wall
        backdrop.hide_render = True
    tiles = []
    for label, az, el in [("front", 0, 5), ("right", 90, 5), ("back", 180, 5), ("top", -0.01, 89)]:
        frame(cam, az, el, margin=1.1)
        tiles.append(still(os.path.join(out_dir, f"_view_{label}.png"), cam))
    sheet = os.path.join(out_dir, "views.png")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *sum([["-i", t] for t in tiles], []),
         "-filter_complex", "xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0", sheet],
        check=True)
    for t in tiles:
        os.remove(t)
    if backdrop:
        backdrop.hide_render = False
    bpy.context.scene.camera = bpy.data.objects["CAM-main"] if "CAM-main" in bpy.data.objects else cam
    return sheet


def turntable(out_dir, frames=72, fps=24, samples=32, res=(800, 600), elevation=18):
    """Seamless 360 loop as mp4 (camera orbit; model untouched)."""
    setup_cycles(samples, res)
    cam = camera("CAM-turntable")
    tmp = os.path.join(out_dir, "_tt")
    os.makedirs(tmp, exist_ok=True)
    for i in range(frames):  # last frame is one step before 360 -> perfect loop
        frame(cam, -35 + 360 * i / frames, elevation)
        still(os.path.join(tmp, f"{i:04d}.png"), cam)
    mp4 = os.path.join(out_dir, "turntable.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "%04d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", mp4], check=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    return mp4
