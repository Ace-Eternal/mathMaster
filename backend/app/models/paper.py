from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_job"
    __table_args__ = (
        Index("ix_import_job_status", "status"),
        Index("ix_import_job_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)


class PipelineTask(TimestampMixin, Base):
    __tablename__ = "pipeline_task"
    __table_args__ = (
        Index("ix_pipeline_task_status_queued_at", "status", "queued_at"),
        Index("ix_pipeline_task_paper_status", "paper_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="SINGLE", nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)

    paper: Mapped["Paper"] = relationship()


class Paper(TimestampMixin, Base):
    __tablename__ = "paper"
    __table_args__ = (
        Index("ix_paper_title", "title"),
        Index("ix_paper_year_region_grade", "year", "region", "grade_level"),
        Index("ix_paper_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(255))
    grade_level: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(64))
    term: Mapped[str | None] = mapped_column(String(64))
    paper_pdf_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    paper_pdf_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="RAW", nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    answer_sheet: Mapped["AnswerSheet | None"] = relationship(back_populates="paper", uselist=False)
    conversion_jobs: Mapped[list["ConversionJob"]] = relationship(back_populates="paper")
    questions: Mapped[list["Question"]] = relationship(back_populates="paper")
    reviews: Mapped[list["ReviewRecord"]] = relationship(back_populates="paper")


class AnswerSheet(TimestampMixin, Base):
    __tablename__ = "answer_sheet"
    __table_args__ = (Index("ix_answer_sheet_paper_id", "paper_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper.id"), nullable=False, unique=True)
    answer_pdf_path: Mapped[str | None] = mapped_column(String(1024))
    answer_pdf_hash: Mapped[str | None] = mapped_column(String(128))
    has_answer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)

    paper: Mapped["Paper"] = relationship(back_populates="answer_sheet")


class ConversionJob(TimestampMixin, Base):
    __tablename__ = "conversion_job"
    __table_args__ = (
        Index("ix_conversion_job_paper_id_job_type", "paper_id", "job_type"),
        Index("ix_conversion_job_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="MINEU", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    markdown_path: Mapped[str | None] = mapped_column(String(1024))
    json_path: Mapped[str | None] = mapped_column(String(1024))
    raw_response_path: Mapped[str | None] = mapped_column(String(1024))
    error_message: Mapped[str | None] = mapped_column(Text)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    paper: Mapped["Paper"] = relationship(back_populates="conversion_jobs")


class Question(TimestampMixin, Base):
    __tablename__ = "question"
    __table_args__ = (
        Index("ix_question_paper_id_question_no", "paper_id", "question_no"),
        Index("ix_question_review_status", "review_status"),
        Index("ix_question_type", "question_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper.id"), nullable=False)
    question_no: Mapped[str] = mapped_column(String(64), nullable=False)
    question_type: Mapped[str | None] = mapped_column(String(64))
    stem_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_md_path: Mapped[str | None] = mapped_column(String(1024))
    question_json_path: Mapped[str | None] = mapped_column(String(1024))
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    review_note: Mapped[str | None] = mapped_column(Text)

    paper: Mapped["Paper"] = relationship(back_populates="questions")
    answer: Mapped["QuestionAnswer | None"] = relationship(back_populates="question", uselist=False)
    knowledges: Mapped[list["QuestionKnowledge"]] = relationship(back_populates="question")
    methods: Mapped[list["QuestionMethod"]] = relationship(back_populates="question")
    analysis: Mapped["QuestionAnalysis | None"] = relationship(back_populates="question", uselist=False)
    reviews: Mapped[list["ReviewRecord"]] = relationship(back_populates="question")
    chat_sessions: Mapped[list["ChatSession"]] = relationship(back_populates="question")


class QuestionAnswer(TimestampMixin, Base):
    __tablename__ = "question_answer"
    __table_args__ = (Index("ix_question_answer_question_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, unique=True)
    answer_text: Mapped[str | None] = mapped_column(Text)
    answer_md_path: Mapped[str | None] = mapped_column(String(1024))
    answer_json_path: Mapped[str | None] = mapped_column(String(1024))
    match_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    match_status: Mapped[str] = mapped_column(String(32), default="UNMATCHED", nullable=False)

    question: Mapped["Question"] = relationship(back_populates="answer")


class ReviewRecord(Base):
    __tablename__ = "review_record"
    __table_args__ = (
        Index("ix_review_record_paper_question", "paper_id", "question_id"),
        Index("ix_review_record_review_type", "review_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper.id"), nullable=False)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("question.id"))
    review_type: Mapped[str] = mapped_column(String(64), nullable=False)
    before_data_json: Mapped[str | None] = mapped_column(Text)
    after_data_json: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    paper: Mapped["Paper"] = relationship(back_populates="reviews")
    question: Mapped["Question | None"] = relationship(back_populates="reviews")


class KnowledgePoint(TimestampMixin, Base):
    __tablename__ = "knowledge_point"
    __table_args__ = (
        Index("ix_knowledge_point_name", "name"),
        Index("ix_knowledge_point_parent", "parent_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point.id"))
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    parent: Mapped["KnowledgePoint | None"] = relationship(remote_side=[id])
    question_links: Mapped[list["QuestionKnowledge"]] = relationship(back_populates="knowledge_point")


class SolutionMethod(TimestampMixin, Base):
    __tablename__ = "solution_method"
    __table_args__ = (Index("ix_solution_method_name", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    question_links: Mapped[list["QuestionMethod"]] = relationship(back_populates="solution_method")


class QuestionKnowledge(Base):
    __tablename__ = "question_knowledge"
    __table_args__ = (
        Index("ix_question_knowledge_question_id", "question_id"),
        Index("ix_question_knowledge_kp_id", "knowledge_point_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_point.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), default="AUTO", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    question: Mapped["Question"] = relationship(back_populates="knowledges")
    knowledge_point: Mapped["KnowledgePoint"] = relationship(back_populates="question_links")


class QuestionMethod(Base):
    __tablename__ = "question_method"
    __table_args__ = (
        Index("ix_question_method_question_id", "question_id"),
        Index("ix_question_method_method_id", "solution_method_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)
    solution_method_id: Mapped[int] = mapped_column(ForeignKey("solution_method.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), default="AUTO", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    question: Mapped["Question"] = relationship(back_populates="methods")
    solution_method: Mapped["SolutionMethod"] = relationship(back_populates="question_links")


class QuestionAnalysis(TimestampMixin, Base):
    __tablename__ = "question_analysis"
    __table_args__ = (Index("ix_question_analysis_question_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, unique=True)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_md: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(128))
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)

    question: Mapped["Question"] = relationship(back_populates="analysis")


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_session"
    __table_args__ = (Index("ix_chat_session_question_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(128))
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    selected_model: Mapped[str | None] = mapped_column(String(128))

    question: Mapped["Question"] = relationship(back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_message"
    __table_args__ = (Index("ix_chat_message_session_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_session.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128))
    token_usage: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class SolutionTemplate(TimestampMixin, Base):
    __tablename__ = "solution_template"
    __table_args__ = (Index("ix_solution_template_name", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[str | None] = mapped_column(String(512))
    template_md_path: Mapped[str | None] = mapped_column(String(1024))
