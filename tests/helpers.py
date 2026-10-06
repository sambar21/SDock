def make_org(client, headers, name="Studio"):
    return client.post("/api/v1/orgs", json={"name": name}, headers=headers).json()["id"]


def add_member(client, owner_headers, org_id, email, role):
    url = f"/api/v1/orgs/{org_id}/members"
    return client.post(url, json={"email": email, "role": role}, headers=owner_headers)


def upload(client, headers, org_id, data, filename="scan.ply", name=None):
    form = {"name": name} if name else None
    return client.post(
        f"/api/v1/orgs/{org_id}/scans", files={"file": (filename, data)}, data=form, headers=headers
    )
