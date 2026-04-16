"""
Health check endpoint — tests Gemini and ElevenLabs connectivity.
Visit /api/health in your browser to diagnose both APIs at once.
"""
import os
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check():
    results = {}

    # ── Gemini Vision ──────────────────────────────────────────────────────────
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key or gemini_key == "your_gemini_key_here":
        results["gemini"] = {"status": "no_key", "message": "GEMINI_API_KEY not set"}
    elif not gemini_key.startswith("AIzaSy"):
        results["gemini"] = {
            "status": "wrong_key_format",
            "message": f"Key starts with '{gemini_key[:6]}…' — Gemini keys must start with 'AIzaSy'. "
                       "Get yours at https://aistudio.google.com/apikey",
        }
    else:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            # Lightweight ping — just list models
            models = client.models.list()
            results["gemini"] = {
                "status": "ok",
                "key_prefix": gemini_key[:8] + "…",
                "message": "Gemini API key is valid",
            }
        except Exception as e:
            err = str(e)
            if "API_KEY_INVALID" in err or "invalid" in err.lower():
                results["gemini"] = {
                    "status": "invalid_key",
                    "message": "Gemini rejected the key. Get a fresh one at https://aistudio.google.com/apikey",
                }
            else:
                results["gemini"] = {"status": "error", "message": err[:300]}

    # ── ElevenLabs TTS ────────────────────────────────────────────────────────
    el_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not el_key or el_key == "your_elevenlabs_api_key_here":
        results["elevenlabs"] = {"status": "no_key", "message": "ELEVENLABS_API_KEY not set"}
    else:
        try:
            from app.services.generators import ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL
            resp = httpx.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
                headers={"xi-api-key": el_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
                json={"text": "Test.", "model_id": ELEVENLABS_MODEL,
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                timeout=12.0,
            )
            if resp.status_code == 200:
                results["elevenlabs"] = {
                    "status": "ok",
                    "key_prefix": el_key[:6] + "…",
                    "message": f"ElevenLabs OK — {len(resp.content)} bytes returned",
                }
            elif resp.status_code == 401:
                results["elevenlabs"] = {
                    "status": "invalid_key",
                    "message": "ElevenLabs rejected the key (401). "
                               "Go to https://elevenlabs.io → Profile → API Keys and copy a fresh key.",
                    "key_prefix": el_key[:6] + "…",
                }
            else:
                results["elevenlabs"] = {
                    "status": "api_error",
                    "http_status": resp.status_code,
                    "message": resp.text[:300],
                }
        except httpx.TimeoutException:
            results["elevenlabs"] = {"status": "timeout", "message": "ElevenLabs did not respond in 12 s"}
        except Exception as e:
            results["elevenlabs"] = {"status": "error", "message": str(e)[:300]}

    overall = "ok" if all(v.get("status") == "ok" for v in results.values()) else "degraded"
    return JSONResponse({"overall": overall, "services": results})
