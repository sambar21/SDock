from pathlib import Path

from tests.helpers import make_org, upload
from tools import scangen


def test_upload_creates_a_scan_in_uploaded_status(client, make_user):
    owner = make_user("owner@example.com")
    org_id = make_org(client, owner)
    data = scangen.point_cloud(2_000)

    response = upload(client, owner, org_id, data, filename="Room.PLY", name="Living room")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "uploaded"
    assert body["name"] == "Living room"
    assert body["original_size"] == len(data)
    assert body["preview_size"] is None


def test_name_defaults_to_filename(client, make_user):
    owner = make_user("owner@example.com")
    org_id = make_org(client, owner)
    response = upload(client, owner, org_id, scangen.point_cloud(500), filename="hallway.ply")
    assert response.json()["name"] == "hallway.ply"


def test_uploaded_file_is_stored_byte_for_byte(client, make_user, tmp_path):
    owner = make_user("owner@example.com")
    org_id = make_org(client, owner)
    data = scangen.mesh(20)
    scan = upload(client, owner, org_id, data).json()
    stored = Path(tmp_path / "storage" / org_id / scan["id"] / "original.ply")
    assert stored.read_bytes() == data


def test_scan_can_be_listed_fetched_and_deleted(client, make_user, tmp_path):
    owner = make_user("owner@example.com")
    org_id = make_org(client, owner)
    scan = upload(client, owner, org_id, scangen.point_cloud(500)).json()

    listing = client.get(f"/api/v1/orgs/{org_id}/scans", headers=owner).json()
    assert [s["id"] for s in listing] == [scan["id"]]
    assert client.get(f"/api/v1/scans/{scan['id']}", headers=owner).json()["id"] == scan["id"]

    assert client.delete(f"/api/v1/scans/{scan['id']}", headers=owner).status_code == 204
    assert client.get(f"/api/v1/scans/{scan['id']}", headers=owner).status_code == 404
    assert not (tmp_path / "storage" / org_id / scan["id"]).exists()


def test_list_is_newest_first_and_paged(client, make_user):
    owner = make_user("owner@example.com")
    org_id = make_org(client, owner)
    ids = [
        upload(client, owner, org_id, scangen.point_cloud(100), filename=f"s{i}.ply").json()["id"]
        for i in range(3)
    ]
    page = client.get(f"/api/v1/orgs/{org_id}/scans?limit=2", headers=owner).json()
    assert [s["id"] for s in page] == [ids[2], ids[1]]
    rest = client.get(f"/api/v1/orgs/{org_id}/scans?limit=2&offset=2", headers=owner).json()
    assert [s["id"] for s in rest] == [ids[0]]


def test_scans_do_not_leak_between_orgs(client, make_user):
    a_owner = make_user("a@example.com")
    b_owner = make_user("b@example.com")
    a_org = make_org(client, a_owner, "A")
    b_org = make_org(client, b_owner, "B")
    upload(client, a_owner, a_org, scangen.point_cloud(100))
    assert client.get(f"/api/v1/orgs/{b_org}/scans", headers=b_owner).json() == []
