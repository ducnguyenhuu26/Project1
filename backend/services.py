"""Detector boundary and grounded disposal advice."""
from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock
from typing import Protocol

from PIL import Image

KNOWLEDGE = json.loads((Path(__file__).parent / "knowledge.json").read_text(encoding="utf-8"))
MATERIALS = {item["id"]: item for item in KNOWLEDGE["materials"]}
NAMES = {0: "plastic", 1: "paper", 2: "metal"}


@dataclass
class Detection:
    class_id: int
    confidence: float | None
    bbox_xyxy: list[float]
    origin: str = "ai"

    def as_dict(self):
        return {"class_id": self.class_id, "material_id": NAMES[self.class_id],
                "confidence": self.confidence, "bbox_xyxy": self.bbox_xyxy, "origin": self.origin}


class Detector(Protocol):
    mode: str
    model_version: str | None

    def predict(self, image: Image.Image, filename: str) -> list[Detection]: ...


class DemoDetector:
    mode = "demo"
    model_version = None

    def predict(self, image: Image.Image, filename: str) -> list[Detection]:
        if filename != "wastewise-sample.png":
            return []
        sx, sy = image.width / 960, image.height / 560
        return [Detection(0, None, [93*sx, 110*sy, 298*sx, 450*sy], "illustration"),
                Detection(1, None, [364*sx, 170*sy, 656*sx, 434*sy], "illustration"),
                Detection(2, None, [710*sx, 138*sy, 866*sx, 425*sy], "illustration")]


class ModelNotReady(RuntimeError):
    pass


class RealYOLODetector:
    mode = "real"

    def __init__(self, model_path: Path, confidence: float = 0.25):
        self.model_path = model_path
        self.confidence = confidence
        self.model_version = model_path.name if model_path.is_file() else None
        self.model = None
        self._predict_lock = Lock()
        if model_path.is_file():
            from ultralytics import YOLO
            model = YOLO(str(model_path))
            if list(model.names.values()) != ["Plastic", "Paper", "Metal"]:
                raise ValueError("MODEL_PATH must be a fine-tuned Plastic/Paper/Metal checkpoint")
            self.model = model

    def predict(self, image: Image.Image, filename: str) -> list[Detection]:
        if self.model is None:
            raise ModelNotReady("Chưa có checkpoint rác 3 lớp. Hãy đặt MODEL_PATH sau khi train.")
        with self._predict_lock:
            result = self.model.predict(image, conf=self.confidence, imgsz=640, device="cpu", verbose=False)[0]
        return [Detection(int(b.cls.item()), float(b.conf.item()),
                          [float(v) for v in b.xyxy[0].tolist()]) for b in result.boxes]


def summarize(detections: list[Detection]) -> list[dict]:
    return [{"material_id": mid, "name": MATERIALS[mid]["name"],
             "estimated_count": sum(NAMES[d.class_id] == mid for d in detections)}
            for mid in NAMES.values() if any(NAMES[d.class_id] == mid for d in detections)]


def answer_chat(message: str, material_ids: list[str]) -> dict:
    query = message.strip().lower()
    if not query:
        return {"answer": "Hãy nhập câu hỏi về cách phân loại hoặc xử lý rác.", "material_id": None}
    if any(word in query for word in ["đốt", "cháy", "burn"]):
        return {"answer": KNOWLEDGE["faq"][1]["answer"], "material_id": None}
    if any(word in query for word in ["tái chế", "recycle"]):
        return {"answer": KNOWLEDGE["faq"][0]["answer"], "material_id": None}
    for item in KNOWLEDGE["materials"]:
        terms = [item["name"].lower(), item["id"], *item["examples"]]
        if any(term in query for term in terms):
            return {"answer": f"{item['name']}: {' '.join(item['do'])} Lưu ý: {item['caution']} {item['vn_tip']}", "material_id": item["id"]}
    if material_ids:
        item = MATERIALS.get(material_ids[0])
        if item:
            return {"answer": f"Với {item['name'].lower()} trong kết quả: {' '.join(item['do'])} {item['caution']}", "material_id": item["id"]}
    return {"answer": "Mình chưa có hướng dẫn được kiểm chứng cho câu hỏi này. Bạn có thể chọn Nhựa, Giấy, Kim loại, Pin, Thủy tinh hoặc Rác hữu cơ để tra cứu.", "material_id": None}
