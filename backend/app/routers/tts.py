"""
Real-time TTS endpoint for LiveNav voice guidance.
Accepts a text string, calls ElevenLabs, and streams back MP3 audio.
Also exposes a /test endpoint so you can diagnose key + connectivity issues.
"""
import os
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

from app.services.generators import generate_audio_elevenlabs, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL

router = APIRouter(prefix="/tts", tags=["TTS"])


class TTSRequest(BaseModel):
    text: str


@router.post("/speak")
async def speak(req: TTSRequest):
    """
    Convert text to speech via ElevenLabs and return audio/mpeg bytes.
    Returns 204 No Content if ELEVENLABS_API_KEY is not configured.
    Returns 502 with detail if ElevenLabs rejects the request.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key or api_key == "your_elevenlabs_api_key_here":
        return Response(status_code=204)   # Key not set — silent skip

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {
            "xi-api-key":   api_key,
            "Content-Type": "application/json",
            "Accept":       "audio/mpeg",
        }
        payload = {
            "text":     req.text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {
                "stability":        0.55,
                "similarity_boost": 0.80,
                "style":            0.0,
                "use_speaker_boost": True,
            },
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=20.0)

        if response.status_code != 200:
            # Bubble up the real ElevenLabs error so the frontend can show it
            raise HTTPException(
                status_code=502,
                detail=f"ElevenLabs error {response.status_code}: {response.text[:300]}"
            )

        return Response(content=response.content, media_type="audio/mpeg")

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ElevenLabs request timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs error: {str(e)}")


@router.get("/test")
async def test_elevenlabs():
    """
    Diagnostic endpoint — checks key presence and pings ElevenLabs.
    Visit /api/tts/test in your browser to debug connectivity.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key or api_key == "your_elevenlabs_api_key_here":
        return JSONResponse({
            "status":  "no_key",
            "message": "ELEVENLABS_API_KEY is not set or is still the placeholder value",
            "voice_id": ELEVENLABS_VOICE_ID,
            "model":    ELEVENLABS_MODEL,
        })

    # Try a tiny test synthesis
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {
            "xi-api-key":   api_key,
            "Content-Type": "application/json",
            "Accept":       "audio/mpeg",
        }
        payload = {
            "text":     "Test.",
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = httpx.post(url, headers=headers, json=payload, timeout=15.0)

        if resp.status_code == 200:
            return JSONResponse({
                "status":       "ok",
                "message":      f"ElevenLabs responded OK — {len(resp.content)} bytes returned",
                "key_prefix":   api_key[:6] + "…",
                "voice_id":     ELEVENLABS_VOICE_ID,
                "model":        ELEVENLABS_MODEL,
            })
        else:
            return JSONResponse({
                "status":       "api_error",
                "http_status":  resp.status_code,
                "elevenlabs_response": resp.text[:500],
                "key_prefix":   api_key[:6] + "…",
                "voice_id":     ELEVENLABS_VOICE_ID,
                "model":        ELEVENLABS_MODEL,
            }, status_code=200)

    except httpx.TimeoutException:
        return JSONResponse({"status": "timeout", "message": "ElevenLabs did not respond within 15 seconds"})
    except Exception as e:
        return JSONResponse({"status": "exception", "error": str(e)})
