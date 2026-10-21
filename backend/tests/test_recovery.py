from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from sqlalchemy import select, update
from test_flow import system
from commlab.common import now
from commlab.jobs import Outbox, dispatch
from commlab.experiments.api import Run
from commlab.investigations.api import Investigation, Decision, ToolRequest
from commlab.simulation.api import ExperimentSpec


def new_run(services, key="test"):
    w = services.workspaces.create("fault test")
    r = services.experiments.submit(w["id"], ExperimentSpec(ebn0_db=[0], bits_per_point=1000), key, "fault-correlation")
    return w["id"], r


def test_outbox_rolls_back_delivery_on_broker_failure(system):
    services, _ = system
    workspace, run = new_run(services)
    def fail(*args):
        raise ConnectionError("broker unavailable")
    with pytest.raises(ConnectionError):
        dispatch(services.sessions, fail)
    messages = []
    assert dispatch(services.sessions, lambda k,p: messages.append(p)) == 1
    assert messages[0]["id"] == run.id


def test_duplicate_workers_publish_once(system):
    services, _ = system
    workspace, run = new_run(services)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(services.experiments.execute, workspace, run.id) for _ in range(2)]
        for f in futures:
            f.result()
    actual = services.experiments.inspect(workspace, run.id)
    assert actual.status == "succeeded" and actual.attempts == 1


def test_transient_storage_retry_is_bounded(system):
    services, _ = system
    workspace, run = new_run(services)
    original = services.artifacts.store.put
    def fail(*args):
        raise OSError("injected disk failure")
    services.artifacts.store.put = fail
    for expected in ["queued", "queued", "failed"]:
        with pytest.raises(OSError):
            services.experiments.execute(workspace, run.id)
        assert services.experiments.inspect(workspace, run.id).status == expected
    services.artifacts.store.put = original
    services.experiments.execute(workspace, run.id)
    assert services.experiments.inspect(workspace, run.id).attempts == 3


def test_lost_worker_and_queued_delivery_recover(system):
    services, _ = system
    workspace, run = new_run(services)
    with services.sessions.begin() as s:
        s.execute(update(Run).where(Run.id == run.id).values(status="running", lease="dead", attempts=1,
                                                           heartbeat=now()-timedelta(seconds=200)))
    services.experiments.recover()
    assert services.experiments.inspect(workspace, run.id).status == "queued"
    services.experiments.execute(workspace, run.id)
    assert services.experiments.inspect(workspace, run.id).status == "succeeded"
    workspace2, queued = new_run(services, "lost-queue")
    with services.sessions.begin() as s:
        s.execute(update(Run).where(Run.id == queued.id).values(heartbeat=now()-timedelta(seconds=70)))
    services.experiments.recover()
    with services.sessions() as s:
        matching = [o for o in s.scalars(select(Outbox)) if o.payload["id"] == queued.id]
    assert len(matching) == 2  # Original plus watchdog redelivery.


def test_cancel_during_execution_fences_publication(system):
    services, _ = system
    workspace, run = new_run(services)
    original = services.capabilities["bpsk.ber"].backend
    class CancellingBackend:
        def execute(self, spec, progress):
            services.experiments.cancel(workspace, run.id)
            return original.execute(spec, progress)
    services.capabilities["bpsk.ber"].backend = CancellingBackend()
    services.experiments.execute(workspace, run.id)
    actual = services.experiments.inspect(workspace, run.id)
    assert actual.status == "cancelled"
    assert actual.result is None and actual.artifact_id is None


def test_tool_budget_and_authorization_apply_to_provider(system):
    services, _ = system
    a, b = services.workspaces.create("a"), services.workspaces.create("b")
    other = services.experiments.submit(b["id"], ExperimentSpec(), "other", "test")
    class RepeatingProvider:
        def decide(self, *args):
            return Decision(provider="test-double", action=ToolRequest(tool="inspect_run", arguments={"id": other.id}))
    services.investigations.provider = RepeatingProvider()
    inv = services.investigations.create(a["id"], "inspect", "test")
    for _ in range(14):
        services.investigations.advance(a["id"], inv["id"])
    actual = services.investigations.inspect(a["id"], inv["id"])
    assert actual["status"] == "failed"
    assert len(actual["activity"]) == 12
    assert all(a["error"]["code"] == "not_found" for a in actual["activity"])
    assert "budget" in actual["error"]


def test_human_review_time_does_not_consume_execution_deadline(system):
    services, _ = system
    w = services.workspaces.create("delayed approval")["id"]
    inv = services.investigations.create(w, "Compare BPSK AWGN and Rayleigh", "deadline")
    for _ in range(4):
        services.investigations.advance(w, inv["id"])
    state = services.investigations.inspect(w, inv["id"])
    assert state["status"] == "review"
    with services.sessions.begin() as s:
        s.execute(update(Investigation).where(Investigation.id == inv["id"]).values(
            created_at=now()-timedelta(days=1), usage={**state["usage"], "deadline_at": (now()-timedelta(hours=1)).isoformat()}))
    approved = services.investigations.approve(w, inv["id"], [ExperimentSpec(ebn0_db=[0], bits_per_point=1000)])
    services.investigations.recover()
    assert services.investigations.inspect(w, inv["id"])["status"] == "waiting"
    services.experiments.execute(w, approved["run_ids"][0])
    services.investigations.recover()
    services.investigations.advance(w, inv["id"])
    assert services.investigations.inspect(w, inv["id"])["status"] == "finished"
