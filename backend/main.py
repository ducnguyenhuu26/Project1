"""WasteWise VN HTTP API."""
from io import BytesIO
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .services import (KNOWLEDGE, MATERIALS, TAXONOMY, TAXONOMY_ITEMS, DemoDetector,
                       ModelNotReady, RealYOLODetector, answer_chat, summarize)
from .recommendation_api import recommendation_router

load_dotenv()


class DetectionResponse(BaseModel):
    id: str
    class_id: int
    category_id: str | None
    label: str
    material_id: str | None
    advice_id: str | None = None
    confidence: float | None
    bbox_xyxy: list[float]
    origin: str
    status: str
    model_version: str | None


class SummaryResponse(BaseModel):
    category_id: str
    material_id: str
    advice_id: str | None = None
    name: str
    estimated_count: int


class ScanResponse(BaseModel):
    mode: str
    model_version: str | None
    taxonomy_version: str
    supported_category_ids: list[str]
    image_width: int
    image_height: int
    detections: list[DetectionResponse]
    summary: list[SummaryResponse]
    advice: list[dict]
    warnings: list[str]


def build_app(mode: str | None = None, detector=None) -> FastAPI:
    selected_mode = mode or os.getenv("DETECTOR_MODE", "demo")
    if selected_mode not in {"demo", "real"}:
        raise ValueError("DETECTOR_MODE must be demo or real")
    provider = detector or (DemoDetector() if selected_mode == "demo" else RealYOLODetector(
        Path(os.getenv("MODEL_PATH", "weights/best.pt")), float(os.getenv("CONFIDENCE", "0.25")),
        os.getenv("INFERENCE_DEVICE", "cpu")))
    app = FastAPI(title="WasteWise VN", version="0.1.0")
    app.state.detector = provider
    # Keep the original waste-type and chat APIs stable; v2 guidance is additive.
    app.include_router(recommendation_router)
    app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.get("/api/v1/health")
    def health():
        model_status = "ready" if provider.mode == "demo" else (
            "invalid_manifest" if getattr(provider, "model_error", None) else
            "ready" if getattr(provider, "model", None) is not None else "missing_checkpoint")
        return {"status": "ok", "mode": provider.mode,
                "model_status": model_status,
                "model_version": provider.model_version,
                "supported_category_ids": getattr(provider, "supported_category_ids",
                    [item["id"] for item in TAXONOMY["categories"] if item["detection_supported"]])}

    @app.get("/api/v1/waste-types")
    def waste_types():
        return {"materials": KNOWLEDGE["materials"], "faq": KNOWLEDGE["faq"],
                "updated_at": KNOWLEDGE["updated_at"], "sources": KNOWLEDGE["sources"],
                "taxonomy_version": TAXONOMY["version"], "categories": TAXONOMY["categories"]}

    @app.get("/api/v1/waste-types/{material_id}")
    def waste_type(material_id: str):
        if material_id not in MATERIALS:
            raise HTTPException(404, detail="Không có mục tra cứu này")
        return MATERIALS[material_id]

    @app.post("/api/v1/scans", response_model=ScanResponse)
    async def scan(image: UploadFile = File(...)):
        if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(415, detail="Chỉ hỗ trợ JPEG, PNG hoặc WebP")
        max_bytes = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
        data = await image.read(max_bytes + 1)
        if not data or len(data) > max_bytes:
            raise HTTPException(413, detail="Ảnh rỗng hoặc vượt quá giới hạn dung lượng")
        try:
            with Image.open(BytesIO(data)) as raw:
                raw.verify()
            with Image.open(BytesIO(data)) as raw:
                if raw.width * raw.height > 24_000_000:
                    raise HTTPException(413, detail="Ảnh vượt quá 24 megapixel")
                picture = ImageOps.exif_transpose(raw).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(422, detail="Không đọc được ảnh")
        try:
            detections = await run_in_threadpool(provider.predict, picture, image.filename or "")
        except ModelNotReady as exc:
            raise HTTPException(503, detail={"code": "MODEL_NOT_READY", "message": str(exc)})
        for detection in detections:
            box = detection.bbox_xyxy
            if (len(box) != 4 or any(not isinstance(value, (int, float)) for value in box)
                    or not (0 <= box[0] < box[2] <= picture.width and 0 <= box[1] < box[3] <= picture.height)):
                raise HTTPException(502, detail={"code": "INVALID_DETECTION", "message": "Detector returned an invalid bounding box"})
            if detection.confidence is not None and not 0 <= detection.confidence <= 1:
                raise HTTPException(502, detail={"code": "INVALID_DETECTION", "message": "Detector confidence must be between 0 and 1"})
        summary = summarize(detections)
        warnings = (["MINH HỌA: đây không phải kết quả AI; chỉ ảnh mẫu có khung ví dụ."] if provider.mode == "demo"
                    else ["Không phát hiện được vật thể không có nghĩa là ảnh không chứa vật liệu đó."] if not detections else [])
        return {"mode": provider.mode, "model_version": provider.model_version,
                "image_width": picture.width, "image_height": picture.height,
                "detections": [d.as_dict() for d in detections], "summary": summary,
                "advice": [MATERIALS[row["advice_id"]] for row in summary if row.get("advice_id") in MATERIALS],
                "taxonomy_version": TAXONOMY["version"],
                "supported_category_ids": getattr(provider, "supported_category_ids",
                                                   [item["id"] for item in TAXONOMY["categories"] if item["detection_supported"]]),
                "warnings": warnings}

    class ChatRequest(BaseModel):
        message: str = Field(max_length=500)
        material_ids: list[str] = Field(default_factory=list)
        category_ids: list[str] = Field(default_factory=list)

    @app.post("/api/v1/chat")
    def chat(request: ChatRequest):
        context = request.category_ids or request.material_ids
        return {**answer_chat(request.message, context), "grounded_in": "WasteWise curated knowledge base"}

    return app


app = build_app()
