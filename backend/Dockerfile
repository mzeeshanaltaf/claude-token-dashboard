# Claude Lens API (FastAPI). Built by the root docker-compose.yml.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.3 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# The project is installed editable, so core/pricing.py finds /app/pricing.json.
COPY claude_lens ./claude_lens
COPY pricing.json ./
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --no-create-home claudelens
USER claudelens

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

CMD ["uvicorn", "claude_lens.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
