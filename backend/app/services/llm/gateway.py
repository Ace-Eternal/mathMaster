from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings


class LLMGateway:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url
        self.api_key = settings.llm_api_key
        self.use_mock = bool(settings.llm_use_mock)
        self.is_packyapi = "packyapi.com" in (self.base_url or "")

    def _load_prompt(self, filename: str) -> str:
        return Path(__file__).resolve().parents[1].joinpath("prompts", filename).read_text(encoding="utf-8")

    def structured_output(self, *, scenario: str, payload: dict[str, Any], model: str | None = None) -> dict[str, Any]:
        if self.use_mock:
            return self._mock_structured_output(scenario=scenario, payload=payload)
        self._ensure_llm_configured()

        system_prompt = {
            "slice_match": self._load_prompt("slice_prompt.md"),
            "global_answer_match": self._load_prompt("slice_prompt.md"),
            "full_paper_boundary": self._load_prompt("full_paper_boundary_prompt.md"),
            "full_answer_boundary": self._load_prompt("full_answer_boundary_prompt.md"),
            "analysis": self._load_prompt("analysis_prompt.md"),
        }[scenario]
        request_payload = {
            "model": model or self._scenario_model(scenario),
            "messages": [
                {
                    "role": "system",
                    "content": f"{system_prompt}\n\nYou must return a valid JSON object only.",
                },
                {
                    "role": "user",
                    "content": (
                        "Please read the following payload and return JSON only.\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
            "temperature": 0.2,
        }
        if not (self.is_packyapi and scenario == "analysis"):
            request_payload["response_format"] = {"type": "json_object"}
        try:
            content = self._run_structured_request(request_payload=request_payload)
            return self._normalize_structured_result(scenario=scenario, payload=payload, result=json.loads(content))
        except Exception as primary_error:  # noqa: BLE001
            fallback_errors: list[str] = []
            for fallback_model in self._fallback_models(requested_model=str(request_payload["model"])):
                fallback_payload = {**request_payload, "model": fallback_model}
                try:
                    content = self._run_structured_request(request_payload=fallback_payload)
                    parsed = self._normalize_structured_result(
                        scenario=scenario,
                        payload=payload,
                        result=json.loads(content),
                    )
                    parsed["_fallback_notice"] = f"主模型调用失败，已切换备用模型 {fallback_model}: {primary_error}"
                    return parsed
                except Exception as fallback_error:  # noqa: BLE001
                    fallback_errors.append(f"{fallback_model}: {fallback_error}")
            if fallback_errors:
                raise RuntimeError(
                    "主模型与备用模型均调用失败。"
                    f" 主模型错误: {primary_error}; 备用模型错误: {' | '.join(fallback_errors)}"
                ) from primary_error
            raise RuntimeError(f"主模型调用失败，且没有可用备用模型: {primary_error}") from primary_error

    def chat(self, *, system_prompt: str, messages: list[dict[str, str]], model: str | None = None) -> dict[str, Any]:
        if self.use_mock:
            user_message = messages[-1]["content"]
            return {
                "content": f"基于当前题目信息，可以先从已知条件、目标结论和可用方法三部分来分析：{user_message}",
                "model_name": model or settings.default_model_chat,
                "token_usage": 128,
            }
        self._ensure_llm_configured()

        request_payload = {
            "model": model or settings.default_model_chat,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "temperature": 0.3,
        }
        try:
            if self.is_packyapi:
                content = self._post_chat_completions_streaming(request_payload=request_payload)
                return {
                    "content": content,
                    "model_name": request_payload["model"],
                    "token_usage": None,
                }
            data = self._post_chat_completions(request_payload=request_payload)
            return {
                "content": self._extract_message_content(data),
                "model_name": data.get("model", model or settings.default_model_chat),
                "token_usage": data.get("usage", {}).get("total_tokens"),
            }
        except Exception as primary_error:  # noqa: BLE001
            fallback_errors: list[str] = []
            for fallback_model in self._fallback_models(requested_model=str(request_payload["model"])):
                fallback_payload = {**request_payload, "model": fallback_model}
                try:
                    if self.is_packyapi:
                        content = self._post_chat_completions_streaming(request_payload=fallback_payload)
                        return {
                            "content": content,
                            "model_name": fallback_model,
                            "token_usage": None,
                        }
                    data = self._post_chat_completions(request_payload=fallback_payload)
                    return {
                        "content": self._extract_message_content(data),
                        "model_name": data.get("model", fallback_model),
                        "token_usage": data.get("usage", {}).get("total_tokens"),
                    }
                except Exception as fallback_error:  # noqa: BLE001
                    fallback_errors.append(f"{fallback_model}: {fallback_error}")
            if fallback_errors:
                raise RuntimeError(
                    "主模型与备用模型均调用失败。"
                    f" 主模型错误: {primary_error}; 备用模型错误: {' | '.join(fallback_errors)}"
                ) from primary_error
            raise RuntimeError(f"主模型调用失败，且没有可用备用模型: {primary_error}") from primary_error

    def _run_structured_request(self, *, request_payload: dict[str, Any]) -> str:
        if self.is_packyapi:
            return self._post_chat_completions_streaming(request_payload=request_payload)
        data = self._post_chat_completions(request_payload=request_payload)
        return self._extract_message_content(data)

    def _ensure_llm_configured(self) -> None:
        if self.base_url and self.api_key:
            return
        raise RuntimeError("LLM 未正确配置，且当前未显式开启 mock。请检查 LLM_BASE_URL、LLM_API_KEY 与 LLM_USE_MOCK。")

    def _normalize_structured_result(
        self,
        *,
        scenario: str,
        payload: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        if scenario in {"full_paper_boundary", "full_answer_boundary"}:
            return self._normalize_boundary_result(scenario=scenario, result=result)
        if scenario == "analysis":
            return self._normalize_analysis_result(payload=payload, result=result)
        if scenario != "slice_match" and scenario != "global_answer_match":
            return result

        return self._normalize_match_result(scenario=scenario, payload=payload, result=result)

    def _normalize_analysis_result(self, *, payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        if "major_knowledge_points" in result or "minor_knowledge_points" in result or "solution_methods" in result:
            return result
        analysis = result.get("analysis") if isinstance(result.get("analysis"), dict) else {}
        reasoning = analysis.get("reasoning") if isinstance(analysis.get("reasoning"), list) else []
        explanation_parts: list[str] = []
        for item in reasoning[:4]:
            if not isinstance(item, dict):
                continue
            option = str(item.get("option") or "").strip()
            judgement = str(item.get("judgement") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if detail:
                prefix = f"{option}：{judgement}。" if option and judgement else ""
                explanation_parts.append(f"{prefix}{detail}".strip())
        conclusion = str(analysis.get("conclusion") or result.get("conclusion") or "").strip()
        if conclusion:
            explanation_parts.append(conclusion)
        explanation_md = "\n\n".join(part for part in explanation_parts if part).strip()
        normalized = {
            "major_knowledge_points": [],
            "minor_knowledge_points": [],
            "solution_methods": [],
            "explanation_md": explanation_md,
            "confidence": 0.72,
            "need_manual_review": False,
        }
        normalized["_fallback_notice"] = "已将 PackyAPI 返回的题解型分析结果归一化为项目字段。"
        return normalized

    def _normalize_boundary_result(self, *, scenario: str, result: dict[str, Any]) -> dict[str, Any]:
        items = result.get("items")
        if not isinstance(items, list):
            items = result.get("boundaries")
        if not isinstance(items, list) and scenario == "full_paper_boundary":
            section_items: list[dict[str, Any]] = []
            for section in result.get("sections") or []:
                for question in section.get("questions") or []:
                    stem = str(question.get("stem") or "").strip()
                    sub_questions = question.get("sub_questions") or []
                    if isinstance(sub_questions, list) and sub_questions:
                        stem = "\n".join([stem, *[str(item).strip() for item in sub_questions if str(item).strip()]]).strip()
                    section_items.append(
                        {
                            "question_no": str(question.get("question_no") or ""),
                            "question_type": self._map_external_question_type(str(question.get("type") or "")),
                            "start_block_index": question.get("start_block_index"),
                            "end_block_index": question.get("end_block_index"),
                            "page_start": question.get("page_start"),
                            "page_end": question.get("page_end"),
                            "has_sub_questions": bool(sub_questions),
                            "need_manual_review": bool(question.get("need_manual_review")),
                            "review_reason": str(question.get("review_reason") or "").strip() or None,
                            "llm_text": stem or None,
                        }
                    )
            items = section_items
        if not isinstance(items, list) and scenario == "full_answer_boundary":
            answer_map = result.get("answers") or {}
            if isinstance(answer_map, dict):
                answer_items: list[dict[str, Any]] = []
                for answer_no, answer_value in self._iter_answer_entries(answer_map):
                    answer_text = self._stringify_answer_value(answer_value)
                    if not answer_text:
                        continue
                    answer_items.append(
                        {
                            "answer_question_no": str(answer_no),
                            "start_block_index": None,
                            "end_block_index": None,
                            "page_start": None,
                            "page_end": None,
                            "has_sub_questions": "（1）" in answer_text or "(1)" in answer_text,
                            "need_manual_review": False,
                            "review_reason": None,
                            "llm_text": answer_text or None,
                            "text_only_candidate": True,
                        }
                    )
                items = answer_items
        if not isinstance(items, list):
            items = []
        normalized_items: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            question_no = str(item.get("question_no") or item.get("answer_question_no") or index)
            normalized_items.append(
                {
                    "question_no": question_no,
                    "answer_question_no": str(item.get("answer_question_no") or question_no),
                    "question_type": str(item.get("question_type") or "解答题"),
                    "start_block_index": item.get("start_block_index"),
                    "end_block_index": item.get("end_block_index"),
                    "page_start": item.get("page_start"),
                    "page_end": item.get("page_end"),
                    "has_sub_questions": bool(item.get("has_sub_questions")),
                    "need_manual_review": bool(item.get("need_manual_review")),
                    "review_reason": str(item.get("review_reason") or "").strip() or None,
                    "llm_text": str(item.get("llm_text") or "").strip() or None,
                    "text_only_candidate": bool(item.get("text_only_candidate")),
                }
            )
        normalized = {"items": normalized_items}
        if normalized_items != items:
            normalized["_fallback_notice"] = "已将 PackyAPI 返回边界结果归一化为项目字段。"
        return normalized

    @staticmethod
    def _map_external_question_type(question_type: str) -> str:
        mapping = {
            "single_choice": "选择题",
            "multiple_choice": "多选题",
            "fill_blank": "填空题",
            "free_response": "解答题",
        }
        return mapping.get(question_type.strip().lower(), "解答题")

    @staticmethod
    def _stringify_answer_value(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = [LLMGateway._stringify_answer_value(item) for item in value]
            return "\n".join(part for part in parts if part).strip()
        if isinstance(value, dict):
            parts: list[str] = []
            score = str(value.get("score") or "").strip()
            solution = str(value.get("solution") or value.get("answer") or "").strip()
            explanation = str(value.get("analysis") or value.get("explanation") or "").strip()
            if score:
                parts.append(score)
            if solution:
                parts.append(solution)
            if explanation:
                parts.append(explanation)
            raw_parts = value.get("parts")
            if isinstance(raw_parts, list):
                for item in raw_parts:
                    rendered = LLMGateway._stringify_answer_value(item)
                    if rendered:
                        parts.append(rendered)
            elif isinstance(raw_parts, dict):
                for key, item in raw_parts.items():
                    rendered = LLMGateway._stringify_answer_value(item)
                    if rendered:
                        parts.append(f"{key}: {rendered}" if key else rendered)
            if not parts:
                parts.append(json.dumps(value, ensure_ascii=False))
            return "\n".join(parts).strip()
        return str(value).strip()

    @staticmethod
    def _iter_answer_entries(value: Any) -> list[tuple[str, Any]]:
        entries: list[tuple[str, Any]] = []

        def walk(node: Any) -> None:
            if not isinstance(node, dict):
                return
            for key, child in node.items():
                question_no = str(key).strip()
                if question_no.isdigit():
                    entries.append((question_no, child))
                    continue
                if isinstance(child, dict):
                    walk(child)

        walk(value)
        deduped: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for question_no, entry in entries:
            if question_no in seen:
                continue
            seen.add(question_no)
            deduped.append((question_no, entry))
        return deduped

    def _normalize_match_result(
        self,
        *,
        scenario: str,
        payload: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        if scenario == "global_answer_match":
            required_keys = {"matched_answer_candidate_id", "match_confidence", "need_manual_review", "review_reason"}
            if required_keys.issubset(result.keys()):
                return result
            candidates = payload.get("answer_candidates") or []
            question_no = str(payload.get("question_no") or "").strip()
            preferred = next(
                (candidate for candidate in candidates if str(candidate.get("answer_question_no") or "").strip() == question_no),
                None,
            )
            if preferred is None:
                preferred = {}
            normalized = {
                "matched_answer_candidate_id": str(
                    result.get("matched_answer_candidate_id")
                    or result.get("answer_candidate_id")
                    or ""
                ),
                "match_confidence": float(result.get("match_confidence") if result.get("match_confidence") is not None else 0.2),
                "need_manual_review": bool(
                    result.get("need_manual_review")
                    if result.get("need_manual_review") is not None
                    else True
                ),
                "review_reason": str(result.get("review_reason") or "").strip() or None,
            }
            normalized["_fallback_notice"] = "已将 PackyAPI 返回匹配结果归一化为项目字段。"
            return normalized

        required_keys = {
            "question_no",
            "question_type",
            "stem_text",
            "has_sub_questions",
            "image_refs",
            "answer_question_no",
            "match_confidence",
            "need_manual_review",
        }
        if required_keys.issubset(result.keys()):
            return result

        answer_candidate = payload.get("answer_candidate") or {}
        is_match = result.get("is_match")
        normalized = {
            "question_no": str(result.get("question_no") or result.get("candidate_no") or payload.get("candidate_no") or "1"),
            "question_type": str(result.get("question_type") or payload.get("question_type") or "解答题"),
            "stem_text": str(result.get("stem_text") or payload.get("markdown_excerpt") or ""),
            "has_sub_questions": bool(
                result.get("has_sub_questions")
                if result.get("has_sub_questions") is not None
                else ("（1）" in str(payload.get("markdown_excerpt") or "") or "(1)" in str(payload.get("markdown_excerpt") or ""))
            ),
            "image_refs": result.get("image_refs") or payload.get("image_blocks") or [],
            "answer_question_no": (
                str(result.get("answer_question_no") or answer_candidate.get("candidate_no") or "")
                if is_match is not False
                else ""
            ),
            "match_confidence": float(
                result.get("match_confidence")
                if result.get("match_confidence") is not None
                else (0.85 if is_match else 0.2)
            ),
            "need_manual_review": bool(
                result.get("need_manual_review")
                if result.get("need_manual_review") is not None
                else (is_match is False or float(result.get("match_confidence") or 0.2) < 0.75)
            ),
        }
        normalized["_fallback_notice"] = (
            str(result.get("_fallback_notice") or "") + "；已将 PackyAPI 返回结果归一化为项目字段。"
        ).strip("；")
        return normalized

    def _post_chat_completions(self, *, request_payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_error: Exception | None = None
        requested_model = str(request_payload.get("model") or "")

        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=request_payload,
                    timeout=settings.llm_timeout_seconds,
                )
                if response.ok:
                    return response.json()

                detail = self._extract_error_detail(response)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    last_error = RuntimeError(detail)
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise RuntimeError(self._append_model_inventory_hint(detail, requested_model=requested_model))
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                detail = f"LLM request failed: {exc}"
                raise RuntimeError(self._append_model_inventory_hint(detail, requested_model=requested_model)) from exc

        detail = f"LLM request failed: {last_error}"
        raise RuntimeError(self._append_model_inventory_hint(detail, requested_model=requested_model))

    def _post_chat_completions_streaming(self, *, request_payload: dict[str, Any]) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {**request_payload, "stream": True}
        requested_model = str(payload.get("model") or "")
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                with requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=settings.llm_timeout_seconds,
                    stream=True,
                ) as response:
                    if not response.ok:
                        detail = self._extract_error_detail(response)
                        if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                            last_error = RuntimeError(detail)
                            time.sleep(1.5 * (attempt + 1))
                            continue
                        raise RuntimeError(self._append_model_inventory_hint(detail, requested_model=requested_model))

                    parts: list[str] = []
                    for raw_line in response.iter_lines(decode_unicode=False):
                        if raw_line in (None, b""):
                            continue
                        if not raw_line.startswith(b"data: "):
                            continue
                        data = raw_line[6:]
                        if data == b"[DONE]":
                            break
                        chunk = json.loads(data.decode("utf-8"))
                        delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                        if delta is not None:
                            parts.append(delta)
                    content = "".join(parts).strip()
                    if content:
                        return content
                    raise RuntimeError(f"LLM streaming response empty for model {requested_model}")
            except (requests.RequestException, UnicodeDecodeError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                detail = f"LLM streaming request failed: {exc}"
                raise RuntimeError(self._append_model_inventory_hint(detail, requested_model=requested_model)) from exc

        detail = f"LLM streaming request failed: {last_error}"
        raise RuntimeError(self._append_model_inventory_hint(detail, requested_model=requested_model))

    @staticmethod
    def _extract_error_detail(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"LLM request failed with status {response.status_code}: {response.text[:500]}"

        error = payload.get("error") or {}
        message = error.get("message") or payload.get("message") or response.text[:500]
        code = error.get("code")
        if code:
            return f"LLM request failed with status {response.status_code} [{code}]: {message}"
        return f"LLM request failed with status {response.status_code}: {message}"

    @staticmethod
    def _extract_message_content(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM response missing choices: {data}")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        raise RuntimeError(f"LLM returned empty content: {data}")

    def _append_model_inventory_hint(self, detail: str, *, requested_model: str) -> str:
        available_models = self._get_available_models()
        chat_models = [model for model in available_models if model != "omni-moderation-latest"]
        if not available_models:
            return detail
        if requested_model and requested_model in available_models:
            return detail
        if not chat_models:
            return f"{detail}；当前 PackyAPI 账户下未发现可用聊天模型，/models 仅返回: {', '.join(available_models)}"
        return f"{detail}；当前 /models 可见模型: {', '.join(available_models)}"

    def _get_available_models(self) -> list[str]:
        try:
            response = requests.get(
                f"{self.base_url.rstrip('/')}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=min(settings.llm_timeout_seconds, 20),
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []

        models = payload.get("data") or []
        return [str(item.get("id")) for item in models if item.get("id")]

    @staticmethod
    def _scenario_model(scenario: str) -> str:
        if scenario in {"slice_match", "global_answer_match", "full_paper_boundary", "full_answer_boundary"}:
            if "packyapi.com" in (settings.llm_base_url or ""):
                return "gpt-5.4-high"
            return settings.default_model_slice
        if scenario == "analysis":
            if "packyapi.com" in (settings.llm_base_url or ""):
                return "gpt-5.4-high"
            return settings.default_model_analysis
        return settings.default_model_chat

    def _fallback_models(self, *, requested_model: str) -> list[str]:
        available_models = self._get_available_models()
        candidates: list[str] = []
        if self.is_packyapi:
            candidates.extend(["gpt-5.4-high", "gpt-5.2-medium", "gpt-5.2", "gpt-5.4"])
        if settings.fallback_model:
            candidates.append(settings.fallback_model)

        deduped: list[str] = []
        for model in candidates:
            if not model or model == requested_model:
                continue
            if available_models and model not in available_models:
                continue
            if model not in deduped:
                deduped.append(model)
        return deduped

    @staticmethod
    def _mock_structured_output(*, scenario: str, payload: dict[str, Any]) -> dict[str, Any]:
        if scenario == "slice_match":
            stem_text = payload.get("markdown_excerpt", "").strip()
            answer_candidate = payload.get("answer_candidate")
            image_blocks = payload.get("image_blocks") or []
            return {
                "question_no": payload.get("candidate_no", "1"),
                "question_type": payload.get("question_type", "解答题"),
                "stem_text": stem_text[:1500],
                "has_sub_questions": "（1）" in stem_text or "(1)" in stem_text,
                "image_refs": image_blocks,
                "answer_question_no": payload.get("candidate_no", "1"),
                "match_confidence": 0.9 if answer_candidate else 0.38,
                "need_manual_review": answer_candidate is None or len(stem_text) < 20,
            }
        if scenario == "global_answer_match":
            candidates = payload.get("answer_candidates") or []
            first_candidate = candidates[0] if candidates else {}
            return {
                "matched_answer_candidate_id": first_candidate.get("answer_candidate_id", ""),
                "match_confidence": 0.86 if candidates else 0.2,
                "need_manual_review": not candidates,
                "review_reason": None if candidates else "未提供答案候选",
            }
        if scenario == "full_paper_boundary":
            blocks = payload.get("blocks") or []
            items = []
            current_start = None
            current_no = None
            current_type = "解答题"
            current_page_start = None
            previous_block_index = None
            previous_page_idx = None
            for block in blocks:
                text = str(block.get("text") or "")
                match = re.search(r"^\s*(\d+)[.．、)]", text)
                if match:
                    if current_start is not None and current_no is not None:
                        items.append(
                            {
                                "question_no": current_no,
                                "question_type": current_type,
                                "start_block_index": current_start,
                                "end_block_index": previous_block_index,
                                "page_start": current_page_start,
                                "page_end": previous_page_idx,
                                "has_sub_questions": False,
                                "need_manual_review": False,
                                "review_reason": None,
                            }
                        )
                    current_no = match.group(1)
                    current_start = block.get("block_index")
                    current_page_start = block.get("page_idx")
                    current_type = "选择题" if re.search(r"\bA[.．、)]", text) else "解答题"
                previous_block_index = block.get("block_index")
                previous_page_idx = block.get("page_idx")
            if current_start is not None and current_no is not None:
                items.append(
                    {
                        "question_no": current_no,
                        "question_type": current_type,
                        "start_block_index": current_start,
                        "end_block_index": previous_block_index,
                        "page_start": current_page_start,
                        "page_end": previous_page_idx,
                        "has_sub_questions": False,
                        "need_manual_review": False,
                        "review_reason": None,
                    }
                )
            return {"items": items}
        if scenario == "full_answer_boundary":
            blocks = payload.get("blocks") or []
            items = []
            current_start = None
            current_no = None
            current_page_start = None
            previous_block_index = None
            previous_page_idx = None
            for block in blocks:
                text = str(block.get("text") or "")
                match = re.search(r"^\s*(\d+)[.．、)]", text)
                if match:
                    if current_start is not None and current_no is not None:
                        items.append(
                            {
                                "answer_question_no": current_no,
                                "start_block_index": current_start,
                                "end_block_index": previous_block_index,
                                "page_start": current_page_start,
                                "page_end": previous_page_idx,
                                "has_sub_questions": False,
                                "need_manual_review": False,
                                "review_reason": None,
                            }
                        )
                    current_no = match.group(1)
                    current_start = block.get("block_index")
                    current_page_start = block.get("page_idx")
                previous_block_index = block.get("block_index")
                previous_page_idx = block.get("page_idx")
            if current_start is not None and current_no is not None:
                items.append(
                    {
                        "answer_question_no": current_no,
                        "start_block_index": current_start,
                        "end_block_index": previous_block_index,
                        "page_start": current_page_start,
                        "page_end": previous_page_idx,
                        "has_sub_questions": False,
                        "need_manual_review": False,
                        "review_reason": None,
                    }
                )
            return {"items": items}
        if scenario == "analysis":
            return {
                "major_knowledge_points": ["函数与导数"],
                "minor_knowledge_points": ["导数求单调区间"],
                "solution_methods": ["分类讨论"],
                "explanation_md": "先整理题目条件，再选择合适的方法完成推导和计算。",
                "confidence": 0.82,
                "need_manual_review": False,
            }
        return {}
