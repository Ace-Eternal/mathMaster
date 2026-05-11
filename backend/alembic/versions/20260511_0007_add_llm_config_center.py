"""add llm config center

Revision ID: 20260511_0007
Revises: 20260506_0006
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260511_0007"
down_revision = "20260506_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_provider_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_llm_provider_config_name", "llm_provider_config", ["name"], unique=True)
    op.create_index("ix_llm_provider_config_enabled", "llm_provider_config", ["is_enabled"])

    op.create_table(
        "llm_scenario_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenario_code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("primary_provider_id", sa.Integer(), sa.ForeignKey("llm_provider_config.id"), nullable=True),
        sa.Column("primary_model", sa.String(length=128), nullable=True),
        sa.Column("fallback_provider_id", sa.Integer(), sa.ForeignKey("llm_provider_config.id"), nullable=True),
        sa.Column("fallback_model", sa.String(length=128), nullable=True),
        sa.Column("temperature", sa.Numeric(4, 2), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_llm_scenario_config_code", "llm_scenario_config", ["scenario_code"], unique=True)
    op.create_index("ix_llm_scenario_config_enabled", "llm_scenario_config", ["is_enabled"])

    op.create_table(
        "llm_prompt_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenario_code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("prompt_content", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_llm_prompt_config_code", "llm_prompt_config", ["scenario_code"], unique=True)


def downgrade() -> None:
    op.drop_table("llm_prompt_config")
    op.drop_table("llm_scenario_config")
    op.drop_table("llm_provider_config")
