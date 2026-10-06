import pytest
from pydantic import ValidationError

from app.core.config import DEV_SECRET, Settings


def test_dev_mode_allows_the_default_secret():
    assert Settings(environment="dev", secret_key=DEV_SECRET).secret_key == DEV_SECRET


@pytest.mark.parametrize("secret", [DEV_SECRET, "short", "x" * 31])
def test_real_deployments_refuse_weak_secrets(secret):
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key=secret)


def test_real_deployments_accept_a_long_secret():
    assert Settings(environment="production", secret_key="k" * 40).environment == "production"


def test_docs_offer_an_authorize_button_and_describe_errors(client):
    spec = client.get("/openapi.json").json()
    assert any(s["type"] == "http" and s["scheme"] == "bearer" for s in spec["components"]["securitySchemes"].values())
    upload = spec["paths"]["/api/v1/orgs/{org_id}/scans"]["post"]
    assert {"202", "400", "401", "403", "404", "413", "503"} <= set(upload["responses"])
    assert "ErrorBody" in spec["components"]["schemas"]


def test_every_api_route_lives_under_v1(client):
    paths = [p for p in client.get("/openapi.json").json()["paths"]]
    assert paths and all(p.startswith("/api/v1/") for p in paths)


def test_root_sends_people_to_the_viewer(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/viewer/"
    assert client.get("/viewer/").status_code == 200
