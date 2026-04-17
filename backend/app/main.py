import os
from dotenv import load_dotenv

# ⚠️  load_dotenv() MUST run before any app imports so module-level os.getenv()
# calls in generators.py pick up .env values before modules are initialised.
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import pipeline, live_nav, health, voice_control

app = FastAPI(
    title="FloorSense AI",
    description="AI-powered floor plan accessibility engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(live_nav.router)
app.include_router(health.router)
app.include_router(voice_control.router)


@app.get("/")
async def root():
    return {"message": "FloorSense AI backend is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
