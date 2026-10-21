"""Supervise API + one outbox consumer on a single free web instance.

One instance only. Durable PostgreSQL is required; migrations precede both
children. A failed child stops the service so the host can restart the pair.
"""
import os
import signal
import subprocess
import sys
import time


def main():
    if not os.getenv("DATABASE_URL", "").startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("Hosted mode requires durable PostgreSQL DATABASE_URL")
    if os.getenv("ARTIFACT_BACKEND") != "database":
        raise RuntimeError("Hosted mode requires ARTIFACT_BACKEND=database")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "commlab.main:app", "--host", "0.0.0.0", "--port", os.getenv("PORT", "8000")]))
        children.append(subprocess.Popen([sys.executable, "-m", "commlab.local_worker"]))
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("API or worker exited; restarting the hosted service is required")
            time.sleep(1)
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 15
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    main()
