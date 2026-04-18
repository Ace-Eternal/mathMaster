import io
import json
import zipfile

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import ChatSession, Paper, Question, QuestionAnswer, QuestionAnalysis, QuestionKnowledge, QuestionMethod, KnowledgePoint, ReviewRecord, SolutionMethod
from app.schemas.question import QuestionCreateRequest, QuestionUpdateRequest
from app.services.analysis import KnowledgeAnalysisService
from app.services.llm.gateway import LLMGateway
from app.services.mineu.service import MineuService
from app.services.pipeline import AnswerBoundaryItem, AnswerSliceDraft, BoundaryItem, MatchService, SliceService, normalize_pair_key
from app.services.review import ReviewService
from app.services.storage.local import LocalFileStorageService


def test_local_storage_round_trip(tmp_path):
    storage = LocalFileStorageService(base_dir=str(tmp_path))
    key = "raw/unpaired/paper/demo.pdf"
    storage.save_file(b"hello", key)
    assert storage.exists(key) is True
    assert storage.read_file(key) == b"hello"


def test_slice_service_uses_json_blocks_first():
    service = SliceService()
    slices = service.coarse_slice(
        {"blocks": [{"type": "question", "question_no": "1", "text": "求函数最值", "page": 1}]},
        "1. 求函数最值",
        "question",
    )
    assert len(slices) == 1
    assert slices[0]["candidate_no"] == "1"
    assert slices[0]["stem_text"] == "求函数最值"


def test_pair_key_normalization_matches_paper_and_answer():
    assert normalize_pair_key("数学试卷-2505高一浙江四校.pdf") == normalize_pair_key("数学答案-2505高一浙江四校.pdf")


def test_pair_key_normalization_matches_math_volume_and_answer():
    assert normalize_pair_key("paper_pdfs/数学卷-2506丽水高一期末.pdf") == normalize_pair_key(
        "ans_pdfs/数学答案-2506丽水高一期末.pdf"
    )


def test_pair_key_normalization_uses_suffix_after_first_dash():
    assert normalize_pair_key("paper_pdfs/数学试卷-校内版-2506联考.pdf") == "校内版-2506联考"


def test_mineu_mock_conversion_returns_markdown_and_json():
    service = MineuService()
    service.use_mock = True
    result = service.convert_pdf(filename="数学试卷-测试.pdf", file_bytes=b"fake", job_type="PAPER")
    assert result["markdown_bytes"]
    assert result["json_bytes"]
    assert result["asset_files"] == {}
    assert result["raw_response_bytes"]


def test_extract_zip_payload_includes_images():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("demo/full.md", "# 测试")
        archive.writestr("demo/content_list.json", '{"content_list": []}')
        archive.writestr("demo/images/question-15.png", b"png-bytes")
    markdown_bytes, json_bytes, asset_files = MineuService._extract_zip_payload(buffer.getvalue())
    assert markdown_bytes == "# 测试".encode("utf-8")
    assert json_bytes == b'{"content_list": []}'
    assert asset_files["images/question-15.png"] == b"png-bytes"


def test_normalize_document_expands_list_items_and_skips_page_numbers():
    service = SliceService()
    blocks = service.normalize_document(
        [
            {"type": "page_number", "text": "第3页 共4页", "page_idx": 2},
            {"type": "list", "list_items": ["12. 第一题", "13. 第二题"], "page_idx": 2},
        ]
    )
    assert [block.text for block in blocks] == ["12. 第一题", "13. 第二题"]
    assert all(block.block_type == "list_item" for block in blocks)


def test_normalize_document_skips_exam_preamble_list_items():
    service = SliceService()
    blocks = service.normalize_document(
        [
            {"type": "text", "text": "考生须知：", "page_idx": 0},
            {
                "type": "list",
                "list_items": [
                    "1. 本卷共4页满分150分，考试时间120分钟；",
                    "2. 答题前，在答题卷指定区域填写班级、姓名、考场号、座位号及准考证号并填涂相应数字；",
                    "3. 所有答案必须写在答题纸上，写在试卷上无效；",
                ],
                "page_idx": 0,
            },
            {"type": "text", "text": "1. 某高中三个年级共有学生1200人。", "page_idx": 0},
        ]
    )
    assert [block.text for block in blocks] == ["1. 某高中三个年级共有学生1200人。"]


def test_question_marker_hints_only_start_after_question_section():
    service = SliceService()
    blocks = service.normalize_document(
        [
            {"type": "text", "text": "2024学年第二学期高一期末联考", "page_idx": 0},
            {"type": "text", "text": "考生须知：", "page_idx": 0},
            {"type": "list", "list_items": ["1. 本卷共4页满分150分，考试时间120分钟；"], "page_idx": 0},
            {"type": "text", "text": "一、单选题：本题共8小题", "page_idx": 0},
            {"type": "text", "text": "1. 某高中三个年级共有学生1200人。", "page_idx": 0},
            {"type": "text", "text": "2. 已知向量m=(3,1)。", "page_idx": 0},
        ]
    )
    first_section = service._find_first_question_section_index(blocks)
    hints = service._collect_question_marker_hints(blocks, first_question_section_index=first_section)
    assert first_section is not None
    assert [hint["question_no"] for hint in hints] == ["1", "2"]
    assert all(hint["block_index"] >= first_section for hint in hints)


def test_build_question_slices_uses_boundaries_and_marks_duplicate_question_no():
    service = SliceService()
    document_json = [
        {"type": "text", "text": "15. 已知函数f(x)", "page_idx": 2},
        {"type": "text", "text": "求最值", "page_idx": 2},
        {"type": "text", "text": "15. 已知数列an", "page_idx": 3},
        {"type": "text", "text": "求前n项和", "page_idx": 3},
    ]
    boundaries = [
        BoundaryItem("paper-1", "15", "解答题", 0, 100, 2, 2, False, False, None),
        BoundaryItem("paper-2", "15", "解答题", 200, 300, 3, 3, False, False, None),
    ]
    drafts = service.build_question_slices(document_json=document_json, boundaries=boundaries)
    assert len(drafts) == 2
    assert drafts[0].stem_text == "15. 已知函数f(x)\n求最值"
    assert drafts[0].need_manual_review is False
    assert drafts[1].need_manual_review is True
    assert "重复题号 15" in (drafts[1].review_reason or "")


def test_build_answer_slices_preserves_page_and_image_blocks():
    service = SliceService()
    document_json = [
        {"type": "text", "text": "17.解：", "page_idx": 1},
        {"type": "image", "img_path": "images/demo.jpg", "image_caption": ["第17题图"], "bbox": [1, 2, 3, 4], "page_idx": 1},
        {"type": "text", "text": "因此结论成立", "page_idx": 1},
    ]
    boundaries = [
        AnswerBoundaryItem("answer-1", "17", 0, 200, 1, 1, True, False, None),
    ]
    drafts = service.build_answer_slices(document_json=document_json, boundaries=boundaries)
    assert len(drafts) == 1
    assert drafts[0].page_start == 1
    assert drafts[0].page_end == 1
    assert drafts[0].image_blocks[0]["src"] == "images/demo.jpg"
    assert drafts[0].has_sub_questions is True


def test_full_answer_boundary_normalization_expands_section_answers_into_per_question_items():
    gateway = LLMGateway()
    normalized = gateway._normalize_boundary_result(
        scenario="full_answer_boundary",
        result={
            "answers": {
                "single_choice": {"1": "A", "2": "D"},
                "fill_in_blank": {"12": "(1,0)"},
                "worked_solutions": {
                    "15": {
                        "score": "15分",
                        "parts": [
                            "（1）证明结论成立",
                            "（2）因此 $\\sin \\angle MCH = \\frac{\\sqrt{6}}{4}$",
                        ],
                    }
                },
            }
        },
    )
    assert [item["answer_question_no"] for item in normalized["items"]] == ["1", "2", "12", "15"]
    worked = next(item for item in normalized["items"] if item["answer_question_no"] == "15")
    assert "15分" in worked["llm_text"]
    assert "（2）因此" in worked["llm_text"]
    assert all(item["text_only_candidate"] is True for item in normalized["items"])


def test_global_answer_match_normalization_does_not_default_to_first_candidate():
    gateway = LLMGateway()
    normalized = gateway._normalize_match_result(
        scenario="global_answer_match",
        payload={
            "question_no": "18",
            "answer_candidates": [
                {"answer_candidate_id": "answer-1", "answer_question_no": "1"},
                {"answer_candidate_id": "answer-18", "answer_question_no": "18"},
            ],
        },
        result={},
    )
    assert normalized["matched_answer_candidate_id"] == ""
    assert normalized["need_manual_review"] is True
    assert normalized["match_confidence"] == 0.2


def test_match_service_prefers_same_question_number_when_llm_returns_invalid_candidate():
    class StubGateway:
        def structured_output(self, *, scenario, payload):
            assert scenario == "global_answer_match"
            return {
                "matched_answer_candidate_id": "",
                "match_confidence": 0.1,
                "need_manual_review": True,
                "review_reason": "模型未给出有效答案",
            }

    question = type(
        "QuestionDraft",
        (),
        {
            "candidate_id": "paper-18",
            "question_no": "18",
            "question_type": "解答题",
            "stem_text": "18. 求证平面垂直条件",
            "page_start": 3,
            "page_end": 3,
            "has_sub_questions": True,
            "image_blocks": [],
            "need_manual_review": False,
            "review_reason": None,
        },
    )()
    answer_candidates = [
        AnswerSliceDraft("answer-1", "1", "A", "A", {}, 1, 1, [], False, False, None),
        AnswerSliceDraft("answer-18", "18", "（1）证明...\n（2）计算...", "（1）证明...\n（2）计算...", {}, 3, 4, [], True, False, None),
    ]
    service = MatchService(StubGateway())
    result = service.refine_and_match(question_candidate=question, answer_candidates=answer_candidates)
    assert result["matched_answer_candidate_id"] == "answer-18"
    assert result["matched_answer"].answer_question_no == "18"
    assert result["need_manual_review"] is True
    assert result["match_confidence"] >= 0.65
    assert "同题号答案" in (result["review_reason"] or "")


def test_build_answer_slices_prefers_llm_text_for_text_only_candidates():
    service = SliceService()
    document_json = [
        {"type": "text", "text": "12.(1,0) 13.0.26 14. $\\frac{5}{4}$", "page_idx": 0},
        {"type": "text", "text": "四、解答题", "page_idx": 0},
        {"type": "text", "text": "13分", "page_idx": 0},
    ]
    boundaries = service._normalize_answer_boundaries(
        items=[
            {
                "answer_question_no": "12",
                "llm_text": "(1,0)",
                "text_only_candidate": True,
            },
            {
                "answer_question_no": "13",
                "llm_text": "0.26",
                "text_only_candidate": True,
            },
        ],
        blocks=service.normalize_document(document_json),
    )
    drafts = service.build_answer_slices(document_json=document_json, boundaries=boundaries)
    assert [draft.answer_question_no for draft in drafts] == ["12", "13"]
    assert drafts[0].stem_text == "(1,0)"
    assert drafts[1].stem_text == "0.26"


def test_analysis_service_creates_analysis_and_missing_dictionaries():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        paper = Paper(title="测试试卷", subject="math", paper_pdf_path="raw/paper.pdf", paper_pdf_hash="hash")
        db.add(paper)
        db.flush()
        question = Question(paper_id=paper.id, question_no="1", stem_text="已知函数f(x)=x^2，求最值。", review_status="APPROVED")
        db.add(question)
        db.flush()
        db.add(QuestionAnswer(question_id=question.id, answer_text="最小值为0", match_status="AUTO_MATCHED"))
        db.commit()

        class StubGateway:
            def structured_output(self, *, scenario, model=None, payload=None):
                assert scenario == "analysis"
                assert sorted(payload.keys()) == ["answer_text", "question_type", "stem_text", "subject"]
                return {
                    "major_knowledge_points": ["函数与导数"],
                    "minor_knowledge_points": ["二次函数最值"],
                    "solution_methods": ["配方法"],
                    "explanation_md": "先配方，再读出最值。",
                    "confidence": 0.92,
                    "need_manual_review": False,
                }

        analysis = KnowledgeAnalysisService(db, StubGateway()).analyze_question(question.id)
        assert analysis.explanation_md == "先配方，再读出最值。"
        assert db.execute(select(QuestionAnalysis)).scalar_one().question_id == question.id
        knowledge_names = [item.name for item in db.execute(select(KnowledgePoint).order_by(KnowledgePoint.level, KnowledgePoint.name)).scalars()]
        method_names = [item.name for item in db.execute(select(SolutionMethod).order_by(SolutionMethod.name)).scalars()]
        assert knowledge_names == ["函数与导数", "二次函数最值"]
        assert method_names == ["配方法"]
        assert all(item.question_id == question.id for item in db.execute(select(QuestionKnowledge)).scalars())
        assert db.execute(select(QuestionMethod)).scalar_one().question_id == question.id


def test_analysis_service_normalizes_generic_knowledge_points_and_long_method_sentences():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        paper = Paper(title="统计试卷", subject="math", paper_pdf_path="raw/paper.pdf", paper_pdf_hash="hash")
        db.add(paper)
        db.flush()
        question = Question(paper_id=paper.id, question_no="15", stem_text="根据频率分布直方图估计平均数。", review_status="APPROVED")
        db.add(question)
        db.flush()
        db.add(QuestionAnswer(question_id=question.id, answer_text="利用组中值估计平均数", match_status="AUTO_MATCHED"))
        db.commit()

        class StubGateway:
            def structured_output(self, *, scenario, model=None, payload=None):
                return {
                    "knowledge_points": ["概率与统计", "频率分布直方图", "组中值估计"],
                    "solution_methods": [
                        "根据频率分布直方图中小矩形面积等于频率，先求各组频率。",
                        "再用组中值乘对应频率估计平均数。",
                    ],
                    "confidence": 0.9,
                    "need_manual_review": False,
                }

        analysis = KnowledgeAnalysisService(db, StubGateway()).analyze_question(question.id)
        payload = json.loads(analysis.analysis_json)
        assert payload["major_knowledge_points"] == ["概率与统计"]
        assert payload["minor_knowledge_points"] == ["频率分布直方图", "组中值估计"]
        assert payload["solution_methods"] == ["频率分布直方图分析", "组中值估计"]
        assert "主要知识点" in (analysis.explanation_md or "")


def test_analysis_service_infers_knowledge_points_from_packy_solution_schema():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        paper = Paper(title="概率试卷", subject="math", paper_pdf_path="raw/paper.pdf", paper_pdf_hash="hash")
        db.add(paper)
        db.flush()
        question = Question(
            paper_id=paper.id,
            question_no="10",
            question_type="多选题",
            stem_text="甲乙两人独立射击同一个靶子，判断互斥事件、对立事件与独立事件。",
            review_status="APPROVED",
        )
        db.add(question)
        db.flush()
        db.add(QuestionAnswer(question_id=question.id, answer_text="AD", match_status="AUTO_MATCHED"))
        db.commit()

        class StubGateway:
            def structured_output(self, *, scenario, model=None, payload=None):
                return {
                    "correct_options": ["A", "D"],
                    "selected_answer": "AD",
                    "is_answer_correct": True,
                    "analysis": {
                        "reasoning": [
                            {"option": "A", "judgement": "正确", "detail": "两事件不能同时发生，因此互斥。"},
                            {"option": "C", "judgement": "错误", "detail": "利用独立事件概率公式判断。"},
                        ],
                        "conclusion": "正确选项为 A、D。",
                    },
                }

        analysis = KnowledgeAnalysisService(db, StubGateway()).analyze_question(question.id)
        payload = json.loads(analysis.analysis_json)
        assert payload["major_knowledge_points"] == ["概率与统计"]
        assert "互斥事件与对立事件" in payload["minor_knowledge_points"]
        assert "概率计算" in payload["solution_methods"]
        assert "正确选项为 A、D。" in (analysis.explanation_md or "")


def test_llm_gateway_normalizes_packy_analysis_shape():
    gateway = LLMGateway()
    normalized = gateway._normalize_structured_result(
        scenario="analysis",
        payload={"stem_text": "概率题"},
        result={
            "correct_options": ["A", "D"],
            "analysis": {
                "reasoning": [
                    {"option": "A", "judgement": "正确", "detail": "两事件不能同时发生。"},
                ],
                "conclusion": "正确选项为 A、D。",
            },
        },
    )
    assert normalized["major_knowledge_points"] == []
    assert normalized["solution_methods"] == []
    assert "正确选项为 A、D。" in normalized["explanation_md"]


def test_analysis_service_rejects_dictionary_echo_results():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        paper = Paper(title="测试卷", subject="math", paper_pdf_path="raw/paper.pdf", paper_pdf_hash="hash")
        db.add(paper)
        db.flush()
        question = Question(paper_id=paper.id, question_no="1", stem_text="求函数最值。", review_status="APPROVED")
        db.add(question)
        db.flush()
        db.add(QuestionAnswer(question_id=question.id, answer_text="最小值为0", match_status="AUTO_MATCHED"))
        db.commit()

        class StubGateway:
            def structured_output(self, *, scenario, model=None, payload=None):
                return {
                    "major_knowledge_points": ["函数与导数"],
                    "minor_knowledge_points": ["二次函数最值", "导数求单调区间", "导数求极值", "导数求最值", "分类讨论"],
                    "solution_methods": ["分类讨论", "导数分析", "换元法", "数形结合", "待定系数法"],
                    "explanation_md": "这是一次异常回显。",
                    "confidence": 0.8,
                    "need_manual_review": False,
                }

        try:
            KnowledgeAnalysisService(db, StubGateway()).analyze_question(question.id)
        except ValueError as exc:
            assert "回显输入词典" in str(exc) or "异常多的解法标签" in str(exc)
        else:
            raise AssertionError("应当拒绝异常宽泛的分析结果")


def test_llm_gateway_only_uses_mock_when_explicitly_enabled():
    from app.core.config import settings

    original_use_mock = settings.llm_use_mock
    original_base_url = settings.llm_base_url
    original_api_key = settings.llm_api_key
    try:
        settings.llm_use_mock = False
        settings.llm_base_url = None
        settings.llm_api_key = None
        gateway = LLMGateway()
        assert gateway.use_mock is False
        try:
            gateway.structured_output(scenario="analysis", payload={"stem_text": "题干"})
        except RuntimeError as exc:
            assert "未正确配置" in str(exc)
        else:
            raise AssertionError("未配置 LLM 时不应自动回退到 mock")
    finally:
        settings.llm_use_mock = original_use_mock
        settings.llm_base_url = original_base_url
        settings.llm_api_key = original_api_key


def test_review_service_build_question_detail_response_handles_analysis_links(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    storage = LocalFileStorageService(base_dir=str(tmp_path))
    with Session(engine) as db:
        paper = Paper(title="测试卷", subject="math", paper_pdf_path="raw/paper.pdf", paper_pdf_hash="hash")
        db.add(paper)
        db.flush()
        question = Question(paper_id=paper.id, question_no="36", stem_text="题干", review_status="PENDING")
        db.add(question)
        db.flush()
        analysis = QuestionAnalysis(question_id=question.id, analysis_json='{"ok":true}', explanation_md="讲解")
        kp = KnowledgePoint(name="函数与导数", level=1, subject="math", sort_no=1)
        method = SolutionMethod(name="分类讨论", subject="math")
        db.add_all([analysis, kp, method])
        db.flush()
        db.add(QuestionKnowledge(question_id=question.id, knowledge_point_id=kp.id, source_type="AUTO"))
        db.add(QuestionMethod(question_id=question.id, solution_method_id=method.id, source_type="AUTO"))
        db.commit()

        payload = ReviewService(db, storage).build_question_detail_response(question.id)
        assert payload.id == question.id
        assert payload.knowledges[0].name == "函数与导数"
        assert payload.methods[0].name == "分类讨论"
        assert payload.analysis.explanation_md == "讲解"


def test_review_service_create_update_delete_question_syncs_slice_files_and_relations(tmp_path):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    storage = LocalFileStorageService(base_dir=str(tmp_path))
    with Session(engine) as db:
        paper = Paper(title="测试卷", subject="math", paper_pdf_path="raw/paper.pdf", paper_pdf_hash="hash")
        db.add(paper)
        db.commit()
        service = ReviewService(db, storage)

        created = service.create_question(
            paper.id,
            QuestionCreateRequest(
                question_no="12",
                question_type="填空题",
                stem_text="12. 这是新增题目",
                answer_text="新增答案",
                page_start=2,
                page_end=2,
            ),
        )
        assert storage.exists(created.question_md_path)
        assert storage.exists(created.question_json_path)
        assert created.answer is not None
        assert storage.exists(created.answer.answer_md_path)

        original_question_path = created.question_md_path
        updated = service.patch_question(
            paper.id,
            created.id,
            QuestionUpdateRequest(
                question_no="13",
                question_type="解答题",
                stem_text="13. 修改后的题干",
                answer_text="修改后的答案",
                page_start=3,
                page_end=4,
                review_note="人工调整",
            ),
        )
        assert updated.question_no == "13"
        assert updated.question_type == "解答题"
        assert updated.answer.answer_text == "修改后的答案"
        assert updated.question_md_path != original_question_path
        assert storage.exists(updated.question_md_path)
        assert not storage.exists(original_question_path)

        analysis = QuestionAnalysis(question_id=updated.id, analysis_json="{}", explanation_md="分析")
        db.add(analysis)
        db.flush()
        kp = KnowledgePoint(name="空间几何", level=1, subject="math", sort_no=1)
        method = SolutionMethod(name="空间向量法", subject="math")
        db.add_all([kp, method])
        db.flush()
        db.add(QuestionKnowledge(question_id=updated.id, knowledge_point_id=kp.id, source_type="AUTO"))
        db.add(QuestionMethod(question_id=updated.id, solution_method_id=method.id, source_type="AUTO"))
        db.add(ReviewRecord(paper_id=paper.id, question_id=updated.id, review_type="SLICE_EDIT"))
        db.flush()
        chat = ChatSession(question_id=updated.id, title="问答")
        db.add(chat)
        db.commit()

        question_id = updated.id
        answer_md_path = updated.answer.answer_md_path
        service.delete_question(paper.id, question_id)

        assert db.get(Question, question_id) is None
        assert db.execute(select(QuestionAnswer).where(QuestionAnswer.question_id == question_id)).scalar_one_or_none() is None
        assert db.execute(select(QuestionAnalysis).where(QuestionAnalysis.question_id == question_id)).scalar_one_or_none() is None
        assert db.execute(select(QuestionKnowledge).where(QuestionKnowledge.question_id == question_id)).scalar_one_or_none() is None
        assert db.execute(select(QuestionMethod).where(QuestionMethod.question_id == question_id)).scalar_one_or_none() is None
        assert db.execute(select(ChatSession).where(ChatSession.question_id == question_id)).scalar_one_or_none() is None
        review_records = list(db.execute(select(ReviewRecord)).scalars())
        assert any(record.question_id is None for record in review_records)
        assert not storage.exists(answer_md_path)
