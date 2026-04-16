"""
Health check — tests Groq vision connectivity.
Visit /api/health in your browser to diagnose.
"""
import os
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check():
    results = {}

    # ── Groq Vision ───────────────────────────────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key or groq_key == "your_groq_api_key_here":
        results["groq"] = {
            "status": "no_key",
            "message": "GROQ_API_KEY not set. Get a free key at https://console.groq.com",
        }
    else:
        try:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 5,
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                results["groq"] = {
                    "status": "ok",
                    "key_prefix": groq_key[:8] + "…",
                    "message": "Groq API key is valid and working",
                }
            elif resp.status_code == 401:
                results["groq"] = {
                    "status": "invalid_key",
                    "key_prefix": groq_key[:8] + "…",
                    "message": "Groq rejected the key. Get a fresh one at https://console.groq.com",
                }
            else:
                results["groq"] = {
                    "status": "api_error",
                    "http_status": resp.status_code,
                    "message": resp.text[:300],
                }
        except httpx.TimeoutException:
            results["groq"] = {"status": "timeout", "message": "Groq did not respond in 10 s"}
        except Exception as e:
            results["groq"] = {"status": "error", "message": str(e)[:300]}

    overall = "ok" if all(v.get("status") == "ok" for v in results.values()) else "degraded"
    return JSONResponse({"overall": overall, "services": results})
