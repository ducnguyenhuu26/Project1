from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "scripts"))

from build_multiclass_v4 import CLASSES, SOURCE_CLASSES, assign_splits
from build_multiclass_v5 import textile_only_rows
import json
from PIL import Image


def test_multiclass_v4_source_mapping_is_explicit_and_six_class() -> None:
    assert CLASSES == ["plastic", "paper", "metal", "glass", "organic", "cigarette_litter"]
    assert SOURCE_CLASSES == {
        "biodegradable": "organic", "cardboard": "paper", "glass": "glass",
        "metal": "metal", "paper": "paper", "plastic": "plastic",
    }


def test_multiclass_v4_split_is_deterministic_and_keeps_groups_together() -> None:
    rows = [
        {"file_name": "glass_1.rf.a.jpg", "labels": {"glass"}},
        {"file_name": "glass_1.rf.b.jpg", "labels": {"glass"}},
        {"file_name": "paper_1.rf.c.jpg", "labels": {"paper"}},
        {"file_name": "organic_1.rf.d.jpg", "labels": {"organic"}},
        {"file_name": "metal_1.rf.e.jpg", "labels": {"metal"}},
        {"file_name": "plastic_1.rf.f.jpg", "labels": {"plastic"}},
    ]
    first = assign_splits(rows, seed=42)
    assert first == assign_splits(rows, seed=42)
    assert first["glass_1.rf.a.jpg"] == first["glass_1.rf.b.jpg"]


def test_mrs_textile_filter_excludes_mixed_unmapped_images(tmp_path: Path) -> None:
    (tmp_path / "classes.json").write_text(json.dumps({"0": "Not recyclable", "3": "Textile"}), encoding="utf-8")
    for folder in ("images/train", "labels/train", "images/val", "labels/val", "images/test", "labels/test"):
        (tmp_path / folder).mkdir(parents=True)
    Image.new("RGB", (12, 8), "white").save(tmp_path / "images/train/textile.jpg")
    Image.new("RGB", (12, 8), "black").save(tmp_path / "images/train/mixed.jpg")
    (tmp_path / "labels/train/textile.txt").write_text("3 0.5 0.5 0.4 0.4\n", encoding="utf-8")
    (tmp_path / "labels/train/mixed.txt").write_text(
        "3 0.5 0.5 0.4 0.4\n0 0.2 0.2 0.1 0.1\n", encoding="utf-8")
    rows, audit = textile_only_rows(tmp_path)
    assert [row["source_file"] for row in rows] == ["textile.jpg"]
    assert audit["images_skipped_mixed_or_other_class"] == 1
    assert audit["boxes_selected"] == 1
