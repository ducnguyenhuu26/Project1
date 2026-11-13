import json
from io import BytesIO
from pathlib import Path
import random
import sys

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "scripts"))
from build_multisource import box_yolo, build
from train_multiclass import inspect_dataset
from backend.services import Detection, MATERIALS, answer_chat, load_model_manifest, summarize
from backend.main import build_app
from fastapi.testclient import TestClient

TAXONOMY_VERSION = json.loads((ROOT / "backend" / "taxonomy.json").read_text(encoding="utf-8"))["version"]


def test_legacy_map_and_object_level_corrections():
    first = Detection(0, .8, [0, 0, 10, 10], category_id="plastic")
    second = Detection(0, .7, [10, 10, 20, 20], category_id="plastic")
    assert summarize([first, second])[0]["estimated_count"] == 2
    assert summarize([first, second], {f"det-{id(first):x}": "battery"}) == [
        {"category_id": "battery", "material_id": "mixed", "advice_id": "battery", "name": "Pin / ắc quy", "estimated_count": 1},
        {"category_id": "plastic", "material_id": "plastic", "advice_id": "plastic", "name": "Nhựa", "estimated_count": 1}]
    assert first.as_dict()["category_id"] == "plastic"


def test_manifest_validation_rejects_version_and_unknown_class(tmp_path):
    checkpoint = tmp_path / "best.pt"
    manifest_file = tmp_path / "model_manifest.json"
    manifest = {"taxonomy_version": "wrong", "class_map": [{"class_id": 0, "category_id": "plastic"}]}
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="taxonomy_version"):
        load_model_manifest(checkpoint)
    manifest["taxonomy_version"] = TAXONOMY_VERSION
    manifest["class_map"] = [{"class_id": 0, "category_id": "battery"}]
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported category"):
        load_model_manifest(checkpoint)


def test_unknown_category_does_not_crash_summary():
    unknown = Detection(99, .6, [0, 0, 5, 5], category_id="future_type")
    assert summarize([unknown]) == []
    assert unknown.as_dict()["status"] == "unsupported"
    cigarette = Detection(3, .7, [0, 0, 5, 5], category_id="cigarette_litter").as_dict()
    assert cigarette["advice_id"] == "cigarette_litter"
    assert summarize([Detection(3, .7, [0, 0, 5, 5], category_id="cigarette_litter")])[0]["category_id"] == "cigarette_litter"
    assert "Giữ nguyên vỏ" in MATERIALS["battery"]["do"][0]
    assert "pin" in answer_chat("Pin tiểu cũ xử lý thế nào?", [])["answer"].lower()


def test_coco_box_conversion_and_synthetic_builder(tmp_path):
    assert box_yolo([10, 20, 30, 40], 100, 100) == (.25, .4, .3, .4)
    assert box_yolo([-1, 0, 10, 10], 100, 100) is None
    images = tmp_path / "images"; images.mkdir()
    image_rows, annotations = [], []
    for i in range(10):
        name = f"img{i}.png"
        Image.frombytes("RGB", (20, 10), random.Random(i).randbytes(20 * 10 * 3)).save(images / name)
        image_rows.append({"id": i, "file_name": name, "width": 20, "height": 10, "scene_id": f"scene-{i}"})
        annotations.append({"id": i, "image_id": i, "category_id": 1, "bbox": [2, 1, 8, 4]})
    coco = {"images": image_rows, "annotations": annotations, "categories": [{"id": 1, "name": "plastic bottle"}]}
    ann_path = tmp_path / "coco.json"; ann_path.write_text(json.dumps(coco))
    config = {"taxonomy_version": TAXONOMY_VERSION, "classes": ["plastic"], "seed": 19,
              "sources": [{"id": "fixture", "annotations": str(ann_path), "image_dir": str(images), "license_reviewed": True,
                           "mapping_reviewed": True,
                           "url": "fixture", "license_status": "synthetic", "fully_annotated": True,
                           "mapping": {"plastic bottle": {"decision": "map", "category_id": "plastic", "reason": "fixture"}}}]}
    out = tmp_path / "built"
    report = build(config, out)
    assert report["images"] == 10
    assert report["class_counts"] == {"plastic": 10}
    _, names, _ = inspect_dataset(out / "data.yaml")
    assert names == ["plastic"]
    manifest = json.loads((out / "dataset_manifest.json").read_text())
    assert all(row["boxes"][0]["source_class"] == "plastic bottle" for row in manifest["images"])
    labels = list(out.glob("*/labels/*.txt"))
    assert len(labels) == 10 and all(len(path.read_text().split()) == 5 for path in labels)
    with pytest.raises(ValueError, match="already exists"):
        build(config, out)


def test_multiclass_api_health_scan_and_manual_fallback_contract():
    class MultiClassDetector:
        mode = "real"
        model = object()
        model_version = "fixture-multiclass.pt"
        supported_category_ids = ["plastic", "paper", "metal", "glass"]

        def predict(self, image, filename):
            return [
                Detection(0, .91, [1.0, 2.0, 10.0, 11.0], category_id="plastic"),
                Detection(3, .41, [11.0, 1.0, 30.0, 25.0], category_id="glass"),
                Detection(4, .18, [2.0, 12.0, 16.0, 30.0], category_id="future_class", status="unsupported"),
            ]

    client = TestClient(build_app(detector=MultiClassDetector()))
    health = client.get("/api/v1/health").json()
    assert health == {"status": "ok", "mode": "real", "model_status": "ready",
                      "model_version": "fixture-multiclass.pt",
                      "supported_category_ids": ["plastic", "paper", "metal", "glass"]}
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    scan = client.post("/api/v1/scans", files={"image": ("multi.png", buffer.getvalue(), "image/png")})
    assert scan.status_code == 200
    result = scan.json()
    assert result["supported_category_ids"] == ["plastic", "paper", "metal", "glass"]
    assert [(d["category_id"], d["origin"]) for d in result["detections"]] == [
        ("plastic", "ai"), ("glass", "ai"), ("future_class", "ai")]
    assert result["detections"][1]["bbox_xyxy"] == [11.0, 1.0, 30.0, 25.0]
    assert result["detections"][2]["status"] == "unsupported"
    assert {row["category_id"] for row in result["summary"]} == {"plastic", "glass"}
    assert {item["id"] for item in result["advice"]} >= {"plastic", "glass"}


def test_exif_rotation_preserves_box_coordinates():
    from build_multisource import orient_yolo_box
    assert orient_yolo_box((.2, .3, .1, .2), 100, 200, 1) == pytest.approx((.2, .3, .1, .2))
    assert orient_yolo_box((.2, .3, .1, .2), 100, 200, 6) == pytest.approx((.7, .2, .2, .1))
    assert orient_yolo_box((.2, .3, .1, .2), 100, 200, 8) == pytest.approx((.3, .8, .2, .1))


def test_builder_normalizes_noncanonical_jpeg_tail_before_manifesting(tmp_path):
    images = tmp_path / "images"; images.mkdir()
    valid = tmp_path / "valid.jpg"
    Image.new("RGB", (20, 10), "white").save(valid, format="JPEG")
    (images / "trailing.jpg").write_bytes(valid.read_bytes() + b"SEEF")
    coco = {"images": [{"id": 1, "file_name": "trailing.jpg", "width": 20, "height": 10}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [2, 1, 8, 4]}],
            "categories": [{"id": 1, "name": "plastic bottle"}]}
    annotations = tmp_path / "annotations.json"; annotations.write_text(json.dumps(coco))
    config = {"taxonomy_version": TAXONOMY_VERSION, "classes": ["plastic"],
              "sources": [{"id": "fixture", "annotations": str(annotations), "image_dir": str(images),
                           "license_reviewed": True, "mapping_reviewed": True, "fully_annotated": True,
                           "mapping": {"plastic bottle": {"decision": "map", "category_id": "plastic"}}}]}
    output = tmp_path / "dataset"
    report = build(config, output)
    manifest = json.loads((output / "dataset_manifest.json").read_text())
    row = manifest["images"][0]
    built_image = output / row["image"]
    assert report["issue_counts"]["jpeg_repaired"] == 1
    assert row["jpeg_repaired"] is True
    assert built_image.read_bytes()[-2:] == b"\xff\xd9"
    assert __import__("hashlib").sha256(built_image.read_bytes()).hexdigest() == row["sha256"]


def test_builder_reports_bad_boxes_partial_labels_duplicates_and_is_deterministic(tmp_path):
    images = tmp_path / "images"; images.mkdir()
    for i in range(3):
        Image.frombytes("RGB", (24, 16), random.Random(100 + i).randbytes(24 * 16 * 3)).save(images / f"p{i}.png")
    # Same bytes, different filename: the second copy must be excluded.
    (images / "duplicate.png").write_bytes((images / "p0.png").read_bytes())
    with Image.open(images / "p0.png") as source:
        near = source.copy(); near.putpixel((23, 15), (255, 0, 255)); near.save(images / "near.png")
    coco = {"images": [{"id": i, "file_name": f"p{i}.png", "width": 24, "height": 16, "scene_id": f"s{i}"} for i in range(3)] +
                         [{"id": 3, "file_name": "duplicate.png", "width": 24, "height": 16},
                          {"id": 4, "file_name": "near.png", "width": 24, "height": 16}],
            "categories": [{"id": 1, "name": "plastic bottle"}, {"id": 2, "name": "unknown household item"}],
            "annotations": [{"id": 1, "image_id": 0, "category_id": 1, "bbox": [1, 1, 10, 8]},
                            {"id": 2, "image_id": 1, "category_id": 2, "bbox": [1, 1, 10, 8]},
                            {"id": 3, "image_id": 2, "category_id": 1, "bbox": [1, 1, 0, 8]}]}
    annotation_path = tmp_path / "audit.json"; annotation_path.write_text(json.dumps(coco))
    config = {"classes": ["plastic"], "seed": 7, "sources": [{"id": "test", "annotations": str(annotation_path),
              "license_reviewed": True, "mapping_reviewed": True,
              "image_dir": str(images), "fully_annotated": False,
              "mapping": {"plastic bottle": {"decision": "map", "category_id": "plastic"}}}]}
    first, second = tmp_path / "first", tmp_path / "second"
    report_a, report_b = build(config, first), build(config, second)
    problems = {row["issue"] for row in report_a["issues"]}
    assert {"unmappable", "invalid_box", "exact_duplicate", "perceptual_near_duplicate", "partial_annotation_dropped"} <= problems
    assert report_a["images"] == 1
    assert (first / "dataset_manifest.json").read_bytes() == (second / "dataset_manifest.json").read_bytes()
