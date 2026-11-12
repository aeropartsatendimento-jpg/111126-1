"""Agent registry — the five-I hierarchy with editable brain per agent."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.models import Agent, AgentModelChange, AgentModelUpdate, aware
from lib.db import db

router = APIRouter()

WORKING_SET = {"status": {"$in": ["queued", "working"]}}

# Sane defaults so the switcher UI auto-fills the "brain" label when the Boss picks a provider.
BRAIN_DEFAULTS = {
    ("openai", "gpt-5.4"): "ChatGPT · gpt-5.4",
    ("openai", "gpt-5.4-mini"): "ChatGPT · gpt-5.4-mini",
    ("anthropic", "claude-sonnet-5-5"): "Claude Sonnet",
    ("anthropic", "claude-opus-5-5"): "Claude Opus",
    ("anthropic", "claude-haiku-5-5"): "Claude Haiku",
    ("gemini", "gemini-3-flash-preview"): "Gemini Flash",
}


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
    # Audit the change before writing — same pattern as revision/proposal ledger.
    if doc.get("provider") != update.provider or doc.get("model") != update.model or doc.get("brain", "") != brain:
        change = AgentModelChange(
            agent_key=key,
            from_provider=doc.get("provider", ""),
            from_model=doc.get("model", ""),
            from_brain=doc.get("brain", ""),
            to_provider=update.provider,
            to_model=update.model,
            to_brain=brain,
            created_at=now,
        )
        await db.agent_model_changes.insert_one(change.model_dump())
    await db.agents.update_one(
        {"key": key},
        {"$set": {
            "provider": update.provider,
            "model": update.model,
            "brain": brain,
            "updated_at": now,
        }},
    )
    fresh = await db.agents.find_one({"key": key})
    fresh["created_at"] = aware(fresh["created_at"])
    fresh["open_tasks"] = await db.tasks.count_documents({"agent_key": key, "status": {"$in": ["queued", "working"]}})
    fresh["status"] = "working" if await db.tasks.find_one({"agent_key": key, "status": "working"}) else "idle"
    return Agent(**fresh)


@router.get("/agents/{key}/history", response_model=list[AgentModelChange])
async def agent_history(key: str, limit: int = 20):
    if not await db.agents.find_one({"key": key}):
        raise HTTPException(status_code=404, detail="agent not found")
    rows = await db.agent_model_changes.find({"agent_key": key}).sort("created_at", -1).to_list(max(1, min(limit, 50)))
    for r in rows:
        r["created_at"] = aware(r["created_at"])
    return [AgentModelChange(**r) for r in rows]
