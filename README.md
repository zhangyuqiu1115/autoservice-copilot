# AutoService Copilot

AutoService Copilot 是一个面向新能源汽车售后场景的中文 RAG 与 AI Agent
项目。系统从车辆手册和服务政策中提取证据，为用户问题提供可追溯的检索结果，
并逐步扩展到风险判断、售后工单和人工审批。

## 当前能力

### API 与数据层

- FastAPI 应用工厂与 OpenAPI 文档
- Pydantic Settings 环境配置
- SQLAlchemy 2.0 ORM 与 Alembic 数据库迁移
- SQLite 开发数据库与外键约束
- 车辆 CRUD、VIN 规范化与重复检查

### 文档处理

- 上传 PDF、TXT 和 Markdown 文档
- 文件扩展名、MIME 类型和容量限制
- SHA-256 内容去重与文档元数据持久化
- PDF 和 UTF-8 文本提取
- 保留段落结构的文本标准化
- 可配置的重叠文本分块
- 文档处理状态、错误信息和重复处理

### Embedding 与向量检索

- FastEmbed 本地多语言 Embedding
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Qdrant Local Mode 本地向量持久化
- 文档重新处理时安全替换旧向量
- Top-K 语义检索与文档 ID 过滤
- 中英文跨语言检索
- 应用关闭时释放 Qdrant 本地资源

### RAG 问答

- 检索、证据阈值过滤和答案生成链路
- 默认离线 `extractive` 模式，无需 API Key
- 可选 OpenAI-compatible Chat Completions 服务
- 回答返回来源编号、文档 ID、文本块 ID、相似度和证据原文
- 无可靠证据时明确拒答
- Prompt 明确隔离检索资料中的潜在指令

### LangGraph Agent 与售后工单

- LangGraph 状态图编排风险识别、RAG 检索和人工转交
- 中英文规则优先匹配火烟、制动、转向、高压等风险描述
- 例行问题调用已有 RAG；中高风险和未知问题转交人工
- 知识服务不可用或证据不足时保留待处理工单
- 原子保存待审核工单，返回执行路径、证据引用和建议
- 支持分页查询工单、按车辆过滤和工单详情

新工单均为 `pending_review`，AI 建议存于 `recommended_action`。
审核人员明确批准后才写入 `final_response`。分流采用演示规则，不构成车辆诊断或安全认证；
规则的保守匹配及局限见 [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md)。
### 人工审核与工单流转

- 独立审核密钥保护审批、退回、重新送审、关闭及审核历史接口
- 审核人员显式填写最终答复；退回必须填写原因
- 按工单版本检查更新，重复和过期操作返回 `409`
- 工单状态与审核事件在同一事务保存，失败完整回滚
- 审核历史保留操作人、意见、答复快照和时间；支持状态筛选

完整示例见 [`docs/HUMAN_REVIEW.md`](docs/HUMAN_REVIEW.md)。评估和容器化将在后续开发日完成。

## 技术栈

- Python 3.12
- FastAPI
- Pydantic 与 Pydantic Settings
- SQLAlchemy 2.0
- Alembic
- SQLite
- Qdrant Client
- FastEmbed
- LangGraph
- pypdf
- python-multipart
- Pytest
- Ruff

## API 端点

### 通用

- `GET /`
- `GET /api/v1/health`

### 车辆

- `POST /api/v1/vehicles`
- `GET /api/v1/vehicles`
- `GET /api/v1/vehicles/{vehicle_id}`
- `PATCH /api/v1/vehicles/{vehicle_id}`
- `DELETE /api/v1/vehicles/{vehicle_id}`

### 文档

- `POST /api/v1/documents`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `POST /api/v1/documents/{document_id}/process`
- `GET /api/v1/documents/{document_id}/chunks`

### 语义检索

- `POST /api/v1/retrieval/search`

请求示例：

```json
{
  "query": "给车辆充电之前需要做什么？",
  "limit": 5,
  "document_id": 1
}
```

### RAG 问答

- `POST /api/v1/rag/answer`

请求示例：

```json
{
  "query": "给车辆充电之前需要做什么？",
  "limit": 5,
  "document_id": 1
}
```

响应会包含 `answer`、`grounded`、`mode` 和 `citations`。当相关文本块全部
低于 `RAG_MIN_SCORE` 时，接口以 `no_evidence` 模式返回明确拒答，不调用
外部生成模型。


### Agent 分流与工单

- `POST /api/v1/agent/triage`：分流并为已有车辆创建待审核工单
- `GET /api/v1/service-tickets`：分页查询，支持 `vehicle_id`、`offset`、`limit`
- `GET /api/v1/service-tickets/{ticket_id}`：查看工单详情

在 Swagger 中先创建车辆，使用返回的车辆 ID 提交：

```json
{
  "vehicle_id": 1,
  "query": "给车辆充电之前需要做什么？",
  "limit": 5,
  "document_id": 1
}
```

`document_id` 可省略；传入时必须为已存在的文档。返回 `201` 和工单信息，
包括 `risk_level`、`recommended_action`、`citations`、`execution_path`。
可再用 `电池冒烟了` 验证直接转人工的路径。每次 POST 都创建新工单，
客户端应避免重复点击或自动重试。

### 人工审核接口

- `POST /api/v1/service-tickets/{ticket_id}/review`：批准或退回
- `POST /api/v1/service-tickets/{ticket_id}/submit-for-review`：草稿重新送审
- `POST /api/v1/service-tickets/{ticket_id}/close`：关闭已批准工单
- `GET /api/v1/service-tickets/{ticket_id}/events`：分页读取审核历史

以上接口需要 `X-Review-Key`。在 `.env` 设置私有 `REVIEW_API_KEY`，重启 API，
在 Swagger 的 **Authorize** 中填入密钥。未配置时接口返回 `503`，无效密钥返回 `403`。
列表接口支持 `status=pending_review` 等筛选。工单详情中的 `version` 用于请求的
`expected_version` 字段。

## 本地运行

创建并激活虚拟环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

创建本地环境配置：

```powershell
Copy-Item .env.example .env
```

应用数据库迁移：

```powershell
python -m alembic upgrade head
```

启动 API：

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

访问：

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

## 文档与检索配置

```env
UPLOAD_DIRECTORY=data/uploads
MAX_UPLOAD_SIZE_MB=10
DOCUMENT_CHUNK_SIZE_CHARS=1000
DOCUMENT_CHUNK_OVERLAP_CHARS=200
QDRANT_PATH=data/qdrant
QDRANT_COLLECTION_NAME=document_chunks
EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_CACHE_DIRECTORY=data/models
RETRIEVAL_TOP_K=5
RAG_PROVIDER=extractive
RAG_MIN_SCORE=0.35
RAG_MAX_CONTEXT_CHARS=6000
```

默认配置无需外部模型。若要接入 Ollama、vLLM 或其他兼容 Chat Completions
的服务，可在 `.env` 中配置：

```env
RAG_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=30
```

Embedding 模型会在首次使用时下载到 `data/models/`。Qdrant 数据保存在
`data/qdrant/`。这两个目录以及上传文件、`.env` 和本地数据库均不会提交到
Git。

项目提供合成测试文档：

```text
sample_documents/byd_han_ev_owner_manual.txt
```

## 质量检查

```powershell
python -m pytest -q
python -m ruff check .
python -m alembic current
git diff --check
```

实际开发进度见 [`docs/PROGRESS.md`](docs/PROGRESS.md)。
