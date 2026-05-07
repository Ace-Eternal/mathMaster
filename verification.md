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

## 2026-05-07 - 讲题对话隔离与随机刷题复用验证

- 执行者：Codex
- 修复：题目详情页讲题面板抽成公共组件，随机刷题页复用同一套历史会话、流式输出、模型选择、停止生成、新对话和删除/清空历史能力。
- 修复：讲题模型列表与停止生成接口增加 `chat.use` 权限；generation 注册当前用户，取消时校验归属。
- 修复：跨用户继续发送他人会话时返回 404，不再暴露为服务端错误。
- 后端测试：`cd backend; uv run --python 3.12.12 pytest`，69 passed。
- 前端构建：`cd frontend; npm run build`，通过；保留既有 Vite 大 chunk 警告。
- 环境说明：`uv run pytest` 因本机未找到项目声明的 Python 3.12.13 未启动测试，已使用本机可用的 Python 3.12.12 完整验证。
- 文件清理：通过项目硬删除服务删除历史试卷关联文件 320 个；额外删除孤儿 PDF 2 个，合计额外释放 2,629,744 bytes。
- 数据库压缩：执行 `PRAGMA wal_checkpoint(TRUNCATE)` 与 `VACUUM`，`mathmaster.db` 从 503,808 bytes 降到 299,008 bytes，WAL 清空为 0 bytes。
- 复核：`/api/papers/manage` 返回 2 条：`数学卷-2506丽水高一期末` 与 `数学卷-2506宁波三峰高一期末`。
- 复核：`data/raw` 仅剩 2 份试卷 PDF 和 2 份答案 PDF；`data/mineu` 仅剩 `28`、`29`；`data/slices` 仅剩 `28`、`29`。

## 2026-04-24 17:36:00 +08:00 - 文件夹导入配对归一化验证

- 执行者：Codex
- 根因：`normalize_pair_key()` 只按短横线 `-` 截取后缀，未处理下划线 `_` 和 `数学卷` / `数学答案` 前缀，导致 `数学卷_2504高一山海协作体` 与 `数学答案_2504高一山海协作体` 被归为不同 key。
- 修复：先统一 `_`、破折号和空格，再剥离 `数学卷`、`数学试卷`、`数学答案`、`答案` 等前缀。
- 后端测试：`cd backend; uv run pytest`，56 passed。

## 2026-04-24 19:06:00 +08:00 - 审核页答案完整性与渲染验证

- 执行者：Codex
- 根因：答案边界归一化遇到 PackyAPI `answers` 结构时会生成 `text_only_candidate`，原实现优先使用 LLM 摘要文本，导致可从 MineU 原始块定位的解答题也只保留结论摘要。
- 修复：`text_only_candidate` 先尝试按题号回到原答案 OCR 块；仅当命中的是多题同块摘要或分值块时才使用 LLM 文本。
- 根因：审核状态维护会把结构完整、可自动通过的题目 `match_confidence` 统一抬到 `0.93`；同题号自动兜底匹配也会抬到同一值。
- 修复：自动通过不再改写历史匹配置信度；同题号兜底使用较低的确定性兜底分，避免整队列显示同一个 0.93。
- 前端修复：`/review` 移除“包含已删除”，筛选按钮与下拉框底部对齐；答案 Markdown 渲染会把裸 TeX 关系符号转换为可读数学符号。
- 数据修复：已从 `data/mineu/28/answer.*` 恢复 `/review/109` 的完整第 17 题答案到 `data/slices/28/q_017/answer.*` 与本地 SQLite。
- 验证：后端完整测试 `uv run pytest`，57 passed；前端构建 `npm run build`，通过。

## 2026-04-24 19:24:00 +08:00 - 答案边界严格契约验证

- 执行者：Codex
- 修复：`full_answer_boundary` 不再接受 `answers`、`boundaries` 等替代结构；必须返回 `items` 数组。
- 修复：`full_answer_boundary.items[*]` 必须严格包含 `answer_question_no`、`start_block_index`、`end_block_index`、`page_start`、`page_end`、`has_sub_questions`、`need_manual_review`、`review_reason` 这 8 个字段，且起止 block 不能为空。
- 行为：主模型若返回旧的 `answers` map 或缺少 block 边界，归一化阶段抛出错误，外层结构化调用会按现有机制尝试备用模型；备用模型仍不合规则答案边界识别失败，不再静默落库摘要答案。
- 验证：针对性测试 `uv run pytest tests/test_storage_and_slice.py -k "full_answer_boundary_normalization"`，2 passed；后端完整测试 `uv run pytest`，58 passed。

## 2026-04-24 19:42:00 +08:00 - Markdown 数学规范化加固验证

- 执行者：Codex
- 修复：Markdown 数学规范化支持行内/块级 `\[...\]`、全角 `＄...＄`、裸 `\frac`、`\sqrt`、`\sin \angle ...` 等常见 OCR/LLM 输出。
- 修复：非数学片段中常见 TeX 关系符号转为可读符号，包括平行、垂直、集合包含/不包含、交并、大小比较、无穷、角、三角形、因此/因为等。
- 修复：处理 OCR 常见的 `/ /` 与 `//` 平行符号。
- 验证：新增 `npm run check:markdown-math`，覆盖 6 个常见失败输入；前端构建 `npm run build` 通过。

## 2026-04-24 19:55:00 +08:00 - JSON 答案 Map 渲染验证

- 执行者：Codex
- 根因：`/review/88` 的答案文本是 JSON 对象字符串，例如 `{"1":"...","2":"..."}`，原 Markdown 渲染器会把它当普通文本处理，后续裸 TeX 包装还会把整段弄乱。
- 修复：`normalizeMathContent()` 在数学规范化前识别纯 JSON answer map，转成 `1. ...`、`2. ...` 的可读 Markdown；当值主要是 TeX 数学表达式时整段包为 inline math。
- 验证：`npm run check:markdown-math` 扩展到 7 个用例并通过；`npm run build` 通过。

## 2026-04-24 20:08:00 +08:00 - 答案文本入库规范化验证

- 执行者：Codex
- 根因：前端预览层规范化只能修“当前答案渲染效果”，但“答案原始文本”来自数据库 `question_answer.answer_text`，历史和未来入库若保存 JSON map 仍会原样显示。
- 修复：新增后端 `normalize_answer_text_for_markdown()`，在流水线自动匹配落库、人工新增/编辑答案时，将纯 JSON answer map 转为编号 Markdown。
- 数据修复：已迁移 `/review/88` 当前本地记录，`question_answer.answer_text`、`data/slices/29/q_015/answer.md`、`answer.json.merged_text/llm_text` 均为 Markdown。
- 验证：`/api/questions/88` 返回 Markdown 答案文本；后端完整测试 `uv run pytest`，59 passed；前端 `npm run check:markdown-math` 与 `npm run build` 通过。

## 2026-04-24 20:22:00 +08:00 - 前端预览兜底撤回验证

- 执行者：Codex
- 撤回：删除前端 `markdownMath.ts`、`check-markdown-math.mjs` 和 `check:markdown-math` 脚本，`MarkdownContent.vue` 恢复为组件内基础 KaTeX 分隔符规范化。
- 保留：后端 `normalize_answer_text_for_markdown()` 入库规范化仍保留，确保 `/review/88` 这类 JSON answer map 不再进入数据库原始答案文本。
- 验证：前端构建 `npm run build` 通过；后端完整测试 `uv run pytest`，59 passed。

## 2026-04-24 21:35:00 +08:00 - 答案边界本地兜底验证

- 执行者：Codex
- 根因：`full_answer_boundary` 只通过 `response_format=json_object` 约束模型，模型仍可能返回 `answers`、`sections`、`title` 等旧式 JSON 对象；严格校验拒绝后，`detect_answer_boundaries()` 没有回退到本地答案 block 标记。
- 修复：`SliceService.detect_answer_boundaries()` 在 LLM 失败或无有效边界时使用 MineU 归一化 block 本地兜底；表格答案按 `题号/答案` 行展开为逐题候选，解答题按显式题号行切分。
- 修复：答案兜底使用更严格的题号起点识别，排除 `3分`、`7分`、`10分` 等评分行被误判为题号。
- 真实数据验证：`data/mineu/30/answer.json` 本地兜底识别 23 个答案边界；`data/mineu/31/answer.json` 本地兜底识别 19 个答案边界。
- 测试：针对性测试 `uv run pytest tests/test_storage_and_slice.py -k "answer_boundary_detection_falls_back"`，1 passed；后端完整测试 `uv run pytest`，60 passed。

## 2026-04-24 22:05:00 +08:00 - Markdown 数学溢出布局验证

- 执行者：Codex
- 根因：`MarkdownContent` 只对 `pre` 和 `.katex-display` 设置横向滚动，普通段落内的 inline KaTeX 长公式仍会形成不可断行内容，导致 `/review/174` 这类长答案行视觉上越过答案卡片并压到右侧 PDF 区域。
- 修复：在通用 `MarkdownContent` 内约束 Markdown 根容器、段落、列表、代码块、表格、inline/display KaTeX 的最大宽度；长公式和表格在各自块内横向滚动，不再撑破调用页面的栅格。
- 覆盖范围：该修复作用于所有复用 `MarkdownContent` 的页面，包括 `/review`、题目详情页、题库搜索结果和模板预览，不针对单个题号硬编码。
- 验证：新增 `npm run check:markdown-layout`，先在旧样式下失败，修复后通过；前端构建 `npm run build` 通过。构建仍保留既有 Vite chunk size warning 与 npmrc 提示。

## 2026-04-25 10:20:00 +08:00 - 审核页双栏容器溢出加固验证

- 执行者：Codex
- 根因：上一轮只约束了 `MarkdownContent`，但 `/review/174` 的新截图显示浅蓝提示块、三列表单和 textarea 等审核页顶层容器本身也会在双栏布局中撑出左侧面板。
- 修复：`ReviewPage.vue` 为审核页 grid、左右 panel、编辑表单、Element Plus 输入/选择/textarea wrapper、三列 meta grid、编辑块、预览块和提示块补齐 `min-width: 0`、`max-width: 100%`、局部 overflow 约束。
- 修正：按用户反馈恢复原审核页双栏比例，单栏断点撤回到 `1280px`；仅为题干/答案两个原始文本 textarea 添加自身横向滚动，审核备注等普通 textarea 不受影响。
- 验证：扩展 `npm run check:markdown-layout` 覆盖 `ReviewPage.vue` 容器约束与 `raw-textarea` 横滚约束，旧样式下失败，修复后通过；`npm run build` 通过。浏览器 DOM 访问 `http://localhost:5173/review/174` 可读取页面内容；截图接口返回 0 width 或 CDP 超时，未作为最终证据。

## 2026-04-25 10:34:00 +08:00 - 答案整框横向滚动验证

- 执行者：Codex
- 根因：答案渲染区仍沿用通用 `MarkdownContent` 的段落/KaTeX 局部横滚策略，导致长公式只在公式所在行出现滚动条，而不是整个“当前答案渲染效果”框统一横向滚动。
- 修复：`ReviewPage.vue` 为题干/答案原始文本表单项和题目/答案渲染预览框增加专用类；题目与答案渲染预览框接管横向滚动，内部 Markdown 段落、列表、代码块、表格、KaTeX display 公式展开为同一滚动面。
- 验证：`npm run check:markdown-layout` 通过；`npm run build` 通过。构建仍保留既有 Vite chunk size warning 与 npmrc 提示。

## 2026-04-25 11:08:00 +08:00 - 多关键词搜索与分析默认值验证

- 执行者：Codex
- 搜索修复：`/api/search/questions` 新增 `keyword_match_mode=any|all`；题干关键词按空格、逗号、顿号、分号和换行拆分，`any` 使用 OR 匹配任意关键词，`all` 使用 AND 要求全部关键词同时出现在题干。
- 前端修复：`/search` 题目搜索输入框支持多关键词，新增“任意关键词满足 / 全部关键词满足”切换，并把条件传给后端搜索接口。
- 分析修复：题目分析服务不再根据题干/答案启发式填入知识点、解法或“高中数学综合”，也不再自动拼接“主要知识点/次级知识点/推荐解法”作为默认解释；缺少明确知识点或解释时拒绝落库，未分析题目保持空状态。
- 详情页修复：`/questions/:id` 的分析结果按 `analysis_json` 中真实的主要知识点、次级知识点、推荐解法显示；没有分析记录时标签表单初始为空。
- 验证：`uv run pytest tests/test_storage_and_slice.py -k "search_service_supports_any_and_all_keyword_modes or analysis_service"`，7 passed；`uv run pytest`，61 passed；前端 `npm run build` 通过。构建仍保留既有 Vite chunk size warning 与 npmrc 提示。

## 2026-04-25 11:22:00 +08:00 - 讲题对话数学格式 Prompt 验证

- 执行者：Codex
- 根因：讲题系统提示只要求教学化，没有明确约束数学表达式必须用 Markdown/LaTeX 数学分隔符输出，因此模型可能返回 `log_2(2^x+t)-x` 这类裸公式，前端 Markdown/KaTeX 不会自动渲染。
- 修复：`chat_system_prompt.md` 增加数学输出格式约束：所有数学表达式必须写成可渲染 LaTeX，行内用 `$...$`，长推导用 `$$...$$`，并明确禁止裸公式示例。
- 验证：`uv run pytest tests/test_storage_and_slice.py -k "chat_tutor_service_sends_image_parts_to_llm"`，1 passed；`uv run pytest tests/test_storage_and_slice.py -k "chat_tutor_service"`，6 passed；`uv run pytest`，61 passed。

## 2026-04-25 11:35:00 +08:00 - LLM Markdown 可渲染 Prompt 全量检查

- 执行者：Codex
- 检查范围：`backend/app/services/prompts/` 下 5 个 prompt，以及 `LLMGateway`、`ChatTutorService` 中的 prompt 读取与兜底调用路径。
- 结论：`slice_prompt.md`、`full_paper_boundary_prompt.md`、`full_answer_boundary_prompt.md` 是严格 JSON 接口契约，输出不会直接进入 `MarkdownContent`，因此必须继续禁止 Markdown、解释文字和代码块。
- 修复：`analysis_prompt.md` 的 `explanation_md` 字段增加“必须能被前端 `MarkdownContent` 渲染”约束，并要求所有数学表达式使用 `$...$` 或 `$$...$$`，禁止裸公式、裸下标、裸上标。
- 保留：`chat_system_prompt.md` 已具备同样的 Markdown/LaTeX 数学格式约束。
- 验证：`uv run pytest tests/test_storage_and_slice.py -k "llm_prompts_pin_project_output_contracts or chat_tutor_service_sends_image_parts_to_llm"`，2 passed；`uv run pytest`，61 passed。

## 2026-04-25 11:48:00 +08:00 - 题目详情页整块横向滚动验证

- 执行者：Codex
- 根因：此前整块横向滚动只加在 `/review/:id` 审核页的预览框；`/questions/:id` 详情页题干和答案仍直接使用通用 `MarkdownContent`，因此沿用段落、公式、表格局部横滚策略。
- 修复：`QuestionDetailPage.vue` 为题干和答案各加 `detail-markdown-surface` 外层滚动容器，并让内部 Markdown、段落、列表、代码块、表格、KaTeX display 公式展开到同一个横向滚动面。
- 验证：扩展 `npm run check:markdown-layout` 覆盖题目详情页整块滚动约束；`npm run check:markdown-layout` 通过；`npm run build` 通过。构建仍保留既有 Vite chunk size warning 与 npmrc 提示。
## 2026-05-02 17:05:02 +08:00 - Codex 部署前可用性检查

### 结论

本地前后端可以启动，现有自动化测试与前端构建通过；项目已经具备本地用户试用/演示条件。若目标是部署到服务器并交给真实用户持续使用，当前仍存在生产化阻塞项，需要先补齐部署配置、环境样例与运行方式。

### 已执行验证

- `backend`: `uv run pytest`，结果 `61 passed in 5.14s`。
- `frontend`: `npm run build`，结果通过；存在 Vite chunk size warning 与 npm 用户配置 warning。
- `frontend`: `npm run check:markdown-layout`，结果通过。
- `GET http://127.0.0.1:8000/healthz`，返回 `{"status":"ok"}`。
- `GET http://127.0.0.1:8000/api/papers`，返回 4 份本地试卷，状态均为 `SLICED`。
- `GET http://127.0.0.1:5173/`，返回 HTTP 200。

### 部署前问题清单

1. 生产部署配置仍是开发形态：`docker-compose.yml` 挂载源码目录，前端容器暴露 Vite dev server 5173，`frontend/Dockerfile` 使用 `npm run dev`，不适合作为服务器生产服务。
2. README 要求复制 `.env.example`，但仓库当前没有 `.env.example`，新服务器无法按文档稳定初始化环境。
3. 前端默认 API 地址硬编码到 `127.0.0.1:8000`，生产环境必须显式注入 `VITE_API_BASE_URL`，否则用户浏览器会请求自己的本机。
4. 当前 Docker Compose 没有持久化挂载 `data/`，且 README 示例使用 Windows 绝对路径，直接搬到 Linux 服务器会路径失效或数据不可持久。
5. `backend/alembic.ini` 保留示例 MySQL 地址与密码占位；虽然运行时会由 `app.core.config` 覆盖，但部署交接上容易误用。
6. 生产依赖版本未完全固定：前端 Dockerfile 未复制 `package-lock.json` 且使用 `npm install`，后端 Dockerfile 未使用 `uv.lock`，服务器构建可重复性不足。
7. 前端构建主 JS chunk 约 1.79 MB，当前不阻塞上线，但会影响首屏加载，应在部署优化阶段做代码拆分。
8. 登录页明确说明无需登录，当前系统更适合内网或受控环境试用；若面向公网真实用户，需要先明确访问边界与运维策略。
## 2026-05-04 22:25:00 +08:00 - 阶段队列与单题分析队列验证

- 执行者：Codex。
- 实现：`pipeline_task` 扩展为统一阶段任务，支持 `MINEU_CONVERT`、`SLICE_MATCH`、`QUESTION_ANALYSIS`；后端按任务类型启动 MineU 2 并发、切题匹配 1 并发、分析 2 并发 worker。
- 行为：单卷/批量运行先创建 MineU 阶段任务，再创建依赖 MineU 的切题匹配任务；单题分析接口改为立即入队返回，前端单题页轮询任务状态。
- 后端验证：`cd backend; uv run pytest` 通过，`61 passed in 3.79s`。
- 前端验证：`cd frontend; npm run build` 通过；保留既有 npm 配置提示和 Vite 大 chunk 警告。

## 2026-05-06 17:xx:xx +08:00 - 多用户、权限审计与随机刷题验证

- 执行者：Codex。
- 实现：新增本地账号登录、默认超级管理员种子、RBAC 权限检查口子、审计日志、用户管理页、用户级随机刷题状态与收藏、随机刷题页、工作台刷题概览；题目详情页答案默认隐藏并可手动显示。
- 后端验证：`cd backend; uv run --python 3.12.12 pytest` 通过，`63 passed`。本机 `uv` 无法下载项目声明的 Python 3.12.13 Windows 包，验证使用相邻托管版本 Python 3.12.12。
- 前端验证：首次 `npm run build` 因未安装依赖缺失 `vue-tsc` 失败；执行 `npm install` 后，`npm run build` 通过。构建保留 Vite 大 chunk 警告。
- 补充说明：`npm install` 报告 3 个依赖漏洞提示，未自动执行 `npm audit fix`，避免引入无关依赖版本变更。

## 2026-05-06 18:20:00 +08:00 - 个人中心与超级管理员用户管理验证

- 执行者：Codex。
- 实现：新增 `/api/profile` 个人中心接口与前端 `/profile` 页面；用户管理接口统一要求 `SUPER_ADMIN` 角色；新增用户直接权限表和角色模板；用户管理页支持角色和直接权限矩阵；导航和路由守卫隐藏/拦截普通用户访问 `/users`；随机刷题按钮替换为本地骰子图标。
- 后端验证：`cd backend; uv run --python 3.12.12 pytest` 通过，`66 passed`。
- 前端验证：`cd frontend; npm run build` 通过；保留既有 Vite 大 chunk 警告。

## 2026-05-06 20:18:00 +08:00 - 服务器打包部署验证

- 执行者：Codex。
- 本地打包：`cd frontend; npm run build` 通过；`cd backend; uv run --python 3.12.12 pytest` 通过，`66 passed`。
- 部署方式：沿用服务器现有 `/opt/mathmaster` 结构与 `mathmaster-backend.service`，前端静态文件部署到 `/var/www/mathmaster`，Nginx 继续监听 `8080` 并反代 `/api` 到 `127.0.0.1:8000`。
- 部署修复：新增生产 Docker 配置文件；修复 MySQL 密码含 `@` 时 SQLAlchemy URL 解析问题；修复 Alembic URL 中 `%` 插值问题。
- 远端验证：MySQL 迁移执行到 `20260506_0006`；`systemctl status mathmaster-backend` 为 active；`http://106.54.35.68:8080/` 返回 200；`/healthz` 返回 `ok`；管理员登录接口验证通过。

## 2026-05-06 20:32:00 +08:00 - 答案显隐与随机刷题状态图标验证

- 执行者：Codex。
- 实现：答案显隐统一为眼睛/眼睛斜杠图标按钮；随机刷题状态改为下拉框，状态项使用白/黄/绿实心圆点加文字；收藏改为星标按钮，未收藏为空心星，已收藏为黄色实心星；个人中心刷题列表同步使用状态圆点和星标。
- 前端验证：`cd frontend; npm run build` 通过；构建产物不再包含 `127.0.0.1:8000`。
- 远端验证：已部署到 `http://106.54.35.68:8080/`，Nginx 配置检查通过，首页返回 200。
