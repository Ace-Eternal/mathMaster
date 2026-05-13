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
- 生成 commit message 时必须依据当前 `git diff` / `git diff --stat` 的实际变更范围编写，使用 Conventional Commit 格式；除极小变更外，应包含简洁 subject 和详细 body，body 用要点说明主要改动、行为影响和验证结果。
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

## 10. 生产容器化部署记录

本节由 Codex 于 2026-05-13 根据服务器 `106.54.35.68` 的实际容器化部署过程补充。敏感信息（服务器密码、数据库密码、MineU Key、LLM Key、`AUTH_SECRET_KEY`）不得写入仓库文件；生产服务器上的真实值保存在服务器部署目录的 `.env.prod` 中。

### 10.1 当前生产架构

- 服务器公网入口：`http://106.54.35.68:8080/`
- 生产部署目录：`/opt/mathmaster/container`
- Compose 文件：`/opt/mathmaster/container/docker-compose.prod.yml`
- 环境变量文件：`/opt/mathmaster/container/.env.prod`
- 前端镜像：`ghcr.io/ace-eternal/mathmaster-frontend:latest`
- 后端镜像：`ghcr.io/ace-eternal/mathmaster-backend:latest`
- 数据库镜像：`mysql:8.4`
- 前端端口映射：宿主机 `8080` -> 容器 `80`
- 后端端口：仅 Docker 内部网络使用 `backend:8000`，不直接暴露公网。
- MySQL 端口：仅 Docker 内部网络使用 `mysql:3306`，不直接暴露公网。
- 文件持久化：`/opt/mathmaster/container/data` 挂载到后端容器 `/data`。
- 数据库持久化：Docker volume `container_mysql-data` 挂载到 MySQL `/var/lib/mysql`。

### 10.2 生产 Compose 关键配置

生产部署使用 GitHub Container Registry 已构建镜像，不在服务器本地 build。Compose 中应使用 `image:`，不要使用 `build:`。

```yaml
services:
  mysql:
    image: mysql:8.4
    restart: unless-stopped

  backend:
    image: ghcr.io/ace-eternal/mathmaster-backend:latest
    restart: unless-stopped
    environment:
      APP_ENV: production
      DATABASE_BACKEND: mysql
      MYSQL_HOST: mysql
      MYSQL_PORT: 3306
      MYSQL_USER: root
      MYSQL_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-mathmaster}
      STORAGE_BACKEND: local
      STORAGE_BASE_DIR: /data
      AUTH_SECRET_KEY: ${AUTH_SECRET_KEY}
      CORS_ORIGINS: ${CORS_ORIGINS}
    volumes:
      - ./data:/data
    depends_on:
      mysql:
        condition: service_healthy

  frontend:
    image: ghcr.io/ace-eternal/mathmaster-frontend:latest
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      - backend
```

### 10.3 生产环境变量

服务器 `.env.prod` 至少需要包含：

```env
MYSQL_ROOT_PASSWORD=生产数据库密码
MYSQL_DATABASE=mathmaster

AUTH_SECRET_KEY=随机长字符串
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=生产管理员密码
BOOTSTRAP_ADMIN_DISPLAY_NAME=超级管理员

CORS_ORIGINS=["http://106.54.35.68:8080"]

MINEU_USE_MOCK=false
MINEU_BASE_URL=https://mineru.net/api/v4
MINEU_API_KEY=生产MineUKey

LLM_USE_MOCK=false
LLM_BASE_URL=https://www.packyapi.com/v1
LLM_API_KEY=生产LLMKey
```

生成 `AUTH_SECRET_KEY` 的推荐命令：

```bash
openssl rand -hex 32
```

如服务器已有非容器化部署，可从旧项目 `.env` 读取 `MINEU_*` 与 `LLM_*` 配置后迁移到 `/opt/mathmaster/container/.env.prod`。

### 10.4 首次容器化切换流程

1. 登录服务器并进入部署目录：

```bash
ssh root@106.54.35.68
mkdir -p /opt/mathmaster/container/data
cd /opt/mathmaster/container
```

2. 写入 `docker-compose.prod.yml` 和 `.env.prod`。

3. 拉取镜像：

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
```

若 GHCR 拉取很慢，优先单独拉取镜像，避免并发下载拖慢：

```bash
docker pull ghcr.io/ace-eternal/mathmaster-backend:latest
docker pull ghcr.io/ace-eternal/mathmaster-frontend:latest
docker pull mysql:8.4
```

4. 停用旧非容器化 MathMaster 后端：

```bash
systemctl stop mathmaster-backend.service
systemctl disable mathmaster-backend.service
```

5. 若旧 Nginx 站点占用 `8080`，备份并移除旧站点入口，保留其它 Nginx 站点：

```bash
mkdir -p /opt/mathmaster/backups
cp -a /etc/nginx/sites-enabled/mathmaster.conf /opt/mathmaster/backups/mathmaster.conf.enabled.$(date +%Y%m%d%H%M%S) 2>/dev/null || true
rm -f /etc/nginx/sites-enabled/mathmaster.conf
nginx -t
systemctl reload nginx
```

6. 启动容器：

```bash
cd /opt/mathmaster/container
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

### 10.5 日常更新流程

GitHub Actions 重新构建并推送镜像后，在服务器执行：

```bash
cd /opt/mathmaster/container
docker compose --env-file .env.prod -f docker-compose.prod.yml pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

清理无用旧镜像：

```bash
docker image prune -f
```

### 10.6 验证与排障命令

查看容器状态：

```bash
cd /opt/mathmaster/container
docker compose -f docker-compose.prod.yml ps
```

查看日志：

```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f mysql
```

健康检查：

```bash
docker compose -f docker-compose.prod.yml exec -T frontend wget -qO- http://backend:8000/healthz
curl -I http://127.0.0.1:8080/
curl -I http://106.54.35.68:8080/
```

端口检查：

```bash
ss -ltnp | grep -E ':(80|8080|8000|3306)\s'
```

预期状态：

- `frontend`：`0.0.0.0:8080->80/tcp`
- `backend`：`Up`，仅显示 `8000/tcp`
- `mysql`：`Up` 且 `healthy`
- `mathmaster-backend.service`：`disabled`

### 10.7 已知服务器注意事项

- 2026-05-13 部署时，服务器 Docker daemon 原配置为：

```json
{
  "data-root": "/hd/docker-data"
}
```

该路径当时是只读文件系统，导致 Docker 无法启动，日志报错 `chmod /hd/docker-data: read-only file system`。已备份原配置并改为：

```json
{
  "data-root": "/var/lib/docker",
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

如果后续 Docker 无法启动，优先检查：

```bash
systemctl status docker --no-pager -l
journalctl -u docker --no-pager -n 120
cat /etc/docker/daemon.json
df -h / /var/lib/docker
```

修改 Docker 配置后重启：

```bash
systemctl restart docker
docker info
```
