from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import LLMProviderConfig, LLMPromptConfig, LLMScenarioConfig


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"

LLM_SCENARIOS: dict[str, dict[str, Any]] = {
    "slice_match": {"name": "题目切片匹配", "prompt_file": "slice_prompt.md", "default_model": "default_model_slice", "temperature": 0.2},
    "global_answer_match": {"name": "全局答案匹配", "prompt_file": "slice_prompt.md", "default_model": "default_model_slice", "temperature": 0.2},
    "full_paper_boundary": {"name": "整卷题目边界识别", "prompt_file": "full_paper_boundary_prompt.md", "default_model": "default_model_slice", "temperature": 0.2},
    "full_answer_boundary": {"name": "整卷答案边界识别", "prompt_file": "full_answer_boundary_prompt.md", "default_model": "default_model_slice", "temperature": 0.2},
    "analysis": {"name": "知识点与解法分析", "prompt_file": "analysis_prompt.md", "default_model": "default_model_analysis", "temperature": 0.2},
    "chat": {"name": "讲题对话", "prompt_file": "chat_system_prompt.md", "default_model": "default_model_chat", "temperature": 0.3},
}


@dataclass(frozen=True)
class ProviderRuntime:
    id: int | None
    name: str
    base_url: str
    api_key: str


@dataclass(frozen=True)
class ScenarioRuntime:
    scenario_code: str
    prompt: str
    primary_provider: ProviderRuntime | None
    primary_model: str
    fallback_provider: ProviderRuntime | None
    fallback_model: str | None
    temperature: float


def default_prompt(scenario_code: str) -> str:
    scenario = LLM_SCENARIOS[scenario_code]
    return PROMPT_DIR.joinpath(str(scenario["prompt_file"])).read_text(encoding="utf-8")


def default_model(scenario_code: str) -> str:
    attr = str(LLM_SCENARIOS[scenario_code]["default_model"])
    return str(getattr(settings, attr))


def mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}{'*' * 8}{api_key[-4:]}"


def provider_summary(provider: LLMProviderConfig | None) -> dict[str, Any] | None:
    if provider is None:
        return None
    return {
        "id": provider.id,
        "name": provider.name,
        "base_url": provider.base_url,
        "api_key_masked": mask_api_key(provider.api_key),
        "is_enabled": provider.is_enabled,
        "remark": provider.remark,
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
    }


def scenario_summary(scenario: LLMScenarioConfig) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "scenario_code": scenario.scenario_code,
        "scenario_name": LLM_SCENARIOS.get(scenario.scenario_code, {}).get("name", scenario.scenario_code),
        "primary_provider_id": scenario.primary_provider_id,
        "primary_provider_name": scenario.primary_provider.name if scenario.primary_provider else None,
        "primary_model": scenario.primary_model,
        "fallback_provider_id": scenario.fallback_provider_id,
        "fallback_provider_name": scenario.fallback_provider.name if scenario.fallback_provider else None,
        "fallback_model": scenario.fallback_model,
        "temperature": float(scenario.temperature),
        "is_enabled": scenario.is_enabled,
        "created_at": scenario.created_at,
        "updated_at": scenario.updated_at,
    }


def prompt_summary(prompt: LLMPromptConfig) -> dict[str, Any]:
    return {
        "id": prompt.id,
        "scenario_code": prompt.scenario_code,
        "scenario_name": LLM_SCENARIOS.get(prompt.scenario_code, {}).get("name", prompt.scenario_code),
        "prompt_content": prompt.prompt_content,
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
        "updated_by_user_id": prompt.updated_by_user_id,
    }


def bootstrap_llm_config(db: Session) -> None:
    provider: LLMProviderConfig | None = None
    if settings.llm_base_url and settings.llm_api_key:
        provider = db.execute(select(LLMProviderConfig).where(LLMProviderConfig.name == "默认环境配置")).scalar_one_or_none()
        if provider is None:
            provider = LLMProviderConfig(
                name="默认环境配置",
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                is_enabled=True,
                remark="由 .env 初始化，可在系统设置中调整。",
            )
            db.add(provider)
            db.flush()

    for scenario_code, scenario_meta in LLM_SCENARIOS.items():
        scenario = db.execute(
            select(LLMScenarioConfig).where(LLMScenarioConfig.scenario_code == scenario_code)
        ).scalar_one_or_none()
        if scenario is None:
            scenario = LLMScenarioConfig(
                scenario_code=scenario_code,
                primary_provider_id=provider.id if provider else None,
                primary_model=default_model(scenario_code),
                fallback_provider_id=provider.id if provider and settings.fallback_model else None,
                fallback_model=settings.fallback_model or None,
                temperature=float(scenario_meta["temperature"]),
                is_enabled=True,
            )
            db.add(scenario)

        prompt = db.execute(select(LLMPromptConfig).where(LLMPromptConfig.scenario_code == scenario_code)).scalar_one_or_none()
        if prompt is None:
            db.add(LLMPromptConfig(scenario_code=scenario_code, prompt_content=default_prompt(scenario_code)))

    db.commit()


def get_runtime_config(db: Session, scenario_code: str, requested_model: str | None = None) -> ScenarioRuntime:
    if scenario_code not in LLM_SCENARIOS:
        raise ValueError(f"未知 LLM 场景: {scenario_code}")

    scenario = db.execute(
        select(LLMScenarioConfig)
        .options(selectinload(LLMScenarioConfig.primary_provider), selectinload(LLMScenarioConfig.fallback_provider))
        .where(LLMScenarioConfig.scenario_code == scenario_code)
    ).scalar_one_or_none()
    prompt = db.execute(select(LLMPromptConfig).where(LLMPromptConfig.scenario_code == scenario_code)).scalar_one_or_none()

    primary_provider = _runtime_provider(scenario.primary_provider) if scenario and scenario.primary_provider else _env_provider()
    fallback_provider = _runtime_provider(scenario.fallback_provider) if scenario and scenario.fallback_provider else None
    primary_model = (requested_model or (scenario.primary_model if scenario else None) or default_model(scenario_code)).strip()
    fallback_model = (scenario.fallback_model if scenario else settings.fallback_model) or None
    temperature = float(scenario.temperature) if scenario else float(LLM_SCENARIOS[scenario_code]["temperature"])

    return ScenarioRuntime(
        scenario_code=scenario_code,
        prompt=prompt.prompt_content if prompt else default_prompt(scenario_code),
        primary_provider=primary_provider,
        primary_model=primary_model,
        fallback_provider=fallback_provider or primary_provider,
        fallback_model=fallback_model,
        temperature=temperature,
    )


def list_models_for_provider(provider: ProviderRuntime, *, timeout_seconds: int | None = None) -> list[str]:
    response = requests.get(
        f"{provider.base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {provider.api_key}"},
        timeout=timeout_seconds or min(settings.llm_timeout_seconds, 20),
    )
    response.raise_for_status()
    payload = response.json()
    return [str(item.get("id")) for item in payload.get("data") or [] if item.get("id")]


def _runtime_provider(provider: LLMProviderConfig) -> ProviderRuntime | None:
    if not provider.is_enabled:
        return None
    return ProviderRuntime(id=provider.id, name=provider.name, base_url=provider.base_url, api_key=provider.api_key)


def _env_provider() -> ProviderRuntime | None:
    if not settings.llm_base_url or not settings.llm_api_key:
        return None
    return ProviderRuntime(id=None, name="环境变量配置", base_url=settings.llm_base_url, api_key=settings.llm_api_key)
