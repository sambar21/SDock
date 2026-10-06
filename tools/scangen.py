"""Make fake 3D scans for tests and demos.

Real scans are not available, so these stand in for them. Every file is a
binary little-endian PLY. Run it directly to write a few samples to disk:

    python -m tools.scangen samples
"""
import sys
from pathlib import Path

import numpy as np

_HEADER_POINTS = (
    "ply\nformat binary_little_endian 1.0\n"
    "element vertex {n}\n"
    "property float x\nproperty float y\nproperty float z\n"
    "property uchar red\nproperty uchar green\nproperty uchar blue\n"
    "end_header\n"
)
_HEADER_MESH = (
    "ply\nformat binary_little_endian 1.0\n"
    "element vertex {n}\n"
    "property float x\nproperty float y\nproperty float z\n"
    "element face {f}\n"
    "property list uchar int vertex_indices\n"
    "end_header\n"
)


def _vertex_bytes(points: np.ndarray, with_color: bool) -> bytes:
    if not with_color:
        return points.astype("<f4").tobytes()
    dtype = np.dtype([("xyz", "<f4", 3), ("rgb", "u1", 3)])
    rows = np.empty(len(points), dtype=dtype)
    rows["xyz"] = points
    # Colour by height so a viewer shows something recognisable.
    span = np.ptp(points[:, 2]) or 1.0
    shade = ((points[:, 2] - points[:, 2].min()) / span * 255).astype("u1")
    rows["rgb"] = np.stack([shade, 255 - shade, np.full_like(shade, 128)], axis=1)
    return rows.tobytes()


def point_cloud(n: int = 50_000, seed: int = 0) -> bytes:
    """A noisy sphere of n coloured points."""
    rng = np.random.default_rng(seed)
    direction = rng.normal(size=(n, 3))
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    points = direction * (1 + rng.normal(scale=0.01, size=(n, 1)))
    return _HEADER_POINTS.format(n=n).encode() + _vertex_bytes(points, with_color=True)


def mesh(grid: int = 100) -> bytes:
    """A wavy surface made of a grid x grid lattice, two triangles per cell."""
    xs, ys = np.meshgrid(np.linspace(-1, 1, grid), np.linspace(-1, 1, grid))
    zs = 0.2 * np.sin(4 * xs) * np.cos(4 * ys)
    points = np.stack([xs.ravel(), ys.ravel(), zs.ravel()], axis=1)

    idx = np.arange(grid * grid).reshape(grid, grid)
    a, b = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    c, d = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    tris = np.concatenate([np.stack([a, b, c], 1), np.stack([b, d, c], 1)]).astype("<i4")

    face_dtype = np.dtype([("count", "u1"), ("idx", "<i4", 3)])
    faces = np.empty(len(tris), dtype=face_dtype)
    faces["count"] = 3
    faces["idx"] = tris
    header = _HEADER_MESH.format(n=len(points), f=len(tris)).encode()
    return header + _vertex_bytes(points, with_color=False) + faces.tobytes()


# Deliberately broken files, one per failure the service has to handle.

def truncated(data: bytes) -> bytes:
    """A good file with the back half cut off."""
    return data[: len(data) // 2]


def with_nan(n: int = 1_000) -> bytes:
    """A point cloud where one coordinate is NaN."""
    data = bytearray(point_cloud(n))
    header_end = data.index(b"end_header\n") + len(b"end_header\n")
    data[header_end : header_end + 4] = np.float32("nan").tobytes()
    return bytes(data)


def zero_vertices() -> bytes:
    return _HEADER_POINTS.format(n=0).encode()


def not_a_ply() -> bytes:
    return b"this is just some text, not a scan\n"


def write_samples(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cloud_small.ply").write_bytes(point_cloud(20_000))
    (folder / "cloud_large.ply").write_bytes(point_cloud(500_000, seed=1))
    (folder / "mesh_small.ply").write_bytes(mesh(60))
    (folder / "mesh_large.ply").write_bytes(mesh(500))
    (folder / "bad_truncated.ply").write_bytes(truncated(point_cloud(20_000)))
    (folder / "bad_nan.ply").write_bytes(with_nan())
    (folder / "bad_zero_vertices.ply").write_bytes(zero_vertices())
    (folder / "bad_not_a_ply.ply").write_bytes(not_a_ply())


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "samples")
    write_samples(target)
    print(f"Wrote sample scans to {target.resolve()}")
