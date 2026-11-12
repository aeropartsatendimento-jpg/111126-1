"""Agent registry — the five-I hierarchy with editable brain per agent."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.models import Agent, AgentModelChange, AgentModelUpdate, aware
from lib.db import db

router = APIRouter()

WORKING_SET = {"status": {"$in": ["queued", "working"]}}
BULK_AGENT_KEYS = ("zero", "pro", "jarvis", "aluna", "plus")

# Sane defaults so the switcher UI auto-fills the "brain" label when the Boss picks a provider.
BRAIN_DEFAULTS = {
    ("openai", "gpt-5.4"): "ChatGPT · gpt-5.4",
    ("openai", "gpt-5.4-mini"): "ChatGPT · gpt-5.4-mini",
    ("openai", "gpt-5.5"): "ChatGPT · gpt-5.5",
    ("anthropic", "claude-sonnet-5-5"): "Claude Sonnet",
    ("anthropic", "claude-opus-5-5"): "Claude Opus",
    ("anthropic", "claude-haiku-5-5"): "Claude Haiku",
    ("gemini", "gemini-3-flash-preview"): "Gemini Flash",
    ("gemini", "gemini-3.1-pro-preview"): "Gemini Pro",
}

# Presets for bulk / per-task routing (reasoning vs fast). Kept in one place so the orchestrator
# and the bulk endpoint share the same map.
PRESET_MODELS: dict[str, dict[str, str]] = {
    "openai": {"balanced": "gpt-5.4", "strong": "gpt-5.4", "fast": "gpt-5.4-mini"},
    "anthropic": {"balanced": "claude-sonnet-5-5", "strong": "claude-opus-5-5", "fast": "claude-haiku-5-5"},
    "gemini": {"balanced": "gemini-3-flash-preview", "strong": "gemini-3.1-pro-preview", "fast": "gemini-3-flash-preview"},
}


class BulkModelUpdate(BaseModel):
    provider: Literal["openai", "anthropic", "gemini"]
    preset: Literal["balanced", "fast", "strong"] = "balanced"
    agent_keys: list[str] | None = Field(default=None, description="omit to update the full squad")


class BulkModelResult(BaseModel):
    updated: list[Agent]
    provider: str
    model: str


async def _apply_change(doc: dict, new_provider: str, new_model: str, new_brain: str, now: datetime) -> dict:
    if doc.get("provider") != new_provider or doc.get("model") != new_model or doc.get("brain", "") != new_brain:
        change = AgentModelChange(
            agent_key=doc["key"],
            from_provider=doc.get("provider", ""),
            from_model=doc.get("model", ""),
            from_brain=doc.get("brain", ""),
            to_provider=new_provider,
            to_model=new_model,
            to_brain=new_brain,
            created_at=now,
        )
        await db.agent_model_changes.insert_one(change.model_dump())
    await db.agents.update_one(
        {"key": doc["key"]},
        {"$set": {
            "provider": new_provider,
            "model": new_model,
            "brain": new_brain,
            "updated_at": now,
        }},
    )
    fresh = await db.agents.find_one({"key": doc["key"]})
    fresh["created_at"] = aware(fresh["created_at"])
    fresh["open_tasks"] = await db.tasks.count_documents({"agent_key": doc["key"], "status": {"$in": ["queued", "working"]}})
    fresh["status"] = "working" if await db.tasks.find_one({"agent_key": doc["key"], "status": "working"}) else "idle"
    return fresh


@router.get("/agents", response_model=list[Agent])
async def list_agents():
    agents = await db.agents.find().sort("created_at", 1).to_list(50)

    open_counts: dict[str, int] = {}
    working_keys: set[str] = set()
    async for doc in db.tasks.aggregate(
        [
            {"$match": WORKING_SET},
            {"$group": {"_id": "$agent_key", "n": {"$sum": 1}, "working": {"$sum": {"$cond": [{"$eq": ["$status", "working"]}, 1, 0]}}}},
        ]
    ):
        open_counts[doc["_id"]] = doc["n"]
        if doc["working"]:
            working_keys.add(doc["_id"])

    out: list[Agent] = []
    for doc in agents:
        doc["created_at"] = aware(doc["created_at"])
        doc["open_tasks"] = open_counts.get(doc["key"], 0)
        doc["status"] = "working" if doc["key"] in working_keys else "idle"
        out.append(Agent(**doc))
    return out


@router.patch("/agents/{key}", response_model=Agent)
async def update_agent_model(key: str, update: AgentModelUpdate):
    doc = await db.agents.find_one({"key": key})
    if not doc:
        raise HTTPException(status_code=404, detail="agent not found")
    brain = update.brain if update.brain is not None else BRAIN_DEFAULTS.get((update.provider, update.model), doc.get("brain", ""))
    now = datetime.now(timezone.utc)
    fresh = await _apply_change(doc, update.provider, update.model, brain, now)
    return Agent(**fresh)


@router.post("/agents/bulk-model", response_model=BulkModelResult)
async def bulk_model(update: BulkModelUpdate):
    model = PRESET_MODELS[update.provider][update.preset]
    brain = BRAIN_DEFAULTS.get((update.provider, model), model)
    now = datetime.now(timezone.utc)
    keys = update.agent_keys or list(BULK_AGENT_KEYS)
    updated: list[Agent] = []
    for key in keys:
        doc = await db.agents.find_one({"key": key})
        if not doc:
            continue
        fresh = await _apply_change(doc, update.provider, model, brain, now)
        updated.append(Agent(**fresh))
    if not updated:
        raise HTTPException(status_code=404, detail="no matching agents")
    return BulkModelResult(updated=updated, provider=update.provider, model=model)


@router.get("/agents/{key}/history", response_model=list[AgentModelChange])
async def agent_history(key: str, limit: int = 20):
    if not await db.agents.find_one({"key": key}):
        raise HTTPException(status_code=404, detail="agent not found")
    rows = await db.agent_model_changes.find({"agent_key": key}).sort("created_at", -1).to_list(max(1, min(limit, 50)))
    for r in rows:
        r["created_at"] = aware(r["created_at"])
    return [AgentModelChange(**r) for r in rows]
