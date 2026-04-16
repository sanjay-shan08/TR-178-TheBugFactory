from fastapi import APIRouter, HTTPException, File, UploadFile
import tempfile
import os
from pydantic import BaseModel
from typing import Optional

from app.services.graph_engine import GraphEngine
from app.services.vision_service import parse_floorplan_real
import app.services.generators as gens

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


class PipelineResponse(BaseModel):
    tactile_svg: str
    aria_html: str
    path_narrative: Optional[str] = None
    vision_error: Optional[str] = None   # Set when Groq vision failed (fell back to mock)
    tts_text: Optional[str] = None       # Spoken by browser Web Speech API


@router.post("/process-mock", response_model=PipelineResponse)
async def process_mock_floorplan(source: str = "n1", target: str = "n4"):
    floor_data = gens.mock_vision_parse()
    engine = GraphEngine(floor_data)
    path = engine.find_shortest_path(source, target)

    if not path:
        raise HTTPException(status_code=404, detail="No accessible path found between source and target.")

    path_details = engine.get_path_details(path)
    total_dist = sum(d.get('distance_to_next', 0) for d in path_details if 'distance_to_next' in d)

    return PipelineResponse(
        tactile_svg=gens.generate_tactile_svg(floor_data),
        aria_html=gens.generate_aria_html(engine),
        path_narrative=f"Path found with {len(path)} steps crossing {total_dist} metres.",
        tts_text=gens.generate_navigation_text(path_details),
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
            return PipelineResponse(
                tactile_svg=gens.generate_tactile_svg(floor_data),
                aria_html=gens.generate_aria_html(engine),
                path_narrative="Warning: No connected path could be found between the requested rooms. Map structure is shown above." + (" ⚠️ (mock data)" if vision_err else ""),
                vision_error=vision_err,
                tts_text="",
            )

        path_details = engine.get_path_details(path)
        total_dist = sum(d.get('distance_to_next', 0) for d in path_details if 'distance_to_next' in d)

        return PipelineResponse(
            tactile_svg=gens.generate_tactile_svg(floor_data),
            aria_html=gens.generate_aria_html(engine),
            path_narrative=f"Path found with {len(path)} steps crossing {total_dist} metres."
                           + (" ⚠️ (mock data)" if vision_err else ""),
            vision_error=vision_err,
            tts_text=gens.generate_navigation_text(path_details),
        )

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
