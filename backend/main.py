from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from backend.config import settings
from backend.database import connect_db, close_db, init_db
from backend.routers.auth import router as auth_router
from backend.routers.stations import router as stations_router
from backend.routers.trains import router as trains_router
from backend.routers.crowd import router as crowd_router, simulation_loop
from backend.routers.crowd import get_live_status
from backend.routers.analytics import router as analytics_router
from backend.routers.schedules import router as schedules_router
from backend.routers.predictions import router as predictions_router
from backend.routers.alerts import router as alerts_router
from backend.routers.reports import router as reports_router
from backend.routers.notifications import router as notifications_router
from backend.routers.announcements import router as announcements_router
from backend.routers.heatmap import router as heatmap_router
from backend.routers.chat import router as chat_router
from fastapi import Depends

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend service for AI Metro Crowd Management & Scheduling Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if settings.FRONTEND_URL and settings.FRONTEND_URL not in origins:
    origins.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(auth_router)
app.include_router(stations_router)
app.include_router(trains_router)
app.include_router(crowd_router)
app.include_router(analytics_router)
app.include_router(schedules_router)
app.include_router(predictions_router)
app.include_router(alerts_router)
app.include_router(reports_router)
app.include_router(notifications_router)
app.include_router(announcements_router)
app.include_router(heatmap_router)
app.include_router(chat_router)

@app.on_event("startup")
async def startup_event():
    # 1. Connect to Database
    await connect_db()
    # 2. Setup indexes and seed files if empty
    await init_db()
    # 3. Start real-time simulated system loop in background
    asyncio.create_task(simulation_loop())
    print("AI MetroFlow Backend Service Started Successfully.")

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()
    print("AI MetroFlow Backend Service Stopped.")

@app.get("/")
async def root():
    return {
        "status": "online",
        "project": "AI MetroFlow – AI Metro Crowd Management and Scheduling Platform",
        "api_documentation": "/docs",
        "system_time": asyncio.get_event_loop().time()
    }





@app.get("/api/live-status")
async def app_live_status():
    return await get_live_status()
