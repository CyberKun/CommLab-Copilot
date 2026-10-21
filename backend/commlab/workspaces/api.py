import hashlib
import secrets
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from commlab.common import DomainError, uid
from commlab.db import Base


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str]
    token_hash: Mapped[str] = mapped_column(unique=True)


class Workspaces:
    """MVP owner-token authorization. Only token hashes are persisted."""
    def __init__(self, sessions):
        self.sessions = sessions

    def create(self, name: str):
        token = secrets.token_urlsafe(32)
        with self.sessions.begin() as s:
            row = Workspace(id=uid(), name=name, token_hash=hashlib.sha256(token.encode()).hexdigest())
            s.add(row)
        return {"id": row.id, "name": name, "token": token}

    def authorize(self, workspace: str, token: str):
        with self.sessions() as s:
            row = s.get(Workspace, workspace)
            if not row or not secrets.compare_digest(row.token_hash, hashlib.sha256(token.encode()).hexdigest()):
                raise DomainError("access_denied", "Workspace not found or access denied.", 404)
