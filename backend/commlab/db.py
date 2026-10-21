import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database(url: str | None = None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///./data/commlab.db")
    engine = create_engine(url, pool_pre_ping=True,
                           connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def sqlite_settings(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
    return engine, sessionmaker(engine, expire_on_commit=False)
