"""Single-consumer durable outbox executor for native and hosted demos."""
import time
import logging
from commlab.assembly import Services
from sqlalchemy import select, update
from commlab.jobs import Outbox


def tick(services):
    # Development executor acknowledges after execution. A crash replays the message;
    # queued/running/terminal claims and lease fencing make the replay safe.
    with services.sessions() as s:
        pending = s.scalars(select(Outbox).where(Outbox.delivered == False).limit(100)).all()
    handlers = {"simulation": services.experiments.execute, "ingestion": services.knowledge.ingest,
                "investigation": services.investigations.advance}
    for row in pending:
        handlers[row.kind](row.payload["workspace"], row.payload["id"])
        with services.sessions.begin() as s:
            s.execute(update(Outbox).where(Outbox.id == row.id).values(delivered=True))
    services.experiments.recover()
    services.knowledge.recover()
    services.investigations.recover()


if __name__ == "__main__":
    services = Services()
    if services.engine.dialect.name == "sqlite":
        services.create_dev_schema()
    while True:
        try:
            tick(services)
        except Exception:
            logging.exception("Local worker tick failed; durable work remains available for retry.")
        time.sleep(1)
