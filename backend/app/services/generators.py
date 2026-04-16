import os
import httpx
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict
from app.models.schemas import FloorPlanData, Node, Edge
from app.services.graph_engine import GraphEngine

current_dir = os.path.dirname(__file__)
template_dir = os.path.join(current_dir, "..", "templates")
env = Environment(loader=FileSystemLoader(template_dir))

# ── ElevenLabs config ─────────────────────────────────────────────────────────
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
ELEVENLABS_MODEL    = "eleven_turbo_v2"   # Fastest, lowest latency


def generate_tactile_svg(data: FloorPlanData) -> str:
    template = env.get_template("bana_tactile.svg.jinja")
    nodes = [node.model_dump() for node in data.nodes]
    return template.render(nodes=nodes, width=data.width, height=data.height)


def generate_aria_html(engine: GraphEngine) -> str:
    template = env.get_template("screen_reader.html.jinja")
    adjacency = engine.export_adjacency_list()
    graph_nodes = {node_id: engine.graph.nodes[node_id] for node_id in engine.graph.nodes}
    return template.render(adjacency=adjacency, graph_nodes=graph_nodes)


def generate_navigation_text(path_details: List[Dict]) -> str:
    """Builds the plain-text navigation script (used as input for ElevenLabs TTS)."""
    script = "Navigation instructions. "
    for i, step in enumerate(path_details):
        if i == 0:
            script += f"Starting at {step.get('label')}. "
        else:
            dist = step.get('distance_to_next', 0)
            script += f"Head towards {step.get('label')}. It is {dist} metres away. "
            if step.get('passes_door'):
                script += "You will pass through a door. "
        if step.get('confidence', 1.0) < 0.8:
            script += "Note: AI confidence is low for this area. "
    script += "You have reached your destination."
    return script


def generate_audio_elevenlabs(text: str) -> bytes:
    """
    Calls ElevenLabs TTS API and returns MP3 audio bytes.
    Falls back to empty bytes if ELEVENLABS_API_KEY is not set.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key or api_key == "your_elevenlabs_api_key_here":
        return b""

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
        response.raise_for_status()
        return response.content

    except Exception as e:
        print(f"[ElevenLabs] Error: {e}")
        return b""


def mock_vision_parse() -> FloorPlanData:
    nodes = [
        Node(id="n1", label="Main Entrance",     node_type="exit",     x=100, y=100, confidence=0.98, width=50,  height=50),
        Node(id="n2", label="Lobby",             node_type="hall",     x=200, y=100, confidence=0.95, width=150, height=100),
        Node(id="n3", label="Corridor A",        node_type="corridor", x=400, y=100, confidence=0.75, width=250, height=40),
        Node(id="n4", label="Accessible Toilet", node_type="toilet",   x=400, y=200, confidence=0.88, width=80,  height=80),
        Node(id="n5", label="Clinic Room 1",     node_type="room",     x=600, y=100, confidence=0.92, width=100, height=100),
    ]
    edges = [
        Edge(source="n1", target="n2", distance=2.5, is_door=True),
        Edge(source="n2", target="n3", distance=5.0, is_door=False),
        Edge(source="n3", target="n4", distance=3.0, is_door=True),
        Edge(source="n3", target="n5", distance=6.0, is_door=True),
    ]
    return FloorPlanData(nodes=nodes, edges=edges, width=800, height=600)
