"""Infrastructure-owned transactional outbox. At-least-once delivery."""
from datetime import datetime, timedelta
from sqlalchemy import JSON, DateTime, select
from sqlalchemy.orm import Mapped, mapped_column
from commlab.common import uid, now
from commlab.db import Base


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    delivered: Mapped[bool] = mapped_column(default=False)


def enqueue(session, kind: str, payload: dict):
    session.add(Outbox(id=uid(), kind=kind, payload=payload, created_at=now(), delivered=False))


def dispatch(sessions, send):
    count = 0
    with sessions.begin() as s:
        rows = s.scalars(select(Outbox).where(Outbox.delivered == False)
                         .order_by(Outbox.created_at).limit(100).with_for_update(skip_locked=True)).all()
        for row in rows:
            send(row.kind, row.payload)
            row.delivered = True
            count += 1
    return count
