from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv("../.env")

from app.db.database import init_db
from app.db.seed import seed_database
from app.models import *  # noqa: F401, F403 - ensure models registered


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_database()
    yield


app = FastAPI(title="基金销售管理工具", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.api.funds import router as funds_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.ai_agent import router as ai_router
from app.api.follow_ups import router as follow_ups_router

app.include_router(funds_router)
app.include_router(customers_router)
app.include_router(dashboard_router)
app.include_router(ai_router)
app.include_router(follow_ups_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
