"""Versioned taxonomy, model adapters, and grounded waste advice."""
from dataclasses import dataclass
import json
from pathlib import Path
from threading import Lock
from typing import Protocol

from PIL import Image

ROOT = Path(__file__).parent
KNOWLEDGE = json.loads((ROOT / "knowledge.json").read_text(encoding="utf-8"))
TAXONOMY = json.loads((ROOT / "taxonomy.json").read_text(encoding="utf-8"))
TAXONOMY_ITEMS = {item["id"]: item for item in TAXONOMY["categories"]}
MATERIALS = {item["id"]: item for item in KNOWLEDGE["materials"]}
LEGACY_CLASS_MAP = {0: "plastic", 1: "paper", 2: "metal"}


@dataclass
class Detection:
    class_id: int
    confidence: float | None
    bbox_xyxy: list[float]
    origin: str = "ai"
    category_id: str | None = None
    label: str | None = None
    status: str = "supported"
    model_version: str | None = None

    def as_dict(self):
        category_id = self.category_id or LEGACY_CLASS_MAP.get(self.class_id)
        item = TAXONOMY_ITEMS.get(category_id or "")
        return {"id": f"det-{id(self):x}", "class_id": self.class_id,
                "category_id": category_id, "label": self.label or (item["name_vi"] if item else "Chưa xác định"),
                "material_id": (item.get("material_id") if item else None) or category_id,
                "confidence": self.confidence, "bbox_xyxy": self.bbox_xyxy,
                "origin": self.origin, "status": self.status if item else "unsupported",
                "model_version": self.model_version}


class Detector(Protocol):
    mode: str
    model_version: str | None

    def predict(self, image: Image.Image, filename: str) -> list[Detection]: ...


class DemoDetector:
    mode = "demo"
    model_version = None
    supported_category_ids = list(LEGACY_CLASS_MAP.values())

    def predict(self, image: Image.Image, filename: str) -> list[Detection]:
        if filename != "wastewise-sample.png":
            return []
        sx, sy = image.width / 960, image.height / 560
        return [Detection(0, None, [93*sx, 110*sy, 298*sx, 450*sy], "illustration", "plastic"),
                Detection(1, None, [364*sx, 170*sy, 656*sx, 434*sy], "illustration", "paper"),
                Detection(2, None, [710*sx, 138*sy, 866*sx, 425*sy], "illustration", "metal")]


class ModelNotReady(RuntimeError):
    pass


def load_model_manifest(model_path: Path, manifest_path: Path | None = None) -> dict:
    path = manifest_path or model_path.with_name("model_manifest.json")
    if not path.is_file():
        # Preserve the established baseline checkpoint contract.
        return {"schema_version": "1.0", "model_id": "legacy-swim3-3class", "model_version": model_path.name,
                "taxonomy_version": TAXONOMY["version"], "class_map": [
                    {"class_id": i, "name": category.title(), "category_id": category}
                    for i, (name, category) in enumerate(LEGACY_CLASS_MAP.items())]}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("taxonomy_version") != TAXONOMY["version"]:
        raise ValueError("Model manifest taxonomy_version does not match backend taxonomy")
    class_map = manifest.get("class_map")
    if not isinstance(class_map, list) or not class_map:
        raise ValueError("Model manifest class_map must be a non-empty list")
    ids = [row.get("class_id") for row in class_map]
    if sorted(ids) != list(range(len(ids))) or len(set(ids)) != len(ids):
        raise ValueError("Model manifest class IDs must be contiguous and unique from 0")
    for row in class_map:
        if row.get("category_id") not in TAXONOMY_ITEMS or not TAXONOMY_ITEMS[row["category_id"]]["detection_supported"]:
            raise ValueError(f"Model manifest contains unknown or unsupported category: {row.get('category_id')}")
    return manifest


class RealYOLODetector:
    mode = "real"

    def __init__(self, model_path: Path, confidence: float = 0.25, device: str = "cpu",
                 manifest_path: Path | None = None):
        if device != "cpu" and not device.isdigit():
            raise ValueError("INFERENCE_DEVICE must be cpu or a CUDA device index")
        self.model_path = model_path
        self.confidence = confidence
        self.device = device
        self.model_version = model_path.name if model_path.is_file() else None
        self.model = None
        self.class_map: dict[int, str] = {}
        self.supported_category_ids: list[str] = []
        self.model_error: str | None = None
        self._predict_lock = Lock()
        if model_path.is_file():
            try:
                self.manifest = load_model_manifest(model_path, manifest_path)
                self.class_map = {int(row["class_id"]): row["category_id"] for row in self.manifest["class_map"]}
                self.supported_category_ids = list(self.class_map.values())
                from ultralytics import YOLO
                model = YOLO(str(model_path))
                names = model.names
                names = {int(k): str(v) for k, v in names.items()} if isinstance(names, dict) else dict(enumerate(names))
                if set(names) != set(self.class_map):
                    raise ValueError("Checkpoint class IDs do not match model manifest")
                for class_id, category_id in self.class_map.items():
                    expected = TAXONOMY_ITEMS[category_id].get("model_names", [])
                    if names[class_id].casefold() not in {value.casefold() for value in expected}:
                        raise ValueError(f"Checkpoint class name mismatch at ID {class_id}: {names[class_id]}")
                self.model = model
            except ValueError as exc:
                self.model_error = str(exc)

    def predict(self, image: Image.Image, filename: str) -> list[Detection]:
        if self.model is None:
            if self.model_error:
                raise ModelNotReady(f"Checkpoint hoặc model manifest không hợp lệ: {self.model_error}")
            raise ModelNotReady("Chưa có checkpoint rác. Hãy đặt MODEL_PATH sau khi train.")
        with self._predict_lock:
            result = self.model.predict(image, conf=self.confidence, imgsz=640, device=self.device, verbose=False)[0]
        output = []
        for box in result.boxes:
            class_id = int(box.cls.item())
            category_id = self.class_map.get(class_id)
            output.append(Detection(class_id, float(box.conf.item()), [float(v) for v in box.xyxy[0].tolist()],
                                    "ai", category_id, model_version=self.model_version,
                                    status="supported" if category_id else "unsupported"))
        return output


def summarize(detections: list[Detection], corrections: dict[str, str] | None = None) -> list[dict]:
    counts: dict[str, int] = {}
    for detection in detections:
        row = detection.as_dict()
        category_id = (corrections or {}).get(row["id"], row["category_id"])
        if category_id in TAXONOMY_ITEMS:
            counts[category_id] = counts.get(category_id, 0) + 1
    return [{"category_id": category_id, "material_id": TAXONOMY_ITEMS[category_id].get("material_id") or category_id,
             "name": TAXONOMY_ITEMS[category_id]["name_vi"], "estimated_count": count}
            for category_id, count in counts.items()]


def answer_chat(message: str, category_ids: list[str]) -> dict:
    query = message.strip().lower()
    if not query:
        return {"answer": "Hãy nhập câu hỏi về cách phân loại hoặc xử lý rác.", "category_id": None}
    if any(word in query for word in ["đốt", "cháy", "burn"]):
        return {"answer": KNOWLEDGE["faq"][1]["answer"], "category_id": None}
    if any(word in query for word in ["tái chế", "recycle"]):
        return {"answer": KNOWLEDGE["faq"][0]["answer"], "category_id": None}
    for item in KNOWLEDGE["materials"]:
        terms = [item["name"].lower(), item["id"], *item.get("examples", []), *item.get("synonyms", [])]
        if any(term in query for term in terms):
            return {"answer": f"{item['name']}: {' '.join(item['do'])} Lưu ý: {item['caution']} {item['vn_tip']}", "category_id": item["id"], "material_id": item["id"]}
    if category_ids:
        item = MATERIALS.get(category_ids[0])
        if item:
            return {"answer": f"Với {item['name'].lower()} trong kết quả: {' '.join(item['do'])} {item['caution']}", "category_id": item["id"], "material_id": item["id"]}
    return {"answer": "Mình chưa có hướng dẫn được kiểm chứng cho câu hỏi này. Hãy tra cứu một nhóm trong thư viện rác hoặc hỏi đơn vị thu gom tại địa phương.", "category_id": None, "material_id": None}
