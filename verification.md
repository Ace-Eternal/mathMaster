# Verification

- 日期：2026-04-24 14:24:54 +08:00
- 执行者：Codex

## 已验证

- 后端完整测试：`uv run pytest`，44 passed。
- 旧 SQLite schema 回归测试：覆盖 `paper`、`knowledge_point`、`solution_method` 的遗留 `subject` 列清理。
- 当前本地数据库：已执行 `init_db()`，`paper` 表 schema 中不再有 `subject`。

## 故障结论

文件夹批量导入的 network error 不是前端目录选择或网络连通性问题，而是旧 SQLite 表结构与当前模型不一致导致服务端插入失败。

## 2026-04-24 15:02:53 +08:00 - 运行按钮与自动刷新验证

- 执行者：Codex
- 前端构建：`cd frontend; npm run build`，通过。
- 后端测试：`cd backend; uv run pytest`，44 passed。
- 接口验证：`POST /api/papers/29/pipeline/run-all` 在 0.58 秒返回，不再阻塞页面等待长流水线。
- 状态验证：`数学卷-2506宁波三峰高一期末` 后台任务继续推进，接口状态刷新到 `BOUNDARY_RUNNING`。
- 日志验证：后端重启后未出现新的 `database is locked` 异常。

## 2026-04-24 15:15:44 +08:00 - Prompt 收紧验证

- 执行者：Codex
- 已收紧 `slice_prompt.md`，明确匹配场景只能输出 `matched_answer_candidate_id`、`match_confidence`、`need_manual_review`、`review_reason` 四个字段，并禁止 `answer_candidate_id`、`is_match` 等别名字段。
- 已收紧试卷/答案边界 prompt，禁止 `sections`、`questions`、`answers`、`boundaries` 等替代结构。
- 新增 prompt 合约测试，防止关键约束被回退。
- 后端完整测试：`uv run pytest`，45 passed。

## 2026-04-24 15:31:41 +08:00 - 待审归零状态同步验证

- 执行者：Codex
- 根因：后端 `paper.status` 保留 `REVIEW_PENDING`，但 `pending_review_count` 已经为 0，前端按后端状态显示为“待人工审核”。
- 修复：前端派生状态兼容 `REVIEW_PENDING + pending_review_count=0` 为“已完成”；后端在列表读取和审核写操作后同步 `paper.status`。
- 后端测试：`uv run pytest`，46 passed。
- 前端构建：`npm run build`，通过。
- 接口验证：`数学卷-2506丽水高一期末` 与 `数学卷-2506宁波三峰高一期末` 均返回 `SLICED / pending_review_count=0`。
