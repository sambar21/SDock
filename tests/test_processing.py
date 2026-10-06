import io

import pytest
import trimesh

from app.services import processing
from tests.helpers import add_member, make_org, upload
from tools import scangen


@pytest.fixture()
def org(client, make_user):
    owner = make_user("owner@example.com")
    return owner, make_org(client, owner)


def scan_status(client, headers, scan_id):
    return client.get(f"/api/v1/scans/{scan_id}", headers=headers).json()


def load_preview(client, headers, scan_id):
    response = client.get(f"/api/v1/scans/{scan_id}/preview", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "model/gltf-binary"
    return trimesh.load(io.BytesIO(response.content), file_type="glb")


# The whole path: upload, queue, worker, preview.

def test_point_cloud_goes_from_upload_to_ready(client, org):
    owner, org_id = org
    scan = upload(client, owner, org_id, scangen.point_cloud(30_000)).json()
    assert scan["status"] == "uploaded"
    assert client.queued == [scan["id"]]

    client.run_jobs()

    done = scan_status(client, owner, scan["id"])
    assert done["status"] == "ready"
    assert done["error_message"] is None
    assert 0 < done["preview_size"] < done["original_size"]
    assert done["reduction_pct"] > 80
    preview = load_preview(client, owner, scan["id"])
    assert sum(len(g.vertices) for g in preview.geometry.values()) == 3_000


def test_mesh_goes_from_upload_to_ready_with_fewer_triangles(client, org):
    owner, org_id = org
    scan = upload(client, owner, org_id, scangen.mesh(100)).json()
    client.run_jobs()

    assert scan_status(client, owner, scan["id"])["status"] == "ready"
    preview = load_preview(client, owner, scan["id"])
    faces = sum(len(g.faces) for g in preview.geometry.values())
    assert 0 < faces < 19_602 / 2  # the original has 19,602 triangles


def test_preview_is_not_available_until_ready(client, org):
    owner, org_id = org
    scan = upload(client, owner, org_id, scangen.point_cloud(1_000)).json()
    early = client.get(f"/api/v1/scans/{scan['id']}/preview", headers=owner)
    assert early.status_code == 409
    assert early.json()["error"] == "not_ready"


def test_a_scan_is_only_processed_once(client, org):
    owner, org_id = org
    scan = upload(client, owner, org_id, scangen.point_cloud(5_000)).json()
    client.queued.append(scan["id"])  # a duplicate job
    client.run_jobs()
    assert scan_status(client, owner, scan["id"])["status"] == "ready"


def test_small_scans_are_not_shrunk_below_the_floor(client, org):
    owner, org_id = org
    scan = upload(client, owner, org_id, scangen.point_cloud(1_500)).json()
    client.run_jobs()
    preview = load_preview(client, owner, scan["id"])
    assert sum(len(g.vertices) for g in preview.geometry.values()) == 1_500


# Bad files that get past the upload checks and fail in the worker.

@pytest.mark.parametrize(
    "data, expected",
    [
        (scangen.truncated(scangen.point_cloud(5_000)), "could not be read"),
        (scangen.with_nan(), "invalid coordinates"),
        (scangen.zero_vertices(), "no geometry"),
    ],
    ids=["truncated", "nan", "zero-vertices"],
)
def test_broken_scans_end_up_failed_with_a_reason(client, org, tmp_path, data, expected):
    owner, org_id = org
    scan = upload(client, owner, org_id, data).json()
    client.run_jobs()

    failed = scan_status(client, owner, scan["id"])
    assert failed["status"] == "failed"
    assert expected in failed["error_message"]
    assert failed["preview_size"] is None
    assert list((tmp_path / "storage").rglob("preview.glb")) == []
    assert client.get(f"/api/v1/scans/{scan['id']}/preview", headers=owner).status_code == 409


# The queue being down must not leave half an upload behind.

def test_upload_is_undone_when_the_queue_is_down(client, org, tmp_path):
    from app.main import app
    from app.services.queue import get_enqueue

    def broken(scan_id):
        raise ConnectionError("redis is down")

    app.dependency_overrides[get_enqueue] = lambda: broken
    owner, org_id = org
    response = upload(client, owner, org_id, scangen.point_cloud(1_000))

    assert response.status_code == 503
    assert response.json()["error"] == "queue_unavailable"
    assert client.get(f"/api/v1/orgs/{org_id}/scans", headers=owner).json() == []
    assert list((tmp_path / "storage").rglob("*.ply")) == []


# Unit tests for the processing step.

def test_shrink_cuts_triangles_but_keeps_a_floor():
    big = trimesh.load(io.BytesIO(scangen.mesh(100)), file_type="ply", process=False)
    assert len(processing.shrink(big).faces) < len(big.faces) * 0.2
    small = trimesh.load(io.BytesIO(scangen.mesh(10)), file_type="ply", process=False)
    assert len(processing.shrink(small).faces) == len(small.faces)


def test_shrink_keeps_point_colors():
    cloud = trimesh.load(io.BytesIO(scangen.point_cloud(20_000)), file_type="ply", process=False)
    smaller = processing.shrink(cloud)
    assert len(smaller.vertices) == 2_000
    assert len(smaller.colors) == 2_000


def test_shrink_is_repeatable():
    cloud = trimesh.load(io.BytesIO(scangen.point_cloud(20_000)), file_type="ply", process=False)
    assert (processing.shrink(cloud).vertices == processing.shrink(cloud).vertices).all()


# Permissions on the preview.

def test_viewer_can_fetch_preview_but_outsider_cannot(client, org, make_user):
    owner, org_id = org
    viewer = make_user("viewer@example.com")
    outsider = make_user("out@example.com")
    add_member(client, owner, org_id, "viewer@example.com", "viewer")
    scan = upload(client, owner, org_id, scangen.point_cloud(3_000)).json()
    client.run_jobs()

    assert client.get(f"/api/v1/scans/{scan['id']}/preview", headers=viewer).status_code == 200
    assert client.get(f"/api/v1/scans/{scan['id']}/preview", headers=outsider).status_code == 404
