"""WasteWise VN HTTP API."""
from io import BytesIO
import math
import os
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .services import (KNOWLEDGE, MATERIALS, TAXONOMY, TAXONOMY_ITEMS, DemoDetector,
                       ModelNotReady, RealYOLODetector, summarize)
from .recommendation_api import recommendation_router
from .environment_news import environment_news
from .chat import chat_status, grounded_chat
from .admission import RequestGuards, client_key

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
    guards = RequestGuards(int(os.getenv("MAX_CONCURRENT_INFERENCES", "2")))
    # Keep the original waste-type and chat APIs stable; v2 guidance is additive.
    app.include_router(recommendation_router)
    origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_methods=["GET", "POST"], allow_headers=["*"], expose_headers=["Retry-After"])

    def throttle(scope: str, request: Request, limit: int, window_seconds: int) -> None:
        allowed, retry_after = guards.allow(scope, client_key(request), limit, window_seconds)
        if not allowed:
            raise HTTPException(429, detail={"code": "RATE_LIMITED", "message": "Yêu cầu quá nhanh; vui lòng thử lại sau."},
                                headers={"Retry-After": str(retry_after)})

    def acquire_inference() -> None:
        if not guards.inference.acquire(blocking=False):
            raise HTTPException(503, detail={"code": "INFERENCE_BUSY", "message": "Máy chủ đang xử lý đủ số ảnh; hãy thử lại sau."},
                                headers={"Retry-After": "2"})

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

    @app.get("/api/v1/ready")
    def ready():
        """Deployment readiness: a real, loaded detector and the imported KB catalog."""
        if provider.mode != "real" or getattr(provider, "model", None) is None:
            raise HTTPException(503, detail={"code": "MODEL_NOT_READY", "message": "Real detector is not ready"})
        return {"status": "ready", "mode": "real", "model_version": provider.model_version}

    @app.get("/api/v1/news/environment")
    async def environment_articles(request: Request, refresh: bool = False):
        if refresh:
            throttle("news-refresh", request, 1, 60)
        return await run_in_threadpool(environment_news.get_news, refresh)

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

    async def read_picture(image: UploadFile) -> Image.Image:
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
        return picture

    def validate_detections(detections, width: int, height: int) -> None:
        for detection in detections:
            box = detection.bbox_xyxy
            if (len(box) != 4 or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in box)
                    or not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height)):
                raise HTTPException(502, detail={"code": "INVALID_DETECTION", "message": "Detector returned an invalid bounding box"})
            if detection.confidence is not None and (not math.isfinite(detection.confidence) or not 0 <= detection.confidence <= 1):
                raise HTTPException(502, detail={"code": "INVALID_DETECTION", "message": "Detector confidence must be between 0 and 1"})

    def scan_response(picture: Image.Image, detections, warnings: list[str]) -> dict:
        summary = summarize(detections)
        return {"mode": provider.mode, "model_version": provider.model_version,
                "image_width": picture.width, "image_height": picture.height,
                "detections": [d.as_dict() for d in detections], "summary": summary,
                "advice": [MATERIALS[row["advice_id"]] for row in summary if row.get("advice_id") in MATERIALS],
                "taxonomy_version": TAXONOMY["version"],
                "supported_category_ids": getattr(provider, "supported_category_ids",
                                                   [item["id"] for item in TAXONOMY["categories"] if item["detection_supported"]]),
                "warnings": warnings}

    @app.post("/api/v1/scans", response_model=ScanResponse)
    async def scan(request: Request, image: UploadFile = File(...)):
        acquire_inference()
        try:
            picture = await read_picture(image)
            try:
                detections = await run_in_threadpool(provider.predict, picture, image.filename or "")
            except ModelNotReady as exc:
                raise HTTPException(503, detail={"code": "MODEL_NOT_READY", "message": str(exc)})
            validate_detections(detections, picture.width, picture.height)
            warnings = (["MINH HỌA: đây không phải kết quả AI; chỉ ảnh mẫu có khung ví dụ."] if provider.mode == "demo"
                        else ["Không phát hiện được vật thể không có nghĩa là ảnh không chứa vật liệu đó."] if not detections else [])
            return scan_response(picture, detections, warnings)
        finally:
            guards.inference.release()

    @app.post("/api/v1/scans/region", response_model=ScanResponse)
    async def scan_region(request: Request, image: UploadFile = File(...), x1: float = Form(...), y1: float = Form(...),
                          x2: float = Form(...), y2: float = Form(...)):
        """Run the current detector on an explicit region; boxes return in full-image coordinates."""
        acquire_inference()
        try:
            picture = await read_picture(image)
            values = (x1, y1, x2, y2)
            if (not all(math.isfinite(value) for value in values)
                    or not (0 <= x1 < x2 <= picture.width and 0 <= y1 < y2 <= picture.height)):
                raise HTTPException(422, detail="Vùng khoanh nằm ngoài ảnh hoặc có tọa độ không hợp lệ")
            left, top, right, bottom = math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2)
            if right - left < 16 or bottom - top < 16:
                raise HTTPException(422, detail="Vùng khoanh phải rộng và cao ít nhất 16 pixel")
            if provider.mode == "demo":
                return scan_response(picture, [], ["Chế độ demo không chạy YOLO lần hai; vùng khoanh cần được xác nhận thủ công trong KB."])
            crop = picture.crop((left, top, right, bottom))
            try:
                detections = await run_in_threadpool(provider.predict, crop, image.filename or "")
            except ModelNotReady as exc:
                raise HTTPException(503, detail={"code": "MODEL_NOT_READY", "message": str(exc)})
            validate_detections(detections, crop.width, crop.height)
            for detection in detections:
                detection.bbox_xyxy = [detection.bbox_xyxy[0] + left, detection.bbox_xyxy[1] + top,
                                       detection.bbox_xyxy[2] + left, detection.bbox_xyxy[3] + top]
            return scan_response(picture, detections, [] if detections else ["YOLO vẫn chưa nhận diện được vùng này; hãy chọn đồ vật trong KB."])
        finally:
            guards.inference.release()

    class ChatRequest(BaseModel):
        message: str = Field(max_length=500)
        material_ids: list[str] = Field(default_factory=list)
        category_ids: list[str] = Field(default_factory=list)
        history: list[dict] = Field(default_factory=list, max_length=8)

    @app.get("/api/v1/chat/status")
    def get_chat_status():
        return chat_status()

    @app.post("/api/v1/chat")
    async def chat(request: Request, body: ChatRequest):
        throttle("chat", request, 10, 60)
        context = body.category_ids or body.material_ids
        history = []
        for turn in body.history:
            role = turn.get('role')
            content = turn.get('content')
            if role not in {'user', 'assistant'} or not isinstance(content, str) or len(content) > 1000:
                raise HTTPException(422, detail='Lịch sử hội thoại không hợp lệ')
            history.append({'role': role, 'content': content})
        return await grounded_chat(body.message, context, history)

    return app


app = build_app()
