from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import KnowledgePoint, Question, QuestionAnalysis, QuestionKnowledge, QuestionMethod, SolutionMethod
from app.services.llm.gateway import LLMGateway


class KnowledgeAnalysisService:
    def __init__(self, db: Session, llm_gateway: LLMGateway) -> None:
        self.db = db
        self.llm_gateway = llm_gateway

    def analyze_question(self, question_id: int) -> QuestionAnalysis:
        question = self.db.execute(
            select(Question).options(selectinload(Question.answer), selectinload(Question.paper)).where(Question.id == question_id)
        ).scalar_one()
        kp_tree = list(self.db.execute(select(KnowledgePoint).order_by(KnowledgePoint.level, KnowledgePoint.sort_no)).scalars())
        methods = list(self.db.execute(select(SolutionMethod).order_by(SolutionMethod.name)).scalars())
        result = self.llm_gateway.structured_output(
            scenario="analysis",
            model=settings.default_model_analysis,
            payload={
                "stem_text": question.stem_text,
                "answer_text": question.answer.answer_text if question.answer else None,
                "knowledge_points": [{"id": kp.id, "name": kp.name, "level": kp.level} for kp in kp_tree],
                "solution_methods": [{"id": method.id, "name": method.name} for method in methods],
            },
        )
        result = self._normalize_analysis_result(result=result)

        analysis = question.analysis or QuestionAnalysis(question_id=question.id, analysis_json="{}")
        analysis.analysis_json = json.dumps(result, ensure_ascii=False)
        analysis.explanation_md = result.get("explanation_md")
        analysis.model_name = settings.default_model_analysis
        analysis.review_status = "PENDING" if result.get("need_manual_review") else "APPROVED"
        self.db.add(analysis)
        self.db.flush()

        self.db.query(QuestionKnowledge).filter(QuestionKnowledge.question_id == question.id).delete()
        self.db.query(QuestionMethod).filter(QuestionMethod.question_id == question.id).delete()

        for name in result.get("major_knowledge_points", []):
            kp = self._get_or_create_knowledge_point(name=name, level=1, subject=question.paper.subject if question.paper else "math")
            self.db.add(QuestionKnowledge(question_id=question.id, knowledge_point_id=kp.id, source_type="AUTO"))
        for name in result.get("minor_knowledge_points", []):
            kp = self._get_or_create_knowledge_point(name=name, level=2, subject=question.paper.subject if question.paper else "math")
            self.db.add(QuestionKnowledge(question_id=question.id, knowledge_point_id=kp.id, source_type="AUTO"))
        for name in result.get("solution_methods", []):
            method = self._get_or_create_solution_method(name=name, subject=question.paper.subject if question.paper else "math")
            self.db.add(QuestionMethod(question_id=question.id, solution_method_id=method.id, source_type="AUTO"))

        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def _normalize_analysis_result(self, *, result: dict) -> dict:
        normalized = dict(result)
        major_points = self._normalize_string_list(normalized.get("major_knowledge_points"))
        minor_points = self._normalize_string_list(normalized.get("minor_knowledge_points"))
        if not major_points and not minor_points:
            generic_points = self._normalize_string_list(normalized.get("knowledge_points"))
            if generic_points:
                major_points = generic_points[:1]
                minor_points = generic_points[1:]
        solution_methods = self._normalize_solution_methods(normalized.get("solution_methods"))
        explanation_md = str(normalized.get("explanation_md") or "").strip()
        if not explanation_md:
            explanation_md = self._build_explanation_md(major_points=major_points, minor_points=minor_points, solution_methods=solution_methods)
        normalized["major_knowledge_points"] = major_points
        normalized["minor_knowledge_points"] = minor_points
        normalized["solution_methods"] = solution_methods
        normalized["explanation_md"] = explanation_md
        normalized["confidence"] = self._normalize_confidence(normalized.get("confidence"))
        normalized["need_manual_review"] = bool(normalized.get("need_manual_review"))
        return normalized

    @staticmethod
    def _normalize_string_list(value: object) -> list[str]:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, list):
            candidates = []
            for item in value:
                if isinstance(item, dict):
                    candidate = item.get("name") or item.get("label") or item.get("title") or ""
                else:
                    candidate = item
                candidates.append(str(candidate))
        else:
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            name = str(item or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cleaned.append(name)
        return cleaned

    def _normalize_solution_methods(self, value: object) -> list[str]:
        methods = self._normalize_string_list(value)
        normalized: list[str] = []
        seen: set[str] = set()
        for item in methods:
            simplified = self._simplify_solution_method(item)
            if not simplified or simplified in seen:
                continue
            seen.add(simplified)
            normalized.append(simplified)
        return normalized

    @staticmethod
    def _simplify_solution_method(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        heuristic_map = [
            ("分类讨论", "分类讨论"),
            ("数形结合", "数形结合"),
            ("配方法", "配方法"),
            ("待定系数", "待定系数法"),
            ("换元", "换元法"),
            ("函数单调", "函数单调性分析"),
            ("导数", "导数分析"),
            ("频率分布直方图", "频率分布直方图分析"),
            ("组中值", "组中值估计"),
            ("线性插值", "线性插值"),
            ("累计频率", "累计频率分析"),
            ("概率", "概率计算"),
            ("向量", "向量运算"),
            ("三角", "三角变换"),
            ("立体几何", "立体几何推理"),
            ("空间向量", "空间向量法"),
        ]
        for keyword, label in heuristic_map:
            if keyword in text:
                return label
        trimmed = text.replace("。", "").replace("；", "，").split("，")[0].strip()
        return trimmed[:24]

    @staticmethod
    def _build_explanation_md(*, major_points: list[str], minor_points: list[str], solution_methods: list[str]) -> str:
        sections: list[str] = []
        if major_points:
            sections.append("主要知识点：" + "、".join(major_points))
        if minor_points:
            sections.append("次级知识点：" + "、".join(minor_points))
        if solution_methods:
            sections.append("推荐解法：" + "、".join(solution_methods))
        return "\n\n".join(sections)

    @staticmethod
    def _normalize_confidence(value: object) -> float:
        try:
            if value is None or value == "":
                return 0.75
            confidence = float(value)
            return max(0.0, min(confidence, 1.0))
        except (TypeError, ValueError):
            return 0.75

    def _get_or_create_knowledge_point(self, *, name: str, level: int, subject: str) -> KnowledgePoint:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("知识点名称不能为空")
        existing = self.db.execute(select(KnowledgePoint).where(KnowledgePoint.name == normalized_name)).scalar_one_or_none()
        if existing is not None:
            if existing.level != level and level < existing.level:
                existing.level = level
            if not existing.subject:
                existing.subject = subject
            return existing
        sort_no = self.db.execute(select(KnowledgePoint).where(KnowledgePoint.level == level).order_by(KnowledgePoint.sort_no.desc())).scalars().first()
        next_sort = (sort_no.sort_no + 1) if sort_no else 1
        knowledge_point = KnowledgePoint(name=normalized_name, level=level, subject=subject, sort_no=next_sort)
        self.db.add(knowledge_point)
        self.db.flush()
        return knowledge_point

    def _get_or_create_solution_method(self, *, name: str, subject: str) -> SolutionMethod:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("解法名称不能为空")
        existing = self.db.execute(select(SolutionMethod).where(SolutionMethod.name == normalized_name)).scalar_one_or_none()
        if existing is not None:
            if not existing.subject:
                existing.subject = subject
            return existing
        method = SolutionMethod(name=normalized_name, subject=subject)
        self.db.add(method)
        self.db.flush()
        return method
