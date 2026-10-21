from test_flow import system
from commlab.retrieval.api import RetrievalRequest
from commlab.knowledge.api import HashEmbedding


def test_source_version_filters_and_embedding_isolation(system):
    services, _ = system
    w = services.workspaces.create("versions")["id"]
    old = services.knowledge.upload(w, "v1.txt", b"BPSK old receiver convention", "test")
    services.knowledge.ingest(w, old["id"])
    new = services.knowledge.upload(w, "v2.txt", b"BPSK new receiver convention", "test", old["source_id"])
    services.knowledge.ingest(w, new["id"])
    latest = services.retrieval.search(w, RetrievalRequest(query="BPSK"))
    assert all(e.source.version_id == new["id"] for e in latest.evidence)
    historic = services.retrieval.search(w, RetrievalRequest(query="BPSK", version_ids=[old["id"]]))
    assert historic.evidence[0].source.version_id == old["id"]
    class NewIndex(HashEmbedding):
        index_version = "2"
    services.knowledge.embeddings = NewIndex()
    services.retrieval.embeddings = services.knowledge.embeddings
    assert services.retrieval.search(w, RetrievalRequest(query="BPSK")).insufficient_evidence
