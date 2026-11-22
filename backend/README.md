# Claude Lens backend

FastAPI API + local collector for Claude Lens. Managed with [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync              # create .venv and install deps
uv run pytest        # run the test suite
uv run claude-lens --help
```

Configuration is read from environment variables, falling back to `.env.local` / `.env`
at the repo root (see `../.env.example`).
