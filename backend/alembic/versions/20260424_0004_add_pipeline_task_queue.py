"""add pipeline task queue

Revision ID: 20260424_0004
Revises: 20260423_0003
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0004"
down_revision = "20260423_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_task",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("paper.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("queued_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_pipeline_task_status_queued_at", "pipeline_task", ["status", "queued_at"])
    op.create_index("ix_pipeline_task_paper_status", "pipeline_task", ["paper_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_task_paper_status", table_name="pipeline_task")
    op.drop_index("ix_pipeline_task_status_queued_at", table_name="pipeline_task")
    op.drop_table("pipeline_task")
