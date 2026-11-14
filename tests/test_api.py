from io import BytesIO
from pathlib import Path
from threading import Lock
from threading import Event
from concurrent.futures import ThreadPoolExecutor
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
    region = real.post("/api/v1/scans/region", data={"x1": 1, "y1": 1, "x2": 40, "y2": 40},
                       files={"image": ("ok.png", png(), "image/png")})
    assert region.status_code == 503


def test_knowledge_and_grounded_chat(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
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
    # The developer's .env may select an installed v7 checkpoint; isolate this
    # device-wiring test from machine-local model configuration.
    monkeypatch.setenv("MODEL_PATH", "weights/best.pt")
    build_app(mode="real")
    assert configured == [(Path("weights/best.pt"), 0.25, "0")]


def test_scan_rejects_invalid_detector_boxes():
    class InvalidDetector:
        mode = "real"
        model_version = "bad-fixture"

        def predict(self, image, filename):
            from backend.services import Detection
            return [Detection(0, .5, [-2, 1, image.width, image.height])]

    client = TestClient(build_app(detector=InvalidDetector()))
    response = client.post("/api/v1/scans", files={"image": ("photo.png", png(), "image/png")})
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "INVALID_DETECTION"


def test_invalid_model_manifest_is_reported_as_not_ready(tmp_path):
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"placeholder")
    (tmp_path / "model_manifest.json").write_text('{"taxonomy_version":"wrong","class_map":[]}')
    detector = RealYOLODetector(checkpoint)
    client = TestClient(build_app(detector=detector))
    assert client.get("/api/v1/health").json()["model_status"] == "invalid_manifest"
    response = client.post("/api/v1/scans", files={"image": ("ok.png", png(), "image/png")})
    assert response.status_code == 503
    assert "taxonomy_version" in response.json()["detail"]["message"]


def test_manifest_rejects_checkpoint_hash_mismatch(tmp_path):
    import json
    from backend.services import TAXONOMY
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"checkpoint bytes")
    manifest = {"taxonomy_version": TAXONOMY["version"], "class_map": [{"class_id": 0, "category_id": "plastic"}],
                "checkpoint_sha256": "0" * 64}
    (tmp_path / "model_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    detector = RealYOLODetector(checkpoint)
    assert detector.model is None
    assert "SHA-256" in detector.model_error


def test_real_checkpoint_manifest_requires_hash(tmp_path):
    import json
    from backend.services import TAXONOMY
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"checkpoint bytes")
    manifest = {"taxonomy_version": TAXONOMY["version"], "class_map": [{"class_id": 0, "category_id": "plastic"}]}
    (tmp_path / "model_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    detector = RealYOLODetector(checkpoint)
    assert detector.model is None
    assert "must include checkpoint_sha256" in detector.model_error


def test_checkpoint_load_and_class_name_mismatch_stay_not_ready(tmp_path, monkeypatch):
    import hashlib
    import json
    import sys
    from types import SimpleNamespace
    from backend.services import TAXONOMY
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"checkpoint bytes")
    manifest = {"taxonomy_version": TAXONOMY["version"], "class_map": [{"class_id": 0, "category_id": "plastic"}],
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
    (tmp_path / "model_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda *_args: SimpleNamespace(names={0: "Paper"})))
    mismatch = RealYOLODetector(checkpoint)
    assert mismatch.model is None
    assert "class name mismatch" in mismatch.model_error
    def fail_loading(*_args):
        raise RuntimeError("fixture checkpoint load failure")
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=fail_loading))
    failed = RealYOLODetector(checkpoint)
    assert failed.model is None
    assert "fixture checkpoint load failure" in failed.model_error


def test_real_checkpoint_without_manifest_fails_closed_unless_explicit_legacy_opt_in(tmp_path, monkeypatch):
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"legacy checkpoint fixture")
    monkeypatch.delenv("ALLOW_LEGACY_MODEL_MANIFEST", raising=False)
    detector = RealYOLODetector(checkpoint)
    assert detector.model is None
    assert "manifest is required" in detector.model_error
    assert TestClient(build_app(detector=detector)).get("/api/v1/health").json()["model_status"] == "invalid_manifest"
    monkeypatch.setenv("ALLOW_LEGACY_MODEL_MANIFEST", "true")
    from backend.services import load_model_manifest
    assert load_model_manifest(checkpoint)["model_id"] == "legacy-swim3-3class"


def test_scan_and_roi_share_nonblocking_inference_admission(monkeypatch):
    entered, release = Event(), Event()
    monkeypatch.setenv("MAX_CONCURRENT_INFERENCES", "1")

    class SlowDetector:
        mode = "real"
        model_version = "slow-fixture"
        supported_category_ids = []

        def predict(self, image, filename):
            entered.set()
            assert release.wait(5)
            return []

    app = build_app(detector=SlowDetector())
    first = TestClient(app)
    second = TestClient(app)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(first.post, "/api/v1/scans", files={"image": ("x.png", png(), "image/png")})
        assert entered.wait(2)
        blocked = second.post("/api/v1/scans/region", data={"x1": 1, "y1": 1, "x2": 40, "y2": 40},
                              files={"image": ("x.png", png(), "image/png")})
        assert blocked.status_code == 503
        assert blocked.headers["retry-after"] == "2"
        assert blocked.json()["detail"]["code"] == "INFERENCE_BUSY"
        release.set()
        assert pending.result(timeout=3).status_code == 200


def test_chat_rate_limit_ignores_untrusted_forwarded_for(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    client = TestClient(build_app(mode="demo"))
    for index in range(10):
        response = client.post("/api/v1/chat", headers={"X-Forwarded-For": f"198.51.100.{index}"},
                               json={"message": "hello"})
        assert response.status_code == 200
    blocked = client.post("/api/v1/chat", headers={"X-Forwarded-For": "203.0.113.99"},
                          json={"message": "hello"})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


def test_news_forced_refresh_is_throttled(monkeypatch):
    monkeypatch.setattr("backend.main.environment_news.get_news", lambda force_refresh=False: {"available": True})
    client = TestClient(build_app(mode="demo"))
    assert client.get("/api/v1/news/environment?refresh=true").status_code == 200
    blocked = client.get("/api/v1/news/environment?refresh=true")
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "RATE_LIMITED"


def test_region_scan_crops_and_maps_boxes_to_original_image():
    from backend.services import Detection

    class RegionDetector:
        mode = "real"
        model_version = "test-model"
        supported_category_ids = ["plastic"]

        def __init__(self):
            self.calls = []

        def predict(self, image, filename):
            self.calls.append((image.size, filename))
            return [Detection(0, .82, [2, 3, image.width - 1, image.height - 1])]

    detector = RegionDetector()
    client = TestClient(build_app(detector=detector))
    response = client.post("/api/v1/scans/region", data={"x1": 10.2, "y1": 5.8, "x2": 50.1, "y2": 35.2},
                           files={"image": ("photo.png", png(), "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert detector.calls == [((41, 31), "photo.png")]
    assert body["image_width"] == 80 and body["image_height"] == 60
    assert body["detections"][0]["bbox_xyxy"] == [12.0, 8.0, 50.0, 35.0]
    assert body["detections"][0]["origin"] == "ai"


def test_region_scan_rejects_invalid_boxes_and_preserves_demo_label():
    client = TestClient(build_app(mode="demo"))
    image = {"image": ("photo.png", png(), "image/png")}
    assert client.post("/api/v1/scans/region", data={"x1": 0, "y1": 0, "x2": 40, "y2": 40},
                       files={"image": ("bad.txt", b"hello", "text/plain")}).status_code == 415
    for box in ({"x1": -1, "y1": 0, "x2": 40, "y2": 30},
                {"x1": 10, "y1": 10, "x2": 15, "y2": 30},
                {"x1": 60, "y1": 20, "x2": 30, "y2": 40}):
        assert client.post("/api/v1/scans/region", data=box, files=image).status_code == 422
    response = client.post("/api/v1/scans/region", data={"x1": 10, "y1": 10, "x2": 40, "y2": 40}, files=image)
    assert response.status_code == 200
    assert response.json()["mode"] == "demo" and response.json()["detections"] == []
    assert "không chạy YOLO" in response.json()["warnings"][0]
