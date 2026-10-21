"""Opt-in real PostgreSQL/Redis smoke test; never silently substitute SQLite."""
import os
import subprocess
import sys
import time
import pytest
from commlab.assembly import Services
from commlab.simulation.api import ExperimentSpec
from commlab.retrieval.api import RetrievalRequest
from commlab.jobs import dispatch


@pytest.mark.skipif(not os.getenv("COMMLAB_TEST_POSTGRES"), reason="Real PostgreSQL/Redis services not configured")
def test_postgres_pgvector_and_real_dramatiq_delivery(tmp_path):
    # Requires DATABASE_URL/REDIS_URL and migrated isolated test database.
    services = Services(storage=str(tmp_path/"artifacts"))
    assert services.engine.dialect.name == "postgresql"
    w = services.workspaces.create("real infrastructure test")["id"]
    source = services.knowledge.upload(w,"source.txt",b"Coherent BPSK uses perfect receiver channel knowledge.","integration")
    services.knowledge.ingest(w,source["id"])
    evidence = services.retrieval.search(w,RetrievalRequest(query="BPSK channel knowledge"))
    assert evidence.evidence and evidence.evidence[0].source.version_id == source["id"]
    partial = services.retrieval.search(w, RetrievalRequest(query="Explain BPSK receiver assumptions please"))
    assert partial.evidence and partial.evidence[0].source.version_id == source["id"]
    assert services.retrieval.search(w, RetrievalRequest(query="quasar telescope" )).insufficient_evidence
    assert services.retrieval.search(w, RetrievalRequest(query="!!!")).insufficient_evidence
    run = services.experiments.submit(w,ExperimentSpec(ebn0_db=[0],bits_per_point=1000,seed=2**32-1),"queue","integration")
    # Artifact root must be identical in both processes.
    env = {**os.environ,"ARTIFACT_ROOT":str(tmp_path/"artifacts")}
    worker = subprocess.Popen([sys.executable,"-m","dramatiq","commlab.worker","--processes","1","--threads","1","--queues","simulation"],
                              env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        from commlab.worker import send
        dispatch(services.sessions,send)
        deadline = time.monotonic()+30
        while time.monotonic()<deadline:
            actual = services.experiments.inspect(w,run.id)
            if actual.status in ["succeeded","failed"]:
                break
            time.sleep(.2)
        assert actual.status == "succeeded"
        send("simulation",{"workspace":w,"id":run.id,"correlation_id":"duplicate"})
        assert services.experiments.inspect(w,run.id).attempts == 1
    finally:
        worker.terminate()
        worker.wait(timeout=10)
