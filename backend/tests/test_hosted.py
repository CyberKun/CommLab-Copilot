import pytest
from fastapi.testclient import TestClient
from commlab.assembly import Services
from commlab.http import create_app
from commlab.local_worker import tick
from commlab.db import _normalize_url
from commlab.hosted import main


def test_database_artifacts_survive_new_service_instance(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_BACKEND", "database")
    url = f"sqlite:///{tmp_path}/hosted.db"
    first = Services(url)
    with TestClient(create_app(first)) as client:
        workspace = client.post("/api/workspaces", json={"name": "hosted"}).json()
        prefix = f"/api/workspaces/{workspace['id']}"
        headers = {"Authorization": f"Bearer {workspace['token']}", "Idempotency-Key": "hosted"}
        run = client.post(prefix + "/runs", headers=headers, json={"channel": "awgn", "ebn0_db": [0], "bits_per_point": 1000}).json()
        tick(first)
        finished = client.get(prefix + "/runs/" + run["id"], headers=headers).json()
        assert finished["status"] == "succeeded"
        artifact = prefix + "/artifacts/" + finished["plot_artifact_id"]
        original = client.get(artifact, headers=headers).content
        assert b"<svg" in original
    second = Services(url)
    with TestClient(create_app(second)) as client:
        assert client.get(artifact, headers=headers).content == original
        other = client.post("/api/workspaces", json={"name": "other"}).json()
        denied = client.get(f"/api/workspaces/{other['id']}/artifacts/{finished['plot_artifact_id']}",
                            headers={"Authorization": f"Bearer {other['token']}"})
        assert denied.status_code == 404


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_provider_database_urls(scheme):
    assert _normalize_url(scheme + "://user:pass@host/db?sslmode=require") == "postgresql+psycopg://user:pass@host/db?sslmode=require"


def test_hosted_rejects_ephemeral_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///temporary.db")
    with pytest.raises(RuntimeError, match="durable PostgreSQL"):
        main()
