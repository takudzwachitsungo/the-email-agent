FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000
# Apply migrations (idempotent) then start the service.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn email_agent.app:app --host 0.0.0.0 --port 8000"]
