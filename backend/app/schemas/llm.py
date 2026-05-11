from datetime import datetime

from pydantic import BaseModel, Field


class LLMProviderCreateRequest(BaseModel):
    name: str
    base_url: str
    api_key: str
    is_enabled: bool = True
    remark: str | None = None


class LLMProviderUpdateRequest(BaseModel):
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    is_enabled: bool | None = None
    remark: str | None = None


class LLMProviderResponse(BaseModel):
    id: int
    name: str
    base_url: str
    api_key_masked: str | None = None
    is_enabled: bool
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class LLMScenarioUpdateItem(BaseModel):
    scenario_code: str
    primary_provider_id: int | None = None
    primary_model: str | None = None
    fallback_provider_id: int | None = None
    fallback_model: str | None = None
    temperature: float = Field(ge=0, le=2)
    is_enabled: bool = True


class LLMScenarioUpdateRequest(BaseModel):
    scenarios: list[LLMScenarioUpdateItem]


class LLMScenarioResponse(BaseModel):
    id: int
    scenario_code: str
    scenario_name: str
    primary_provider_id: int | None = None
    primary_provider_name: str | None = None
    primary_model: str | None = None
    fallback_provider_id: int | None = None
    fallback_provider_name: str | None = None
    fallback_model: str | None = None
    temperature: float
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class LLMPromptUpdateItem(BaseModel):
    scenario_code: str
    prompt_content: str


class LLMPromptUpdateRequest(BaseModel):
    prompts: list[LLMPromptUpdateItem]


class LLMPromptResponse(BaseModel):
    id: int
    scenario_code: str
    scenario_name: str
    prompt_content: str
    created_at: datetime
    updated_at: datetime
    updated_by_user_id: int | None = None


class LLMProviderTestRequest(BaseModel):
    model: str
    prompt: str = "请回复 OK"


class LLMProviderTestResponse(BaseModel):
    ok: bool
    provider_id: int
    model: str
    content: str | None = None
    error: str | None = None
