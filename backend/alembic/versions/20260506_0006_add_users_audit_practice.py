"""add users audit and practice state

Revision ID: 20260506_0006
Revises: 20260504_0005
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260506_0006"
down_revision = "20260504_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_app_user_username", "app_user", ["username"], unique=True)
    op.create_index("ix_app_user_status", "app_user", ["status"])

    op.create_table(
        "role",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_role_code", "role", ["code"], unique=True)

    op.create_table(
        "user_role",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("role.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role_user_role"),
    )
    op.create_index("ix_user_role_user_id", "user_role", ["user_id"])
    op.create_index("ix_user_role_role_id", "user_role", ["role_id"])

    op.create_table(
        "role_permission",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("role.id"), nullable=False),
        sa.Column("permission", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("role_id", "permission", name="uq_role_permission_role_permission"),
    )
    op.create_index("ix_role_permission_role_id", "role_permission", ["role_id"])

    op.create_table(
        "user_permission",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("permission", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "permission", name="uq_user_permission_user_permission"),
    )
    op.create_index("ix_user_permission_user_id", "user_permission", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("before_summary_json", sa.Text(), nullable=True),
        sa.Column("after_summary_json", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_audit_log_actor_created", "audit_log", ["actor_user_id", "created_at"])
    op.create_index("ix_audit_log_resource", "audit_log", ["resource_type", "resource_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    op.create_table(
        "user_question_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=False),
        sa.Column("practice_status", sa.String(length=32), nullable=False),
        sa.Column("is_favorited", sa.Boolean(), nullable=False),
        sa.Column("last_practiced_at", sa.DateTime(), nullable=True),
        sa.Column("solved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "question_id", name="uq_user_question_state_user_question"),
    )
    op.create_index("ix_user_question_state_user_status", "user_question_state", ["user_id", "practice_status"])
    op.create_index("ix_user_question_state_user_favorite", "user_question_state", ["user_id", "is_favorited"])
    op.create_index("ix_user_question_state_question_id", "user_question_state", ["question_id"])

    for table_name in [
        "import_job",
        "pipeline_task",
        "answer_sheet",
        "conversion_job",
        "question_answer",
        "knowledge_point",
        "solution_method",
        "question_analysis",
        "solution_template",
        "chat_session",
        "chat_message",
        "question_knowledge",
        "question_method",
    ]:
        op.add_column(table_name, sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        op.add_column(table_name, sa.Column("updated_by_user_id", sa.Integer(), nullable=True))

    for table_name in ["paper", "question"]:
        op.add_column(table_name, sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        op.add_column(table_name, sa.Column("updated_by_user_id", sa.Integer(), nullable=True))
        op.add_column(table_name, sa.Column("deleted_by_user_id", sa.Integer(), nullable=True))

    op.add_column("review_record", sa.Column("actor_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("review_record", "actor_user_id")
    for table_name in ["question", "paper"]:
        op.drop_column(table_name, "deleted_by_user_id")
        op.drop_column(table_name, "updated_by_user_id")
        op.drop_column(table_name, "created_by_user_id")
    for table_name in [
        "question_method",
        "question_knowledge",
        "chat_message",
        "chat_session",
        "solution_template",
        "question_analysis",
        "solution_method",
        "knowledge_point",
        "question_answer",
        "conversion_job",
        "answer_sheet",
        "pipeline_task",
        "import_job",
    ]:
        op.drop_column(table_name, "updated_by_user_id")
        op.drop_column(table_name, "created_by_user_id")
    op.drop_table("user_question_state")
    op.drop_table("audit_log")
    op.drop_table("user_permission")
    op.drop_table("role_permission")
    op.drop_table("user_role")
    op.drop_table("role")
    op.drop_table("app_user")
