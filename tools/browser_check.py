"""Drive the real viewer page in a real browser, end to end.

Needs `pip install playwright pillow` and Microsoft Edge (no browser download).
Redis is not needed: the script runs the worker inside the server process.

    python -m tools.scangen samples
    python -m tools.browser_check

Screenshots land in ./screenshots.
"""
import io
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

work = Path(tempfile.mkdtemp(prefix="scan_check_"))
os.environ["DATABASE_URL"] = f"sqlite:///{work / 'check.db'}"
os.environ["STORAGE_DIR"] = str(work / "storage")

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from app.main import app  # noqa: E402
from app.services.queue import get_enqueue  # noqa: E402
from app.worker import process_scan  # noqa: E402

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}/viewer/"
SAMPLES = Path("samples")
SHOTS = Path("screenshots")


def run_inline(scan_id: str) -> None:
    threading.Thread(target=process_scan, args=(scan_id,), daemon=True).start()


app.dependency_overrides[get_enqueue] = lambda: run_inline


def canvas_has_picture(page) -> bool:
    """True if the 3D stage shows more than a flat background.

    A WebGL canvas cannot be read back once drawn, so look at a screenshot of it.
    """
    shot = Image.open(io.BytesIO(page.locator("#stage").screenshot())).convert("RGB")
    colours = shot.resize((64, 64)).getcolors(maxcolors=4096)
    return colours is None or len(colours) > 5


def snap(page, frames: list, hold: int = 1) -> None:
    """Remember the page as it looks now. `hold` repeats the frame so the GIF lingers on it."""
    image = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    frames.extend([image] * hold)


def orbit(page, frames: list) -> None:
    """Drag across the 3D view a few times, grabbing a frame after each step."""
    box = page.locator("#stage").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for step in range(1, 7):
        page.mouse.move(x + step * 45, y - step * 8, steps=4)
        page.wait_for_timeout(120)
        snap(page, frames)
    page.mouse.up()


def save_gif(frames: list, target: Path) -> None:
    """Write the frames as a small GIF (about 900 px wide, 6 frames per second)."""
    target.parent.mkdir(exist_ok=True)
    width = 900
    small = [f.resize((width, round(f.height * width / f.width))).quantize(colors=96, dither=Image.Dither.NONE) for f in frames]
    small[0].save(target, save_all=True, append_images=small[1:], duration=160, loop=0, optimize=True)
    print(f"Wrote {target} ({target.stat().st_size / 1024:.0f} KB, {len(frames)} frames)")


def main() -> None:
    frames: list = []
    SHOTS.mkdir(exist_ok=True)
    command.upgrade(Config("alembic.ini"), "head")
    server = uvicorn.Server(uvicorn.Config(app, port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)

    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        page.on("console", lambda m: m.type == "error" and problems.append(f"console error: {m.text}"))
        page.goto(BASE)

        # Sign up and create an organization.
        page.fill("#email", "check@example.com")
        page.fill("#password", "password123")
        page.click("button[data-kind=register]")
        page.wait_for_selector("#app:not(.hidden)")
        page.fill("#org-name", "Check Studio")
        page.click("#org-form button")
        page.wait_for_selector("#org-select option", state="attached")
        page.screenshot(path=SHOTS / "1-empty.png")

        # Upload a point cloud, a mesh and a broken file.
        for filename, name in [("cloud_small.ply", "Point cloud"), ("mesh_small.ply", "Wavy mesh"), ("bad_nan.ply", "Broken scan")]:
            page.set_input_files("#file", SAMPLES / filename)
            page.fill("#scan-name", name)
            snap(page, frames, hold=2)
            page.click("#upload-button")
            page.wait_for_selector(f"#scan-list button:has-text('{name}')")
            snap(page, frames)

        # Wait for the list to settle, then look at each scan.
        page.wait_for_function("document.querySelectorAll('#scan-list .badge.ready').length === 2", timeout=30000)
        page.wait_for_function("document.querySelectorAll('#scan-list .badge.failed').length === 1", timeout=30000)
        page.screenshot(path=SHOTS / "2-list.png")

        for name, expect_picture in [("Point cloud", True), ("Wavy mesh", True), ("Broken scan", False)]:
            page.click(f"#scan-list button:has-text('{name}')")
            if expect_picture:
                page.wait_for_function("document.getElementById('stage-message').classList.contains('hidden')", timeout=15000)
                page.wait_for_timeout(500)
                if not canvas_has_picture(page):
                    problems.append(f"{name}: the canvas looks blank")
            else:
                text = page.inner_text("#stage-message")
                if "invalid coordinates" not in text:
                    problems.append(f"{name}: expected the failure reason, saw {text!r}")
            page.screenshot(path=SHOTS / f"3-{name.lower().replace(' ', '-')}.png")
            snap(page, frames, hold=3)
            if expect_picture:
                orbit(page, frames)

        # Make a viewer through the API, as the owner would.
        token = page.evaluate("sessionStorage.getItem('token')")
        org_id = page.input_value("#org-select")
        api = f"http://127.0.0.1:{PORT}/api/v1"
        httpx.post(f"{api}/auth/register", json={"email": "viewer@example.com", "password": "password123"})
        added = httpx.post(
            f"{api}/orgs/{org_id}/members",
            json={"email": "viewer@example.com", "role": "viewer"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if added.status_code != 201:
            problems.append(f"could not add the viewer: {added.text}")

        # A brand-new user sees no organizations.
        page.click("#sign-out")
        page.fill("#email", "stranger@example.com")
        page.fill("#password", "password123")
        page.click("button[data-kind=register]")
        page.wait_for_selector("#app:not(.hidden)")
        if page.locator("#org-select option").count() != 0:
            problems.append("a new user should not see someone else's organization")

        # The viewer can look, but the upload and delete controls are gone.
        page.click("#sign-out")
        page.fill("#email", "viewer@example.com")
        page.fill("#password", "password123")
        page.click("button[data-kind=login]")
        page.wait_for_selector("#scan-list button:has-text('Point cloud')")
        if page.is_visible("#upload-card"):
            problems.append("the viewer can see the upload form")
        page.click("#scan-list button:has-text('Point cloud')")
        page.wait_for_function("document.getElementById('stage-message').classList.contains('hidden')", timeout=15000)
        page.wait_for_timeout(500)
        if page.is_visible("#delete-button"):
            problems.append("the viewer can see the delete button")
        if not canvas_has_picture(page):
            problems.append("the viewer could not see the model")
        page.screenshot(path=SHOTS / "4-viewer.png")

        browser.close()

    if "--gif" in sys.argv:
        save_gif(frames, Path("docs") / "demo.gif")

    print("PROBLEMS:" if problems else "All browser checks passed.")
    for problem in problems:
        print(" -", problem)


if __name__ == "__main__":
    main()
