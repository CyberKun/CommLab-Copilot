from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, ConfigDict


def uid() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class StructuredError(Contract):
    code: str
    message: str
    correlation_id: str
