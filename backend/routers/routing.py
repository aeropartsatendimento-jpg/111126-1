"""Automatic per-task routing settings — reasoning tier vs fast tier."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from lib.db import db

router = APIRouter()


class RoutingSettings(BaseModel):
    auto: bool = False  # off by default — the squad keeps the model chosen per agent


class RoutingSettingsIn(BaseModel):
    auto: bool | None = None


# Mirror of the map in routers.agents so the orchestrator can import it standalone.
TIER_MODELS: dict[str, dict[str, str]] = {
    "openai": {"reasoning": "gpt-5.4", "fast": "gpt-5.4-mini"},
    "anthropic": {"reasoning": "claude-opus-5-5", "fast": "claude-haiku-5-5"},
    "gemini": {"reasoning": "gemini-3.1-pro-preview", "fast": "gemini-3-flash-preview"},
}


async def routing_auto() -> bool:
    doc = await db.settings.find_one({"key": "routing"}) or {}
    return bool(doc.get("auto", False))


def tier_model(provider: str, tier: Literal["reasoning", "fast"]) -> str | None:
    return TIER_MODELS.get(provider, {}).get(tier)


@router.get("/routing/settings", response_model=RoutingSettings)
async def read_routing_settings():
    return RoutingSettings(auto=await routing_auto())


@router.patch("/routing/settings", response_model=RoutingSettings)
async def update_routing_settings(update: RoutingSettingsIn):
    patch = {k: v for k, v in update.model_dump().items() if v is not None}
    if patch:
        await db.settings.update_one(
            {"key": "routing"},
            {"$set": patch, "$setOnInsert": {"key": "routing"}},
            upsert=True,
        )
    return RoutingSettings(auto=await routing_auto())
