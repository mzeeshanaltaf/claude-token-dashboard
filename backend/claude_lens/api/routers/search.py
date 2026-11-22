"""`/api/search` (new in Claude Lens, phase 06): the Cmd+K palette's backend."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, Query

from ...db.queries import search as sq
from ..deps import get_conn
from ..schemas_insights import SearchResults

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResults)
def search(q: str = Query("", max_length=200),
           limit: int = Query(8, ge=1, le=20, description="per group"),
           conn: psycopg.Connection = Depends(get_conn)):
    """Grouped results: prompts (full-text, ranked, with a snippet), sessions
    (title) and projects (name or slug). A blank `q` returns empty groups."""
    q = q.strip()
    if not q:
        return {"q": q, "prompts": [], "sessions": [], "projects": []}
    return {
        "q": q,
        "prompts": sq.search_prompts(conn, q, limit),
        "sessions": sq.search_sessions(conn, q, limit),
        "projects": sq.search_projects(conn, q, limit),
    }
