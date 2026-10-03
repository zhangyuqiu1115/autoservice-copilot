# AutoService Copilot

AutoService Copilot is a Chinese-language RAG and AI agent application for
new-energy vehicle after-sales support.

The project aims to retrieve evidence from vehicle manuals and service
policies, assess safety risks, and create service-ticket drafts with human
approval.

## Current capabilities

### API foundation

- FastAPI application factory
- Environment-based configuration
- Health-check endpoint
- Interactive OpenAPI documentation
- Automated tests and Ruff code-quality checks

### Database foundation

- SQLAlchemy 2.0 ORM
- Alembic database migrations
- SQLite development database
- Vehicle, document, and service-ticket data models
- SQLite foreign-key enforcement

### Vehicle management

- Create vehicles
- List vehicles
- Retrieve a vehicle by ID
- Update vehicles
- Delete vehicles
- Validate and normalize VIN values
- Reject duplicate VIN values

### Document ingestion foundation

- Upload PDF, TXT, and Markdown documents
- Validate file extensions and MIME types
- Enforce configurable upload-size limits
- Stream files to local storage
- Generate SHA-256 checksums
- Reject duplicate document content
- Store document metadata in the database
- List uploaded documents
- Retrieve document metadata by ID

Document parsing, chunking, embeddings, and vector retrieval will be added in
later stages.

## Technology stack

- Python 3.12
- FastAPI
- Pydantic and Pydantic Settings
- SQLAlchemy 2.0
- Alembic
- SQLite
- python-multipart
- Pytest
- Ruff

Later stages will add Qdrant, PostgreSQL, hybrid retrieval, LangGraph,
evaluation, and deployment.

## API endpoints

### General

- `GET /`
- `GET /api/v1/health`

### Vehicles

- `POST /api/v1/vehicles`
- `GET /api/v1/vehicles`
- `GET /api/v1/vehicles/{vehicle_id}`
- `PATCH /api/v1/vehicles/{vehicle_id}`
- `DELETE /api/v1/vehicles/{vehicle_id}`

### Documents

- `POST /api/v1/documents`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`

## Local setup

Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

Apply database migrations:

```powershell
python -m alembic upgrade head
```

Run the API:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Open:

- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/v1/health

## Upload configuration

The default development configuration is:

```env
UPLOAD_DIRECTORY=data/uploads
MAX_UPLOAD_SIZE_MB=10
```

Uploaded files, the local `.env` file, and the SQLite development database are
excluded from Git.

A synthetic test document is available at:

```text
sample_documents/byd_han_ev_owner_manual.txt
```

## Quality checks

```powershell
python -m ruff check .
python -m pytest -q
python -m alembic current
git diff --check
```