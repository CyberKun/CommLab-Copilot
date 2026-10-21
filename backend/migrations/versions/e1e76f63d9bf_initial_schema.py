"""initial_schema

Revision ID: e1e76f63d9bf
Revises: 
"""
from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy

revision = 'e1e76f63d9bf'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('artifacts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.Column('key', sa.String(), nullable=False),
    sa.Column('sha256', sa.String(), nullable=False),
    sa.Column('media_type', sa.String(), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_artifacts_workspace_id'), 'artifacts', ['workspace_id'], unique=False)
    op.create_table('chunks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.Column('version_id', sa.String(), nullable=False),
    sa.Column('text', sa.String(), nullable=False),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('section', sa.String(), nullable=True),
    sa.Column('embedding', sa.JSON().with_variant(pgvector.sqlalchemy.vector.VECTOR(dim=384), 'postgresql'), nullable=False),
    sa.Column('embedding_model', sa.String(), nullable=False),
    sa.Column('index_version', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chunks_version_id'), 'chunks', ['version_id'], unique=False)
    op.create_index(op.f('ix_chunks_workspace_id'), 'chunks', ['workspace_id'], unique=False)
    op.create_table('investigations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.Column('question', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('activity', sa.JSON(), nullable=False),
    sa.Column('plans', sa.JSON(), nullable=False),
    sa.Column('run_ids', sa.JSON(), nullable=False),
    sa.Column('answer', sa.JSON(), nullable=True),
    sa.Column('usage', sa.JSON(), nullable=False),
    sa.Column('error', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('heartbeat', sa.DateTime(), nullable=False),
    sa.Column('lease', sa.String(), nullable=True),
    sa.Column('retries', sa.Integer(), nullable=False),
    sa.Column('correlation_id', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investigations_status'), 'investigations', ['status'], unique=False)
    op.create_index(op.f('ix_investigations_workspace_id'), 'investigations', ['workspace_id'], unique=False)
    op.create_table('outbox',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('delivered', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('runs',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.Column('idempotency_key', sa.String(), nullable=False),
    sa.Column('fingerprint', sa.String(), nullable=False),
    sa.Column('implementation', sa.String(), nullable=False),
    sa.Column('spec', sa.JSON(), nullable=False),
    sa.Column('channel', sa.String(), nullable=False),
    sa.Column('seed', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('findings', sa.JSON(), nullable=False),
    sa.Column('artifact_id', sa.String(), nullable=True),
    sa.Column('error', sa.JSON(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('lease', sa.String(), nullable=True),
    sa.Column('heartbeat', sa.DateTime(), nullable=False),
    sa.Column('correlation_id', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('workspace_id', 'idempotency_key')
    )
    op.create_index(op.f('ix_runs_channel'), 'runs', ['channel'], unique=False)
    op.create_index(op.f('ix_runs_seed'), 'runs', ['seed'], unique=False)
    op.create_index(op.f('ix_runs_status'), 'runs', ['status'], unique=False)
    op.create_index(op.f('ix_runs_workspace_id'), 'runs', ['workspace_id'], unique=False)
    op.create_table('source_versions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('source_id', sa.String(), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('content_sha256', sa.String(), nullable=False),
    sa.Column('artifact_id', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('warnings', sa.JSON(), nullable=False),
    sa.Column('error', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('heartbeat', sa.DateTime(), nullable=False),
    sa.Column('lease', sa.String(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('correlation_id', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_source_versions_source_id'), 'source_versions', ['source_id'], unique=False)
    op.create_index(op.f('ix_source_versions_workspace_id'), 'source_versions', ['workspace_id'], unique=False)
    op.create_table('workspaces',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE INDEX ix_chunks_fts ON chunks USING gin (to_tsvector('simple', text))")

def downgrade():
    op.drop_table('workspaces')
    op.drop_index(op.f('ix_source_versions_workspace_id'), table_name='source_versions')
    op.drop_index(op.f('ix_source_versions_source_id'), table_name='source_versions')
    op.drop_table('source_versions')
    op.drop_index(op.f('ix_runs_workspace_id'), table_name='runs')
    op.drop_index(op.f('ix_runs_status'), table_name='runs')
    op.drop_index(op.f('ix_runs_seed'), table_name='runs')
    op.drop_index(op.f('ix_runs_channel'), table_name='runs')
    op.drop_table('runs')
    op.drop_table('outbox')
    op.drop_index(op.f('ix_investigations_workspace_id'), table_name='investigations')
    op.drop_index(op.f('ix_investigations_status'), table_name='investigations')
    op.drop_table('investigations')
    op.drop_index(op.f('ix_chunks_workspace_id'), table_name='chunks')
    op.drop_index(op.f('ix_chunks_version_id'), table_name='chunks')
    op.drop_table('chunks')
    op.drop_index(op.f('ix_artifacts_workspace_id'), table_name='artifacts')
    op.drop_table('artifacts')
