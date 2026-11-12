import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
from lib.db import client, db, ensure_indexes


# Startup runs before the yield, shutdown after it. Add your own setup/teardown here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index_task = asyncio.create_task(ensure_indexes())  # background: a big index build must not block boot
    from lib.recovery import recover_incomplete_work
    await recover_incomplete_work()
    yield
    app.state.index_task.cancel()  # stop a build still running before its client closes
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    client.close()


# Create the main app without a prefix
app = FastAPI(lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Feature routers — one module per resource, each exporting its own APIRouter.
from routers.agents import router as agents_router
from routers.briefing import router as briefing_router
from routers.channels import router as channels_router
from routers.cron import router as cron_router
from routers.memories import router as memories_router
from routers.mcp import router as mcp_router
from routers.missions import router as missions_router
from routers.projects import router as projects_router
from routers.room import router as room_router
from routers.routing import router as routing_router
from routers.store import router as store_router
from routers.system import router as system_router
from routers.tasks import router as tasks_router
from routers.visual import router as visual_router
from routers.zero import router as zero_router

api_router.include_router(agents_router)
api_router.include_router(briefing_router)
api_router.include_router(channels_router)
api_router.include_router(cron_router)
api_router.include_router(mcp_router)
api_router.include_router(memories_router)
api_router.include_router(missions_router)
api_router.include_router(projects_router)
api_router.include_router(routing_router)
api_router.include_router(store_router)
api_router.include_router(room_router)
api_router.include_router(system_router)
api_router.include_router(tasks_router)
api_router.include_router(visual_router)
api_router.include_router(zero_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Keep this final: every feature route above is folded into the /api router first.
app.include_router(api_router)
