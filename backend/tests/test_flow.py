import pytest
from fastapi.testclient import TestClient
from commlab.assembly import Services
from commlab.http import create_app
from commlab.jobs import dispatch


@pytest.fixture
def system(tmp_path):
    services = Services(f"sqlite:///{tmp_path}/test.db", str(tmp_path / "artifacts"))
    with TestClient(create_app(services)) as client:
        yield services, client


def test_experiment_product_flow(system):
    services, client = system
    workspace = client.post("/api/workspaces", json={"name": "lab"}).json()
    prefix = f"/api/workspaces/{workspace['id']}"
    headers = {"Authorization": f"Bearer {workspace['token']}", "Idempotency-Key": "demo"}
    body = {"channel": "rayleigh", "ebn0_db": [0, 4], "bits_per_point": 1000}
    response = client.post(prefix + "/runs", json=body, headers=headers)
    assert response.status_code == 200, response.text
    run = response.json()
    assert client.post(prefix + "/runs", json=body, headers=headers).json()["id"] == run["id"]
    assert client.post(prefix + "/runs", json={**body, "seed": 1}, headers=headers).status_code == 409
    assert client.get(prefix + "/runs/" + run["id"]).status_code == 404
    messages = []
    assert dispatch(services.sessions, lambda k, p: messages.append(p)) == 1
    for _ in range(2):
        services.experiments.execute(workspace["id"], messages[0]["id"])
    finished = client.get(prefix + "/runs/" + run["id"], headers=headers).json()
    assert finished["status"] == "succeeded"
    assert finished["attempts"] == 1
    assert finished["result"]["points"][0]["bits"] == 1000
    artifact = prefix + "/artifacts/" + finished["artifact_id"]
    assert client.get(artifact, headers=headers).status_code == 200
    assert client.get(artifact).status_code == 404
    plot = client.get(prefix + "/artifacts/" + finished["plot_artifact_id"], headers=headers)
    assert plot.status_code == 200 and b"<svg" in plot.content
    headers["Idempotency-Key"] = "cancel"
    cancelled = client.post(prefix + "/runs", json=body, headers=headers).json()
    client.post(prefix + "/runs/" + cancelled["id"] + "/cancel", headers=headers)
    services.experiments.execute(workspace["id"], cancelled["id"])
    assert services.experiments.inspect(workspace["id"], cancelled["id"]).status == "cancelled"
