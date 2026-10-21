from test_flow import system
from commlab.local_worker import tick


def test_documents_agent_and_isolation(system):
    services, client = system
    a = client.post("/api/workspaces", json={"name": "a"}).json()
    b = client.post("/api/workspaces", json={"name": "b"}).json()
    prefix = f"/api/workspaces/{a['id']}"
    headers = {"Authorization": f"Bearer {a['token']}"}
    source = client.post(prefix + "/sources", headers=headers,
        files={"file": ("lab.md", b"# Synthetic BPSK handout\n\nBPSK Rayleigh uses perfect channel knowledge and unit average channel power.", "text/plain")})
    assert source.status_code == 200, source.text
    tick(services)
    result = client.post(prefix + "/search", headers=headers, json={"query": "BPSK Rayleigh"}).json()
    assert result["evidence"]
    evidence = result["evidence"][0]
    assert client.get(prefix + "/evidence/" + evidence["id"], headers=headers).json()["source"]["version_id"] == source.json()["id"]
    b_prefix, b_headers = f"/api/workspaces/{b['id']}", {"Authorization": f"Bearer {b['token']}"}
    assert not client.post(b_prefix + "/search", headers=b_headers, json={"query": "BPSK"}).json()["evidence"]
    assert client.get(b_prefix + "/evidence/" + evidence["id"], headers=b_headers).status_code == 404
    assert client.get(b_prefix + "/artifacts/" + evidence["source"]["artifact_id"], headers=b_headers).status_code == 404
    investigation = client.post(prefix + "/investigations", headers=headers,
        json={"question": "Compare BPSK over AWGN and Rayleigh using the handout"}).json()
    for _ in range(5):
        tick(services)
    state = client.get(prefix + "/investigations/" + investigation["id"], headers=headers).json()
    assert state["status"] == "review", state
    assert state["answer"]["retrieved_facts"]
    assert not services.experiments.find(a["id"])
    specs = [{**x, "bits_per_point": 1000} for x in state["plans"]]
    approval = client.post(prefix + "/investigations/" + investigation["id"] + "/approve", headers=headers, json={"specs": specs})
    assert approval.status_code == 200, approval.text
    for _ in range(3):
        tick(services)
    state = services.investigations.inspect(a["id"], investigation["id"])
    assert state["status"] == "finished"
    assert len(state["answer"]["observed_results"]) == 2
    assert all(r["status"] == "succeeded" for r in state["answer"]["observed_results"])
    assert client.get(b_prefix + "/investigations/" + investigation["id"], headers=b_headers).status_code == 404


def test_upload_and_unsupported(system):
    services, client = system
    a = client.post("/api/workspaces", json={"name": "a"}).json()
    prefix, headers = f"/api/workspaces/{a['id']}", {"Authorization": f"Bearer {a['token']}"}
    assert client.post(prefix + "/sources", headers=headers, files={"file": ("bad.pdf", b"bad")}).status_code == 400
    assert client.post(prefix + "/sources", headers=headers, files={"file": ("bad.txt", b"x"*2_000_001)}).status_code == 413
    inv = client.post(prefix + "/investigations", headers=headers, json={"question": "Simulate OFDM"}).json()
    tick(services)
    state = services.investigations.inspect(a["id"], inv["id"])
    assert state["status"] == "finished"
    assert "Unsupported" in state["answer"]["hypotheses"][0]
    assert not state["plans"]
