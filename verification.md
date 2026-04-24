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

## 2026-04-24 16:05:00 +08:00 - 本地单 Worker 持久化队列验证

- 执行者：Codex
- 后端测试：`cd backend; uv run pytest`，54 passed。
- 前端构建：`cd frontend; npm run build`，通过。
- 已覆盖：入队、重复入队去重、按顺序 claim、成功/失败标记、启动恢复、单试卷 API、批量 API、队列位置 API。
- 构建提示：Vite chunk size warning 与 npmrc 配置提示仍为既有提示，不影响本次验证。

## 2026-04-24 16:18:00 +08:00 - 待运行任务删除按钮验证

- 执行者：Codex
- 前端构建：`cd frontend; npm run build`，通过。
- 修复：任务状态列表中 `待运行` 且非临时任务新增“删除任务”按钮，确认后调用 `DELETE /api/papers/{paper_id}` 删除并刷新列表。

## 2026-04-24 16:40:00 +08:00 - 试卷硬删除与存储清理验证

- 执行者：Codex
- 后端测试：`cd backend; uv run pytest`，55 passed。
- 前端构建：`cd frontend; npm run build`，通过。
- 修复：`DELETE /api/papers/{paper_id}` 改为硬删除，清理试卷 PDF、答案 PDF、`mineu/{paper_id}`、`slices/{paper_id}` 以及题目、答案、审核、聊天、队列等关联记录。
- 约束：试卷流水线处于 `RUNNING` 时拒绝删除，避免 worker 正在读写同一试卷。

## 2026-04-24 16:50:00 +08:00 - 删除确认与管理页筛选清理验证

- 执行者：Codex
- 前端构建：`cd frontend; npm run build`，通过。
- 修复：确认 `/papers` 待运行任务删除与 `/paper-management` 试卷删除均有二次确认。
- 修复：移除 `/paper-management` 筛选区中的“已删除”开关，并清理硬删除后不再可用的恢复按钮逻辑。

## 2026-04-24 17:02:00 +08:00 - 试卷管理列表横向压缩验证

- 执行者：Codex
- 前端构建：`cd frontend; npm run build`，通过。
- 修复：`/paper-management` 表格从多列横向展开改为 4 列纵向信息堆叠，合并年份、地区、年级、学期、答案和待审信息，减少用户横向滚动需求。

## 2026-04-24 17:18:00 +08:00 - 本地试卷存储清理验证

- 执行者：Codex
- 数据库清理：硬删除除 `paper_id=28`、`paper_id=29` 之外的历史试卷记录 27 条。
- 文件清理：通过项目硬删除服务删除历史试卷关联文件 320 个；额外删除孤儿 PDF 2 个，合计额外释放 2,629,744 bytes。
- 数据库压缩：执行 `PRAGMA wal_checkpoint(TRUNCATE)` 与 `VACUUM`，`mathmaster.db` 从 503,808 bytes 降到 299,008 bytes，WAL 清空为 0 bytes。
- 复核：`/api/papers/manage` 返回 2 条：`数学卷-2506丽水高一期末` 与 `数学卷-2506宁波三峰高一期末`。
- 复核：`data/raw` 仅剩 2 份试卷 PDF 和 2 份答案 PDF；`data/mineu` 仅剩 `28`、`29`；`data/slices` 仅剩 `28`、`29`。
