def make_org(client, headers, name="Studio"):
    return client.post("/api/v1/orgs", json={"name": name}, headers=headers).json()["id"]


def test_creator_becomes_owner(client, make_user):
    owner = make_user("owner@example.com")
    org = client.post("/api/v1/orgs", json={"name": "Studio"}, headers=owner)
    assert org.status_code == 201
    assert org.json()["your_role"] == "owner"


def test_my_orgs_lists_only_orgs_i_belong_to_with_my_role(client, make_user):
    owner = make_user("owner@example.com")
    other = make_user("other@example.com")
    shared = make_org(client, owner, "Shared")
    make_org(client, owner, "Private")
    client.post(
        f"/api/v1/orgs/{shared}/members", json={"email": "other@example.com", "role": "viewer"}, headers=owner
    )

    mine = client.get("/api/v1/orgs", headers=owner).json()
    assert [(o["name"], o["your_role"]) for o in mine] == [("Private", "owner"), ("Shared", "owner")]
    theirs = client.get("/api/v1/orgs", headers=other).json()
    assert [(o["name"], o["your_role"]) for o in theirs] == [("Shared", "viewer")]
    assert client.get("/api/v1/orgs").status_code == 401


def test_owner_adds_changes_and_removes_members(client, make_user):
    owner = make_user("owner@example.com")
    make_user("ed@example.com")
    org_id = make_org(client, owner)
    base = f"/api/v1/orgs/{org_id}/members"

    added = client.post(base, json={"email": "ed@example.com", "role": "viewer"}, headers=owner)
    assert added.status_code == 201
    user_id = added.json()["user_id"]

    changed = client.patch(f"{base}/{user_id}", json={"role": "editor"}, headers=owner)
    assert changed.json()["role"] == "editor"

    assert client.delete(f"{base}/{user_id}", headers=owner).status_code == 204
    assert len(client.get(f"/api/v1/orgs/{org_id}", headers=owner).json()["members"]) == 1


def test_adding_unknown_user_or_duplicate_fails(client, make_user):
    owner = make_user("owner@example.com")
    make_user("ed@example.com")
    org_id = make_org(client, owner)
    base = f"/api/v1/orgs/{org_id}/members"
    ghost = client.post(base, json={"email": "ghost@example.com", "role": "viewer"}, headers=owner)
    assert ghost.status_code == 404
    client.post(base, json={"email": "ed@example.com", "role": "viewer"}, headers=owner)
    again = client.post(base, json={"email": "ed@example.com", "role": "viewer"}, headers=owner)
    assert again.status_code == 409


def test_last_owner_cannot_leave_or_step_down(client, make_user):
    owner = make_user("owner@example.com")
    org_id = make_org(client, owner)
    me = client.get(f"/api/v1/orgs/{org_id}", headers=owner).json()["members"][0]["user_id"]
    url = f"/api/v1/orgs/{org_id}/members/{me}"
    assert client.delete(url, headers=owner).json()["error"] == "last_owner"
    assert client.patch(url, json={"role": "viewer"}, headers=owner).json()["error"] == "last_owner"


def test_non_owner_cannot_manage_members(client, make_user):
    owner = make_user("owner@example.com")
    editor = make_user("ed@example.com")
    make_user("new@example.com")
    org_id = make_org(client, owner)
    base = f"/api/v1/orgs/{org_id}/members"
    client.post(base, json={"email": "ed@example.com", "role": "editor"}, headers=owner)
    denied = client.post(base, json={"email": "new@example.com", "role": "viewer"}, headers=editor)
    assert denied.status_code == 403


def test_outsider_gets_404_not_403(client, make_user):
    owner = make_user("owner@example.com")
    outsider = make_user("out@example.com")
    org_id = make_org(client, owner)
    assert client.get(f"/api/v1/orgs/{org_id}", headers=outsider).status_code == 404
    assert client.get("/api/v1/orgs/does-not-exist", headers=owner).status_code == 404
