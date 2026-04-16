import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import pipeline
from dotenv import load_dotenv

load_dotenv()

# In development: http://localhost:5173
# In production: set ALLOWED_ORIGINS to your Vercel URL in Render dashboard
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app = FastAPI(
    title="FloorSense AI",
    description="AI-powered floor plan accessibility engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)


@app.get("/")
async def root():
    return {"message": "FloorSense AI backend is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
