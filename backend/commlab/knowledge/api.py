import hashlib
import io
import math
import re
import time
from datetime import datetime, timedelta
from typing import Protocol
import httpx
from pgvector.sqlalchemy import Vector
from pypdf import PdfReader
from sqlalchemy import JSON, DateTime, func, select, update, literal, cast
from sqlalchemy.orm import Mapped, mapped_column
from commlab.common import Contract, DomainError, uid, now
from commlab.db import Base
from commlab.jobs import enqueue

DIMENSIONS = 384


def tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class EmbeddingProvider(Protocol):
    model: str
    index_version: str
    def embed(self, text: str) -> list[float]: ...


class HashEmbedding:
    """Offline lexical baseline, NOT a learned semantic embedding."""
    model, index_version = "signed-token-hash-384", "1"

    def embed(self, text):
        vector = [0.0] * DIMENSIONS
        for token in tokens(text):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % DIMENSIONS] += 1 if digest[4] & 1 else -1
        norm = math.sqrt(sum(x*x for x in vector)) or 1
        return [x / norm for x in vector]


class OllamaEmbedding:
    index_version = "1"

    def __init__(self, base_url, model, revision):
        self.base_url, self.tag, self.revision = base_url, model, revision
        self.model = f"ollama:{model}@{revision or 'UNPINNED'}"

    def embed(self, text):
        if not self.revision:
            raise DomainError("embedding_unpinned", "Set EMBEDDING_REVISION to the installed model digest.")
        models = httpx.get(self.base_url + "/api/tags", timeout=10)
        models.raise_for_status()
        matching = [m for m in models.json().get("models", []) if m["name"] in [self.tag, self.tag+":latest"]]
        if not matching or matching[0].get("digest") != self.revision:
            raise DomainError("embedding_revision_changed", "Embedding model digest changed; create a new versioned index.")
        response = httpx.post(self.base_url + "/api/embed", json={"model": self.tag, "input": text, "truncate": False}, timeout=30)
        response.raise_for_status()
        result = response.json()["embeddings"][0]
        if len(result) != DIMENSIONS or not all(math.isfinite(v) for v in result):
            raise DomainError("embedding_incompatible", "Embedding must contain 384 finite dimensions.")
        return result


class SourceRef(Contract):
    source_id: str
    version_id: str
    content_sha256: str
    title: str
    page: int | None
    section: str | None
    artifact_id: str


class EvidenceChunk(Contract):
    id: str
    source: SourceRef
    text: str
    extraction_warnings: list[str]
    embedding_model: str
    index_version: str
    schema_version: int = 1


class SourceView(Contract):
    id: str
    source_id: str
    title: str
    artifact_id: str
    status: str
    warnings: list[str]
    error: str | None
    content_sha256: str
    correlation_id: str


class SourceVersion(Base):
    __tablename__ = "source_versions"
    id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(index=True)
    workspace_id: Mapped[str] = mapped_column(index=True)
    title: Mapped[str]
    content_sha256: Mapped[str]
    artifact_id: Mapped[str]
    status: Mapped[str]
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime)
    heartbeat: Mapped[datetime] = mapped_column(DateTime)
    lease: Mapped[str | None]
    attempts: Mapped[int] = mapped_column(default=0)
    correlation_id: Mapped[str]


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(index=True)
    version_id: Mapped[str] = mapped_column(index=True)
    text: Mapped[str]
    page: Mapped[int | None]
    section: Mapped[str | None]
    embedding: Mapped[list] = mapped_column(JSON().with_variant(Vector(DIMENSIONS), "postgresql"))
    embedding_model: Mapped[str]
    index_version: Mapped[str]


class Knowledge:
    def __init__(self, sessions, artifacts, embeddings: EmbeddingProvider):
        self.sessions, self.artifacts, self.embeddings = sessions, artifacts, embeddings

    def upload(self, workspace, filename, content, correlation, source_id=None):
        title = re.split(r"[/\\]", filename or "source.txt")[-1][:160]
        if len(content) > 2_000_000 or not content:
            raise DomainError("upload_size", "Upload must contain 1 byte to 2 MB.", 413)
        is_pdf = title.lower().endswith(".pdf")
        if not title.lower().endswith((".pdf", ".txt", ".md")) or (is_pdf and not content.startswith(b"%PDF-")):
            raise DomainError("upload_type", "Only valid PDF, UTF-8 TXT, and Markdown files are supported.")
        if not is_pdf:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                raise DomainError("upload_encoding", "Text uploads must use UTF-8.")
        if source_id:
            with self.sessions() as s:
                if not s.scalar(select(SourceVersion.id).where(SourceVersion.workspace_id == workspace,
                                                               SourceVersion.source_id == source_id)):
                    raise DomainError("not_found", "Source not found.", 404)
        artifact = self.artifacts.save(workspace, content, "application/pdf" if is_pdf else "text/plain")
        with self.sessions.begin() as s:
            row = SourceVersion(id=uid(), source_id=source_id or uid(), workspace_id=workspace, title=title,
                                artifact_id=artifact.id, content_sha256=artifact.sha256, status="queued",
                                warnings=[], created_at=now(), heartbeat=now(), attempts=0, correlation_id=correlation)
            s.add(row)
            enqueue(s, "ingestion", {"workspace": workspace, "id": row.id, "correlation_id": correlation})
        return self.describe(row)

    @staticmethod
    def describe(row):
        return {k: getattr(row, k) for k in ["id", "source_id", "title", "artifact_id", "status",
                                             "warnings", "error", "content_sha256", "correlation_id"]}

    def sources(self, workspace):
        with self.sessions() as s:
            return [self.describe(r) for r in s.scalars(select(SourceVersion).where(SourceVersion.workspace_id == workspace)
                                                       .order_by(SourceVersion.created_at.desc()))]

    def ingest(self, workspace, ident):
        lease = uid()
        source = None
        started = time.monotonic()
        with self.sessions.begin() as s:
            changed = s.execute(update(SourceVersion).where(SourceVersion.id == ident, SourceVersion.workspace_id == workspace,
                                                            SourceVersion.status == "queued")
                                .values(status="running", lease=lease, heartbeat=now(), attempts=SourceVersion.attempts+1))
            if not changed.rowcount:
                return
        try:
            with self.sessions() as s:
                source = s.get(SourceVersion, ident)
            content, media = self.artifacts.load(workspace, source.artifact_id)
            warnings = []
            if media == "application/pdf":
                reader = PdfReader(io.BytesIO(content))
                if reader.is_encrypted or len(reader.pages) > 100:
                    raise DomainError("pdf_limits", "Encrypted PDFs and PDFs over 100 pages are unsupported.")
                pages = [(i+1, p.extract_text() or "") for i, p in enumerate(reader.pages)]
                warnings.append("PDF equations are unvalidated text extraction; inspect the original before using formulas.")
                if any(not text.strip() for _, text in pages):
                    warnings.append("One or more pages have no extracted text; OCR is not available.")
            else:
                pages = [(None, content.decode("utf-8"))]
            if sum(len(t) for _, t in pages) > 500_000:
                raise DomainError("extraction_limit", "Extracted text exceeds 500,000 characters.")
            chunks = []
            for page, text in pages:
                if "\ufffd" in text:
                    warnings.append("Replacement characters detected; extraction may be corrupted.")
                section = None
                # Paragraphs retain equation/definition context; oversize blocks are flagged.
                for paragraph in re.split(r"\n\s*\n", text):
                    paragraph = paragraph.strip()
                    if not paragraph:
                        continue
                    if paragraph.startswith("#"):
                        section = paragraph.splitlines()[0].lstrip("# ")[:120]
                    if len(paragraph) > 4000:
                        warnings.append("Oversize paragraph split; equation context may span chunks.")
                    for start in range(0, len(paragraph), 3600):
                        if len(chunks) >= 250 or time.monotonic()-started > 120:
                            raise DomainError("ingestion_limit", "Ingestion exceeded 250 chunks or 120 seconds.")
                        block = paragraph[start:start+4000]
                        chunks.append(Chunk(id=uid(), workspace_id=workspace, version_id=ident, page=page,
                                            section=section, text=block, embedding=self.embeddings.embed(block),
                                            embedding_model=self.embeddings.model, index_version=self.embeddings.index_version))
                        with self.sessions.begin() as s:
                            active = s.execute(update(SourceVersion).where(SourceVersion.id == ident, SourceVersion.lease == lease)
                                               .values(heartbeat=now()))
                            if not active.rowcount:
                                return
            if not chunks:
                raise DomainError("no_text", "No searchable text extracted. Upload a text version.")
            with self.sessions.begin() as s:
                changed = s.execute(update(SourceVersion).where(SourceVersion.id == ident, SourceVersion.lease == lease,
                                                                SourceVersion.status == "running")
                                    .values(status="ready", warnings=list(dict.fromkeys(warnings)), lease=None, error=None))
                if changed.rowcount:
                    s.add_all(chunks)
        except Exception as exc:
            transient = isinstance(exc, (httpx.TransportError, OSError))
            with self.sessions.begin() as s:
                state = "queued" if transient and source and source.attempts < 3 else "failed"
                changed = s.execute(update(SourceVersion).where(SourceVersion.id == ident, SourceVersion.lease == lease)
                                    .values(status=state, lease=None,
                                            error=exc.message if isinstance(exc, DomainError) else "Parser or embedding provider failed."))
                if changed.rowcount and state == "queued":
                    enqueue(s, "ingestion", {"workspace": workspace, "id": ident, "correlation_id": source.correlation_id})

    def recover(self):
        with self.sessions.begin() as s:
            for row in s.scalars(select(SourceVersion).where(SourceVersion.status == "running",
                               SourceVersion.heartbeat < now()-timedelta(seconds=180)).with_for_update(skip_locked=True)):
                row.status = "queued" if row.attempts < 3 else "failed"
                row.lease = None
                row.error = "Ingestion worker interrupted."
                if row.status == "queued":
                    enqueue(s, "ingestion", {"workspace": row.workspace_id, "id": row.id, "correlation_id": row.correlation_id})
            for row in s.scalars(select(SourceVersion).where(SourceVersion.status == "queued",
                               SourceVersion.heartbeat < now()-timedelta(seconds=60)).with_for_update(skip_locked=True)):
                row.heartbeat = now()
                enqueue(s, "ingestion", {"workspace": row.workspace_id, "id": row.id, "correlation_id": row.correlation_id})

    def evidence(self, chunk, source):
        return EvidenceChunk(id=chunk.id, source=SourceRef(source_id=source.source_id, version_id=source.id,
            content_sha256=source.content_sha256, title=source.title, page=chunk.page, section=chunk.section,
            artifact_id=source.artifact_id), text=chunk.text, extraction_warnings=source.warnings,
            embedding_model=chunk.embedding_model, index_version=chunk.index_version)

    def chunk(self, workspace, ident):
        with self.sessions() as s:
            chunk = s.get(Chunk, ident)
            if not chunk or chunk.workspace_id != workspace:
                raise DomainError("not_found", "Evidence not found.", 404)
            return self.evidence(chunk, s.get(SourceVersion, chunk.version_id))

    def candidates(self, workspace, query, embedding, versions, limit=30):
        """Public query boundary. Workspace/version/index filters precede ranking."""
        with self.sessions() as s:
            versions_query = select(SourceVersion).where(SourceVersion.workspace_id == workspace, SourceVersion.status == "ready")
            if versions:
                versions_query = versions_query.where(SourceVersion.id.in_(versions))
            sources = s.scalars(versions_query.order_by(SourceVersion.created_at.desc())).all()
            if not versions:
                latest = {}
                for source in sources:
                    latest.setdefault(source.source_id, source)
                sources = list(latest.values())
            source_map = {r.id: r for r in sources}
            base = select(Chunk).where(Chunk.workspace_id == workspace, Chunk.version_id.in_(source_map),
                                      Chunk.embedding_model == self.embeddings.model,
                                      Chunk.index_version == self.embeddings.index_version)
            if s.bind.dialect.name == "postgresql":
                # A natural-language question rarely has every word in one chunk.
                # Match any normalized term, as the portable candidate path does.
                # tokens() emits only alphanumerics; raw query syntax is never used.
                terms = sorted(set(tokens(query)))
                if not terms:
                    return [], []
                lex = func.ts_rank_cd(func.to_tsvector("simple", Chunk.text),
                                      func.to_tsquery("simple", " | ".join(terms)))
                keyword = s.scalars(base.where(lex > 0).order_by(lex.desc()).limit(limit)).all()
                distance = Chunk.embedding.op("<=>")(cast(literal(embedding, type_=Vector(DIMENSIONS)), Vector(DIMENSIONS)))
                vector = s.scalars(base.order_by(distance).limit(limit)).all()
            else:
                # Portable test/dev implementation of the same filtered read interface.
                rows = s.scalars(base).all()
                q = set(tokens(query))
                keyword = sorted([r for r in rows if q.intersection(tokens(r.text))],
                                 key=lambda r: len(q.intersection(tokens(r.text))), reverse=True)[:limit]
                vector = sorted(rows, key=lambda r: sum(a*b for a, b in zip(r.embedding, embedding)), reverse=True)[:limit]
            return ([self.evidence(r, source_map[r.version_id]) for r in keyword],
                    [self.evidence(r, source_map[r.version_id]) for r in vector])
