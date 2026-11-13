from __future__ import annotations

from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from PIL import ImageOps
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "kaggle"))

import audit_multiclass_final
import final_train
import perceptual_hash
import preflight_multiclass_final


CLASSES = ["plastic", "paper", "metal", "glass", "organic", "textile"]


def make_dataset(root: Path) -> tuple[Path, dict]:
    root.mkdir(parents=True)
    rows = []
    split_counts = {}
    source_counts = {}
    for split in ("train", "val", "test"):
        (root / split / "images").mkdir(parents=True)
        (root / split / "labels").mkdir()
        box_counts = Counter()
        class_images = Counter()
        for class_id, name in enumerate(CLASSES):
            image_rel = f"{split}/images/{name}.jpg"
            label_rel = f"{split}/labels/{name}.txt"
            image_path = root / image_rel
            pixels = np.zeros((24, 24, 3), dtype=np.uint8)
            pixels[:, :, class_id % 3] = 20 + class_id * 25 + (0 if split == "train" else 1 if split == "val" else 2)
            pixels[::2, ::2, :] = 255 - pixels[::2, ::2, :]
            Image.fromarray(pixels).save(image_path, quality=90)
            (root / label_rel).write_text(f"{class_id} 0.5 0.5 0.8 0.8\n", encoding="utf-8")
            image_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            rows.append({"split": split, "image": image_rel, "label": label_rel, "sha256": image_sha,
                         "source": "fixture", "group": f"{split}-{class_id}",
                         "boxes": [{"category_id": name}]})
            box_counts[name] += 1
            class_images[name] += 1
        split_counts[split] = {"images": len(CLASSES), "boxes": dict(box_counts),
                               "class_images": dict(class_images), "unlabeled_images": 0}
        source_counts[split] = {"fixture": len(CLASSES)}
    manifest = {"dataset_id": "multiclass_final_v7", "classes": CLASSES,
                "taxonomy_version": "2026-11-13.3", "images": rows}
    (root / "dataset_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "taxonomy.json").write_text(json.dumps({"version": "2026-11-13.3", "classes": CLASSES}), encoding="utf-8")
    (root / "data.yaml").write_text(yaml.safe_dump({"path": ".", "train": "train/images", "val": "val/images",
                                                       "test": "test/images", "nc": len(CLASSES), "names": CLASSES}),
                                    encoding="utf-8")
    report = {"dataset_id": "multiclass_final_v7", "classes": CLASSES, "taxonomy_version": "2026-11-13.3",
              "dataset_manifest_sha256": hashlib.sha256((root / "dataset_manifest.json").read_bytes()).hexdigest(),
              "pass": True, "all_images_decoded": True, "all_images_have_label_files": True,
              "valid_yolo_boxes": True, "all_manifest_image_hashes_match": True,
              "exact_cross_split_duplicate_pairs": 0, "cross_split_group_leaks": 0,
              "cross_split_foreground_phash_candidate_hash_pairs": 0,
              "all_classes_present_each_split": True,
              "splits": split_counts, "source_images_by_split": source_counts}
    return root, report


def install_fixture_review(root: Path, report: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    report_path = tmp_path / "committed-review.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(preflight_multiclass_final, "REVIEWED_AUDIT_REPORT", report_path)
    monkeypatch.setattr(preflight_multiclass_final, "REVIEWED_DATASET_MANIFEST_SHA256",
                        report["dataset_manifest_sha256"])
    return report["dataset_manifest_sha256"]


def test_full_audit_emits_progress_profile_and_keeps_hashes(tmp_path: Path) -> None:
    root, _ = make_dataset(tmp_path / "dataset")
    output = io.StringIO()
    report = audit_multiclass_final.audit(root, progress_every=5, progress_stream=output)
    logs = output.getvalue()
    assert "image integrity/decode/hash pass" in logs
    assert "dHash comparison finished" in logs and "foreground pHash comparison finished" in logs
    assert report["profile"]["image_read_seconds"] >= 0
    assert report["profile"]["sha256_seconds"] >= 0
    assert report["profile"]["decode_seconds"] >= 0
    assert report["profile"]["dhash_seconds"] >= 0
    assert report["profile"]["phash_seconds"] >= 0
    assert report["profile"]["dhash_cross_split_comparison_seconds"] >= 0
    assert report["profile"]["phash_cross_split_comparison_seconds"] >= 0


def test_optimized_perceptual_hashes_match_original_formulas() -> None:
    random = np.random.default_rng(20261113)
    for _ in range(12):
        image = Image.fromarray(random.integers(0, 256, (37, 51, 3), dtype=np.uint8), "RGB")
        grey = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        expected_dhash = sum((grey.getpixel((x, y)) > grey.getpixel((x + 1, y))) << (y * 8 + x)
                             for y in range(8) for x in range(8))
        assert perceptual_hash.dhash_image(image) == expected_dhash

        pixels = np.asarray(image.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
        n = 32
        cos = np.cos(np.pi / n * (np.arange(n, dtype=np.float32) + 0.5)[:, None]
                     * np.arange(n, dtype=np.float32)[None, :])
        dct = cos.T @ pixels @ cos
        low = dct[:8, :8].reshape(-1)[1:]
        expected_phash = 0
        for bit in low > float(np.median(low)):
            expected_phash = (expected_phash << 1) | int(bit)
        assert perceptual_hash.phash_image(image) == expected_phash


def test_hashes_are_unchanged_when_reusing_already_oriented_full_audit_image() -> None:
    pixels = np.arange(37 * 51 * 3, dtype=np.uint8).reshape(37, 51, 3)
    image = Image.fromarray(pixels, "RGB")
    exif = image.getexif()
    exif[274] = 6
    image.info["exif"] = exif.tobytes()
    oriented = ImageOps.exif_transpose(image)
    assert perceptual_hash.dhash_image(oriented) == perceptual_hash.dhash_image(oriented, exif_transpose=False)
    assert perceptual_hash.phash_image(oriented) == perceptual_hash.phash_image(oriented, exif_transpose=False)


def test_fast_preflight_requires_exact_reviewed_manifest_and_is_explicitly_fast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, report = make_dataset(tmp_path / "dataset")
    manifest_sha = install_fixture_review(root, report, tmp_path, monkeypatch)
    output = io.StringIO()
    result = preflight_multiclass_final.fast_preflight(root, progress_every=4, progress_stream=output)
    assert result["pass"] is True
    assert result["audit_mode"] == "fast_preflight_manifest_pinned_not_full_audit"
    assert result["full_audit_equivalent"] is False
    assert result["dataset_manifest_sha256"] == manifest_sha
    assert result["all_manifest_image_and_label_files_present"] is True
    assert result["all_label_rows_and_class_mappings_valid"] is True
    assert result["representative_images_decoded"] == len(CLASSES) * 3
    assert result["all_images_sha256_checked"] is False
    assert result["all_images_decoded"] is False
    assert result["cross_split_near_duplicates_recomputed"] is False
    assert "not a full audit" in output.getvalue()
    assert "PASS in" in output.getvalue()


def test_fast_preflight_fails_closed_on_unreviewed_manifest_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, report = make_dataset(tmp_path / "dataset")
    report["dataset_manifest_sha256"] = "0" * 64
    install_fixture_review(root, report, tmp_path, monkeypatch)
    monkeypatch.setattr(preflight_multiclass_final, "REVIEWED_DATASET_MANIFEST_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="differs from the reviewed full-audit manifest"):
        preflight_multiclass_final.fast_preflight(root, progress_stream=io.StringIO())


def test_fast_preflight_rejects_bad_labels_and_corrupt_representative_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, report = make_dataset(tmp_path / "dataset")
    install_fixture_review(root, report, tmp_path, monkeypatch)
    bad_label = root / "train" / "labels" / "plastic.txt"
    bad_label.write_text("0 0.9 0.5 0.8 0.8\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Out-of-bounds"):
        preflight_multiclass_final.fast_preflight(root, progress_stream=io.StringIO())

    good_root, good_report = make_dataset(tmp_path / "second-dataset")
    install_fixture_review(good_root, good_report, tmp_path, monkeypatch)
    first_image = good_root / "train" / "images" / "plastic.jpg"
    first_image.write_bytes(b"truncated-image")
    with pytest.raises(OSError):
        preflight_multiclass_final.fast_preflight(good_root, progress_stream=io.StringIO())


def test_runner_only_calls_fast_preflight() -> None:
    source = (ROOT / "ml" / "kaggle" / "final_train.py").read_text(encoding="utf-8")
    assert "from preflight_multiclass_final import fast_preflight" in source
    assert "run_dataset_preflight(data)" in source
    assert "from audit_multiclass_final import audit" not in source


def test_near_pair_examples_stop_at_cap_without_expanding_duplicate_cartesian_product() -> None:
    rows = {0: [("train", f"t{i}") for i in range(1000)],
            1: [("val", f"v{i}") for i in range(1000)]}
    count, examples = audit_multiclass_final.cross_split_near_pairs(rows, 1)
    assert count == 1
    assert len(examples) == 100
    assert examples[0] == ["t0", "v0"]
