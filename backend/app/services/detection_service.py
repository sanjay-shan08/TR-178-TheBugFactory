"""
detection_service.py

Uses Groq vision (llama-4-scout) to analyse live camera frames for:
  - Object / obstacle detection  → run_detection()
  - Indoor sign OCR              → run_ocr()

Falls back to mock data when:
  - DETECTION_MODE=mock
  - GROQ_API_KEY is missing
  - Groq returns an error
"""

import os
import json
import base64
import httpx
from app.models.detection_schemas import (
    Detection, BoundingBox, DetectionResponse, OCRResponse,
)

# ── Warning priority map ──────────────────────────────────────────────────────
WARN_MAP = {
    "person":        "high",
    "chair":         "high",
    "stairs":        "high",
    "step":          "high",
    "table":         "high",
    "door":          "medium",
    "elevator":      "medium",
    "lift":          "medium",
    "exit":          "medium",
    "couch":         "medium",
    "sofa":          "medium",
    "furniture":     "medium",
    "wall":          "medium",
    "plant":         "medium",
    "bin":           "medium",
    "trolley":       "high",
    "wheelchair":    "medium",
    "toilet":        "low",
    "sink":          "low",
    "screen":        "low",
    "laptop":        "low",
    "bag":           "medium",
    "bottle":        "low",
}

PRIORITY = {"high": 0, "medium": 1, "low": 2}

# ── Groq helper ───────────────────────────────────────────────────────────────

def _groq_vision(prompt: str, base64_image: str, mime: str = "image/jpeg") -> str | None:
    """Send one image + prompt to Groq vision. Returns raw text or None on error."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    try:
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{base64_image}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                "temperature": 0.1,
                "max_tokens": 512,
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Groq vision] {e}")
    return None


def _strip_b64_header(data: str) -> tuple[str, str]:
    """Return (base64_data, mime_type) stripping any data-URI header."""
    if data.startswith("data:"):
        header, data = data.split(",", 1)
        mime = header.split(":")[1].split(";")[0]
    else:
        mime = "image/jpeg"
    return data, mime


# ── Detection ─────────────────────────────────────────────────────────────────

_DETECT_PROMPT = """\
You are an indoor obstacle detection AI for a visually impaired navigation assistant.
Analyse the camera frame and identify every obstacle or object relevant to safe walking.

Return ONLY valid JSON (no markdown) in this exact structure:
{
  "objects": [
    {
      "label": "chair",
      "confidence": 0.92,
      "warning_level": "high",
      "position": "left",
      "bbox": {"x1": 50, "y1": 200, "x2": 220, "y2": 420}
    }
  ],
  "frame_width": 640,
  "frame_height": 480
}

Rules:
- bbox coordinates must be pixel values within the frame dimensions
- warning_level: "high" (blocks path), "medium" (nearby hazard), "low" (informational)
- position: "left", "center", or "right" based on horizontal centre of bbox
- Only include objects with confidence >= 0.4
- If the path is completely clear, return an empty objects array
"""

def run_detection(base64_image: str) -> DetectionResponse:
    if os.getenv("DETECTION_MODE", "mock") == "mock":
        return _mock_detection()

    b64, mime = _strip_b64_header(base64_image)
    raw = _groq_vision(_DETECT_PROMPT, b64, mime)

    if raw:
        try:
            raw_clean = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_clean)
            fw = int(data.get("frame_width", 640))
            fh = int(data.get("frame_height", 480))

            detections = []
            for obj in data.get("objects", []):
                label      = str(obj.get("label", "object")).lower()
                confidence = float(obj.get("confidence", 0.8))
                warn       = obj.get("warning_level") or WARN_MAP.get(label, "medium")
                bbox_raw   = obj.get("bbox", {})
                bbox = BoundingBox(
                    x1=float(bbox_raw.get("x1", 0)),
                    y1=float(bbox_raw.get("y1", 0)),
                    x2=float(bbox_raw.get("x2", fw // 2)),
                    y2=float(bbox_raw.get("y2", fh // 2)),
                )
                pos = obj.get("position", "ahead")
                detections.append(Detection(
                    label=label,
                    confidence=confidence,
                    bbox=bbox,
                    warning_level=warn,
                    voice_message=f"{label} {pos}",
                ))

            detections.sort(key=lambda d: PRIORITY.get(d.warning_level, 3))
            return DetectionResponse(detections=detections, frame_width=fw, frame_height=fh, mode="real")

        except Exception as e:
            print(f"[Detection] Parse error: {e} — falling back to mock")

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

_OCR_PROMPT = """\
You are an indoor sign reader for a visually impaired navigation assistant.
Read every piece of visible text in this image — room numbers, department signs,
exit labels, warning signs, door labels, and any other signage.

Return ONLY valid JSON (no markdown):
{
  "texts": ["Lab 401", "Emergency Exit →", "Radiology Department"]
}

If no text is visible, return: {"texts": []}
"""

def run_ocr(base64_image: str) -> OCRResponse:
    if os.getenv("DETECTION_MODE", "mock") == "mock":
        return _mock_ocr()

    b64, mime = _strip_b64_header(base64_image)
    raw = _groq_vision(_OCR_PROMPT, b64, mime)

    if raw:
        try:
            raw_clean = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_clean)
            texts    = [str(t) for t in data.get("texts", [])]
            combined = ". ".join(texts)
            return OCRResponse(texts=texts, combined=combined, mode="real")
        except Exception as e:
            print(f"[OCR] Parse error: {e} — falling back to mock")

    return _mock_ocr()


def _mock_ocr() -> OCRResponse:
    return OCRResponse(
        texts=["Lab 401", "Biotechnology Department", "Emergency Exit →"],
        combined="Lab 401. Biotechnology Department. Emergency Exit →",
        mode="mock",
    )
