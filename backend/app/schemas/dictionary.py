from pydantic import BaseModel

from app.schemas.common import TimestampedResponse


class KnowledgePointCreate(BaseModel):
    name: str
    parent_id: int | None = None
    level: int
    subject: str = "math"
    sort_no: int = 0


class KnowledgePointUpdate(BaseModel):
    name: str
    parent_id: int | None = None
    level: int
    subject: str = "math"
    sort_no: int = 0


class KnowledgePointResponse(TimestampedResponse):
    id: int
    name: str
    parent_id: int | None = None
    level: int
    subject: str
    sort_no: int


class SolutionMethodCreate(BaseModel):
    name: str
    description: str | None = None
    subject: str = "math"


class SolutionMethodUpdate(BaseModel):
    name: str
    description: str | None = None
    subject: str = "math"


class SolutionMethodResponse(TimestampedResponse):
    id: int
    name: str
    description: str | None = None
    subject: str
