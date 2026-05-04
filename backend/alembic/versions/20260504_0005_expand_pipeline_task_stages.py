"""expand pipeline task stages

Revision ID: 20260504_0005
Revises: 20260424_0004
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260504_0005"
down_revision = "20260424_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_task", sa.Column("question_id", sa.Integer(), nullable=True))
    op.add_column("pipeline_task", sa.Column("task_type", sa.String(length=64), nullable=False, server_default="MINEU_CONVERT"))
    op.add_column("pipeline_task", sa.Column("depends_on_task_id", sa.Integer(), nullable=True))
    op.add_column("pipeline_task", sa.Column("blocked_reason", sa.Text(), nullable=True))
    op.add_column("pipeline_task", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("pipeline_task", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"))
    op.create_foreign_key("fk_pipeline_task_question_id_question", "pipeline_task", "question", ["question_id"], ["id"])
    op.create_foreign_key("fk_pipeline_task_depends_on_task_id", "pipeline_task", "pipeline_task", ["depends_on_task_id"], ["id"])
    op.create_index("ix_pipeline_task_type_status_queued_at", "pipeline_task", ["task_type", "status", "queued_at"])
    op.create_index("ix_pipeline_task_question_status", "pipeline_task", ["question_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_task_question_status", table_name="pipeline_task")
    op.drop_index("ix_pipeline_task_type_status_queued_at", table_name="pipeline_task")
    op.drop_constraint("fk_pipeline_task_depends_on_task_id", "pipeline_task", type_="foreignkey")
    op.drop_constraint("fk_pipeline_task_question_id_question", "pipeline_task", type_="foreignkey")
    op.drop_column("pipeline_task", "max_attempts")
    op.drop_column("pipeline_task", "attempt_count")
    op.drop_column("pipeline_task", "blocked_reason")
    op.drop_column("pipeline_task", "depends_on_task_id")
    op.drop_column("pipeline_task", "task_type")
    op.drop_column("pipeline_task", "question_id")
