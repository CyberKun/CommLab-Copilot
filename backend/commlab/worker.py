import json
import logging
import os
import time
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from prometheus_client import Histogram
from commlab.assembly import Services
from commlab.jobs import dispatch

broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
dramatiq.set_broker(broker)
services = Services()
JOB_TIME = Histogram("commlab_job_seconds", "Job duration", ["kind"])


def execute(kind, workspace, id, correlation_id):
    start = time.monotonic()
    handlers = {"simulation": services.experiments.execute, "ingestion": services.knowledge.ingest,
                "investigation": services.investigations.advance}
    try:
        handlers[kind](workspace, id)
    finally:
        JOB_TIME.labels(kind).observe(time.monotonic()-start)
        logging.info(json.dumps({"event": "job", "kind": kind, "id": id,
                                 "correlation_id": correlation_id, "seconds": time.monotonic()-start}))


@dramatiq.actor(queue_name="simulation", max_retries=2, time_limit=150_000, min_backoff=2000, max_backoff=30000)
def simulation(**payload):
    execute("simulation", **payload)


@dramatiq.actor(queue_name="ingestion", max_retries=2, time_limit=150_000, min_backoff=2000, max_backoff=30000)
def ingestion(**payload):
    execute("ingestion", **payload)


@dramatiq.actor(queue_name="investigation", max_retries=2, time_limit=90_000, min_backoff=2000, max_backoff=30000)
def investigation(**payload):
    execute("investigation", **payload)


def send(kind, payload):
    {"simulation": simulation, "ingestion": ingestion, "investigation": investigation}[kind].send(**payload)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            services.experiments.recover()
            services.knowledge.recover()
            services.investigations.recover()
            dispatch(services.sessions, send)
        except Exception:
            logging.exception("Dispatcher failed; durable outbox retained.")
        time.sleep(2)
