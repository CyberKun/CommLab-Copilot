"""Persist exported plot references, preserving readability of existing runs."""
from alembic import op
import sqlalchemy as sa

revision = "b2c4f9a73100"
down_revision = "e1e76f63d9bf"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("runs", sa.Column("plot_artifact_id", sa.String(), nullable=True))


def downgrade():
    op.drop_column("runs", "plot_artifact_id")
