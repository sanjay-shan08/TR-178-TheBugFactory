import os
import json
from typing import Tuple, Optional
from app.models.schemas import FloorPlanData, Node, Edge
import app.services.generators as gens


def parse_floorplan_real(image_path: str) -> Tuple[FloorPlanData, Optional[str]]:
    """
    Parse a floor plan image using Gemini Vision.
    Returns (FloorPlanData, error_message).
    error_message is None on success, or a human-readable string on failure.
    Always returns valid FloorPlanData (falls back to mock on error).
    """
    gemini_key = os.environ.get("GEMINI_API_KEY", "")

    # ── Key not set ──────────────────────────────────────────────────────────
    if not gemini_key or gemini_key == "your_gemini_key_here":
        return gens.mock_vision_parse(), (
            "GEMINI_API_KEY not set — using mock floor plan. "
            "Get a free key at https://aistudio.google.com/apikey (it starts with AIzaSy...)"
        )

    # ── Key looks wrong ───────────────────────────────────────────────────────
    if not gemini_key.startswith("AIzaSy"):
        return gens.mock_vision_parse(), (
            f"GEMINI_API_KEY looks invalid (got prefix '{gemini_key[:6]}…', expected 'AIzaSy'). "
            "Go to https://aistudio.google.com/apikey and copy the correct key."
        )

    # ── Real Gemini call ──────────────────────────────────────────────────────
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_key)

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        prompt = (
            "Analyze this floor plan image. Return ONLY valid JSON (no markdown, no extra text) "
            "with this exact structure:\n"
            '{"nodes": [{"id": "n1", "label": "Lobby", "node_type": "hall", "confidence": 0.95}], '
            '"edges": [{"source": "n1", "target": "n2", "distance": 3.0, "is_door": false}]}\n'
            "node_type must be one of: hall, corridor, room, toilet, exit, stairs, elevator. "
            "Infer room purposes from the image."
        )

        response = client.models.generate_content(
            model="gemini-1.5-flash",   # Stable, widely available
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ]
        )

        raw = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        nodes = []
        for i, rn in enumerate(data.get("nodes", [])):
            nodes.append(Node(
                id=rn["id"],
                label=rn["label"],
                node_type=rn.get("node_type", "room"),
                confidence=rn.get("confidence", 0.9),
                x=100 + (i * 120),
                y=100 + (i * 60),
                width=100,
                height=100,
            ))

        edges = []
        for re_ in data.get("edges", []):
            edges.append(Edge(
                source=re_["source"],
                target=re_["target"],
                distance=re_.get("distance", 5.0),
                is_door=re_.get("is_door", False),
            ))

        if not nodes:
            return gens.mock_vision_parse(), "Gemini returned no nodes — using mock data"

        return FloorPlanData(nodes=nodes, edges=edges, width=1024, height=768), None

    except json.JSONDecodeError as e:
        return gens.mock_vision_parse(), f"Gemini response was not valid JSON: {e}"
    except Exception as e:
        err = str(e)
        # Surface common API errors clearly
        if "API_KEY_INVALID" in err or "invalid" in err.lower():
            return gens.mock_vision_parse(), (
                f"Gemini rejected the API key (invalid). "
                "Get a fresh key at https://aistudio.google.com/apikey"
            )
        if "quota" in err.lower() or "429" in err:
            return gens.mock_vision_parse(), "Gemini quota exceeded — wait a minute and try again"
        if "not found" in err.lower() or "404" in err:
            return gens.mock_vision_parse(), "Gemini model not found — check your API key region"
        return gens.mock_vision_parse(), f"Gemini error: {err}"
