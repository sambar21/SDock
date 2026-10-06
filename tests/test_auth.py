def test_register_then_login(client):
    creds = {"email": "Ada@Example.com", "password": "password123"}
    assert client.post("/api/v1/auth/register", json=creds).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "password123"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_duplicate_email_is_rejected(client):
    creds = {"email": "ada@example.com", "password": "password123"}
    client.post("/api/v1/auth/register", json=creds)
    again = client.post("/api/v1/auth/register", json=creds)
    assert again.status_code == 409
    assert again.json()["error"] == "email_taken"


def test_wrong_password_and_unknown_email_look_the_same(client):
    client.post("/api/v1/auth/register", json={"email": "ada@example.com", "password": "password123"})
    wrong = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "nope-nope-1"})
    unknown = client.post("/api/v1/auth/login", json={"email": "who@example.com", "password": "nope-nope-1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_short_password_and_bad_email_are_rejected(client):
    assert client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "short"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={"email": "nope", "password": "password123"}).status_code == 422


def test_missing_or_garbage_token_is_401(client):
    assert client.post("/api/v1/orgs", json={"name": "x"}).status_code == 401
    bad = client.post("/api/v1/orgs", json={"name": "x"}, headers={"Authorization": "Bearer garbage"})
    assert bad.status_code == 401
    assert bad.json()["error"] == "not_authenticated"
