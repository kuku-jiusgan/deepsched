from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.models import models
from app.api import instruments, projects, schedules, stats, notifications

Base.metadata.create_all(bind=engine)

app = FastAPI(title="DeepSched - 山大淄博生物医药研究院排程管理系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(instruments.router)
app.include_router(projects.router)
app.include_router(schedules.router)
app.include_router(stats.router)
app.include_router(notifications.router)

@app.get("/api/v1/health")
def health():
    return {"status": "ok", "version": "1.0.0"}