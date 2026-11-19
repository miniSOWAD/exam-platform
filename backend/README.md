# ExamFlow API

FastAPI backend for the ExamFlow online examination platform.

## FastAPI Cloud

The ASGI entrypoint is `app.main:app` (configured in `pyproject.toml`). Install the project from this directory so the `[build-system]` and `[project]` metadata are available to `uv`.

Required production environment variables include `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, and `AUTO_MIGRATE=true`. `ENABLE_API_DOCS=true` enables Swagger UI at `/docs`.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Alembic migrations are applied during ASGI startup when `AUTO_MIGRATE=true`.
