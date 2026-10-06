"""Turn an uploaded scan into a small preview.

Meshes lose triangles, point clouds lose points. The result is a GLB, which
the browser viewer loads directly.
"""
from typing import BinaryIO

import numpy as np
import trimesh

# Keep about this share of the geometry in the preview.
KEEP_RATIO = 0.10
# Never shrink below this, so small scans stay recognisable.
MIN_FACES = 500
MIN_POINTS = 2_000


class ScanRejected(Exception):
    """The scan is unusable. The message is written for the person who uploaded it."""


def load_scan(source: BinaryIO) -> trimesh.Trimesh | trimesh.PointCloud:
    try:
        geometry = trimesh.load(source, file_type="ply", process=False)
    except Exception as exc:
        raise ScanRejected(f"The file could not be read as a PLY scan ({exc}).") from exc
    if not isinstance(geometry, (trimesh.Trimesh, trimesh.PointCloud)):
        raise ScanRejected("The file contains no geometry.")
    return geometry


def check_geometry(geometry: trimesh.Trimesh | trimesh.PointCloud) -> None:
    vertices = np.asarray(geometry.vertices)
    if len(vertices) == 0:
        raise ScanRejected("The scan has no vertices.")
    if not np.isfinite(vertices).all():
        raise ScanRejected("The scan has invalid coordinates (NaN or infinity).")


def shrink(geometry: trimesh.Trimesh | trimesh.PointCloud) -> trimesh.Trimesh | trimesh.PointCloud:
    if isinstance(geometry, trimesh.Trimesh):
        target = max(MIN_FACES, int(len(geometry.faces) * KEEP_RATIO))
        if len(geometry.faces) <= target:
            return geometry
        return geometry.simplify_quadric_decimation(face_count=target)

    count = len(geometry.vertices)
    target = max(MIN_POINTS, int(count * KEEP_RATIO))
    if count <= target:
        return geometry
    # A fixed seed keeps previews repeatable. Sorting keeps the points in scan order.
    keep = np.sort(np.random.default_rng(0).choice(count, size=target, replace=False))
    colors = geometry.colors[keep] if len(geometry.colors) == count else None
    return trimesh.PointCloud(np.asarray(geometry.vertices)[keep], colors=colors)
