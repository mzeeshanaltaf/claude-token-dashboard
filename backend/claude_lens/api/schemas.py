"""Pydantic response/request models: they document the API in OpenAPI (phase 04
generates the frontend's TS types from it) and pin the JSON shapes.

Field names match the old `token_dashboard/server.py` JSON exactly. Additions
are noted inline; the only structural change is the `{items, total, page,
page_size}` envelope on `/api/sessions` and `/api/prompts`.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..core.passwords import MIN_PASSWORD_LENGTH

Usd = Optional[float]


class Ok(BaseModel):
    ok: bool = True


class Health(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------- analytics

class Overview(BaseModel):
    sessions: int
    projects: int
    turns: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_create_5m_tokens: int
    cache_create_1h_tokens: int
    cost_usd: float
    cost_input_usd: float
    cost_output_usd: float
    cost_cache_read_usd: float
    cost_cache_create_5m_usd: float
    cost_cache_create_1h_usd: float
    cost_cache_create_usd: float


class DailyRow(BaseModel):
    day: date  # local date in the configured timezone
    sessions: int  # new in Claude Lens (phase 05): sessions active that day
    turns: int  # new in Claude Lens (phase 05): user prompts that day
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_create_tokens: int
    # new in Claude Lens (phase 05): the day's estimated cost, total and per model
    # (unpriced models are left out of both)
    cost_usd: float
    cost_by_model: dict[str, float]


class ModelRow(BaseModel):
    model: str
    turns: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_create_5m_tokens: int
    cache_create_1h_tokens: int
    cost_usd: Usd
    cost_estimated: bool


class ToolRow(BaseModel):
    tool_name: str
    calls: int
    result_tokens: int


class SkillRow(BaseModel):
    skill: str
    invocations: int
    sessions: int
    last_used: Optional[datetime]
    tokens_per_call: Optional[int]


# ---------------------------------------------------------------- projects

class ProjectRow(BaseModel):
    project_slug: str
    project_name: str
    sessions: int
    turns: int
    input_tokens: int
    output_tokens: int
    core_tokens: int
    cache_read_tokens: int
    cache_create_5m_tokens: int
    cache_create_1h_tokens: int
    cache_write_tokens: int
    total_tokens: int
    last_active: Optional[datetime] = None  # new in Claude Lens
    estimated_cost_usd: Usd = None
    cost_input_usd: Usd = None
    cost_output_usd: Usd = None
    cost_cache_read_usd: Usd = None
    cost_cache_create_5m_usd: Usd = None
    cost_cache_create_1h_usd: Usd = None
    cost_cache_write_usd: Usd = None


class ProjectDailyCost(BaseModel):
    """New in Claude Lens (phase 05): one project's estimated cost on one local day."""
    project_slug: str
    day: date
    cost_usd: float


class ProjectSessionRow(BaseModel):
    session_id: str
    project_slug: str
    project_name: str
    started: datetime
    ended: datetime
    turns: int
    tokens: int
    title: Optional[str] = None
    estimated_cost_usd: Usd = None


# ---------------------------------------------------------------- sessions

class SessionRow(BaseModel):
    session_id: str
    project_slug: str
    project_name: str
    started: datetime
    ended: datetime
    turns: int
    tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_create_5m_tokens: int
    cache_create_1h_tokens: int
    cache_write_tokens: int
    total_tokens: int
    title: Optional[str] = None
    estimated_cost_usd: Usd = None


class SessionPage(BaseModel):
    items: list[SessionRow]
    total: int
    page: int
    page_size: int


class TurnRow(BaseModel):
    uuid: str
    parent_uuid: Optional[str] = None
    type: str
    timestamp: datetime
    model: Optional[str] = None
    is_sidechain: bool  # was 0/1 in the old app
    agent_id: Optional[str] = None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_create_5m_tokens: int
    cache_create_1h_tokens: int
    prompt_text: Optional[str] = None
    prompt_chars: Optional[int] = None
    tool_calls_json: Any = None  # parsed JSON (the old app sent a JSON string)
    project_slug: str
    cwd: Optional[str] = None
    title: Optional[str] = None
    cost_input_usd: Usd = None
    cost_output_usd: Usd = None
    cost_cache_read_usd: Usd = None
    cost_cache_create_5m_usd: Usd = None
    cost_cache_create_1h_usd: Usd = None
    estimated_cost_usd: Usd = None


# ---------------------------------------------------------------- prompts

class PromptRow(BaseModel):
    user_uuid: str
    session_id: str
    project_slug: str
    timestamp: datetime
    prompt_text: Optional[str] = None
    prompt_chars: Optional[int] = None
    assistant_uuid: str
    model: Optional[str] = None
    core_tokens: int
    cache_read_tokens: int
    # new in Claude Lens: the rest of the assistant turn's tokens and its cost breakdown
    input_tokens: int
    output_tokens: int
    cache_create_5m_tokens: int
    cache_create_1h_tokens: int
    title: Optional[str] = None
    estimated_cost_usd: Usd = None  # the full turn (all 5 token types)
    cost_input_usd: Usd = None
    cost_output_usd: Usd = None
    cost_cache_read_usd: Usd = None
    cost_cache_create_5m_usd: Usd = None
    cost_cache_create_1h_usd: Usd = None


class PromptPage(BaseModel):
    items: list[PromptRow]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------- tips

class Tip(BaseModel):
    key: str
    category: str
    title: str
    body: str
    scope: Optional[str] = None


class TipDismiss(BaseModel):
    key: str = Field(min_length=1, max_length=2000)


# ---------------------------------------------------------------- settings

class PlanResponse(BaseModel):
    plan: str
    pricing: dict[str, Any]


class PlanUpdate(BaseModel):
    plan: str = Field(min_length=1, max_length=50)


class SettingsResponse(BaseModel):
    plan: Optional[str]  # null until a plan has been chosen (the first-run picker)
    timezone: str


class SettingsUpdate(BaseModel):
    plan: Optional[str] = Field(default=None, min_length=1, max_length=50)
    timezone: Optional[str] = Field(default=None, min_length=1, max_length=64)


class SyncRun(BaseModel):
    id: int
    machine: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    error: Optional[str] = None
    files: Optional[int] = None
    messages: Optional[int] = None
    tools: Optional[int] = None
    titles: Optional[int] = None


class MachineSync(BaseModel):
    machine: str
    last_run: SyncRun
    last_ok_at: Optional[datetime] = None


class SyncStatus(BaseModel):
    last_synced_at: Optional[datetime]
    machines: list[MachineSync]
    runs: list[SyncRun]


# ---------------------------------------------------------------- auth

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=1024)


class Me(BaseModel):
    username: str
    expires_at: datetime


class PasswordChange(BaseModel):
    current: str = Field(min_length=1, max_length=1024)
    new: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)


class PasswordChanged(BaseModel):
    ok: bool = True
    revoked_sessions: int
