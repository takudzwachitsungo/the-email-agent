"""add tg_message_id to processed_messages

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("processed_messages", sa.Column("tg_message_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("processed_messages", "tg_message_id")
