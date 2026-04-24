from pathlib import Path

from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
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
    if "subject" in existing_columns:
        statements.append("ALTER TABLE paper DROP COLUMN subject")

    chat_session_columns = set()
    if "chat_session" in table_names:
        chat_session_columns = {column["name"] for column in inspector.get_columns("chat_session")}
        if "selected_model" not in chat_session_columns:
            statements.append("ALTER TABLE chat_session ADD COLUMN selected_model VARCHAR(128)")

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


def init_db() -> None:
    ensure_data_dirs()
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()
