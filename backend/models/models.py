"""Pydantic v2 models for the QG do Zero squad — one source of truth.

Every model here has a hand-written TS mirror in frontend/src/lib/types.ts;
keep the two in sync in the same edit (nothing infers across the boundary).
"""

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def new_id() -> str:
    return str(uuid.uuid4())


def aware(dt: datetime) -> datetime:
    """Motor hands naive datetimes back from BSON (stored UTC) — normalise on read."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Agent(BaseModel):
    id: str = Field(default_factory=new_id)
    key: str  # zero | pro | jarvis | aluna | plus
    name: str
    role_pt: str
    role_en: str
    description_pt: str
    description_en: str
    provider: str  # openai | anthropic | gemini
    model: str
    brain: str = ""  # borrowed upstream brain (Router Eight, Codex Pro, Claude Sonnet...)
    status: str = "idle"  # idle | working (computed on read)
    open_tasks: int = 0  # computed on read
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentModelUpdate(BaseModel):
    provider: str = Field(pattern=r"^(openai|anthropic|gemini)$")
    model: str = Field(min_length=2, max_length=80)
    brain: Optional[str] = Field(default=None, max_length=80)


class AgentModelChange(BaseModel):
    id: str = Field(default_factory=new_id)
    agent_key: str
    from_provider: str
    from_model: str
    from_brain: str
    to_provider: str
    to_model: str
    to_brain: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Mission(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str
    status: str  # planning | delegating | completed | failed
    plan_intro: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MissionCreate(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    project_id: Optional[str] = None


class Task(BaseModel):
    id: str = Field(default_factory=new_id)
    mission_id: str
    mission_text: str = ""
    agent_key: str
    title: str
    detail: str = ""
    status: str  # queued | working | review | verified | rejected | failed
    result: Optional[str] = None
    project_id: Optional[str] = None
    review_note: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoomMessage(BaseModel):
    id: str = Field(default_factory=new_id)
    sender_key: str  # user | zero | pro | jarvis | aluna | plus | system
    kind: str  # chat | delegation | system | summary
    content: str
    mission_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RoomMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class DirectMessage(BaseModel):
    id: str = Field(default_factory=new_id)
    role: str  # user | zero
    content: str
    intent: str = ""  # explicando | propondo | executando (zero only)
    proposal: Optional[str] = None  # mission text Zero proposes
    project_id: Optional[str] = None
    mission_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ZeroChatCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class Channel(BaseModel):
    id: str = Field(default_factory=new_id)
    key: str  # whatsapp | facebook | internet
    name: str
    description_pt: str
    description_en: str
    status: str = "disconnected"  # connected | disconnected
    config: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChannelUpdate(BaseModel):
    status: Optional[str] = None
    config: Optional[dict[str, str]] = None


class VisualMissionStep(BaseModel):
    key: str
    label: str
    detail: str = ""
    status: str = "pending"  # pending | completed


class VisualBrowserAction(BaseModel):
    type: str  # open | read | click | write | copy | paste
    label: str
    target: str
    status: str = "pending"  # pending | completed
    output: str = ""


class VisualMission(BaseModel):
    id: str = Field(default_factory=new_id)
    url: str
    objective: str
    status: str = "queued"  # queued | running | completed | failed
    mode: str = "simulated"
    steps: list[VisualMissionStep] = Field(default_factory=list)
    actions: list[VisualBrowserAction] = Field(default_factory=list)
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VisualMissionCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    objective: str = Field(min_length=3, max_length=1000)
    action_types: list[str] = Field(
        default_factory=lambda: ["open", "read", "click", "write", "copy", "paste"],
        min_length=1,
        max_length=6,
    )

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        clean = value.strip()
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must start with http:// or https:// and include a host")
        return clean

    @field_validator("objective")
    @classmethod
    def trim_objective(cls, value: str) -> str:
        return value.strip()

    @field_validator("action_types")
    @classmethod
    def validate_action_types(cls, values: list[str]) -> list[str]:
        allowed = {"open", "read", "click", "write", "copy", "paste"}
        if any(value not in allowed for value in values):
            raise ValueError("action_types contains an unsupported browser action")
        if len(values) != len(set(values)):
            raise ValueError("action_types must not contain duplicates")
        return values


class SearchCreate(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class SearchHit(BaseModel):
    title: str
    url: str
    snippet: str = ""


class SearchResponse(BaseModel):
    query: str
    engine: str
    results: list[SearchHit] = Field(default_factory=list)


class SystemInfo(BaseModel):
    app: str
    llm_configured: bool
    brain: str  # cloud | simulated


class Briefing(BaseModel):
    id: str = Field(default_factory=new_id)
    day: str  # YYYY-MM-DD (America/Sao_Paulo)
    city: str = ""
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BriefingSettingsIn(BaseModel):
    auto: Optional[bool] = None
    hour: Optional[int] = Field(default=None, ge=0, le=23)
    city: Optional[str] = Field(default=None, max_length=80)


class BriefingSettingsOut(BaseModel):
    auto: bool = True
    hour: int = 7
    city: str = "São Paulo"


class CronWebhookEnvelope(BaseModel):
    event: Literal["schedule.triggered"]
    schedule_id: str = Field(min_length=1, max_length=100)
    run_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    dispatch_time: Optional[str] = None
    job_id: Optional[str] = None
    data: None = None


class CronWebhookAck(BaseModel):
    accepted: bool = True
    duplicate: bool = False
    run_id: str


class TaskReview(BaseModel):
    approve: bool
    note: Optional[str] = Field(default=None, max_length=1000)


class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    objective: str = ""
    status: str = "active"  # active | paused | done
    in_progress: str = ""
    blocker: str = ""  # bloqueio ou decisão necessária
    next_step: str = ""
    last_verified: str = ""  # última entrega verificada
    last_verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    objective: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    objective: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = None
    in_progress: Optional[str] = Field(default=None, max_length=2000)
    blocker: Optional[str] = Field(default=None, max_length=2000)
    next_step: Optional[str] = Field(default=None, max_length=2000)


class Account(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str  # nome amigável, ex: "Trabalho"
    provider: str  # ex: ChatGPT Pro, Gemini web
    status: str = "unverified"  # available | busy | offline | unverified
    note: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=300)


class AccountUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=300)


class StoreItem(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: str  # stock | order | coupon
    title: str
    detail: str = ""
    value: str = ""  # qtd / valor / código
    status: str  # stock: critical|ok · order: open|done · coupon: active|expired
    is_sample: bool = False
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StoreItemCreate(BaseModel):
    kind: str
    title: str = Field(min_length=1, max_length=140)
    detail: str = Field(default="", max_length=500)
    value: str = Field(default="", max_length=60)
    status: str


class StoreItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=140)
    detail: Optional[str] = Field(default=None, max_length=500)
    value: Optional[str] = Field(default=None, max_length=60)
    status: Optional[str] = None


class McpRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int | str] = None
    method: str
    params: dict = Field(default_factory=dict)


class McpInfo(BaseModel):
    path: str
    token_configured: bool
    tools: list[str]


class Memory(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: str  # decisao_chefe | fato_verificado | proposta | antiga
    title: str
    content: str = ""
    source: str = ""  # de onde veio (tarefa, conversa, Chefe)
    project_id: Optional[str] = None
    replaces: Optional[str] = None
    superseded_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryCreate(BaseModel):
    kind: str
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(default="", max_length=3000)
    source: str = Field(default="", max_length=300)
    project_id: Optional[str] = None
    replaces: Optional[str] = None
