import os
import json
from jinja2 import Environment, FileSystemLoader
from typing import List, Dict, Any
from app.models.schemas import FloorPlanData, Node, Edge
from app.services.graph_engine import GraphEngine

current_dir = os.path.dirname(__file__)
template_dir = os.path.join(current_dir, "..", "templates")
env = Environment(loader=FileSystemLoader(template_dir))

def generate_tactile_svg(data: FloorPlanData) -> str:
    template = env.get_template("bana_tactile.svg.jinja")
    nodes = [node.model_dump() for node in data.nodes]
    return template.render(nodes=nodes, width=data.width, height=data.height)

def generate_aria_html(engine: GraphEngine) -> str:
    template = env.get_template("screen_reader.html.jinja")
    adjacency = engine.export_adjacency_list()
    graph_nodes = {node_id: engine.graph.nodes[node_id] for node_id in engine.graph.nodes}
    return template.render(adjacency=adjacency, graph_nodes=graph_nodes)

def generate_audio_guide(path_details: List[Dict]) -> bytes:
    prompt = "Navigation Instructions:\n"
    for i, step in enumerate(path_details):
        if i == 0:
            prompt += f"Starting at {step.get('label')}. "
        else:
            prompt += f"Head towards {step.get('label')}. It is {step.get('distance_to_next', 0)} meters away. "
            if step.get('passes_door'):
                prompt += "You will pass through a door. "

        if step.get('confidence', 1.0) < 0.8:
            prompt += "Please note, the AI had low confidence detecting this area. "

    prompt += "\nYou have reached your destination."

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key or openai_key == "your_openai_api_key_here":
        return b"MOCK_MP3_AUDIO_BYTES_REPRESENTING_TTS"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=prompt
        )
        return response.content
    except Exception as e:
        print(f"TTS Error: {e}")
        return b"MOCK_MP3_AUDIO_BYTES_REPRESENTING_TTS"

def mock_vision_parse() -> FloorPlanData:
    nodes = [
        Node(id="n1", label="Main Entrance", node_type="exit", x=100, y=100, confidence=0.98, width=50, height=50),
        Node(id="n2", label="Lobby", node_type="hall", x=200, y=100, confidence=0.95, width=150, height=100),
        Node(id="n3", label="Corridor A", node_type="corridor", x=400, y=100, confidence=0.75, width=250, height=40),
        Node(id="n4", label="Accessible Toilet", node_type="toilet", x=400, y=200, confidence=0.88, width=80, height=80),
        Node(id="n5", label="Clinic Room 1", node_type="room", x=600, y=100, confidence=0.92, width=100, height=100),
    ]
    edges = [
        Edge(source="n1", target="n2", distance=2.5, is_door=True),
        Edge(source="n2", target="n3", distance=5.0, is_door=False),
        Edge(source="n3", target="n4", distance=3.0, is_door=True),
        Edge(source="n3", target="n5", distance=6.0, is_door=True),
    ]
    return FloorPlanData(nodes=nodes, edges=edges, width=800, height=600)
