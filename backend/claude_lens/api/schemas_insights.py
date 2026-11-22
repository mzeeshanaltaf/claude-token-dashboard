"""Response models for the phase 06 endpoints: activity, session insights, tools
insights and search. (Split from `schemas.py` to keep each file small.)

"Tokens" here means **core tokens**: input + output + cache writes. Cache
reads are left out (they are ~100x larger and nearly free).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Usd = Optional[float]


# ---------------------------------------------------------------- activity

class CalendarDay(BaseModel):
    day: date  # local date in the `timezone` setting
    value: float  # cost_usd or tokens, per `metric`
    cost_usd: float
    tokens: int  # core tokens
    sessions: int
    turns: int


class ActivityCalendar(BaseModel):
    metric: Literal["cost", "tokens"]
    timezone: str
    start: date  # first day of the window (inclusive)
    end: date  # today, in `timezone`
    days: list[CalendarDay] = Field(description="active days only, oldest first")


class HourCell(BaseModel):
    dow: int = Field(ge=1, le=7, description="ISO weekday: 1 = Monday … 7 = Sunday")
    hour: int = Field(ge=0, le=23, description="local hour")
    turns: int
    tokens: int  # core tokens
    cost_usd: float


class ActivityHourly(BaseModel):
    timezone: str
    cells: list[HourCell] = Field(description="all 168 cells, Monday 00h first")


class BusiestDay(BaseModel):
    day: date
    cost_usd: float
    tokens: int


class TopProject(BaseModel):
    project_slug: str
    project_name: str
    turns: int
    sessions: int
    cost_usd: float


class PeakHour(BaseModel):
    hour: int
    turns: int


class ActivitySummary(BaseModel):
    timezone: str
    first_day: Optional[date]  # the range's first local day (first activity for "all")
    last_day: date  # the range's last local day (today, or the day before `until`)
    days_in_range: int
    active_days: int
    current_streak: int  # consecutive active days ending on last_day (or the day before)
    longest_streak: int
    busiest_day: Optional[BusiestDay]  # by cost
    avg_cost_per_active_day: float
    avg_tokens_per_active_day: float
    total_cost_usd: float
    total_tokens: int
    top_project: Optional[TopProject]  # by turns
    peak_hour: Optional[PeakHour]  # by turns


# ---------------------------------------------------------------- session insights

class ContextPoint(BaseModel):
    uuid: str  # the assistant turn (for "scroll to turn")
    ts: datetime
    context_tokens: int  # input + cache_read + cache writes
    output_tokens: int
    cost: Usd
    model: Optional[str]
    is_sidechain: bool


class ToolEvent(BaseModel):
    ts: datetime
    tool_name: str
    target: Optional[str]
    is_error: Optional[bool]  # null: no tool_use_id (migrated row) or no result
    message_uuid: str


class Subagent(BaseModel):
    agent_id: str
    turns: int
    tokens: int  # core tokens
    cost: Usd
    first_ts: datetime
    last_ts: datetime


class SubagentInvocation(BaseModel):
    ts: datetime
    subagent_type: Optional[str]  # null: the default agent, or a row ingested before phase 06
    message_uuid: str


class FileTouch(BaseModel):
    path: str
    read: int
    edit: int
    write: int
    total: int


class ModelUse(BaseModel):
    model: str
    turns: int
    cost: Usd


class SessionInsights(BaseModel):
    context_growth: list[ContextPoint]
    tool_timeline: list[ToolEvent]
    subagents: list[Subagent]
    subagent_invocations: list[SubagentInvocation]
    files: list[FileTouch] = Field(description="Read/Edit/Write targets, most touched first (max 100)")
    files_total: int
    branches: list[str]  # in order of first use
    models: list[ModelUse]
    duration_s: Optional[float]
    started: Optional[datetime]
    ended: Optional[datetime]
    cost_usd: float  # every assistant turn, sidechains included
    tool_calls_linked: int  # tool calls with a tool_use_id (is_error known)


# ---------------------------------------------------------------- tools insights

class ToolStat(BaseModel):
    tool_name: str
    calls: int
    linked: int  # calls with a tool_use_id and a result: the base for errors and result tokens
    errors: int
    error_rate: Optional[float]  # errors / linked; null when nothing is linked
    result_tokens: int  # over linked calls only (chars / 4)


class FileStat(BaseModel):
    path: str
    read: int
    edit: int
    write: int
    total: int
    sessions: int
    last_used: datetime


class CommandStat(BaseModel):
    command: str
    tool_name: str
    calls: int
    sessions: int
    last_used: datetime


class DomainStat(BaseModel):
    domain: str
    calls: int
    last_used: datetime


class ToolsInsights(BaseModel):
    tools: list[ToolStat]
    calls: int
    linked: int
    linked_note: str
    files: list[FileStat]
    commands: list[CommandStat]
    domains: list[DomainStat]


# ---------------------------------------------------------------- search

class PromptHit(BaseModel):
    user_uuid: str
    session_id: str
    project_slug: str
    timestamp: datetime
    rank: float
    snippet: str = Field(description="matches wrapped in U+E000 … U+E001")
    title: Optional[str] = None


class SessionHit(BaseModel):
    session_id: str
    title: str
    project_slug: str
    started: datetime
    ended: datetime


class ProjectHit(BaseModel):
    project_slug: str
    project_name: str
    sessions: int
    last_active: datetime


class SearchResults(BaseModel):
    q: str
    prompts: list[PromptHit]
    sessions: list[SessionHit]
    projects: list[ProjectHit]
