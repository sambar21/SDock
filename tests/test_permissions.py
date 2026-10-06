"""Every endpoint, tried as every kind of caller.

Each case builds its own organization, so destructive calls (delete a scan,
remove a member) never affect the next case.
"""
import pytest

from app.models import ROLE_RANK, Role
from tests.helpers import add_member, make_org, upload
from tools import scangen

CALLERS = ["anonymous", "outsider", "viewer", "editor", "owner"]

# name, method, path, minimum role, status on success
ENDPOINTS = [
    ("get org", "GET", "/orgs/{org}", "viewer", 200),
    ("list scans", "GET", "/orgs/{org}/scans", "viewer", 200),
    ("get scan", "GET", "/scans/{scan}", "viewer", 200),
    ("get preview", "GET", "/scans/{scan}/preview", "viewer", 200),
    ("upload scan", "POST", "/orgs/{org}/scans", "editor", 202),
    ("delete scan", "DELETE", "/scans/{scan}", "editor", 204),
    ("add member", "POST", "/orgs/{org}/members", "owner", 201),
    ("change role", "PATCH", "/orgs/{org}/members/{target}", "owner", 200),
    ("remove member", "DELETE", "/orgs/{org}/members/{target}", "owner", 204),
]


@pytest.fixture()
def world(client, make_user):
    """One org with an owner, editor and viewer, one ready scan, plus an outsider and a spare user."""
    owner = make_user("owner@example.com")
    org = make_org(client, owner)
    callers = {"anonymous": {}, "owner": owner, "outsider": make_user("outsider@example.com")}
    for role in ("editor", "viewer"):
        callers[role] = make_user(f"{role}@example.com")
        add_member(client, owner, org, f"{role}@example.com", role)
    make_user("spare@example.com")  # someone an owner can add

    scan = upload(client, owner, org, scangen.point_cloud(3_000)).json()["id"]
    client.run_jobs()
    target = next(m["user_id"] for m in client.get(f"/api/v1/orgs/{org}", headers=owner).json()["members"]
                  if m["email"] == "viewer@example.com")
    return {"org": org, "scan": scan, "target": target, "callers": callers}


def send(client, world, method, path, headers):
    url = "/api/v1" + path.format(org=world["org"], scan=world["scan"], target=world["target"])
    if path == "/orgs/{org}/scans" and method == "POST":
        return client.post(url, files={"file": ("new.ply", scangen.point_cloud(500))}, headers=headers)
    if path == "/orgs/{org}/members" and method == "POST":
        return client.post(url, json={"email": "spare@example.com", "role": "viewer"}, headers=headers)
    if method == "PATCH":
        return client.patch(url, json={"role": "editor"}, headers=headers)
    return client.request(method, url, headers=headers)


def expected(caller, minimum, success):
    if caller == "anonymous":
        return 401
    if caller == "outsider":
        return 404
    return success if ROLE_RANK[Role(caller)] >= ROLE_RANK[Role(minimum)] else 403


@pytest.mark.parametrize("caller", CALLERS)
@pytest.mark.parametrize("name, method, path, minimum, success", ENDPOINTS, ids=[e[0] for e in ENDPOINTS])
def test_permission_matrix(client, world, name, method, path, minimum, success, caller):
    response = send(client, world, method, path, world["callers"][caller])
    assert response.status_code == expected(caller, minimum, success), response.text


@pytest.mark.parametrize("caller", ["outsider", "viewer", "editor", "owner"])
def test_any_signed_in_user_can_list_and_create_orgs_but_anonymous_cannot(client, world, caller):
    headers = world["callers"][caller]
    assert client.get("/api/v1/orgs", headers=headers).status_code == 200
    assert client.post("/api/v1/orgs", json={"name": "Another"}, headers=headers).status_code == 201


def test_anonymous_cannot_list_or_create_orgs(client):
    assert client.get("/api/v1/orgs").status_code == 401
    assert client.post("/api/v1/orgs", json={"name": "x"}).status_code == 401


def test_a_scan_id_from_another_org_gives_404_even_to_an_owner(client, world, make_user):
    other_owner = make_user("other@example.com")
    make_org(client, other_owner, "Other")
    for suffix in ("", "/preview"):
        response = client.get(f"/api/v1/scans/{world['scan']}{suffix}", headers=other_owner)
        assert response.status_code == 404
    assert client.delete(f"/api/v1/scans/{world['scan']}", headers=other_owner).status_code == 404


def test_removed_member_loses_access_immediately(client, world):
    owner = world["callers"]["owner"]
    viewer = world["callers"]["viewer"]
    assert client.get(f"/api/v1/scans/{world['scan']}", headers=viewer).status_code == 200
    client.delete(f"/api/v1/orgs/{world['org']}/members/{world['target']}", headers=owner)
    assert client.get(f"/api/v1/scans/{world['scan']}", headers=viewer).status_code == 404


def test_demoted_editor_can_no_longer_upload(client, world):
    owner, editor = world["callers"]["owner"], world["callers"]["editor"]
    editor_id = next(m["user_id"] for m in client.get(f"/api/v1/orgs/{world['org']}", headers=owner).json()["members"]
                     if m["email"] == "editor@example.com")
    client.patch(f"/api/v1/orgs/{world['org']}/members/{editor_id}", json={"role": "viewer"}, headers=owner)
    denied = upload(client, editor, world["org"], scangen.point_cloud(500))
    assert denied.status_code == 403


def test_error_bodies_always_have_the_same_shape(client, world):
    for caller in ("anonymous", "outsider", "viewer"):
        body = send(client, world, "DELETE", "/scans/{scan}", world["callers"][caller]).json()
        assert set(body) == {"error", "message"}
