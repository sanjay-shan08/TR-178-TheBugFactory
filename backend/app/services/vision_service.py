import os
import base64
import json
from typing import Optional
from app.models.schemas import FloorPlanData, Node, Edge
import app.services.generators as gens

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def call_sam_for_geometry(image_path: str) -> dict:
    return {"status": "mocked", "features": []}

def parse_floorplan_real(image_path: str) -> FloorPlanData:
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key or openai_key == "your_openai_api_key_here":
        print("Using MVP mock vision parse. Supply OPENAI_API_KEY for real inference.")
        return gens.mock_vision_parse()
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        base64_image = encode_image(image_path)
        
        prompt = '''
        Analyze this floor plan. Give me a JSON list of "nodes" (rooms/corridors/pois) and "edges" (connections between nodes).
        Format:
        {
          "nodes": [{"id": "n1", "label": "Lobby", "node_type": "hall", "confidence": 0.95}],
          "edges": [{"source": "n1", "target": "n2", "distance": 3.0, "is_door": false}]
        }
        Only output the JSON. Infer room purposes (toilets, exits, stairs).
        '''
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        
        raw_json = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw_json)
        
        sam_data = call_sam_for_geometry(image_path)
        
        nodes = []
        for i, raw_node in enumerate(data.get("nodes", [])):
            nodes.append(Node(
                id=raw_node["id"],
                label=raw_node["label"],
                node_type=raw_node.get("node_type", "room"),
                confidence=raw_node.get("confidence", 0.9),
                x=100 + (i * 100),
                y=100 + (i * 50),
                width=100,
                height=100
            ))
            
        edges = []
        for raw_edge in data.get("edges", []):
            edges.append(Edge(
                source=raw_edge["source"],
                target=raw_edge["target"],
                distance=raw_edge.get("distance", 5.0),
                is_door=raw_edge.get("is_door", False)
            ))
            
        return FloorPlanData(nodes=nodes, edges=edges, width=1024, height=768)

    except Exception as e:
        print(f"Error during Vision parse: {e}")
        return gens.mock_vision_parse()
