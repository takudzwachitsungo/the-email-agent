"""initial: processed_messages + pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-05-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "processed_messages",
        sa.Column("message_id", sa.Text(), primary_key=True),
        sa.Column("thread_id", sa.Text()),
        sa.Column("sender", sa.Text()),
        sa.Column("subject", sa.Text()),
        sa.Column("triage_decision", sa.Text()),
        sa.Column("triage_reason", sa.Text()),
        sa.Column("skip_source", sa.Text()),
        sa.Column("draft_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("processed_messages")
