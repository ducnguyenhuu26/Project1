"""Staging degradation and probe behavior without a real checkpoint."""
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import build_app


def image_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (80, 80), "white").save(stream, format="PNG")
    return stream.getvalue()


def test_missing_yolo_keeps_kb_and_chat_fallback(monkeypatch):
    monkeypatch.setenv("MODEL_PATH", "missing-staging-model.pt")
    monkeypatch.setenv("GROQ_API_KEY", "")
    client = TestClient(build_app(mode="real"))
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ready").status_code == 503
    assert client.get("/api/v1/recommendations/catalog?limit=1").json()["total_count"] > 0
    assert client.get("/api/v1/waste-types").json()["materials"]
    answer = client.post("/api/v1/chat", json={"message": "Có nên đốt rác?"})
    assert answer.status_code == 200
    assert answer.json()["assistant"] == "knowledge_base"
    assert client.post("/api/v1/scans", files={"image": ("photo.png", image_bytes(), "image/png")}).status_code == 503


def test_news_refresh_failure_does_not_block_scan(monkeypatch):
    class Detector:
        mode = "real"
        model_version = "staging-test"
        model = object()
        supported_category_ids = ["plastic"]

        def predict(self, image, filename):
            return []

    def failed_refresh(force_refresh=False):
        return {"items": [], "latest_items": [], "older_items": [], "partial_failure": True, "available": False}

    monkeypatch.setattr("backend.main.environment_news.get_news", failed_refresh)
    client = TestClient(build_app(detector=Detector()))
    news = client.get("/api/v1/news/environment?refresh=true")
    assert news.status_code == 200 and news.json()["partial_failure"]
    scan = client.post("/api/v1/scans", files={"image": ("photo.png", image_bytes(), "image/png")})
    assert scan.status_code == 200 and scan.json()["mode"] == "real"
