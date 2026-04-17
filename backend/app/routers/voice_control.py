import os
import json
import tempfile
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/voice", tags=["Voice Control"])

class VoiceIntentResponse(BaseModel):
    action: str
    transcript: str

@router.post("/process-voice", response_model=VoiceIntentResponse)
async def process_voice_command(audio: UploadFile = File(...)):
    """
    Takes an audio file, transcribes it using Groq's whisper-large-v3,
    and then parses the intent using Groq's llama-3.1-8b-instant.
    """
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key or groq_key == "your_groq_api_key_here":
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured.")

    # 1. Save uploaded file temporarily for httpx
    suffix = os.path.splitext(audio.filename)[1] or ".webm"
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    content = await audio.read()
    temp_audio.write(content)
    temp_audio.close()

    try:
        # 2. Transcribe via Whisper
        with open(temp_audio.name, "rb") as f:
            stt_response = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {groq_key}"},
                files={"file": (audio.filename, f, audio.content_type)},
                data={"model": "whisper-large-v3", "response_format": "json"},
                timeout=30.0
            )

        if stt_response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Groq Whisper Error: {stt_response.text}")
        
        transcript = stt_response.json().get("text", "")

        if not transcript.strip():
            return VoiceIntentResponse(action="unknown", transcript="(Inaudible)")

        # 3. Parse intent via LLM
        prompt = f"""
You are a Voice Command Parser for an accessibility application called FloorSense AI.
Given this user's speech transcript: "{transcript}"
Determine which UI action they want to perform. Return ONLY valid JSON with exactly one "action" field.
Choose the action from this exact list:
- "switch_to_livenav" (switching to camera mode, live navigation, scanner)
- "switch_to_floorplan" (switching back to floor plan map mode)
- "run_pipeline" (analyze the map, run pipeline, submit)
- "play_audio_guide" (read the text, play audio, speak out loud)
- "stop_audio" (stop speaking, stop talking, shut up)
- "unknown" (if it doesn't match anything above)

Format Example: {{"action": "switch_to_livenav"}}
"""
        
        llm_response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            },
            timeout=20.0
        )

        if llm_response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Groq LLM Error: {llm_response.text}")

        # Extract the action from the JSON response
        llm_content = llm_response.json()["choices"][0]["message"]["content"]
        action_data = json.loads(llm_content)
        action = action_data.get("action", "unknown")

        return VoiceIntentResponse(action=action, transcript=transcript)

    except json.JSONDecodeError:
         # Fallback if model fails JSON
         return VoiceIntentResponse(action="unknown", transcript=transcript)
    finally:
        os.unlink(temp_audio.name)
