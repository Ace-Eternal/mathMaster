# MathMaster

MathMaster 是一个面向高中数学试卷整理、MineU 转换、按题切片、答案匹配与人工审核的本地工具系统。当前版本默认使用：

- SQLite
- 本地文件存储
- 数据根目录 `D:\code\mathMaster\data`
- MineU / LLM 真实接口优先，未配置时自动降级 mock

## 当前可跑通的主链路

1. 上传单份试卷 PDF 与单份答案 PDF
2. 上传试卷文件夹与答案文件夹，按文件名自动配对
3. 缺失答案时自动标记 `has_answer = false`
4. 调用 MineU 将 PDF 转成 Markdown 与 JSON，并保留原始响应
5. 结合 JSON 粗切题与 LLM 精修，按“每道题”落地题目与答案
6. 低置信度题目进入人工审核队列
7. 在审核页人工修改题号、题干、答案、匹配状态与审核状态
8. 原始 PDF 从 `raw/unpaired` 归档到 `raw/archived`

## 目录结构

```text
backend/
  app/
    api/routes/
    core/
    db/
    models/
    schemas/
    services/
frontend/
  src/
scripts/
data/
  raw/unpaired/paper
  raw/unpaired/answer
  raw/archived/paper
  raw/archived/answer
  mineu/
  slices/
  review/
  analysis/
  mathmaster.db
```

## 环境变量

复制 [`.env.example`](/D:/code/mathMaster/.env.example) 为 `.env`。

默认本地运行推荐配置：

```env
DATABASE_BACKEND=sqlite
SQLITE_PATH=D:/code/mathMaster/data/mathmaster.db
STORAGE_BACKEND=local
STORAGE_BASE_DIR=D:/code/mathMaster/data
MINEU_USE_MOCK=true
LLM_USE_MOCK=true
VITE_API_BASE_URL=http://localhost:8000/api
```

如果要接真实 MineU：

```env
MINEU_BASE_URL=你的 MineU API 地址
MINEU_API_KEY=你的 MineU Key
MINEU_USE_MOCK=false
```

如果要接真实 LLM：

```env
LLM_BASE_URL=你的 OpenAI 兼容中转地址
LLM_API_KEY=你的 API Key
LLM_USE_MOCK=false
```

## 启动方式

### 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动时会自动：

- 创建 `D:\code\mathMaster\data` 及其子目录
- 初始化 SQLite 数据库表

### 前端

```powershell
cd frontend
npm install
npm run dev
```

## 主要页面

- `/papers`：单份上传、文件夹导入、配对结果、试卷列表
- `/papers/:id`：试卷详情、流程状态、切片结果
- `/papers/:id/mineu`：MineU Markdown / JSON 预览
- `/review`：待审核队列
- `/review/:questionId`：题级人工修正
- `/questions/:id`：单题详情与讲题对话

## 主要接口

- `POST /api/papers/upload`
- `POST /api/papers/import-folders`
- `GET /api/papers/import-jobs/{import_job_id}`
- `POST /api/papers/{paper_id}/pipeline/run-all`
- `POST /api/papers/batch/run`
- `GET /api/papers`
- `GET /api/papers/{paper_id}`
- `GET /api/papers/{paper_id}/mineu-preview`
- `GET /api/questions/{question_id}`
- `GET /api/review/queue`
- `POST /api/review/questions/{question_id}`

## 测试

```powershell
cd backend
pytest
```

当前包含的基础测试：

- Local storage 读写回环
- JSON 粗切题
- 文件名配对归一化
- MineU mock 转换结果完整性

## 备注

- 当前实现优先保证“试卷整理切片”这条链路完整可跑
- 知识点分析、搜索、讲题对话仍保留基础能力，但不是本次验收主线
- 若 MineU / LLM 未配置，系统会自动退回 mock 模式，方便本地演示与联调
"# mathMaster" 
