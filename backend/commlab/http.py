import json
import logging
import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from commlab.common import Contract, DomainError, uid
from commlab.assembly import Services
from commlab.simulation.api import ExperimentSpec
from commlab.experiments.api import RunView, ComparisonView
from commlab.retrieval.api import RetrievalRequest, RetrievalResult
from commlab.knowledge.api import EvidenceChunk, SourceView
from commlab.investigations.api import InvestigationView
from commlab.http_limits import BodyLimit

REQUESTS = Counter("commlab_requests_total", "API requests", ["method", "status"])
LATENCY = Histogram("commlab_http_seconds", "API latency")
log = logging.getLogger("commlab")
logging.basicConfig(level=logging.INFO)


class WorkspaceCreate(Contract):
    name: str = Field(min_length=1, max_length=100)


class CompareRequest(Contract):
    left: str
    right: str


class Question(Contract):
    question: str = Field(min_length=1, max_length=2000)


class Approval(Contract):
    specs: list[ExperimentSpec] = Field(min_length=1, max_length=2)


def create_app(services: Services | None = None):
    services = services or Services()

    @asynccontextmanager
    async def lifespan(app):
        if services.engine.dialect.name == "sqlite":
            services.create_dev_schema()
        yield
        services.engine.dispose()

    app = FastAPI(title="CommLab Copilot", version="0.1.0", lifespan=lifespan)
    app.state.services = services
    app.add_middleware(BodyLimit)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        request.state.correlation = uid()
        start = time.monotonic()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation
        REQUESTS.labels(request.method, response.status_code).inc()
        LATENCY.observe(time.monotonic()-start)
        log.info(json.dumps({"event": "request", "correlation_id": request.state.correlation,
                             "method": request.method, "status": response.status_code}))
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message,
                                                            "correlation_id": request.state.correlation})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={"code": "validation_error",
            "message": "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()),
            "correlation_id": request.state.correlation})

    def access(workspace: str, authorization: str = Header(default="")):
        services.workspaces.authorize(workspace, authorization.removeprefix("Bearer "))
        return workspace

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/workspaces/{workspace}/settings")
    def settings(workspace=Depends(access)):
        return {"llm": os.getenv("LLM_MODEL") or "offline_rules (not an LLM)",
                "embedding": services.embeddings.model, "index_version": services.embeddings.index_version}

    @app.get("/metrics", include_in_schema=False)
    def metrics(authorization: str = Header(default="")):
        token = os.getenv("METRICS_TOKEN")
        if not token or authorization != f"Bearer {token}":
            raise DomainError("access_denied", "Metrics token required.", 401)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/api/workspaces")
    def create_workspace(body: WorkspaceCreate):
        return services.workspaces.create(body.name)

    @app.get("/api/workspaces/{workspace}/capabilities")
    def capabilities(workspace=Depends(access)):
        return [c.describe() for c in services.capabilities.values()]

    @app.post("/api/workspaces/{workspace}/runs", response_model=RunView)
    def submit(body: ExperimentSpec, request: Request, workspace=Depends(access),
               idempotency_key: str = Header(min_length=1, max_length=128)):
        return services.experiments.submit(workspace, body, idempotency_key, request.state.correlation)

    @app.get("/api/workspaces/{workspace}/runs", response_model=list[RunView])
    def runs(seed: int | None = None, channel: str | None = None, workspace=Depends(access)):
        return services.experiments.find(workspace, seed, channel)

    @app.get("/api/workspaces/{workspace}/runs/{ident}", response_model=RunView)
    def inspect(ident: str, workspace=Depends(access)):
        return services.experiments.inspect(workspace, ident)

    @app.post("/api/workspaces/{workspace}/runs/{ident}/cancel", response_model=RunView)
    def cancel(ident: str, workspace=Depends(access)):
        return services.experiments.cancel(workspace, ident)

    @app.post("/api/workspaces/{workspace}/compare", response_model=ComparisonView)
    def compare(body: CompareRequest, workspace=Depends(access)):
        return services.experiments.compare(workspace, body.left, body.right)

    @app.get("/api/workspaces/{workspace}/artifacts/{ident}")
    def artifact(ident: str, workspace=Depends(access)):
        content, media = services.artifacts.load(workspace, ident)
        return Response(content, media_type=media, headers={"X-Content-Type-Options": "nosniff",
                        "Content-Disposition": f'attachment; filename="{ident}"'})

    @app.post("/api/workspaces/{workspace}/sources", response_model=SourceView)
    async def upload(request: Request, file: UploadFile = File(...), source_id: str | None = Form(None), workspace=Depends(access)):
        content = await file.read(2_000_001)
        await file.close()
        return services.knowledge.upload(workspace, file.filename, content, request.state.correlation, source_id)

    @app.get("/api/workspaces/{workspace}/sources", response_model=list[SourceView])
    def sources(workspace=Depends(access)):
        return services.knowledge.sources(workspace)

    @app.post("/api/workspaces/{workspace}/search", response_model=RetrievalResult)
    def search(body: RetrievalRequest, workspace=Depends(access)):
        return services.retrieval.search(workspace, body)

    @app.get("/api/workspaces/{workspace}/evidence/{ident}", response_model=EvidenceChunk)
    def evidence(ident: str, workspace=Depends(access)):
        return services.knowledge.chunk(workspace, ident)

    @app.post("/api/workspaces/{workspace}/investigations", response_model=InvestigationView)
    def investigate(body: Question, request: Request, workspace=Depends(access)):
        return services.investigations.create(workspace, body.question, request.state.correlation)

    @app.get("/api/workspaces/{workspace}/investigations", response_model=list[InvestigationView])
    def investigations(workspace=Depends(access)):
        return services.investigations.history(workspace)

    @app.get("/api/workspaces/{workspace}/investigations/{ident}", response_model=InvestigationView)
    def investigation(ident: str, workspace=Depends(access)):
        return services.investigations.inspect(workspace, ident)

    @app.post("/api/workspaces/{workspace}/investigations/{ident}/approve", response_model=InvestigationView)
    def approve(ident: str, body: Approval, workspace=Depends(access)):
        return services.investigations.approve(workspace, ident, body.specs)

    return app
