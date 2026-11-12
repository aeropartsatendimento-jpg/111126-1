"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

logger = logging.getLogger(__name__)

# One entry per collection: every field a route filters, sorts, or dedupes on. Applied by ensure_indexes() at startup.
INDEXES: dict[str, list[IndexModel]] = {
    "status_checks": [IndexModel([("timestamp", DESCENDING)], name="timestamp_desc")],
    "agents": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("key", ASCENDING)], name="key", unique=True),
    ],
    "missions": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("created_at", DESCENDING)], name="created_desc"),
        IndexModel([("status", ASCENDING), ("lease_until", ASCENDING)], name="status_lease"),
    ],
    "tasks": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created"),
        IndexModel([("agent_key", ASCENDING), ("status", ASCENDING)], name="agent_status"),
        IndexModel([("mission_id", ASCENDING), ("created_at", ASCENDING)], name="mission_created"),
        IndexModel([("project_id", ASCENDING), ("updated_at", DESCENDING)], name="project_updated"),
    ],
    "room_messages": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("created_at", DESCENDING)], name="created_desc"),
        IndexModel([("reply_status", ASCENDING), ("reply_lease_until", ASCENDING)], name="reply_status_lease"),
    ],
    "zero_messages": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("created_at", ASCENDING)], name="created_asc"),
        IndexModel([("reply_status", ASCENDING), ("reply_lease_until", ASCENDING)], name="reply_status_lease"),
    ],
    "channels": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("key", ASCENDING)], name="key", unique=True),
    ],
    "visual_missions": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("created_at", DESCENDING)], name="created_desc"),
        IndexModel([("status", ASCENDING), ("updated_at", DESCENDING)], name="status_updated"),
        IndexModel([("status", ASCENDING), ("lease_until", ASCENDING)], name="status_lease"),
    ],
    "briefings": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("day", ASCENDING)], name="day"),
        IndexModel([("created_at", DESCENDING)], name="created_desc"),
    ],
    "cron_runs": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("status", ASCENDING), ("updated_at", DESCENDING)], name="status_updated"),
    ],
    "projects": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("updated_at", DESCENDING)], name="updated_desc"),
    ],
    "accounts": [IndexModel([("id", ASCENDING)], name="id", unique=True)],
    "store_items": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("kind", ASCENDING), ("status", ASCENDING)], name="kind_status"),
    ],
    "agent_model_changes": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("agent_key", ASCENDING), ("created_at", DESCENDING)], name="agent_created"),
    ],
    "memories": [
        IndexModel([("id", ASCENDING)], name="id", unique=True),
        IndexModel([("project_id", ASCENDING), ("created_at", DESCENDING)], name="project_created"),
    ],
    "settings": [
        IndexModel([("key", ASCENDING)], name="key", unique=True),
    ],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:  # never block boot on an index; the log line names what to fix
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)
