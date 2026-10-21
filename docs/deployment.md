# Hosted portfolio demo

Live frontend: https://commlab-copilot.vercel.app

Backend health: https://commlab-api.onrender.com/health

API documentation: https://commlab-api.onrender.com/docs

The backend root `/` has no page; use the frontend URL for the application.

Deploy the React frontend on Vercel and the API on Render. Vercel Functions do
not host this application's continuous Python worker processes. The free demo
uses one Render web instance supervising two separate processes: Uvicorn and a
single durable database-outbox consumer. It does not run Redis/Dramatiq; Compose
retains that independent-worker deployment for environments that support it.

## Persistence and limits

`ARTIFACT_BACKEND=database` stores small immutable blobs in the artifacts module's
`artifact_blobs` table. The external PostgreSQL database owns persistence across
web-instance restarts, including uploads, results and plots. Local files are not
used for durable data in hosted mode. Existing local blobs are not automatically
migrated. The adapter is intended for small demos, not large datasets.

Render's free web instance sleeps after 15 minutes without inbound traffic;
queued jobs resume after the service wakes. Do not use artificial keep-alive
traffic to evade this limitation. This deployment is one instance only: the
outbox consumer is not a competing-consumer replacement for Dramatiq.

The Blueprint uses the owner's dedicated Neon PostgreSQL/pgvector database.
Set its direct connection URL as the secret DATABASE_URL during creation; no
Render database is provisioned. Neon compute/storage quotas and its retention
policy apply. No paid upgrade is authorized by this file.
Free compute/storage/traffic quotas still apply. The offline investigator is
explicitly labelled; hosting does not add a live LLM.

## Deploy

1. Push the repository to GitHub, then create a Render Blueprint using
   `render.yaml`. Verify all selected plans are free before creation and enter
   the dedicated Neon database URL into the secret DATABASE_URL field.
2. The hosted launcher runs Alembic before starting API and worker. Verify the
   Render deployment succeeds and its `/health` returns JSON.
3. Set `COMMLAB_API_ORIGIN` to the actual HTTPS Render origin and run
   `node scripts/configure-vercel.mjs` from the repository root. Commit the
   generated `vercel.json` (contains only the public backend URL).
4. Deploy with `vercel --prod`. API rewrites must precede the SPA fallback.
   Same-origin proxying preserves bearer authorization without permissive CORS.
5. Through the Vercel URL, create a workspace, upload the synthetic handout,
   run a simulation, and download its result. Recheck after a service restart.

The existing deployment was created through Render's web-service form using
the public GitHub repository, root directory `backend`, Dockerfile `./Dockerfile`,
build context `.`, command `python -m commlab.hosted`, health path `/health` and
free compute. It was observed auto-deploying the subsequent backend fix. The
Blueprint remains the reproducible alternative for new deployments. METRICS_TOKEN
was not configured on the existing service; its metrics endpoint remains denied.

To repeat the actual remote checks from `backend/`, run:

```sh
python scripts/smoke_hosted.py https://commlab-copilot.vercel.app
```

This creates synthetic demonstration workspaces and jobs, saves private access
credentials under ignored `data/`, and reports only executed checks. Run it after
the service has woken; a free-instance cold start can exceed a request timeout.
Do not repeatedly create workspaces to work around a cold start.

For a pre-existing external database, configure `DATABASE_URL` in Render's
secret environment settings; do not commit credentials. Use a direct database
connection with migration privileges and pgvector support. Provider postgres://
and postgresql:// URLs are normalized to the pinned psycopg v3 driver.

The launcher stops both children if either exits, and handles SIGTERM with a
bounded shutdown. Work interrupted during host shutdown is recovered through
the existing lease/outbox mechanism after restart. Public service hardening,
account quotas, identity management and live-provider evaluation remain work
described in operations.md. Do not upload sensitive documents to a public demo.

Hosting references: https://render.com/docs/free and
https://vercel.com/docs/functions/limitations (checked 2026-10-21).
