ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-cache
ENV PATH="/app/.venv/bin:$PATH"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY tests ./tests
COPY scripts ./scripts
RUN chmod +x scripts/*.sh

EXPOSE 8000
ENTRYPOINT ["/app/scripts/init.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--port", "8000", "--host", "0.0.0.0"]