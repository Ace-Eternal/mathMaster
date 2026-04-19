"""add solution template and remove subject fields

Revision ID: 20260419_0002
Revises: 20260409_0001
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260419_0002"
down_revision = "20260409_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solution_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(length=512), nullable=True),
        sa.Column("template_md_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_solution_template_name", "solution_template", ["name"])

    op.drop_column("solution_method", "subject")
    op.drop_column("knowledge_point", "subject")
    op.drop_column("paper", "subject")


def downgrade() -> None:
    op.add_column("paper", sa.Column("subject", sa.String(length=64), nullable=False, server_default="math"))
    op.add_column("knowledge_point", sa.Column("subject", sa.String(length=64), nullable=False, server_default="math"))
    op.add_column("solution_method", sa.Column("subject", sa.String(length=64), nullable=False, server_default="math"))

    op.drop_index("ix_solution_template_name", table_name="solution_template")
    op.drop_table("solution_template")
