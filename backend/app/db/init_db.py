from pathlib import Path

from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.services.auth import bootstrap_auth_data
import app.models  # noqa: F401


def ensure_data_dirs() -> None:
    base_dir = Path(settings.storage_base_dir).resolve()
    for relative in [
        "raw/unpaired/paper",
        "raw/unpaired/answer",
        "raw/archived/paper",
        "raw/archived/answer",
        "mineu",
        "slices",
        "review",
        "analysis",
        "templates",
    ]:
        (base_dir / relative).mkdir(parents=True, exist_ok=True)

    if settings.database_backend.lower() == "sqlite":
        settings.sqlite_path_obj.parent.mkdir(parents=True, exist_ok=True)


def ensure_sqlite_columns() -> None:
    if settings.database_backend.lower() != "sqlite":
        return

    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "paper" not in table_names:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("paper")}
    statements: list[str] = []
    if "is_deleted" not in existing_columns:
        statements.append("ALTER TABLE paper ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT 0")
    if "deleted_at" not in existing_columns:
        statements.append("ALTER TABLE paper ADD COLUMN deleted_at DATETIME")
    for column_name in ["created_by_user_id", "updated_by_user_id", "deleted_by_user_id"]:
        if column_name not in existing_columns:
            statements.append(f"ALTER TABLE paper ADD COLUMN {column_name} INTEGER")
    if "subject" in existing_columns:
        statements.append("ALTER TABLE paper DROP COLUMN subject")

    chat_session_columns = set()
    if "chat_session" in table_names:
        chat_session_columns = {column["name"] for column in inspector.get_columns("chat_session")}
        if "selected_model" not in chat_session_columns:
            statements.append("ALTER TABLE chat_session ADD COLUMN selected_model VARCHAR(128)")

    if "pipeline_task" in table_names:
        pipeline_task_columns = {column["name"] for column in inspector.get_columns("pipeline_task")}
        if "question_id" not in pipeline_task_columns:
            statements.append("ALTER TABLE pipeline_task ADD COLUMN question_id INTEGER")
        if "task_type" not in pipeline_task_columns:
            statements.append("ALTER TABLE pipeline_task ADD COLUMN task_type VARCHAR(64) NOT NULL DEFAULT 'MINEU_CONVERT'")
        if "depends_on_task_id" not in pipeline_task_columns:
            statements.append("ALTER TABLE pipeline_task ADD COLUMN depends_on_task_id INTEGER")
        if "blocked_reason" not in pipeline_task_columns:
            statements.append("ALTER TABLE pipeline_task ADD COLUMN blocked_reason TEXT")
        if "attempt_count" not in pipeline_task_columns:
            statements.append("ALTER TABLE pipeline_task ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")
        if "max_attempts" not in pipeline_task_columns:
            statements.append("ALTER TABLE pipeline_task ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 1")
        for column_name in ["created_by_user_id", "updated_by_user_id"]:
            if column_name not in pipeline_task_columns:
                statements.append(f"ALTER TABLE pipeline_task ADD COLUMN {column_name} INTEGER")

    actor_tables = [
        "import_job",
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
    ]
    for table_name in actor_tables:
        if table_name not in table_names:
            continue
        table_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in ["created_by_user_id", "updated_by_user_id"]:
            if column_name not in table_columns:
                statements.append(f"ALTER TABLE {table_name} ADD COLUMN {column_name} INTEGER")

    if "question" in table_names:
        question_columns = {column["name"] for column in inspector.get_columns("question")}
        if "review_note" not in question_columns:
            statements.append("ALTER TABLE question ADD COLUMN review_note TEXT")
        for column_name in ["created_by_user_id", "updated_by_user_id", "deleted_by_user_id"]:
            if column_name not in question_columns:
                statements.append(f"ALTER TABLE question ADD COLUMN {column_name} INTEGER")

    if "review_record" in table_names:
        review_columns = {column["name"] for column in inspector.get_columns("review_record")}
        if "actor_user_id" not in review_columns:
            statements.append("ALTER TABLE review_record ADD COLUMN actor_user_id INTEGER")

    if "user_permission" not in table_names and "app_user" in table_names:
        statements.append(
            """
            CREATE TABLE user_permission (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                permission VARCHAR(128) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                UNIQUE (user_id, permission)
            )
            """
        )
        statements.append("CREATE INDEX ix_user_permission_user_id ON user_permission (user_id)")

    # 旧版数学单科设计遗留 subject 字段，当前模型已统一移除。
    for table_name in ["knowledge_point", "solution_method"]:
        if table_name in table_names:
            table_columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "subject" in table_columns:
                statements.append(f"ALTER TABLE {table_name} DROP COLUMN subject")

    if not statements:
        return

    with engine.begin() as connection:
        for stmt in statements:
            connection.execute(text(stmt))


def configure_sqlite_runtime() -> None:
    if settings.database_backend.lower() != "sqlite":
        return

    with engine.begin() as connection:
        # 本地开发常有页面轮询与长任务并发读写，WAL 可减少读请求阻塞写入。
        connection.execute(text("PRAGMA journal_mode=WAL"))
        connection.execute(text("PRAGMA busy_timeout=30000"))


def init_db() -> None:
    ensure_data_dirs()
    configure_sqlite_runtime()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        bootstrap_auth_data(db)
