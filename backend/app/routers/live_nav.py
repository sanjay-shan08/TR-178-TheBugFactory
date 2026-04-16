from fastapi import APIRouter
from pydantic import BaseModel

from app.services.detection_service import run_detection, run_ocr
from app.models.detection_schemas import DetectionResponse, OCRResponse

router = APIRouter(prefix="/live-nav", tags=["Live Navigation"])


class ImageFrame(BaseModel):
    image: str  # base64-encoded image (data URI or raw base64)


@router.post("/detect", response_model=DetectionResponse)
async def detect_objects(frame: ImageFrame):
    """
    Accepts a base64 camera frame and returns detected objects with
    bounding boxes, warning levels, and voice messages.
    Uses YOLOv8 Nano when DETECTION_MODE=real, mock data otherwise.
    """
    return run_detection(frame.image)


@router.post("/ocr", response_model=OCRResponse)
async def read_text(frame: ImageFrame):
    """
    Accepts a base64 camera frame and returns OCR-detected text
    from room signs, exit labels, and department boards.
    Uses EasyOCR when DETECTION_MODE=real, mock data otherwise.
    """
    return run_ocr(frame.image)


@router.get("/status")
async def nav_status():
    """Returns the current detection mode (real or mock)."""
    import os
    mode = os.getenv("DETECTION_MODE", "mock")
    return {
        "detection_mode": mode,
        "yolo_available": _check_import("ultralytics"),
        "ocr_available": _check_import("easyocr"),
    }


def _check_import(package: str) -> bool:
    try:
        __import__(package)
        return True
    except ImportError:
        return False
