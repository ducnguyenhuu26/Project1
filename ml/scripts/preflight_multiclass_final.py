"""Fast, explicitly non-equivalent preflight for the reviewed Kaggle dataset.

This routine relies on the SHA-256 of the previously full-audited, committed
manifest. It checks structure, labels, split distributions and representative
decodes, but it does NOT hash/decode every image or recalculate duplicate
checks. A manifest with any other SHA is rejected and must use the full audit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time

import yaml
from PIL import Image


REVIEWED_DATASET_MANIFEST_SHA256 = "a92e916ae3f9019ffb52cd20fea48defabae20c8b52cf8a22f4e7b4c954983b7"
REVIEWED_AUDIT_REPORT = Path(__file__).resolve().parents[1] / "reports" / "multiclass_final_v7_audit.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SPLITS = ("train", "val", "test")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _say(stream, message: str) -> None:
    print(f"[fast-preflight] {message}", file=stream, flush=True)


def _safe_relative(value: str, split: str, expected_dir: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.parts[:2] != (split, expected_dir):
        raise ValueError(f"Unsafe or misplaced manifest path for {split}: {value}")
    return path


def fast_preflight(root: Path, progress_every: int = 2000, progress_stream=None) -> dict:
    """Validate the reviewed v7 structure without repeating its full image audit."""
    started = time.perf_counter()
    if progress_stream is None:
        progress_stream = sys.stdout
    root = Path(root).resolve()
    _say(progress_stream, f"starting fast preflight (not a full audit): {root}")
    manifest_path = root / "dataset_manifest.json"
    taxonomy_path = root / "taxonomy.json"
    yaml_path = root / "data.yaml"
    for required in (manifest_path, taxonomy_path, yaml_path):
        if not required.is_file():
            raise FileNotFoundError(f"Required dataset file is missing: {required}")

    report = json.loads(REVIEWED_AUDIT_REPORT.read_text(encoding="utf-8"))
    if report.get("dataset_id") != "multiclass_final_v7" or report.get("pass") is not True:
        raise ValueError("Committed full-audit report is missing, invalid, or for another dataset")
    required_full_audit_checks = (
        report.get("all_images_decoded") is True,
        report.get("all_images_have_label_files") is True,
        report.get("valid_yolo_boxes") is True,
        report.get("all_manifest_image_hashes_match") is True,
        report.get("exact_cross_split_duplicate_pairs") == 0,
        report.get("cross_split_group_leaks") == 0,
        report.get("cross_split_foreground_phash_candidate_hash_pairs") == 0,
        report.get("all_classes_present_each_split") is True,
    )
    if not all(required_full_audit_checks):
        raise ValueError("Committed review report does not prove the required full-audit gates")
    if report.get("dataset_manifest_sha256") != REVIEWED_DATASET_MANIFEST_SHA256:
        raise ValueError("Committed full-audit report does not contain the reviewed manifest SHA-256")
    manifest_sha = sha256_file(manifest_path)
    if manifest_sha != REVIEWED_DATASET_MANIFEST_SHA256:
        raise ValueError(
            "Uploaded manifest SHA-256 differs from the reviewed full-audit manifest; "
            "fast preflight is not permitted. Run the full audit and review a new report."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset_id") != report["dataset_id"]:
        raise ValueError("Dataset manifest identity does not match the committed audit report")
    classes = report.get("classes")
    if manifest.get("classes") != classes or manifest.get("taxonomy_version") != report.get("taxonomy_version"):
        raise ValueError("Manifest class order or taxonomy version differs from the reviewed audit report")
    _say(progress_stream, f"reviewed manifest SHA-256 confirmed: {manifest_sha}")

    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    data_config = yaml.safe_load(yaml_path.read_text(encoding="utf-8-sig"))
    backend_path = Path(__file__).resolve().parents[2] / "backend" / "taxonomy.json"
    backend_taxonomy = json.loads(backend_path.read_text(encoding="utf-8"))
    if taxonomy.get("classes") != classes or taxonomy.get("version") != report.get("taxonomy_version"):
        raise ValueError("taxonomy.json differs from the reviewed class order/version")
    if backend_taxonomy.get("version") != taxonomy.get("version"):
        raise ValueError("Backend taxonomy version differs from the reviewed dataset")
    backend_categories = {item["id"]: item for item in backend_taxonomy.get("categories", [])}
    for name in classes:
        category = backend_categories.get(name)
        if (not category or not category.get("detection_supported")
                or name.casefold() not in {value.casefold() for value in category.get("model_names", [])}):
            raise ValueError(f"Dataset class is not supported by backend taxonomy: {name}")
    if data_config.get("path") != "." or data_config.get("names") != classes or data_config.get("nc") != len(classes):
        raise ValueError("Portable data.yaml path or class order/count differs from reviewed dataset")
    for split in SPLITS:
        if data_config.get(split) != f"{split}/images":
            raise ValueError(f"Unexpected data.yaml {split} path: {data_config.get(split)}")
        if not (root / split / "images").is_dir() or not (root / split / "labels").is_dir():
            raise FileNotFoundError(f"Missing {split}/images or {split}/labels directory")

    rows = manifest.get("images")
    if not isinstance(rows, list):
        raise ValueError("Manifest images must be a list")
    rows_by_split: dict[str, list[dict]] = defaultdict(list)
    manifest_images: set[str] = set()
    manifest_labels: set[str] = set()
    for row in rows:
        split = row.get("split")
        if split not in SPLITS:
            raise ValueError(f"Unexpected split in manifest: {split}")
        image_rel = _safe_relative(row.get("image", ""), split, "images").as_posix()
        label_rel = _safe_relative(row.get("label", ""), split, "labels").as_posix()
        if image_rel in manifest_images or label_rel in manifest_labels:
            raise ValueError(f"Duplicate image/label path in manifest: {image_rel} {label_rel}")
        manifest_images.add(image_rel)
        manifest_labels.add(label_rel)
        rows_by_split[split].append(row)

    # Inventory check catches omitted and unlisted images without opening their bytes.
    actual_images = {
        path.relative_to(root).as_posix()
        for split in SPLITS
        for path in (root / split / "images").rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }
    if actual_images != manifest_images:
        raise ValueError(
            f"Image inventory differs from manifest: unlisted={len(actual_images - manifest_images)}, "
            f"missing={len(manifest_images - actual_images)}"
        )
    actual_labels = {
        path.relative_to(root).as_posix()
        for split in SPLITS
        for path in (root / split / "labels").rglob("*.txt")
        if path.is_file()
    }
    if actual_labels != manifest_labels:
        raise ValueError(
            f"Label inventory differs from manifest: unlisted={len(actual_labels - manifest_labels)}, "
            f"missing={len(manifest_labels - actual_labels)}"
        )

    counts = {}
    selected_decode: set[str] = set()
    representatives = {split: {} for split in SPLITS}
    images_checked = 0
    for split in SPLITS:
        expected_split = report["splits"][split]
        split_rows = rows_by_split[split]
        if len(split_rows) != expected_split["images"]:
            raise ValueError(f"Reviewed {split} image count mismatch: {len(split_rows)} != {expected_split['images']}")
        box_counts = Counter()
        class_images = Counter()
        unlabeled = 0
        source_counts = Counter()
        for row in split_rows:
            # Paths were validated in the manifest pass above.
            image_rel = row["image"]
            label_rel = row["label"]
            image_path, label_path = root / image_rel, root / label_rel
            try:
                image_size = image_path.stat().st_size
                label_text = label_path.read_text(encoding="utf-8-sig")
            except OSError as exc:
                raise FileNotFoundError(f"Missing image/label: {image_rel} / {label_rel}: {exc}") from exc
            if image_size == 0:
                raise ValueError(f"Empty image file: {image_rel}")
            lines = [line.strip() for line in label_text.splitlines() if line.strip()]
            expected_boxes = row.get("boxes")
            if not isinstance(expected_boxes, list) or len(lines) != len(expected_boxes):
                raise ValueError(f"Label/manifest box-count mismatch: {image_rel}")
            seen = set()
            for box_index, (line, expected_box) in enumerate(zip(lines, expected_boxes)):
                fields = line.split()
                try:
                    class_id = int(fields[0])
                    coordinates = [float(item) for item in fields[1:]]
                except (ValueError, IndexError):
                    raise ValueError(f"Malformed YOLO label {label_rel}:{box_index + 1}") from None
                if (len(fields) != 5 or len(coordinates) != 4 or class_id < 0 or class_id >= len(classes)
                        or any(not 0 <= value <= 1 for value in coordinates)
                        or coordinates[2] <= 0 or coordinates[3] <= 0):
                    raise ValueError(f"Invalid YOLO box/class {label_rel}:{box_index + 1}")
                x, y, width, height = coordinates
                if x - width / 2 < -1e-6 or x + width / 2 > 1 + 1e-6 or y - height / 2 < -1e-6 or y + height / 2 > 1 + 1e-6:
                    raise ValueError(f"Out-of-bounds YOLO box {label_rel}:{box_index + 1}")
                class_name = classes[class_id]
                if expected_box.get("category_id") != class_name:
                    raise ValueError(f"Manifest/label category mismatch {image_rel}:{box_index}")
                box_counts[class_name] += 1
                seen.add(class_name)
            for class_name in seen:
                class_images[class_name] += 1
                representatives[split].setdefault(class_name, image_rel)
            if not lines:
                unlabeled += 1
            source_counts[row.get("source", "unknown")] += 1
            images_checked += 1
            if progress_every > 0 and images_checked % progress_every == 0:
                elapsed = time.perf_counter() - started
                _say(progress_stream, f"labels/files checked {images_checked:,}/{len(rows):,}; elapsed {elapsed:.1f}s")
        actual_counts = {"images": len(split_rows), "boxes": dict(box_counts),
                         "class_images": dict(class_images), "unlabeled_images": unlabeled}
        for key, actual in actual_counts.items():
            expected = expected_split.get(key)
            if actual != expected:
                raise ValueError(f"Reviewed {split} {key} mismatch: {actual} != {expected}")
        expected_sources = report.get("source_images_by_split", {}).get(split)
        if expected_sources is not None and dict(source_counts) != expected_sources:
            raise ValueError(f"Reviewed {split} source image distribution differs from manifest")
        counts[split] = actual_counts
        _say(progress_stream, f"{split}: checked {len(split_rows):,} image/label records; class counts match")

    # Also cover each class in each split, selecting the lexicographically first
    # encountered image. The set is small (at most 18) and deterministic.
    for split in SPLITS:
        for class_name in classes:
            candidate = representatives[split].get(class_name)
            if candidate is None:
                raise ValueError(f"Reviewed class {class_name} is absent from {split}")
            selected_decode.add(candidate)
        if report["splits"][split].get("unlabeled_images", 0):
            negative = next((row["image"] for row in rows_by_split[split] if not row.get("boxes")), None)
            if negative:
                selected_decode.add(negative)
    for rel_image in sorted(selected_decode):
        with Image.open(root / rel_image) as image:
            image.load()
            if image.width < 1 or image.height < 1:
                raise ValueError(f"Representative image has invalid dimensions: {rel_image}")
    _say(progress_stream, f"decoded {len(selected_decode)} representative images (all-image decoding is full-audit only)")

    elapsed = time.perf_counter() - started
    result = {
        "audit_mode": "fast_preflight_manifest_pinned_not_full_audit",
        "full_audit_equivalent": False,
        "dataset_id": manifest["dataset_id"],
        "dataset_manifest_sha256": manifest_sha,
        "reviewed_manifest_sha256": REVIEWED_DATASET_MANIFEST_SHA256,
        "taxonomy_version": taxonomy["version"],
        "classes": classes,
        "images": len(rows),
        "splits": counts,
        "all_manifest_image_and_label_files_present": True,
        "all_label_rows_and_class_mappings_valid": True,
        "representative_images_decoded": len(selected_decode),
        "all_images_sha256_checked": False,
        "all_images_decoded": False,
        "cross_split_near_duplicates_recomputed": False,
        "elapsed_seconds": elapsed,
        "pass": True,
    }
    _say(progress_stream, f"PASS in {elapsed:.1f}s (fast preflight; not a full audit)")
    return result
