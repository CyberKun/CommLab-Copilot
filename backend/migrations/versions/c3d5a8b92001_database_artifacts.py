"""Optional durable small blobs for ephemeral hosting."""
from alembic import op
import sqlalchemy as sa

revision = "c3d5a8b92001"
down_revision = "b2c4f9a73100"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("artifact_blobs", sa.Column("key", sa.String(200), primary_key=True),
                    sa.Column("content", sa.LargeBinary(), nullable=False))


def downgrade():
    op.drop_table("artifact_blobs")
