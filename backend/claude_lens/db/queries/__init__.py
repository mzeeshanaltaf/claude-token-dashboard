"""Read/write queries for the API, ported from `token_dashboard/db.py`.

Each function takes a psycopg connection whose `search_path` is the Claude
Lens schema and returns plain dicts / lists of dicts.
"""
