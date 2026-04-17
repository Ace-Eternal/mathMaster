"""init mathmaster schema

Revision ID: 20260409_0001
Revises:
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("grade_level", sa.String(length=64), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column("term", sa.String(length=64), nullable=True),
        sa.Column("paper_pdf_path", sa.String(length=1024), nullable=False),
        sa.Column("paper_pdf_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_paper_title", "paper", ["title"])
    op.create_index("ix_paper_year_region_grade", "paper", ["year", "region", "grade_level"])
    op.create_index("ix_paper_status", "paper", ["status"])

    op.create_table(
        "answer_sheet",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("paper.id"), nullable=False, unique=True),
        sa.Column("answer_pdf_path", sa.String(length=1024), nullable=True),
        sa.Column("answer_pdf_hash", sa.String(length=128), nullable=True),
        sa.Column("has_answer", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_answer_sheet_paper_id", "answer_sheet", ["paper_id"])

    op.create_table(
        "conversion_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("paper.id"), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("markdown_path", sa.String(length=1024), nullable=True),
        sa.Column("json_path", sa.String(length=1024), nullable=True),
        sa.Column("raw_response_path", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_conversion_job_paper_id_job_type", "conversion_job", ["paper_id", "job_type"])
    op.create_index("ix_conversion_job_status", "conversion_job", ["status"])

    op.create_table(
        "question",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("paper.id"), nullable=False),
        sa.Column("question_no", sa.String(length=64), nullable=False),
        sa.Column("question_type", sa.String(length=64), nullable=True),
        sa.Column("stem_text", sa.Text(), nullable=False),
        sa.Column("question_md_path", sa.String(length=1024), nullable=True),
        sa.Column("question_json_path", sa.String(length=1024), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_question_paper_id_question_no", "question", ["paper_id", "question_no"])
    op.create_index("ix_question_review_status", "question", ["review_status"])
    op.create_index("ix_question_type", "question", ["question_type"])

    op.create_table(
        "question_answer",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=False, unique=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_md_path", sa.String(length=1024), nullable=True),
        sa.Column("answer_json_path", sa.String(length=1024), nullable=True),
        sa.Column("match_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("match_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_question_answer_question_id", "question_answer", ["question_id"])

    op.create_table(
        "review_record",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("paper.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=True),
        sa.Column("review_type", sa.String(length=64), nullable=False),
        sa.Column("before_data_json", sa.Text(), nullable=True),
        sa.Column("after_data_json", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_review_record_paper_question", "review_record", ["paper_id", "question_id"])
    op.create_index("ix_review_record_review_type", "review_record", ["review_type"])

    op.create_table(
        "knowledge_point",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("knowledge_point.id"), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_knowledge_point_name", "knowledge_point", ["name"])
    op.create_index("ix_knowledge_point_parent", "knowledge_point", ["parent_id"])

    op.create_table(
        "solution_method",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_solution_method_name", "solution_method", ["name"])

    op.create_table(
        "question_knowledge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=False),
        sa.Column("knowledge_point_id", sa.Integer(), sa.ForeignKey("knowledge_point.id"), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_question_knowledge_question_id", "question_knowledge", ["question_id"])
    op.create_index("ix_question_knowledge_kp_id", "question_knowledge", ["knowledge_point_id"])

    op.create_table(
        "question_method",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=False),
        sa.Column("solution_method_id", sa.Integer(), sa.ForeignKey("solution_method.id"), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_question_method_question_id", "question_method", ["question_id"])
    op.create_index("ix_question_method_method_id", "question_method", ["solution_method_id"])

    op.create_table(
        "question_analysis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=False, unique=True),
        sa.Column("analysis_json", sa.Text(), nullable=False),
        sa.Column("explanation_md", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_question_analysis_question_id", "question_analysis", ["question_id"])

    op.create_table(
        "chat_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_session_question_id", "chat_session", ["question_id"])

    op.create_table(
        "chat_message",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("chat_session.id"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_chat_message_session_id", "chat_message", ["session_id"])


def downgrade() -> None:
    for table in [
        "chat_message",
        "chat_session",
        "question_analysis",
        "question_method",
        "question_knowledge",
        "solution_method",
        "knowledge_point",
        "review_record",
        "question_answer",
        "question",
        "conversion_job",
        "answer_sheet",
        "paper",
    ]:
        op.drop_table(table)
