FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.11-slim

COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra training --no-install-project
COPY src ./src
COPY examples ./examples
RUN uv sync --locked --no-dev --extra training --no-editable \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /app/artifacts /app/examples/data/uploads \
    && chown app:app /app/artifacts /app/examples/data/uploads

USER app
EXPOSE 8000
CMD ["uvicorn", "ml_pipeline_pro.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
