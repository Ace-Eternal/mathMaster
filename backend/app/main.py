from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analysis, chat, dictionary, files, papers, questions, review, search, settings as settings_routes, templates
from app.core.config import settings
from app.db.init_db import init_db
from app.services.pipeline_queue import pipeline_task_queue


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    pipeline_task_queue.start()
    yield
    pipeline_task_queue.stop()


app = FastAPI(
    title="MathMaster API",
    version="0.2.0",
    description="Math paper ingestion, MineU conversion, slicing, matching, review, and tutoring.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(papers.router, prefix="/api/papers", tags=["papers"])
app.include_router(questions.router, prefix="/api/questions", tags=["questions"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(dictionary.router, prefix="/api/dictionary", tags=["dictionary"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
