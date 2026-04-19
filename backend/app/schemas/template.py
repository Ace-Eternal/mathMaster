from pydantic import BaseModel

from app.schemas.common import TimestampedResponse


class SolutionTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    content: str = ""
    tags: str | None = None


class SolutionTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    tags: str | None = None


class SolutionTemplateResponse(TimestampedResponse):
    id: int
    name: str
    description: str | None = None
    content: str
    tags: str | None = None
    template_md_path: str | None = None
