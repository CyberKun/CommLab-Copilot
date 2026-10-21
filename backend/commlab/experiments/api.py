import hashlib
import json
from datetime import datetime, timedelta
from typing import Literal
from sqlalchemy import JSON, DateTime, BigInteger, UniqueConstraint, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Mapped, mapped_column
from commlab.common import Contract, DomainError, uid, now
from commlab.db import Base
from commlab.jobs import enqueue
from commlab.simulation.api import ExperimentSpec, SimulationResult, IMPLEMENTATION, runtime
from ._plot import render_ber


class RunView(Contract):
    id: str
    workspace_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: float
    spec: ExperimentSpec
    result: SimulationResult | None
    findings: list[dict]
    artifact_id: str | None
    plot_artifact_id: str | None
    error: dict | None
    attempts: int
    correlation_id: str
    implementation: str


class ConfigDifference(Contract):
    left: str | int | float | list[float]
    right: str | int | float | list[float]


class ComparisonPoint(Contract):
    ebn0_db: float
    measured_ber_difference_right_minus_left: float
    theory_difference_right_minus_left: float
    marginal_95_intervals_overlap: bool


class ComparisonView(Contract):
    left: RunView
    right: RunView
    changes: dict[str, ConfigDifference]
    matched_points: list[ComparisonPoint]
    interpretation: str


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    workspace_id: Mapped[str] = mapped_column(index=True)
    idempotency_key: Mapped[str]
    fingerprint: Mapped[str]
    implementation: Mapped[str]
    spec: Mapped[dict] = mapped_column(JSON)
    channel: Mapped[str] = mapped_column(index=True)
    seed: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(index=True)
    progress: Mapped[float] = mapped_column(default=0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    artifact_id: Mapped[str | None]
    plot_artifact_id: Mapped[str | None]
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(default=0)
    lease: Mapped[str | None]
    heartbeat: Mapped[datetime] = mapped_column(DateTime)
    correlation_id: Mapped[str]


def view(row):
    return RunView(**{key: getattr(row, key) for key in RunView.model_fields})


class Experiments:
    def __init__(self, sessions, capabilities, artifacts, verifier):
        self.sessions, self.capabilities = sessions, capabilities
        self.artifacts, self.verifier = artifacts, verifier

    def submit(self, workspace, spec: ExperimentSpec, key: str, correlation: str):
        # Runtime included for future cache eligibility. No automatic cache reuse in MVP.
        fingerprint = hashlib.sha256(json.dumps({"spec": spec.model_dump(), "implementation": IMPLEMENTATION,
                                                "runtime": runtime()}, sort_keys=True).encode()).hexdigest()
        try:
            with self.sessions.begin() as s:
                previous = s.scalar(select(Run).where(Run.workspace_id == workspace, Run.idempotency_key == key))
                if previous:
                    if previous.spec != spec.model_dump():
                        raise DomainError("idempotency_conflict", "Key already used with a different configuration.", 409)
                    return view(previous)
                row = Run(id=uid(), workspace_id=workspace, idempotency_key=key, fingerprint=fingerprint,
                          implementation=IMPLEMENTATION, spec=spec.model_dump(), channel=spec.channel, seed=spec.seed,
                          status="queued", progress=0, findings=[], attempts=0, heartbeat=now(), correlation_id=correlation)
                s.add(row)
                enqueue(s, "simulation", {"workspace": workspace, "id": row.id, "correlation_id": correlation})
            return view(row)
        except IntegrityError:
            # A concurrent identical submission won the unique constraint.
            with self.sessions() as s:
                row = s.scalar(select(Run).where(Run.workspace_id == workspace, Run.idempotency_key == key))
                if row and row.spec == spec.model_dump():
                    return view(row)
            raise DomainError("idempotency_conflict", "Concurrent submission used this key.", 409)

    def inspect(self, workspace, ident):
        with self.sessions() as s:
            row = s.get(Run, ident)
            if not row or row.workspace_id != workspace:
                raise DomainError("not_found", "Run not found.", 404)
            return view(row)

    def find(self, workspace, seed: int | None = None, channel: str | None = None):
        with self.sessions() as s:
            query = select(Run).where(Run.workspace_id == workspace)
            if seed is not None:
                query = query.where(Run.seed == seed)
            if channel is not None:
                query = query.where(Run.channel == channel)
            return [view(r) for r in s.scalars(query.order_by(Run.heartbeat.desc()).limit(100))]

    def cancel(self, workspace, ident):
        self.inspect(workspace, ident)
        with self.sessions.begin() as s:
            s.execute(update(Run).where(Run.id == ident, Run.workspace_id == workspace,
                                        Run.status.in_(["queued", "running"]))
                      .values(status="cancelled", lease=None))
        return self.inspect(workspace, ident)

    def execute(self, workspace, ident):
        token = uid()
        with self.sessions.begin() as s:
            claimed = s.execute(update(Run).where(Run.id == ident, Run.workspace_id == workspace,
                                                 Run.status == "queued")
                                .values(status="running", lease=token, heartbeat=now(), attempts=Run.attempts+1))
            if claimed.rowcount != 1:
                return  # Duplicate delivery or cancellation.
        run = self.inspect(workspace, ident)

        def progress(value):
            with self.sessions.begin() as s:
                changed = s.execute(update(Run).where(Run.id == ident, Run.lease == token, Run.status == "running")
                                    .values(progress=value, heartbeat=now()))
                if changed.rowcount != 1:
                    raise DomainError("cancelled", "Execution lease revoked.")
        try:
            if run.implementation != IMPLEMENTATION:
                raise DomainError("implementation_unavailable", "Requested simulator version is no longer installed.")
            result = self.capabilities[run.spec.capability].backend.execute(run.spec, progress)
            result = SimulationResult.model_validate(result.model_dump())
            if result.spec != run.spec or result.implementation != run.implementation:
                raise DomainError("result_contract", "Simulator output does not match the requested configuration/version.")
            findings = self.verifier.check(result)
            artifact = self.artifacts.save(workspace, result.model_dump_json().encode(), "application/json")
            plot = self.artifacts.save(workspace, render_ber(result), "image/svg+xml")
            # CAS fences stale workers and ensures one visible result publication.
            with self.sessions.begin() as s:
                s.execute(update(Run).where(Run.id == ident, Run.lease == token, Run.status == "running")
                          .values(status="succeeded", progress=1, result=result.model_dump(),
                                  findings=findings, artifact_id=artifact.id, plot_artifact_id=plot.id, lease=None, error=None, heartbeat=now()))
        except (OperationalError, OSError):
            with self.sessions.begin() as s:
                changed = s.execute(update(Run).where(Run.id == ident, Run.lease == token, Run.status == "running")
                                    .values(status="queued" if run.attempts < 3 else "failed", lease=None,
                                            error={"code": "transient_io", "message": "Storage temporarily unavailable."}))
                if changed.rowcount and run.attempts < 3:
                    enqueue(s, "simulation", {"workspace": workspace, "id": ident, "correlation_id": run.correlation_id})
            raise
        except Exception as exc:
            with self.sessions.begin() as s:
                s.execute(update(Run).where(Run.id == ident, Run.lease == token, Run.status == "running")
                          .values(status="failed", lease=None,
                                  error={"code": exc.code if isinstance(exc, DomainError) else "execution_failed",
                                         "message": exc.message if isinstance(exc, DomainError) else "Simulation failed; consult correlated logs."}))
            if not isinstance(exc, DomainError):
                raise

    def recover(self):
        """Heartbeat timeout exceeds max execution time; old workers cannot publish."""
        with self.sessions.begin() as s:
            rows = s.scalars(select(Run).where(Run.status == "running", Run.heartbeat < now()-timedelta(seconds=180))
                             .with_for_update(skip_locked=True)).all()
            for row in rows:
                row.lease = None
                row.status = "queued" if row.attempts < 3 else "failed"
                row.error = {"code": "worker_interrupted", "message": "Worker lease expired."}
                if row.status == "queued":
                    enqueue(s, "simulation", {"workspace": row.workspace_id, "id": row.id, "correlation_id": row.correlation_id})
            # Repair an acknowledged queue message lost before a worker claimed it.
            for row in s.scalars(select(Run).where(Run.status == "queued", Run.heartbeat < now()-timedelta(seconds=60))
                                 .with_for_update(skip_locked=True)):
                row.heartbeat = now()
                enqueue(s, "simulation", {"workspace": row.workspace_id, "id": row.id, "correlation_id": row.correlation_id})

    def compare(self, workspace, left, right):
        a, b = self.inspect(workspace, left), self.inspect(workspace, right)
        changes = {key: {"left": a.spec.model_dump()[key], "right": b.spec.model_dump()[key]}
                   for key in ExperimentSpec.model_fields if a.spec.model_dump()[key] != b.spec.model_dump()[key]}
        points = []
        if a.result and b.result:
            right_points = {p.ebn0_db: p for p in b.result.points}
            for p in a.result.points:
                if p.ebn0_db in right_points:
                    q = right_points[p.ebn0_db]
                    points.append({"ebn0_db": p.ebn0_db, "measured_ber_difference_right_minus_left": q.ber-p.ber,
                                   "theory_difference_right_minus_left": q.theory-p.theory,
                                   "marginal_95_intervals_overlap": max(p.ci_low,q.ci_low) <= min(p.ci_high,q.ci_high)})
        explanation = ("Multiple fields changed; this comparison does not isolate a causal effect." if len(changes) > 1
            else "Compare empirical confidence intervals and the applicable theory; a run difference alone does not establish causation.")
        if "channel" in changes:
            explanation += " Under the supported perfect-CSI model, Rayleigh deep fades raise theoretical average BER relative to AWGN at the same Eb/N0."
        return {"left": a.model_dump(), "right": b.model_dump(), "changes": changes, "matched_points": points,
                "interpretation": explanation}
