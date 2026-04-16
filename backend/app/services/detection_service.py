import os
import base64
import io
from typing import List
from PIL import Image

from app.models.detection_schemas import (
    Detection, BoundingBox, DetectionResponse, OCRResponse
)

# Object warning config — label → (warning_level, voice_message)
OBJECT_CONFIG = {
    "person":      ("high",   "Person ahead, move carefully"),
    "chair":       ("high",   "Chair obstacle ahead"),
    "stairs":      ("high",   "Stairs detected, proceed with caution"),
    "door":        ("medium", "Door on your path"),
    "elevator":    ("medium", "Elevator nearby"),
    "lift":        ("medium", "Lift detected on your left"),
    "exit":        ("medium", "Emergency exit detected"),
    "table":       ("high",   "Table ahead, go around"),
    "couch":       ("medium", "Furniture ahead"),
    "bed":         ("medium", "Bed obstacle ahead"),
    "toilet":      ("low",    "Washroom detected"),
    "sink":        ("low",    "Sink detected"),
    "tv":          ("low",    "Screen detected on wall"),
    "laptop":      ("low",    "Laptop on surface nearby"),
    "backpack":    ("medium", "Bag on floor ahead"),
    "bottle":      ("low",    "Small object on surface"),
    "clock":       ("low",    "Clock on wall"),
    "potted plant":("medium", "Plant obstacle"),
}

# ── Model caches ─────────────────────────────────────────────────────────────

_yolo_model = None
_ocr_reader = None


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO
        _yolo_model = YOLO("yolov8n.pt")   # Nano — smallest & fastest
    return _yolo_model


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


# ── Image helpers ─────────────────────────────────────────────────────────────

def _decode_image(base64_str: str) -> Image.Image:
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    return Image.open(io.BytesIO(base64.b64decode(base64_str)))


# ── Detection ─────────────────────────────────────────────────────────────────

def run_detection(base64_image: str) -> DetectionResponse:
    """
    Run YOLOv8 Nano object detection.
    Falls back to mock if DETECTION_MODE=mock or if ultralytics is unavailable.
    """
    if os.getenv("DETECTION_MODE", "mock") == "mock":
        return _mock_detection()

    try:
        img = _decode_image(base64_image)
        w, h = img.size
        model = _get_yolo()
        results = model(img, verbose=False)[0]

        detections: List[Detection] = []
        for box in results.boxes:
            label = results.names[int(box.cls)].lower()
            confidence = round(float(box.conf), 2)
            if confidence < 0.4:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            warning, voice = OBJECT_CONFIG.get(label, ("low", f"{label} detected"))
            detections.append(Detection(
                label=label,
                confidence=confidence,
                bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                warning_level=warning,
                voice_message=voice,
            ))

        # Sort: high warnings first
        priority = {"high": 0, "medium": 1, "low": 2}
        detections.sort(key=lambda d: priority.get(d.warning_level, 3))

        return DetectionResponse(
            detections=detections,
            frame_width=w,
            frame_height=h,
            mode="real",
        )

    except Exception as e:
        print(f"[Detection] Error: {e} — falling back to mock")
        return _mock_detection()


def _mock_detection() -> DetectionResponse:
    return DetectionResponse(
        detections=[
            Detection(
                label="door",
                confidence=0.91,
                bbox=BoundingBox(x1=220, y1=80, x2=420, y2=420),
                warning_level="medium",
                voice_message="Door on your path",
            ),
            Detection(
                label="chair",
                confidence=0.78,
                bbox=BoundingBox(x1=30, y1=310, x2=160, y2=460),
                warning_level="high",
                voice_message="Chair obstacle ahead",
            ),
        ],
        frame_width=640,
        frame_height=480,
        mode="mock",
    )


# ── OCR ───────────────────────────────────────────────────────────────────────

def run_ocr(base64_image: str) -> OCRResponse:
    """
    Run EasyOCR to read indoor signage.
    Falls back to mock if DETECTION_MODE=mock or if easyocr is unavailable.
    """
    if os.getenv("DETECTION_MODE", "mock") == "mock":
        return _mock_ocr()

    try:
        img = _decode_image(base64_image)
        reader = _get_ocr()
        results = reader.readtext(img)

        texts = [text for (_, text, conf) in results if conf > 0.4]
        combined = ". ".join(texts) if texts else ""

        return OCRResponse(texts=texts, combined=combined, mode="real")

    except Exception as e:
        print(f"[OCR] Error: {e} — falling back to mock")
        return _mock_ocr()


def _mock_ocr() -> OCRResponse:
    return OCRResponse(
        texts=["Lab 401", "Biotechnology Department", "Emergency Exit →"],
        combined="Lab 401. Biotechnology Department. Emergency Exit →",
        mode="mock",
    )
