from __future__ import annotations

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models import AppUser, LLMProviderConfig, LLMPromptConfig, LLMScenarioConfig
from app.schemas.llm import (
    LLMProviderCreateRequest,
    LLMProviderResponse,
    LLMProviderTestRequest,
    LLMProviderTestResponse,
    LLMProviderUpdateRequest,
    LLMPromptResponse,
    LLMPromptUpdateRequest,
    LLMScenarioResponse,
    LLMScenarioUpdateRequest,
)
from app.services.audit import entity_summary, set_created_actor, set_updated_actor, write_audit_log
from app.services.auth import request_meta, require_super_admin
from app.services.llm.config import (
    LLM_SCENARIOS,
    bootstrap_llm_config,
    prompt_summary,
    provider_summary,
    scenario_summary,
)

router = APIRouter()


@router.get("/providers", response_model=list[LLMProviderResponse])
def list_providers(db: Session = Depends(get_db), _actor: AppUser = Depends(require_super_admin)):
    bootstrap_llm_config(db)
    providers = db.execute(select(LLMProviderConfig).order_by(LLMProviderConfig.created_at.desc())).scalars()
    return [provider_summary(provider) for provider in providers]


@router.post("/providers", response_model=LLMProviderResponse)
def create_provider(
    payload: LLMProviderCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    provider = LLMProviderConfig(
        name=payload.name.strip(),
        base_url=payload.base_url.strip().rstrip("/"),
        api_key=payload.api_key.strip(),
        is_enabled=payload.is_enabled,
        remark=(payload.remark or "").strip() or None,
    )
    set_created_actor(provider, actor)
    db.add(provider)
    db.flush()
    write_audit_log(
        db,
        actor=actor,
        action="llm.provider.create",
        resource_type="llm_provider_config",
        resource_id=provider.id,
        after={**entity_summary(provider, ["name", "base_url", "is_enabled", "remark"]), "api_key": "***"},
        **request_meta(request),
    )
    db.commit()
    db.refresh(provider)
    return provider_summary(provider)


@router.patch("/providers/{provider_id}", response_model=LLMProviderResponse)
def update_provider(
    provider_id: int,
    payload: LLMProviderUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    provider = db.get(LLMProviderConfig, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    before = {**entity_summary(provider, ["name", "base_url", "is_enabled", "remark"]), "api_key": "***"}
    if payload.name is not None:
        provider.name = payload.name.strip()
    if payload.base_url is not None:
        provider.base_url = payload.base_url.strip().rstrip("/")
    if payload.api_key is not None and payload.api_key.strip():
        provider.api_key = payload.api_key.strip()
    if payload.is_enabled is not None:
        provider.is_enabled = payload.is_enabled
    if payload.remark is not None:
        provider.remark = payload.remark.strip() or None
    set_updated_actor(provider, actor)
    db.add(provider)
    write_audit_log(
        db,
        actor=actor,
        action="llm.provider.update",
        resource_type="llm_provider_config",
        resource_id=provider.id,
        before=before,
        after={**entity_summary(provider, ["name", "base_url", "is_enabled", "remark"]), "api_key": "***"},
        **request_meta(request),
    )
    db.commit()
    db.refresh(provider)
    return provider_summary(provider)


@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    provider = db.get(LLMProviderConfig, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    linked = db.execute(
        select(LLMScenarioConfig).where(
            (LLMScenarioConfig.primary_provider_id == provider_id)
            | (LLMScenarioConfig.fallback_provider_id == provider_id)
        )
    ).scalars().first()
    if linked is not None:
        raise HTTPException(status_code=409, detail="Provider is used by scenario config")
    before = {**entity_summary(provider, ["name", "base_url", "is_enabled", "remark"]), "api_key": "***"}
    db.delete(provider)
    write_audit_log(
        db,
        actor=actor,
        action="llm.provider.delete",
        resource_type="llm_provider_config",
        resource_id=provider_id,
        before=before,
        **request_meta(request),
    )
    db.commit()
    return {"ok": True, "provider_id": provider_id}


@router.post("/providers/{provider_id}/test", response_model=LLMProviderTestResponse)
def test_provider(
    provider_id: int,
    payload: LLMProviderTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    provider = db.get(LLMProviderConfig, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    try:
        response = requests.post(
            f"{provider.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json={
                "model": payload.model,
                "messages": [{"role": "user", "content": payload.prompt}],
                "temperature": 0,
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        result = LLMProviderTestResponse(ok=True, provider_id=provider.id, model=payload.model, content=content)
    except Exception as exc:  # noqa: BLE001
        result = LLMProviderTestResponse(ok=False, provider_id=provider.id, model=payload.model, error=str(exc))
    write_audit_log(
        db,
        actor=actor,
        action="llm.provider.test",
        resource_type="llm_provider_config",
        resource_id=provider.id,
        after={"ok": result.ok, "model": payload.model, "error": result.error},
        **request_meta(request),
    )
    db.commit()
    return result


@router.get("/scenarios", response_model=list[LLMScenarioResponse])
def list_scenarios(db: Session = Depends(get_db), _actor: AppUser = Depends(require_super_admin)):
    bootstrap_llm_config(db)
    scenarios = db.execute(
        select(LLMScenarioConfig)
        .options(selectinload(LLMScenarioConfig.primary_provider), selectinload(LLMScenarioConfig.fallback_provider))
        .order_by(LLMScenarioConfig.scenario_code.asc())
    ).scalars()
    return [scenario_summary(scenario) for scenario in scenarios]


@router.put("/scenarios", response_model=list[LLMScenarioResponse])
def update_scenarios(
    payload: LLMScenarioUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    bootstrap_llm_config(db)
    unknown = [item.scenario_code for item in payload.scenarios if item.scenario_code not in LLM_SCENARIOS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown scenarios: {', '.join(unknown)}")
    provider_ids = {
        provider_id
        for item in payload.scenarios
        for provider_id in [item.primary_provider_id, item.fallback_provider_id]
        if provider_id is not None
    }
    if provider_ids:
        found = set(db.execute(select(LLMProviderConfig.id).where(LLMProviderConfig.id.in_(provider_ids))).scalars())
        missing = sorted(provider_ids - found)
        if missing:
            raise HTTPException(status_code=422, detail=f"Unknown provider ids: {missing}")
    before: list[dict] = []
    after: list[dict] = []
    for item in payload.scenarios:
        scenario = db.execute(
            select(LLMScenarioConfig).where(LLMScenarioConfig.scenario_code == item.scenario_code)
        ).scalar_one()
        before.append(entity_summary(scenario, ["scenario_code", "primary_provider_id", "primary_model", "fallback_provider_id", "fallback_model", "temperature", "is_enabled"]))
        scenario.primary_provider_id = item.primary_provider_id
        scenario.primary_model = (item.primary_model or "").strip() or None
        scenario.fallback_provider_id = item.fallback_provider_id
        scenario.fallback_model = (item.fallback_model or "").strip() or None
        scenario.temperature = item.temperature
        scenario.is_enabled = item.is_enabled
        set_updated_actor(scenario, actor)
        db.add(scenario)
        after.append(entity_summary(scenario, ["scenario_code", "primary_provider_id", "primary_model", "fallback_provider_id", "fallback_model", "temperature", "is_enabled"]))
    write_audit_log(db, actor=actor, action="llm.scenarios.update", resource_type="llm_scenario_config", resource_id="bulk", before=before, after=after, **request_meta(request))
    db.commit()
    return list_scenarios(db, actor)


@router.get("/prompts", response_model=list[LLMPromptResponse])
def list_prompts(db: Session = Depends(get_db), _actor: AppUser = Depends(require_super_admin)):
    bootstrap_llm_config(db)
    prompts = db.execute(select(LLMPromptConfig).order_by(LLMPromptConfig.scenario_code.asc())).scalars()
    return [prompt_summary(prompt) for prompt in prompts]


@router.put("/prompts", response_model=list[LLMPromptResponse])
def update_prompts(
    payload: LLMPromptUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    bootstrap_llm_config(db)
    unknown = [item.scenario_code for item in payload.prompts if item.scenario_code not in LLM_SCENARIOS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown prompts: {', '.join(unknown)}")
    before: list[dict] = []
    after: list[dict] = []
    for item in payload.prompts:
        prompt = db.execute(select(LLMPromptConfig).where(LLMPromptConfig.scenario_code == item.scenario_code)).scalar_one()
        before.append({"scenario_code": prompt.scenario_code, "prompt_length": len(prompt.prompt_content)})
        prompt.prompt_content = item.prompt_content
        set_updated_actor(prompt, actor)
        db.add(prompt)
        after.append({"scenario_code": prompt.scenario_code, "prompt_length": len(prompt.prompt_content)})
    write_audit_log(db, actor=actor, action="llm.prompts.update", resource_type="llm_prompt_config", resource_id="bulk", before=before, after=after, **request_meta(request))
    db.commit()
    return list_prompts(db, actor)
