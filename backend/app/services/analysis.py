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
        result = self.llm_gateway.structured_output(
            scenario="analysis",
            model=settings.default_model_analysis,
            payload={
                "stem_text": question.stem_text,
                "answer_text": question.answer.answer_text if question.answer else None,
                "question_type": question.question_type,
                "subject": question.paper.subject if question.paper else "math",
            },
        )
        result = self._normalize_analysis_result(result=result, question=question)
        self._validate_analysis_result(result=result, question=question)
        stored_result = self._sanitize_analysis_result(result)

        analysis = question.analysis or QuestionAnalysis(question_id=question.id, analysis_json="{}")
        analysis.analysis_json = json.dumps(stored_result, ensure_ascii=False)
        analysis.explanation_md = stored_result.get("explanation_md")
        analysis.model_name = settings.default_model_analysis
        analysis.review_status = "PENDING" if stored_result.get("need_manual_review") else "APPROVED"
        self.db.add(analysis)
        self.db.flush()

        self.db.query(QuestionKnowledge).filter(QuestionKnowledge.question_id == question.id).delete()
        self.db.query(QuestionMethod).filter(QuestionMethod.question_id == question.id).delete()

        for name in stored_result.get("major_knowledge_points", []):
            kp = self._get_or_create_knowledge_point(name=name, level=1, subject=question.paper.subject if question.paper else "math")
            self.db.add(QuestionKnowledge(question_id=question.id, knowledge_point_id=kp.id, source_type="AUTO"))
        for name in stored_result.get("minor_knowledge_points", []):
            kp = self._get_or_create_knowledge_point(name=name, level=2, subject=question.paper.subject if question.paper else "math")
            self.db.add(QuestionKnowledge(question_id=question.id, knowledge_point_id=kp.id, source_type="AUTO"))
        for name in stored_result.get("solution_methods", []):
            method = self._get_or_create_solution_method(name=name, subject=question.paper.subject if question.paper else "math")
            self.db.add(QuestionMethod(question_id=question.id, solution_method_id=method.id, source_type="AUTO"))

        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    @staticmethod
    def _sanitize_analysis_result(result: dict) -> dict:
        return {key: value for key, value in result.items() if not str(key).startswith("_")}

    def _normalize_analysis_result(self, *, result: dict, question: Question) -> dict:
        normalized = dict(result)
        major_points = self._normalize_string_list(normalized.get("major_knowledge_points"))
        minor_points = self._normalize_string_list(normalized.get("minor_knowledge_points"))
        if not major_points and not minor_points:
            generic_points = self._normalize_string_list(normalized.get("knowledge_points"))
            if generic_points:
                major_points = generic_points[:1]
                minor_points = generic_points[1:]
        inferred_major, inferred_minor, inferred_methods = self._infer_from_question(question=question, result=normalized)
        if not major_points and inferred_major:
            major_points = inferred_major
        if not minor_points and inferred_minor:
            minor_points = inferred_minor
        solution_methods = self._normalize_solution_methods(normalized.get("solution_methods"))
        if not solution_methods and inferred_methods:
            solution_methods = inferred_methods
        explanation_md = str(normalized.get("explanation_md") or "").strip()
        if not explanation_md:
            explanation_md = self._build_explanation_from_packy_result(normalized)
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
    def _build_explanation_from_packy_result(result: dict) -> str:
        analysis = result.get("analysis") if isinstance(result.get("analysis"), dict) else {}
        reasoning = analysis.get("reasoning") if isinstance(analysis.get("reasoning"), list) else []
        parts: list[str] = []
        for item in reasoning[:4]:
            if not isinstance(item, dict):
                continue
            option = str(item.get("option") or "").strip()
            judgement = str(item.get("judgement") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if not detail:
                continue
            prefix = f"{option}：{judgement}。" if option and judgement else ""
            parts.append(f"{prefix}{detail}".strip())
        conclusion = str(analysis.get("conclusion") or result.get("conclusion") or "").strip()
        if conclusion:
            parts.append(conclusion)
        return "\n\n".join(part for part in parts if part).strip()

    def _infer_from_question(self, *, question: Question, result: dict) -> tuple[list[str], list[str], list[str]]:
        stem_text = str(question.stem_text or "")
        answer_text = str(question.answer.answer_text if question.answer else "")
        combined = "\n".join(
            part for part in [
                stem_text,
                answer_text,
                str(result.get("explanation_md") or ""),
                json.dumps(result.get("analysis") or {}, ensure_ascii=False),
            ] if part
        )
        major_points: list[str] = []
        minor_points: list[str] = []
        methods: list[str] = []

        def add_major(name: str) -> None:
            if name and name not in major_points:
                major_points.append(name)

        def add_minor(name: str) -> None:
            if name and name not in minor_points:
                minor_points.append(name)

        def add_method(name: str) -> None:
            if name and name not in methods:
                methods.append(name)

        if any(keyword in combined for keyword in ("概率", "互斥", "对立事件", "独立", "至少1人", "无人击中")):
            add_major("概率与统计")
            add_minor("互斥事件与对立事件")
            add_minor("独立事件概率")
            add_method("概率计算")
        if any(keyword in combined for keyword in ("频率分布直方图", "组中值", "百分位数", "众数")):
            add_major("概率与统计")
            add_minor("频率分布直方图")
            if "组中值" in combined:
                add_minor("组中值估计")
            add_method("频率分布直方图分析")
        if any(keyword in combined for keyword in ("向量", "投影向量", "平行", "垂直", "坐标")):
            add_major("平面向量")
            if "平行" in combined:
                add_minor("向量平行的坐标表示")
            if "投影" in combined:
                add_minor("向量投影")
            add_method("向量运算")
        if any(keyword in combined for keyword in ("复数", "共轭复数", "复平面")):
            add_major("复数")
            add_minor("复数的乘法运算")
            add_method("复数运算")
        if any(keyword in combined for keyword in ("余弦定理", "正弦定理", "三角形", "sin", "cos", "tan", "角")):
            add_major("三角函数与解三角形")
            if "余弦定理" in combined:
                add_minor("余弦定理")
            if "tan" in combined or "正切" in combined:
                add_minor("同角三角函数基本关系")
            add_method("三角变换")
        if any(keyword in combined for keyword in ("正方体", "平面", "直线", "二面角", "立体几何", "空间")):
            add_major("立体几何")
            add_minor("线面位置关系")
            add_method("空间几何推理")
        if not major_points:
            add_major("高中数学综合")
        return major_points[:3], minor_points[:5], methods[:3]

    def _validate_analysis_result(self, *, result: dict, question: Question) -> None:
        major_points = self._normalize_string_list(result.get("major_knowledge_points"))
        minor_points = self._normalize_string_list(result.get("minor_knowledge_points"))
        methods = self._normalize_solution_methods(result.get("solution_methods"))
        if not major_points and not minor_points:
            raise ValueError(f"题目 {question.id} 的分析结果缺少知识点，拒绝落库。")
        if len(major_points) + len(minor_points) > 6:
            raise ValueError(f"题目 {question.id} 的分析结果疑似回显输入词典，拒绝落库。")
        if len(methods) > 4:
            raise ValueError(f"题目 {question.id} 的分析结果包含异常多的解法标签，拒绝落库。")
        explanation_md = str(result.get("explanation_md") or "").strip()
        if not explanation_md:
            raise ValueError(f"题目 {question.id} 的分析结果缺少 explanation_md，拒绝落库。")

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
