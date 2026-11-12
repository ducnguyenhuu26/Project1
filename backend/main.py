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

from .services import KNOWLEDGE, MATERIALS, DemoDetector, ModelNotReady, RealYOLODetector, answer_chat, summarize

load_dotenv()


def build_app(mode: str | None = None, detector=None) -> FastAPI:
    selected_mode = mode or os.getenv("DETECTOR_MODE", "demo")
    if selected_mode not in {"demo", "real"}:
        raise ValueError("DETECTOR_MODE must be demo or real")
    provider = detector or (DemoDetector() if selected_mode == "demo" else RealYOLODetector(
        Path(os.getenv("MODEL_PATH", "weights/best.pt")), float(os.getenv("CONFIDENCE", "0.25")),
        os.getenv("INFERENCE_DEVICE", "cpu")))
    app = FastAPI(title="WasteWise VN", version="0.1.0")
    app.state.detector = provider
    app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                       allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "mode": provider.mode,
                "model_status": "ready" if provider.mode == "demo" or provider.model_version else "missing_checkpoint",
                "model_version": provider.model_version}

    @app.get("/api/v1/waste-types")
    def waste_types():
        return {"materials": KNOWLEDGE["materials"], "faq": KNOWLEDGE["faq"],
                "updated_at": KNOWLEDGE["updated_at"], "sources": KNOWLEDGE["sources"]}

    @app.get("/api/v1/waste-types/{material_id}")
    def waste_type(material_id: str):
        if material_id not in MATERIALS:
            raise HTTPException(404, detail="Không có mục tra cứu này")
        return MATERIALS[material_id]

    @app.post("/api/v1/scans")
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
        summary = summarize(detections)
        warnings = (["MINH HỌA: đây không phải kết quả AI; chỉ ảnh mẫu có khung ví dụ."] if provider.mode == "demo"
                    else ["Không phát hiện được vật thể không có nghĩa là ảnh không chứa vật liệu đó."] if not detections else [])
        return {"mode": provider.mode, "model_version": provider.model_version,
                "image_width": picture.width, "image_height": picture.height,
                "detections": [d.as_dict() for d in detections], "summary": summary,
                "advice": [MATERIALS[row["material_id"]] for row in summary], "warnings": warnings}

    class ChatRequest(BaseModel):
        message: str = Field(max_length=500)
        material_ids: list[str] = Field(default_factory=list)

    @app.post("/api/v1/chat")
    def chat(request: ChatRequest):
        return {**answer_chat(request.message, request.material_ids), "grounded_in": "WasteWise curated knowledge base"}

    return app


app = build_app()
