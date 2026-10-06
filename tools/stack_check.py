"""Exercise a running stack (docker compose up) over real HTTP.

    python -m tools.scangen samples
    API_PORT=8010 docker compose up -d --build
    python -m tools.stack_check http://localhost:8010

Uploads every sample scan, waits for the real worker, downloads each preview
and prints what happened.
"""
import sys
import time
import uuid
from pathlib import Path

import httpx

SAMPLES = Path("samples")


def main(base: str) -> int:
    api = f"{base.rstrip('/')}/api/v1"
    failures = []
    with httpx.Client(timeout=60) as http:
        email = f"stack-{uuid.uuid4().hex[:8]}@example.com"
        token = http.post(f"{api}/auth/register", json={"email": email, "password": "password123"}).json()["access_token"]
        http.headers["Authorization"] = f"Bearer {token}"
        org = http.post(f"{api}/orgs", json={"name": "Stack check"}).json()["id"]

        scans = {}
        for path in sorted(SAMPLES.glob("*.ply")):
            response = http.post(f"{api}/orgs/{org}/scans", files={"file": (path.name, path.read_bytes())})
            print(f"upload {path.name:<22} -> {response.status_code} {response.json().get('status') or response.json().get('error')}")
            if response.status_code == 202:
                scans[path.name] = response.json()["id"]

        started = time.time()
        pending = dict(scans)
        results = {}
        while pending and time.time() - started < 120:
            for name, scan_id in list(pending.items()):
                scan = http.get(f"{api}/scans/{scan_id}").json()
                if scan["status"] in ("ready", "failed"):
                    results[name] = scan
                    del pending[name]
            time.sleep(0.5)
        print(f"\nall scans finished in {time.time() - started:.1f}s" if not pending else f"\nSTILL PENDING: {list(pending)}")

        print(f"\n{'file':<22}{'status':<9}{'smaller':>9}  detail")
        for name, scan in results.items():
            detail = scan["error_message"] or ""
            if scan["status"] == "ready":
                preview = http.get(f"{api}/scans/{scan['id']}/preview")
                ok = preview.status_code == 200 and preview.content[:4] == b"glTF" and len(preview.content) == scan["preview_size"]
                detail = f"preview {len(preview.content):,} bytes, valid GLB: {ok}"
                if not ok:
                    failures.append(f"{name}: preview is not a valid GLB")
            expected_bad = name.startswith("bad_")
            if (scan["status"] == "failed") != expected_bad:
                failures.append(f"{name}: expected {'failed' if expected_bad else 'ready'}, got {scan['status']}")
            pct = f"{scan['reduction_pct']:.1f}%" if scan["reduction_pct"] is not None else "-"
            print(f"{name:<22}{scan['status']:<9}{pct:>9}  {detail}")

        mine = http.get(f"{api}/orgs/{org}/scans").json()
        if len(mine) != len(scans):
            failures.append("the list does not match what was uploaded")
    if pending:
        failures.append("some scans never finished")

    print("\nPROBLEMS:" if failures else "\nStack check passed.")
    for failure in failures:
        print(" -", failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
