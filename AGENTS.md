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
- 数据库、导入、解析、存储相关改动必须覆盖正常流程和旧数据/边界场景。
- 验证结果写入：
  - `.codex/testing.md`
  - `verification.md`
- 无法执行的验证必须说明原因和残余风险。

## 6. 文档与留痕

Codex 工作文件统一写入项目本地 `.codex/`：

- `.codex/context-scan.json`
- `.codex/context-question-N.json`
- `.codex/operations-log.md`
- `.codex/testing.md`
- `.codex/review-report.md`

生成或更新文档时标注日期与执行者 `Codex`。外部资料引用需保留 URL；内部依据需保留文件路径。

## 7. Git 约束

- 可以执行 `git status`、`git diff`、`git add`、`git commit` 等本地操作。
- 不主动执行 `git push`，除非用户明确要求。
- 不使用破坏性命令，例如 `git reset --hard`、`git checkout -- <file>`，除非用户明确要求并确认范围。
- 不提交无关文件，不回滚用户已有改动。

## 8. 例外确认

以下操作需要用户明确确认：

- 删除核心配置文件，例如 `package.json`、`pyproject.toml`、`.env`、`tsconfig.json`。
- 数据库破坏性变更，例如 `DROP TABLE`、删除生产数据、不可恢复迁移。
- 推送到远程仓库，尤其是 `main` / `master`。
- 连续三次同类失败后需要调整策略。
- 用户明确要求先确认的事项。

## 9. 当前项目注意事项

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
