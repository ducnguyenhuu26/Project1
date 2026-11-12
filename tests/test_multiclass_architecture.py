import json
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


def test_legacy_map_and_object_level_corrections():
    first = Detection(0, .8, [0, 0, 10, 10], category_id="plastic")
    second = Detection(0, .7, [10, 10, 20, 20], category_id="plastic")
    assert summarize([first, second])[0]["estimated_count"] == 2
    assert summarize([first, second], {f"det-{id(first):x}": "battery"}) == [
        {"category_id": "battery", "material_id": "mixed", "name": "Pin / ắc quy", "estimated_count": 1},
        {"category_id": "plastic", "material_id": "plastic", "name": "Nhựa", "estimated_count": 1}]
    assert first.as_dict()["category_id"] == "plastic"


def test_manifest_validation_rejects_version_and_unknown_class(tmp_path):
    checkpoint = tmp_path / "best.pt"
    manifest_file = tmp_path / "model_manifest.json"
    manifest = {"taxonomy_version": "wrong", "class_map": [{"class_id": 0, "category_id": "plastic"}]}
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="taxonomy_version"):
        load_model_manifest(checkpoint)
    manifest["taxonomy_version"] = "2026-11-12.1"
    manifest["class_map"] = [{"class_id": 0, "category_id": "battery"}]
    manifest_file.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsupported category"):
        load_model_manifest(checkpoint)


def test_unknown_category_does_not_crash_summary():
    unknown = Detection(99, .6, [0, 0, 5, 5], category_id="future_type")
    assert summarize([unknown]) == []
    assert unknown.as_dict()["status"] == "unsupported"
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
    config = {"taxonomy_version": "2026-11-12.1", "classes": ["plastic"], "seed": 19,
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
