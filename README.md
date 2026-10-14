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

RAG 答案生成、LangGraph Agent、售后工单审批、评估和容器化将在后续实际
开发日完成。

## 技术栈

- Python 3.12
- FastAPI
- Pydantic 与 Pydantic Settings
- SQLAlchemy 2.0
- Alembic
- SQLite
- Qdrant Client
- FastEmbed
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
