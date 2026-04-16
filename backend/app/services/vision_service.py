import os
import json
import base64
from typing import Tuple, Optional
from app.models.schemas import FloorPlanData, Node, Edge
import app.services.generators as gens


def _resolve_overlaps(nodes: list, width: int, height: int) -> list:
    """Helper function to cleanly pass through nodes (or later add collision logic)"""
    return nodes

def parse_floorplan_real(image_path: str) -> Tuple[FloorPlanData, Optional[str]]:
    """
    Parse a floor plan image using Groq vision (free tier, no quota issues).
    Returns (FloorPlanData, error_message).
    Falls back to mock data on any failure.
    """
    groq_key = os.environ.get("GROQ_API_KEY", "")

    if not groq_key or groq_key == "your_groq_api_key_here":
        return gens.mock_vision_parse(), (
            "GROQ_API_KEY not set — using mock floor plan. "
            "Get a free key at https://console.groq.com (no credit card needed)"
        )

    try:
        import httpx

        # Read and encode image as base64
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Detect mime type from extension
        ext = os.path.splitext(image_path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"

        prompt = (
            "You are a highly specialised floor plan AI for a low-vision accessibility system.\n"
            "Examine this floor plan image and extract all distinct rooms, corridors, and POIs as completely tight bounding boxes.\n"
            "Return ONLY valid JSON (no markdown, no intro/outro).\n\n"
            "Use EXACTLY this structure:\n"
            "{\n"
            '  "canvas_width": 1000,\n'
            '  "canvas_height": 1000,\n'
            '  "nodes": [\n'
            '    {"id": "n1", "label": "Entrance Lobby", "node_type": "hall", "confidence": 0.95,\n'
            '     "x": 120, "y": 80, "width": 180, "height": 120}\n'
            "  ],\n"
            '  "edges": [\n'
            '    {"source": "n1", "target": "n2", "distance": 3.5, "is_door": true}\n'
            "  ]\n"
            "}\n\n"
            "CRITICAL RULES:\n"
            "- 'x' and 'y' must represent the exact TOP-LEFT corner of the room bounding box on the original map. DO NOT output the central point!\n"
            "- 'width' and 'height' track the box's size extending rightwards and downwards from (x, y).\n"
            "- Normalize all pixel coordinates strictly to a 0 to 1000 coordinate plane.\n"
            "- Rooms MUST NOT overlap improperly. Fit the boundary boxes correctly to match the image walls.\n"
            "- Create edges for every pair of directly connected rooms ('distance' is your real-meter estimate).\n"
            "- Node_type: hall, corridor, room, toilet, exit, stairs, elevator, balcony, etc.\n"
            "- Label every room, corridor, exit, etc."
        )

        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{image_b64}"
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
            },
            timeout=30.0,
        )

        if response.status_code == 401:
            return gens.mock_vision_parse(), (
                "Groq rejected the API key (401). "
                "Get a fresh key at https://console.groq.com → API Keys"
            )
        if response.status_code == 429:
            return gens.mock_vision_parse(), "Groq rate limit hit — wait a moment and try again"
        if response.status_code != 200:
            return gens.mock_vision_parse(), f"Groq API error {response.status_code}: {response.text[:200]}"

        content = response.json()["choices"][0]["message"]["content"]
        raw = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        # Use canvas dimensions from Groq response, or sensible defaults
        canvas_w = int(data.get("canvas_width",  1000))
        canvas_h = int(data.get("canvas_height", 750))

        # Normalise node_type — Groq sometimes returns types not in our schema
        VALID_TYPES = {"hall", "corridor", "room", "toilet", "exit", "stairs", "elevator"}
        TYPE_MAP = {
            "entrance":    "exit",
            "entry":       "exit",
            "lobby":       "hall",
            "foyer":       "hall",
            "hallway":     "corridor",
            "passage":     "corridor",
            "bathroom":    "toilet",
            "restroom":    "toilet",
            "wc":          "toilet",
            "staircase":   "stairs",
            "stairwell":   "stairs",
            "stair":       "stairs",
            "lift":        "elevator",
            "office":      "room",
            "meeting":     "room",
            "conference":  "room",
            "storage":     "room",
            "kitchen":     "room",
            "reception":   "hall",
            "atrium":      "hall",
            "courtyard":   "hall",
            "balcony":     "room",
            "terrace":     "room",
            "waiting":     "hall",
            "lounge":      "hall",
            "ward":        "room",
            "clinic":      "room",
            "lab":         "room",
            "pharmacy":    "room",
            "shop":        "room",
            "store":       "room",
            "canteen":     "room",
            "cafeteria":   "room",
        }

        def normalise_type(raw: str) -> str:
            t = raw.lower().strip()
            if t in VALID_TYPES:
                return t
            if t in TYPE_MAP:
                return TYPE_MAP[t]
            # Partial match fallback
            for key, val in TYPE_MAP.items():
                if key in t or t in key:
                    return val
            return "room"  # safe default

        raw_nodes = []
        for i, rn in enumerate(data.get("nodes", [])):
            raw_nodes.append({
                "id":         rn["id"],
                "label":      rn["label"],
                "node_type":  normalise_type(rn.get("node_type", "room")),
                "confidence": float(rn.get("confidence", 0.9)),
                "x":          float(rn.get("x",      50  + (i % 5) * 180)),
                "y":          float(rn.get("y",      50  + (i // 5) * 150)),
                "width":      float(rn.get("width",  140)),
                "height":     float(rn.get("height", 100)),
            })

        raw_nodes = _resolve_overlaps(raw_nodes, canvas_w, canvas_h)
        nodes = [Node(**rn) for rn in raw_nodes]

        edges = []
        for re_ in data.get("edges", []):
            edges.append(Edge(
                source=re_["source"],
                target=re_["target"],
                distance=re_.get("distance", 5.0),
                is_door=re_.get("is_door", False),
            ))

        if not nodes:
            return gens.mock_vision_parse(), "Groq returned no nodes — using mock data"

        return FloorPlanData(nodes=nodes, edges=edges, width=canvas_w, height=canvas_h), None

    except json.JSONDecodeError as e:
        return gens.mock_vision_parse(), f"Groq response was not valid JSON: {e}"
    except httpx.TimeoutException:
        return gens.mock_vision_parse(), "Groq request timed out (30 s) — try again"
    except Exception as e:
        return gens.mock_vision_parse(), f"Groq error: {str(e)[:200]}"