from io import BytesIO
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import build_app
from backend.services import RealYOLODetector


def png(width=80, height=60):
    out = BytesIO()
    Image.new("RGB", (width, height), "#e4ece1").save(out, format="PNG")
    return out.getvalue()


def test_demo_sample_and_arbitrary_image():
    client = TestClient(build_app(mode="demo"))
    sample = client.post("/api/v1/scans", files={"image": ("wastewise-sample.png", png(960, 560), "image/png")})
    assert sample.status_code == 200
    result = sample.json()
    assert result["mode"] == "demo" and len(result["detections"]) == 3
    assert all(row["confidence"] is None and row["origin"] == "illustration" for row in result["detections"])
    arbitrary = client.post("/api/v1/scans", files={"image": ("photo.png", png(), "image/png")})
    assert arbitrary.status_code == 200 and arbitrary.json()["detections"] == []


def test_reject_bad_uploads_and_missing_model(monkeypatch):
    client = TestClient(build_app(mode="demo"))
    assert client.post("/api/v1/scans", files={"image": ("bad.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/v1/scans", files={"image": ("bad.png", b"not a png", "image/png")}).status_code == 422
    monkeypatch.setenv("MODEL_PATH", "no-such-checkpoint.pt")
    real = TestClient(build_app(mode="real"))
    assert real.get("/api/v1/health").json()["model_status"] == "missing_checkpoint"
    response = real.post("/api/v1/scans", files={"image": ("ok.png", png(), "image/png")})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "MODEL_NOT_READY"


def test_knowledge_and_grounded_chat():
    client = TestClient(build_app(mode="demo"))
    kb = client.get("/api/v1/waste-types").json()
    assert len([m for m in kb["materials"] if m["ai_class"] is not None]) == 3
    assert client.get("/api/v1/waste-types/battery").json()["ai_class"] is None
    answer = client.post("/api/v1/chat", json={"message": "Có nên đốt rác?"}).json()["answer"]
    assert "Không tự đốt" in answer
    assert "Không tự đốt" in client.post("/api/v1/chat", json={"message": "Có nên đốt nhựa không?"}).json()["answer"]
    unknown = client.post("/api/v1/chat", json={"message": "Cho tôi biết lượng khí thải carbon chính xác?"}).json()["answer"]
    assert "chưa có" in unknown


def test_real_detector_uses_configured_device(monkeypatch):
    calls = []

    class FakeModel:
        def predict(self, image, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(boxes=[])]

    detector = RealYOLODetector(Path("missing.pt"), device="0")
    detector.model = FakeModel()
    assert detector.predict(Image.new("RGB", (16, 16)), "photo.png") == []
    assert calls[0]["device"] == "0"

    configured = []

    def fake_detector(path, confidence, device):
        configured.append((path, confidence, device))
        return detector

    monkeypatch.setattr("backend.main.RealYOLODetector", fake_detector)
    monkeypatch.setenv("INFERENCE_DEVICE", "0")
    build_app(mode="real")
    assert configured == [(Path("weights/best.pt"), 0.25, "0")]
