# AutoService Copilot

AutoService Copilot is a Chinese-language RAG and agent application for
new-energy vehicle after-sales support.

The system will retrieve evidence from vehicle manuals and service policies,
assess safety risks, and create service-ticket drafts with human approval.

## Current status

Day 1 provides:

- FastAPI application factory
- Environment-based configuration
- Health-check endpoint
- OpenAPI documentation
- Automated API test
- Ruff code-quality checks

## Technology stack

- Python 3.12
- FastAPI
- Pydantic Settings
- Pytest
- Ruff

Later stages will add Qdrant, PostgreSQL, hybrid retrieval, LangGraph,
evaluation, and deployment.

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

Run the API:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Open:

- API documentation: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/v1/health

## Quality checks

```powershell
python -m ruff check .
python -m pytest -q
```