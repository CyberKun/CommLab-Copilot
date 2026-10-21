# CommLab Copilot

A runnable communication-experiment workspace built as a modular Python monolith with a React client and separate background workers. The software contribution is typed tool execution, durable workflows, evidence provenance, reproducibility and evaluation. BPSK is the deliberately narrow scientific domain.

**Implemented:** coherent BPSK over AWGN and iid flat Rayleigh fading; reviewed experiment configurations; background execution; progress and cancellation; versioned results and SVG plots; exact uncertainty bounds; deterministic verification; source ingestion; workspace-scoped hybrid retrieval; persisted investigator activity; comparisons; and reproduction.

**Verification:** the local SQLite flow and numerical/evaluation suites have been executed. The expanded local suite passed 33 tests (one infrastructure test skipped locally). [GitHub CI](https://github.com/CyberKun/CommLab-Copilot/actions/runs/39605827527) additionally passed the real PostgreSQL/pgvector/Redis smoke test. No live Ollama model was installed: real-provider adapters are implemented, but their model quality and the three-way LLM benchmark are not claimed as verified. Default mode is visibly labelled offline rules plus lexical hashing, not a simulated LLM.

**Live demo:** https://commlab-copilot.vercel.app uses the Render API at https://commlab-api.onrender.com with durable Neon PostgreSQL storage. The hosted end-to-end smoke test passed on 2026-10-21: ingestion, retrieval, citations, reviewed AWGN/Rayleigh execution, comparison, JSON/SVG downloads and workspace isolation. Free Render instances sleep when inactive, so the first request can take a minute or more; retry if startup times out. See [deployment instructions](docs/deployment.md) for limits.

## Run with Docker

```sh
cp .env.example .env
docker compose up --build
```

Open http://localhost:8080. API documentation is at http://localhost:8000/docs. Compose starts PostgreSQL with pgvector, Redis with AOF persistence, Alembic migrations, FastAPI, an outbox dispatcher, dedicated simulation/ingestion/investigator workers, and the React client.

Only the web and API ports bind to loopback. The defaults are for a local portfolio demonstration. Before a network deployment, add real identity/membership management, TLS, quotas, rate limits, backups, and an operational secrets manager. Do not publish the example passwords.

## Run without Docker

Use **Python 3.12** and Node 22 or 24. The native development path uses SQLite and a durable local outbox worker; it does not claim to exercise PostgreSQL or Redis.

```sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r backend/requirements.lock
.venv\Scripts\python -m pip install --no-deps -e backend
# macOS/Linux: replace .venv\Scripts\python with .venv/bin/python
cd frontend
npm ci
npm run dev
```

In two terminals, from `backend/` with the environment active:

```sh
python -m uvicorn commlab.main:app --host 127.0.0.1 --port 8000
python -m commlab.local_worker
```

On Windows, after installation, `scripts/start-local.ps1` starts all three processes in the background; `scripts/stop-local.ps1` stops only the processes it recorded, checking process start times to avoid PID reuse. Logs live in ignored `backend/data/`. Start scripts do not install dependencies.

Create a workspace in the UI. Export its access credential if you want to reconnect after closing the browser session. That JSON contains a bearer secret: keep it private. Alternatively, from `backend/`, run `python scripts/seed_demo.py`; import the resulting `data/demo-credential.json` in the UI's reconnect control. The seed script creates real source chunks and measured runs.

The application reads environment variables, not an implicit dotenv file. Compose reads the root `.env`. For native execution, explicitly set variables in the shell. Leave `DATABASE_URL` unset for SQLite. Use the same database and artifact root in API and worker processes.

## Try the complete flow

1. Upload `samples/synthetic-bpsk-lab.md`. Wait for **ready**.
2. Ask: “Compare BPSK over AWGN and Rayleigh using this handout. Check consistency with theory.”
3. Inspect cited evidence and the two proposed configurations. Offline mode proposes documented defaults; it does not claim to understand arbitrary numerical instructions.
4. Review/edit Eb/N0 points, sample counts and seeds, then approve.
5. Watch the runs finish. Select the two rows to compare curves and configuration differences.
6. Inspect error counts, theoretical BER, exact 95% intervals and verification findings. Download JSON and SVG artifacts.
7. Use **Reproduce** to load a stored configuration, then submit it as a new run. Compare the recorded implementation/runtime before interpreting reproducibility.

Source versions are immutable. The upload endpoint accepts an existing `source_id` to add a new version; the UI currently uploads new sources. Search defaults to the latest ready version per source, while explicit `version_ids` can retrieve older versions.

## Optional real model integration

Configure an existing Ollama server with a structured-output-capable chat model:

```text
OLLAMA_URL=http://localhost:11434
LLM_MODEL=<installed-model-tag>
EMBEDDING_MODEL=<installed-384-dimensional-model-tag>
EMBEDDING_REVISION=<exact-digest-returned-by-api-tags>
```

In Compose, use a hostname reachable from the containers, such as the supplied `host.docker.internal` on Docker Desktop. If using Linux Docker Engine, configure its host gateway explicitly or provide a reachable Ollama URL. This project does not download models or send documents to a hosted provider automatically.

LLM and embedding adapters are independent: either may be enabled alone. The embedding adapter checks the configured model digest before every embedding request, rejects incompatible dimensions and disables silent truncation. After changing an embedding identity, reingest sources into new source versions; incompatible vectors are never mixed. Existing citations remain readable.

The LLM selects bounded tools and may provide labelled hypotheses. Stored source quotations and measured results are assembled from validated tool outputs, not copied from model claims. User review is the only route from a proposed plan to simulation submission.

## Verify

From `backend/`:

```sh
python -m pytest -q
python scripts/evaluate.py --split calibration
python scripts/evaluate.py --split heldout
python scripts/export_openapi.py
```

From `frontend/`:

```sh
npm run types
npm run build
npm audit
```

For a real PostgreSQL/Redis check, migrate an isolated database, set `DATABASE_URL`, `REDIS_URL`, and `COMMLAB_TEST_POSTGRES=1`, then run `pytest tests/test_postgres_queue.py -q`. The supplied CI workflow provisions those services. A skipped infrastructure test is not a passing infrastructure test.

`python scripts/evaluate_models.py` requires `LLM_MODEL` and records real basic-LLM, RAG-only and tool-workflow outputs for human scoring. It produces no fabricated baseline values.

## Project guide

- [Vercel + Render deployment and free-tier limits](docs/deployment.md)

- [Architecture and entity ownership](docs/architecture.md)
- [Scientific conventions and reproducibility](docs/science.md)
- [Execution, security and operations](docs/operations.md)
- [Contracts and compatibility](docs/contracts.md)
- [Change impact and extension guide](docs/extensions.md)
- [Roadmap and interview explanation](docs/roadmap.md)
- [Verification report](docs/verification.md)
- [Evaluation protocol](eval/rubric.md) and [actual held-out outputs](eval/results-heldout.json)
- [OpenAPI schema](docs/openapi.json)

This is a production-minded portfolio foundation, not a production-certified service. Unsupported scope includes arbitrary code execution, MATLAB interpretation, OCR, extracted-formula execution, OFDM, hardware integration, unrestricted browsing and team membership management.
