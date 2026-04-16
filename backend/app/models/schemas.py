from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Node(BaseModel):
    id: str = Field(..., description="Unique identifier for the node")
    label: str = Field(..., description="Human-readable name of the room or area")
    node_type: Literal["room", "corridor", "exit", "toilet", "stairs", "elevator", "hall"] = Field(
        ..., description="Semantic type of the node"
    )
    x: float = Field(..., description="X coordinate representing center or entrance")
    y: float = Field(..., description="Y coordinate representing center or entrance")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence score for this detection")
    width: Optional[float] = Field(None, description="Physical width if bounding box is known")
    height: Optional[float] = Field(None, description="Physical height if bounding box is known")

class Edge(BaseModel):
    source: str = Field(..., description="Node ID of the starting room")
    target: str = Field(..., description="Node ID of the destination room")
    distance: float = Field(..., description="Distance in pixels or meters")
    is_door: bool = Field(False, description="Whether this connection passes through a door")

class FloorPlanData(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    width: float = Field(..., description="Total canvas width")
    height: float = Field(..., description="Total canvas height")

class PathRequest(BaseModel):
    source_id: str
    target_id: str
