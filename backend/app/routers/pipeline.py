from fastapi import APIRouter, HTTPException, File, UploadFile
import tempfile
import os
from pydantic import BaseModel
from typing import Optional

from app.models.schemas import FloorPlanData, PathRequest
from app.services.graph_engine import GraphEngine
from app.services.vision_service import parse_floorplan_real
import app.services.generators as gens

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

class PipelineResponse(BaseModel):
    tactile_svg: str
    aria_html: str
    path_narrative: Optional[str] = None
    tts_audio_url: Optional[str] = None

@router.post("/process-mock", response_model=PipelineResponse)
async def process_mock_floorplan(source: str = "n1", target: str = "n4"):
    floor_data = gens.mock_vision_parse()

    engine = GraphEngine(floor_data)
    path = engine.find_shortest_path(source, target)

    if not path:
        raise HTTPException(status_code=404, detail="No accessible path found between source and target.")

    path_details = engine.get_path_details(path)

    svg_output = gens.generate_tactile_svg(floor_data)
    html_output = gens.generate_aria_html(engine)
    audio_bytes = gens.generate_audio_guide(path_details)

    narrative = f"Path found with {len(path)} steps crossing {sum(d.get('distance_to_next', 0) for d in path_details if 'distance_to_next' in d)} meters."

    return PipelineResponse(
        tactile_svg=svg_output,
        aria_html=html_output,
        path_narrative=narrative,
        tts_audio_url="/api/mock-audio.mp3"
    )

@router.post("/process", response_model=PipelineResponse)
async def process_real_floorplan(file: UploadFile = File(...), source: str = "n1", target: str = "n4"):
    suffix = os.path.splitext(file.filename or "plan.png")[1] or ".png"
    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        floor_data = parse_floorplan_real(tmp_path)

        engine = GraphEngine(floor_data)
        
        valid_nodes = [n.id for n in floor_data.nodes]
        source_id = source if source in valid_nodes else (valid_nodes[0] if valid_nodes else "n1")
        target_id = target if target in valid_nodes else (valid_nodes[-1] if valid_nodes else "n4")
        
        path = engine.find_shortest_path(source_id, target_id)

        if not path:
            raise HTTPException(status_code=404, detail="No accessible path found between source and target.")

        path_details = engine.get_path_details(path)

        svg_output = gens.generate_tactile_svg(floor_data)
        html_output = gens.generate_aria_html(engine)
        audio_bytes = gens.generate_audio_guide(path_details)
        
        narrative = f"Path found with {len(path)} steps crossing {sum(d.get('distance_to_next', 0) for d in path_details if 'distance_to_next' in d)} meters."

        return PipelineResponse(
            tactile_svg=svg_output,
            aria_html=html_output,
            path_narrative=narrative,
            tts_audio_url="/api/mock-audio.mp3"
        )
    finally:
        os.unlink(tmp_path)
