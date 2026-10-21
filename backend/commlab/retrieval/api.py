import time
from typing import Protocol
from pydantic import Field
from commlab.common import Contract
from commlab.knowledge.api import EvidenceChunk, tokens


class RetrievalRequest(Contract):
    query: str = Field(min_length=1, max_length=2000)
    version_ids: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=5, ge=1, le=10)


class RetrievalResult(Contract):
    evidence: list[EvidenceChunk]
    insufficient_evidence: bool
    strategy: str
    embedding_model: str
    index_version: str
    latency_seconds: float
    warnings: list[str]


class RetrievalStrategy(Protocol):
    def rank(self, keyword: list[EvidenceChunk], vector: list[EvidenceChunk], limit: int) -> list[EvidenceChunk]: ...


class ReciprocalRankFusion:
    def rank(self, keyword, vector, limit):
        scores, chunks = {}, {}
        for ranking in [keyword, vector]:
            for i, chunk in enumerate(ranking):
                scores[chunk.id] = scores.get(chunk.id, 0) + 1 / (60 + i + 1)
                chunks[chunk.id] = chunk
        return [chunks[key] for key in sorted(scores, key=scores.get, reverse=True)[:limit]]


class Retrieval:
    def __init__(self, knowledge, embeddings, strategy: RetrievalStrategy):
        self.knowledge, self.embeddings, self.strategy = knowledge, embeddings, strategy

    def search(self, workspace, request: RetrievalRequest):
        start = time.monotonic()
        kw, vec = self.knowledge.candidates(workspace, request.query, self.embeddings.embed(request.query), request.version_ids)
        # Offline hash embeddings cannot establish semantic relevance by themselves.
        offline = self.embeddings.model.startswith("signed-token-hash")
        if offline:
            valid = {c.id for c in kw}
            vec = [c for c in vec if c.id in valid]
        evidence = self.strategy.rank(kw, vec, request.limit)
        return RetrievalResult(evidence=evidence, insufficient_evidence=not evidence, strategy="hybrid-rrf-v1",
            embedding_model=self.embeddings.model, index_version=self.embeddings.index_version,
            latency_seconds=time.monotonic()-start,
            warnings=["Offline lexical hash baseline; semantic recall is limited."] if offline else [])
