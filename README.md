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
- Vehicle, document, document-chunk, and service-ticket data models
- SQLite foreign-key enforcement
- Cascading deletion of document chunks

### Vehicle management

- Create vehicles
- List vehicles
- Retrieve a vehicle by ID
- Update vehicles
- Delete vehicles
- Validate and normalize VIN values
- Reject duplicate VIN values

### Document ingestion and processing

- Upload PDF, TXT, and Markdown documents
- Validate file extensions and MIME types
- Enforce configurable upload-size limits
- Stream files to local storage
- Generate SHA-256 checksums
- Reject duplicate document content
- Store document metadata in the database
- Extract text from UTF-8 text files and PDF files
- Normalize extracted text while preserving paragraph boundaries
- Split text into configurable overlapping chunks
- Persist ordered document chunks in the database
- Track pending, processing, completed, and failed states
- Safely replace existing chunks when reprocessing a document
- List uploaded documents and retrieve their metadata
- Process an uploaded document through the API
- Retrieve the generated chunks through the API

Embeddings, vector indexing, and retrieval will be added in later stages.

## Technology stack

- Python 3.12
- FastAPI
- Pydantic and Pydantic Settings
- SQLAlchemy 2.0
- Alembic
- SQLite
- python-multipart
- pypdf
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
- `POST /api/v1/documents/{document_id}/process`
- `GET /api/v1/documents/{document_id}/chunks`

## Local setup

Create and activate a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1