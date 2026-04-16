from fastapi import APIRouter, HTTPException, File, UploadFile
import tempfile
import os
import base64
from pydantic import BaseModel
from typing import Optional, Tuple

from app.services.graph_engine import GraphEngine
from app.services.vision_service import parse_floorplan_real
import app.services.generators as gens

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


class PipelineResponse(BaseModel):
    tactile_svg: str
    aria_html: str
    path_narrative: Optional[str] = None
    vision_error: Optional[str] = None     # Set when Gemini failed (fell back to mock)
    # tts_text: Optional[str] = None       # WEB SPEECH API — commented out
    tts_audio_b64: Optional[str] = None    # ElevenLabs MP3 audio as base64 data URI
    tts_error: Optional[str] = None        # Human-readable reason if TTS failed


def _build_audio_b64(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Call ElevenLabs TTS.
    Returns (data_uri, None) on success, (None, error_msg) on failure.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key or api_key == "your_elevenlabs_api_key_here":
        return None, "ELEVENLABS_API_KEY not configured in backend .env / environment variables"

    import httpx
    from app.services.generators import ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {
            "xi-api-key":   api_key,
            "Content-Type": "application/json",
            "Accept":       "audio/mpeg",
        }
        payload = {
            "text":     text,
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
            return None, f"ElevenLabs API returned {response.status_code}: {response.text[:200]}"

        b64 = base64.b64encode(response.content).decode("utf-8")
        return f"data:audio/mpeg;base64,{b64}", None

    except httpx.TimeoutException:
        return None, "ElevenLabs request timed out (20 s)"
    except Exception as e:
        return None, f"ElevenLabs error: {str(e)}"


@router.post("/process-mock", response_model=PipelineResponse)
async def process_mock_floorplan(source: str = "n1", target: str = "n4"):
    floor_data = gens.mock_vision_parse()
    engine = GraphEngine(floor_data)
    path = engine.find_shortest_path(source, target)

    if not path:
        raise HTTPException(status_code=404, detail="No accessible path found between source and target.")

    path_details = engine.get_path_details(path)
    total_dist = sum(d.get('distance_to_next', 0) for d in path_details if 'distance_to_next' in d)
    nav_text = gens.generate_navigation_text(path_details)

    audio_b64, tts_err = _build_audio_b64(nav_text)
    return PipelineResponse(
        tactile_svg=gens.generate_tactile_svg(floor_data),
        aria_html=gens.generate_aria_html(engine),
        path_narrative=f"Path found with {len(path)} steps crossing {total_dist} metres.",
        # tts_text=nav_text,               # WEB SPEECH API — commented out
        tts_audio_b64=audio_b64,
        tts_error=tts_err,
    )


@router.post("/process", response_model=PipelineResponse)
async def process_real_floorplan(
    file: UploadFile = File(...),
    source: str = "n1",
    target: str = "n4",
):
    suffix = os.path.splitext(file.filename or "plan.png")[1] or ".png"
    content = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        floor_data, vision_err = parse_floorplan_real(tmp_path)
        engine = GraphEngine(floor_data)

        valid_nodes = [n.id for n in floor_data.nodes]
        source_id = source if source in valid_nodes else (valid_nodes[0]  if valid_nodes else "n1")
        target_id = target if target in valid_nodes else (valid_nodes[-1] if valid_nodes else "n4")

        path = engine.find_shortest_path(source_id, target_id)
        if not path:
            raise HTTPException(status_code=404, detail="No accessible path found between source and target.")

        path_details = engine.get_path_details(path)
        total_dist = sum(d.get('distance_to_next', 0) for d in path_details if 'distance_to_next' in d)
        nav_text = gens.generate_navigation_text(path_details)

        audio_b64, tts_err = _build_audio_b64(nav_text)
        return PipelineResponse(
            tactile_svg=gens.generate_tactile_svg(floor_data),
            aria_html=gens.generate_aria_html(engine),
            path_narrative=f"Path found with {len(path)} steps crossing {total_dist} metres."
                           + (" ⚠️ (mock data)" if vision_err else ""),
            vision_error=vision_err,
            # tts_text=nav_text,           # WEB SPEECH API — commented out
            tts_audio_b64=audio_b64,
            tts_error=tts_err,
        )

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
