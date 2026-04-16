from pydantic import BaseModel
from typing import List, Optional


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: BoundingBox
    warning_level: str   # "high" | "medium" | "low"
    voice_message: str


class DetectionResponse(BaseModel):
    detections: List[Detection]
    frame_width: int
    frame_height: int
    mode: str  # "real" | "mock"


class OCRResponse(BaseModel):
    texts: List[str]
    combined: str
    mode: str


class SensorSnapshot(BaseModel):
    steps: int
    heading_degrees: Optional[float] = None
    turn_direction: Optional[str] = None  # "left" | "right" | "straight"
    voice_instruction: Optional[str] = None
