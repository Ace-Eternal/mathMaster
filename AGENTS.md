# AGENTS.md — MathMaster Codex 工作手册

本文件由 Codex 于 2026-04-24 初始化，来源参考：

- `C:\Users\洛畔\.codex\AGENTS.md`

适用范围：`D:\code\mathMaster` 及其子目录。若子目录存在更近的 `AGENTS.md`，优先遵循子目录文件。

## 1. 项目定位

MathMaster 是前后端分离项目：

- `backend/`：Python FastAPI 后端，使用 SQLAlchemy、Alembic、pytest。
- `frontend/`：Vue 3 + Vite 前端，使用 TypeScript、Element Plus。
- `data/`：本地 SQLite 与文件存储目录。
- `logs/`：本地开发服务日志。
- `.codex/`：Codex 本地工作留痕目录，存放上下文、测试、审查和操作日志。

## 2. 工作原则

- 优先复用项目既有框架、库、工具和代码模式，避免新增不必要的自研维护面。
- 先阅读代码和日志，再做实现判断；所有结论应有文件、日志或测试证据支撑。
- 默认自主完成需求分析、实现、验证、文档记录和质量审查。
- 发现缺陷时优先修复缺陷，再扩展新功能。
- 保持小步修改，每次变更尽量可编译、可验证、可回滚。
- 不回退用户已有改动；遇到脏工作区时只处理与任务相关的文件。

## 3. 工具与降级

- 文件检索优先使用 `rg` / `rg --files`。
- 写文件优先使用 `apply_patch`。
- 复杂任务使用计划工具维护步骤和状态。
- Python 版本与虚拟环境统一使用 `uv` 管理；后端命令默认在 `backend/` 下通过 `uv run ...` 执行，并以 `backend/.python-version` 为项目 Python 版本声明。
- Node.js 版本统一使用 `nvm` 管理；前端命令默认在 `frontend/` 下先切换到项目约定的 Node.js 版本，再执行 `npm install`、`npm run dev` 等命令。
- 若全局手册要求的 MCP 工具当前不可用，例如 `sequential-thinking`、`shrimp-task-manager`、`code-index`、`exa`，需要在 `.codex/operations-log.md` 中记录不可用原因，并用当前可用工具完成等价分析。
- 网络信息、最新版本、外部文档等不稳定事实必须联网核验，并优先使用官方来源。

## 4. 本地开发命令

后端：

```powershell
cd D:\code\mathMaster\backend
uv run pytest
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd D:\code\mathMaster\frontend
npm install
npm run dev
```

常用健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

## 5. 验证要求

- 后端改动默认运行 `cd backend; uv run pytest`，或至少运行与改动相关的测试子集。
- 前端改动默认运行项目已有构建、类型检查或可用的本地验证命令。
- 涉及前端依赖变更、鉴权、渲染、上传、文件访问、外部请求时，必须运行 `cd frontend; npm audit --audit-level=moderate`，并优先用兼容补丁修复公开漏洞。
- 数据库、导入、解析、存储相关改动必须覆盖正常流程和旧数据/边界场景。
- 鉴权、文件存储、上传、Markdown/HTML 渲染、第三方 API key、生产配置相关改动必须补充安全回归测试，覆盖未登录访问、越权访问、路径穿越、非预期文件类型、超限输入和敏感信息不回显。
- 提交或交付前必须检索敏感信息模式，例如 `API_KEY`、`SECRET`、`TOKEN`、`sk-`、JWT 形态字符串，确认没有真实密钥进入源码、构建产物、日志或文档。
- 验证结果写入：
  - `.codex/testing.md`
  - `verification.md`
- 无法执行的验证必须说明原因和残余风险。

## 6. 安全编码规范

本节沉淀自 2026-05-11 安全审查与修复。之后所有新功能、重构和部署相关改动都必须默认遵守。

### 6.1 接口鉴权与授权

- 后端是唯一可信访问控制边界；不得依赖 Vue 路由守卫、按钮隐藏或前端状态判断来保护数据。
- 除 `/healthz`、`/api/auth/login` 等明确白名单外，所有 `/api/*` 业务接口默认必须要求登录。
- 读接口也必须鉴权；题库、答案、解析预览、任务状态、导入记录、字典、模板、审计、模型列表都属于业务数据，不得匿名开放。
- 新增接口时必须选择或新增明确权限点，例如 `paper.read`、`question.read`、`task.read`、`chat.use`、`paper.edit`，不得用“临时公开”“前端不会展示”作为理由跳过权限依赖。
- 敏感读接口需要细粒度权限：已删除数据、答案内容、MineU 原始预览、任务错误、审计日志、LLM 配置仅对对应管理权限开放。
- 前端权限控制只用于体验优化，服务端必须独立拒绝未登录和越权请求。

### 6.2 文件、路径与存储

- 所有本地/SFTP/对象存储 key 必须当作不可信输入处理，统一走安全解析函数。
- 路径解析必须拒绝绝对路径、空路径、`.`、`..`、控制字符和反斜杠绕过；本地路径必须 `resolve()` 后确认仍在 `storage_base_dir` 内。
- 文件读取接口必须同时具备鉴权、业务授权、固定前缀白名单和扩展名/MIME 白名单；不得提供“按任意 key 下载”的通用后门。
- 即使路径位于 `data/` 内，也不得默认可下载；SQLite、日志、配置、原始响应、临时文件、密钥文件必须显式排除。
- 删除、移动、写入、读取都必须使用同一套路径 containment 规则，不能只保护读取。
- 处理外部 ZIP、归档、OCR/MineU 返回资产时，只允许安全相对路径或纯文件名；拒绝 `../`、绝对路径、嵌套逃逸和非预期扩展名。

### 6.3 上传、导入与外部解析

- 上传入口必须限制单文件大小、批量数量、扩展名、MIME、文件头魔数和空文件。
- 不得直接无上限 `await file.read()` 读取用户上传；需要先做大小控制，必要时流式落盘。
- 上传 UI 的 `accept` 只是体验提示，不能视为安全校验。
- 进入 MineU、LLM 或其他外部服务前必须完成本地输入校验，避免非预期内容造成费用、队列或服务压力。
- 批量导入和后台任务必须有配额、队列限制和失败脱敏；任务错误不得向普通用户暴露本地路径、SQL、第三方响应体或密钥形态内容。

### 6.4 密钥、默认配置与生产启动

- 真实 API key、数据库密码、JWT/Token secret 不得写入源码、测试、文档、`.codex/` 留痕或前端环境变量。
- `.env` 只允许本地开发使用，且不得提交；发现真实 key 曾暴露时必须清空本地值并提示轮换供应商侧密钥。
- Vite 只允许暴露非敏感 `VITE_*` 变量；任何 `API_KEY`、`SECRET`、`TOKEN` 不得以 `VITE_*` 形式进入前端 bundle。
- 生产环境必须 fail fast：默认管理员密码、固定开发 secret、弱 secret、空关键配置都应拒绝启动。
- 登录页、示例代码、README 不得预填或宣传真实可用的管理员账号密码；示例必须使用占位符。
- 第三方 API 调用日志、审计记录和错误响应必须脱敏 Authorization、key、token、cookie、数据库连接串。

### 6.5 前端渲染、会话与浏览器侧安全

- 不得把后端返回内容直接作为 HTML 注入；必须使用 Vue moustache 文本渲染，或在确需 `v-html` 时先经过 DOMPurify 等成熟库白名单消毒。
- Markdown 渲染必须禁用原始 HTML，并对最终 HTML 做 sanitize；链接协议限制为安全协议，外链需防止 opener 风险。
- 认证 token 不应长期保存在 `localStorage`；优先使用 HttpOnly、Secure、SameSite Cookie。若当前架构仍用 Bearer，至少使用内存态 token 并缩短生命周期。
- 原生 `fetch` 不会自动走 axios 拦截器；所有需要鉴权的 fetch 必须显式附带 Authorization，或统一封装 authenticated fetch。
- 前端不得展示默认管理员凭据、真实密钥、内部路径、SQL 错误、第三方 API 原始错误体。

### 6.6 依赖与安全验证

- 优先复用成熟生态库处理安全敏感能力，例如 HTML sanitize、密码哈希、JWT/会话、文件类型识别；禁止临时自研净化器、签名协议或路径过滤器。
- 前端依赖变更后必须运行 `npm audit --audit-level=moderate`；发现兼容补丁可用时应立即修复。
- 后端依赖、认证、上传、文件解析、外部 API 客户端变更时，必须检查对应官方安全建议或项目当前锁定版本是否存在公开漏洞。
- 安全修复必须补测试：至少覆盖攻击路径被拒绝、正常路径仍可用、错误信息不泄露敏感内容。
- 部署前必须确认后端管理端口不直接公网裸露，除非所有接口均完成生产级鉴权、限流、日志脱敏和反向代理限制。

## 7. 文档与留痕

Codex 工作文件统一写入项目本地 `.codex/`：

- `.codex/context-scan.json`
- `.codex/context-question-N.json`
- `.codex/operations-log.md`
- `.codex/testing.md`
- `.codex/review-report.md`

生成或更新文档时标注日期与执行者 `Codex`。外部资料引用需保留 URL；内部依据需保留文件路径。

## 8. Git 约束

- 可以执行 `git status`、`git diff`、`git add`、`git commit` 等本地操作。
- 生成 commit message 时必须依据当前 `git diff` / `git diff --stat` 的实际变更范围编写，使用 Conventional Commit 格式；除极小变更外，应包含简洁 subject 和详细 body，body 用要点说明主要改动、行为影响和验证结果。
- 不主动执行 `git push`，除非用户明确要求。
- 不使用破坏性命令，例如 `git reset --hard`、`git checkout -- <file>`，除非用户明确要求并确认范围。
- 不提交无关文件，不回滚用户已有改动。

## 9. 例外确认

以下操作需要用户明确确认：

- 删除核心配置文件，例如 `package.json`、`pyproject.toml`、`.env`、`tsconfig.json`。
- 数据库破坏性变更，例如 `DROP TABLE`、删除生产数据、不可恢复迁移。
- 推送到远程仓库，尤其是 `main` / `master`。
- 连续三次同类失败后需要调整策略。
- 用户明确要求先确认的事项。

## 10. 当前项目注意事项

- 本项目历史 SQLite 库可能保留旧 schema，启动兼容逻辑位于 `backend/app/db/init_db.py`。
- 文件夹批量导入入口：
  - 前端：`frontend/src/pages/PaperListPage.vue`
  - 后端路由：`backend/app/api/routes/papers.py`
  - 后端服务：`backend/app/services/pipeline.py`
- 后端日志优先查看：
  - `logs/backend-dev.err.log`
  - `logs/backend-dev.log`
- 前端日志优先查看：
  - `logs/frontend-dev.err.log`
  - `logs/frontend-dev.out.log`
