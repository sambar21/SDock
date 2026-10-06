"""Measure how much smaller the previews are.

    python -m tools.scangen samples
    python -m tools.measure samples

Prints one row per good sample scan and the average reduction.
"""
import sys
import tempfile
import time
from pathlib import Path

from app.services import processing


def measure(folder: Path) -> list[tuple[str, int, int, float, float]]:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for path in sorted(folder.glob("*.ply")):
            if path.name.startswith("bad_"):
                continue
            started = time.perf_counter()
            geometry = processing.load_scan(path)
            processing.check_geometry(geometry)
            out = Path(tmp) / f"{path.stem}.glb"
            processing.shrink(geometry).export(str(out), file_type="glb")
            seconds = time.perf_counter() - started
            before, after = path.stat().st_size, out.stat().st_size
            rows.append((path.name, before, after, (1 - after / before) * 100, seconds))
    return rows


if __name__ == "__main__":
    rows = measure(Path(sys.argv[1] if len(sys.argv) > 1 else "samples"))
    print(f"{'file':<20}{'original':>12}{'preview':>12}{'smaller':>10}{'seconds':>10}")
    for name, before, after, pct, seconds in rows:
        print(f"{name:<20}{before:>12,}{after:>12,}{pct:>9.1f}%{seconds:>10.2f}")
    if rows:
        print(f"\naverage reduction: {sum(r[3] for r in rows) / len(rows):.1f}%")
