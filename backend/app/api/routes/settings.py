from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("")
def get_settings_overview():
    return {
        "database_backend": settings.database_backend,
        "sqlite_path": settings.sqlite_path,
        "storage_backend": settings.storage_backend,
        "storage_base_dir": settings.storage_base_dir,
        "mysql_host": settings.mysql_host,
        "mysql_port": settings.mysql_port,
        "models": {
            "slice": settings.default_model_slice,
            "analysis": settings.default_model_analysis,
            "chat": settings.default_model_chat,
            "fallback": settings.fallback_model,
        },
        "mineu_use_mock": settings.mineu_use_mock,
        "llm_use_mock": settings.llm_use_mock,
    }
