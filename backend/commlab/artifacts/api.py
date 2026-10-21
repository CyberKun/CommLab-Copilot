import hashlib
import os
from pathlib import Path
from typing import Protocol
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from commlab.common import Contract, DomainError, uid
from commlab.db import Base


class ArtifactRef(Contract):
    id: str
    workspace_id: str
    sha256: str
    media_type: str
    size_bytes: int
    schema_version: int = 1


class BlobStore(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...


class LocalStore:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise DomainError("invalid_path", "Invalid artifact key.")
        return path

    def put(self, key, content):
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix("." + uid() + ".partial")
        with temp.open("wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)

    def get(self, key):
        return self.path(key).read_bytes()


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(index=True)
    key: Mapped[str]
    sha256: Mapped[str]
    media_type: Mapped[str]
    size_bytes: Mapped[int]


class Artifacts:
    def __init__(self, sessions, store: BlobStore):
        self.sessions, self.store = sessions, store

    def save(self, workspace, content: bytes, media_type: str) -> ArtifactRef:
        ident = uid()
        key = f"{workspace}/{ident}"
        self.store.put(key, content)
        with self.sessions.begin() as s:
            row = Artifact(id=ident, workspace_id=workspace, key=key,
                           sha256=hashlib.sha256(content).hexdigest(), media_type=media_type,
                           size_bytes=len(content))
            s.add(row)
        return ArtifactRef(id=ident, workspace_id=workspace, sha256=row.sha256,
                           media_type=media_type, size_bytes=len(content))

    def load(self, workspace, ident):
        with self.sessions() as s:
            row = s.get(Artifact, ident)
            if not row or row.workspace_id != workspace:
                raise DomainError("not_found", "Artifact not found.", 404)
            content = self.store.get(row.key)
            if hashlib.sha256(content).hexdigest() != row.sha256:
                raise DomainError("artifact_integrity", "Stored artifact checksum does not match.", 500)
            return content, row.media_type
