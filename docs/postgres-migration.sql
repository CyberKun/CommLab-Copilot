BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> e1e76f63d9bf

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE artifacts (
    id VARCHAR(36) NOT NULL, 
    workspace_id VARCHAR NOT NULL, 
    key VARCHAR NOT NULL, 
    sha256 VARCHAR NOT NULL, 
    media_type VARCHAR NOT NULL, 
    size_bytes INTEGER NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_artifacts_workspace_id ON artifacts (workspace_id);

CREATE TABLE chunks (
    id VARCHAR NOT NULL, 
    workspace_id VARCHAR NOT NULL, 
    version_id VARCHAR NOT NULL, 
    text VARCHAR NOT NULL, 
    page INTEGER, 
    section VARCHAR, 
    embedding VECTOR(384) NOT NULL, 
    embedding_model VARCHAR NOT NULL, 
    index_version VARCHAR NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_chunks_version_id ON chunks (version_id);

CREATE INDEX ix_chunks_workspace_id ON chunks (workspace_id);

CREATE TABLE investigations (
    id VARCHAR NOT NULL, 
    workspace_id VARCHAR NOT NULL, 
    question VARCHAR NOT NULL, 
    status VARCHAR NOT NULL, 
    activity JSON NOT NULL, 
    plans JSON NOT NULL, 
    run_ids JSON NOT NULL, 
    answer JSON, 
    usage JSON NOT NULL, 
    error VARCHAR, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    heartbeat TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    lease VARCHAR, 
    retries INTEGER NOT NULL, 
    correlation_id VARCHAR NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_investigations_status ON investigations (status);

CREATE INDEX ix_investigations_workspace_id ON investigations (workspace_id);

CREATE TABLE outbox (
    id VARCHAR NOT NULL, 
    kind VARCHAR NOT NULL, 
    payload JSON NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    delivered BOOLEAN NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE runs (
    id VARCHAR NOT NULL, 
    workspace_id VARCHAR NOT NULL, 
    idempotency_key VARCHAR NOT NULL, 
    fingerprint VARCHAR NOT NULL, 
    implementation VARCHAR NOT NULL, 
    spec JSON NOT NULL, 
    channel VARCHAR NOT NULL, 
    seed BIGINT NOT NULL, 
    status VARCHAR NOT NULL, 
    progress FLOAT NOT NULL, 
    result JSON, 
    findings JSON NOT NULL, 
    artifact_id VARCHAR, 
    error JSON, 
    attempts INTEGER NOT NULL, 
    lease VARCHAR, 
    heartbeat TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    correlation_id VARCHAR NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (workspace_id, idempotency_key)
);

CREATE INDEX ix_runs_channel ON runs (channel);

CREATE INDEX ix_runs_seed ON runs (seed);

CREATE INDEX ix_runs_status ON runs (status);

CREATE INDEX ix_runs_workspace_id ON runs (workspace_id);

CREATE TABLE source_versions (
    id VARCHAR NOT NULL, 
    source_id VARCHAR NOT NULL, 
    workspace_id VARCHAR NOT NULL, 
    title VARCHAR NOT NULL, 
    content_sha256 VARCHAR NOT NULL, 
    artifact_id VARCHAR NOT NULL, 
    status VARCHAR NOT NULL, 
    warnings JSON NOT NULL, 
    error VARCHAR, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    heartbeat TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    lease VARCHAR, 
    attempts INTEGER NOT NULL, 
    correlation_id VARCHAR NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_source_versions_source_id ON source_versions (source_id);

CREATE INDEX ix_source_versions_workspace_id ON source_versions (workspace_id);

CREATE TABLE workspaces (
    id VARCHAR(36) NOT NULL, 
    name VARCHAR NOT NULL, 
    token_hash VARCHAR NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (token_hash)
);

CREATE INDEX ix_chunks_fts ON chunks USING gin (to_tsvector('simple', text));

INSERT INTO alembic_version (version_num) VALUES ('e1e76f63d9bf') RETURNING alembic_version.version_num;

-- Running upgrade e1e76f63d9bf -> b2c4f9a73100

ALTER TABLE runs ADD COLUMN plot_artifact_id VARCHAR;

UPDATE alembic_version SET version_num='b2c4f9a73100' WHERE alembic_version.version_num = 'e1e76f63d9bf';

COMMIT;

