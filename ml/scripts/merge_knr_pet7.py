"""Merge audited TACO ODbL boxes with the licensed Vietnam KNR-PET-7 source.

The PET dataset uses oriented YOLO polygons and seven industrial PET grades.
This script maps those grades to the already-reviewed ``plastic`` taxonomy and
converts each polygon to its enclosing axis-aligned detection box. Official
source splits are preserved; no source test image is moved into train/val.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from PIL import Image


PET_CLASS_NAMES = {
    0: "B1",
    1: "B2.1",
    2: "B2.2",
    3: "B3",
    4: "B4",
    5: "B5",
    6: "B6",
}
PET_FILENAME_CLASS = {"B1_": 0, "B21_": 1, "B22_": 2, "B3_": 3, "B4_": 4, "B5_": 5, "B6_": 6}
PET_SOURCE_URL = "https://data.mendeley.com/datasets/5x9bzrk9ch/2"
PET_LICENSE = "CC BY 4.0; attribution required"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def convert_obb_line(line: str, line_number: int, label_path: Path) -> tuple[int, str, dict[str, Any]]:
    values = line.split()
    if len(values) != 9:
        raise ValueError(f"{label_path}:{line_number}: expected class id plus 8 OBB coordinates")
    try:
        class_id = int(values[0])
        points = [float(value) for value in values[1:]]
    except ValueError as exc:
        raise ValueError(f"{label_path}:{line_number}: non-numeric annotation") from exc
    if class_id not in PET_CLASS_NAMES or any(value < 0 or value > 1 for value in points):
        raise ValueError(f"{label_path}:{line_number}: class id or normalized coordinate out of range")
    xs, ys = points[0::2], points[1::2]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    width, height = xmax - xmin, ymax - ymin
    if width <= 0 or height <= 0:
        raise ValueError(f"{label_path}:{line_number}: degenerate OBB")
    xc, yc = (xmin + xmax) / 2, (ymin + ymax) / 2
    yolo = f"0 {xc:.8f} {yc:.8f} {width:.8f} {height:.8f}"
    provenance = {
        "source_class": PET_CLASS_NAMES[class_id],
        "source_class_id": class_id,
        "category_id": "plastic",
        "mapping_rule": "KNR-PET-7 identifies all seven source grades as post-consumer PET bottles; mapped to the broad plastic class",
        "transform": "normalized 4-corner YOLO OBB → enclosing axis-aligned YOLO xywh",
    }
    return class_id, yolo, provenance


def merge_duplicate_boxes(left: tuple[str, ...], right: tuple[str, ...], threshold: float = 0.85) -> tuple[tuple[str, ...] | None, float]:
    """Accept duplicate-source box jitter only for same-class, strongly overlapping boxes."""
    if len(left) != len(right):
        return None, 0.0
    overlaps = []
    merged = []
    for a, b in zip(left, right):
        ap, bp = a.split(), b.split()
        if ap[0] != bp[0]:
            return None, 0.0
        ax, ay, aw, ah = map(float, ap[1:])
        bx, by, bw, bh = map(float, bp[1:])
        al, at, ar, ab = ax-aw/2, ay-ah/2, ax+aw/2, ay+ah/2
        bl, bt, br, bb = bx-bw/2, by-bh/2, bx+bw/2, by+bh/2
        inter = max(0.0, min(ar, br)-max(al, bl)) * max(0.0, min(ab, bb)-max(at, bt))
        union = aw*ah + bw*bh - inter
        iou = inter / union if union else 0.0
        overlaps.append(iou)
        left_edge, top_edge = min(al, bl), min(at, bt)
        right_edge, bottom_edge = max(ar, br), max(ab, bb)
        merged.append(f"{ap[0]} {(left_edge+right_edge)/2:.8f} {(top_edge+bottom_edge)/2:.8f} "
                      f"{right_edge-left_edge:.8f} {bottom_edge-top_edge:.8f}")
    min_iou = min(overlaps, default=1.0)
    return (tuple(merged) if min_iou >= threshold else None), min_iou


def pet_root_from(path: Path) -> Path:
    if (path / "images" / "train").is_dir() and (path / "labels" / "train").is_dir():
        return path
    candidates = [child for child in path.iterdir() if child.is_dir() and (child / "images" / "train").is_dir()]
    if len(candidates) != 1:
        raise ValueError(f"Expected one extracted KNR-PET-7 dataset under {path}; found {len(candidates)}")
    return candidates[0]


def pet_filename_class(stem: str) -> int:
    for prefix, class_id in sorted(PET_FILENAME_CLASS.items(), key=lambda item: -len(item[0])):
        if stem.startswith(prefix):
            return class_id
    raise ValueError(f"KNR-PET-7 filename has no recognized class prefix: {stem}")


def audit_pet_records(pet_root: Path) -> tuple[list[dict[str, Any]], int, int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate every image/label and deduplicate exact bytes without split leakage."""
    paths = sorted(p for split in ("train", "val", "test")
                   for p in (pet_root / "images" / split).iterdir() if p.is_file())
    if len(paths) != 5424:
        raise ValueError(f"KNR-PET-7 expected 5,424 images; found {len(paths)}")
    groups: dict[str, list[dict[str, Any]]] = {}
    source_boxes = 0
    for image_path in paths:
        split = image_path.parent.name
        label_path = pet_root / "labels" / split / f"{image_path.stem}.txt"
        if split not in {"train", "val", "test"} or not label_path.is_file():
            raise ValueError(f"Missing/invalid split label for {image_path}")
        expected_class_id = pet_filename_class(image_path.stem)
        converted, provenance = [], []
        for line_number, line in enumerate(label_path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            source_class_id, box, box_meta = convert_obb_line(line, line_number, label_path)
            if source_class_id != expected_class_id:
                raise ValueError(f"Filename/label class mismatch in {label_path}: expected {expected_class_id}, got {source_class_id}")
            converted.append(box)
            provenance.append(box_meta)
        if not converted:
            raise ValueError(f"No annotated bottle box in {label_path}")
        source_boxes += len(converted)
        with Image.open(image_path) as image:
            if image.size != (1920, 1200):
                raise ValueError(f"Unexpected KNR image dimensions {image.size}: {image_path}")
            image.verify()
        digest = sha256(image_path)
        groups.setdefault(digest, []).append({
            "source_image": image_path, "source_label": label_path, "split": split,
            "sha256": digest, "converted": tuple(converted), "provenance": provenance,
            "source_class_id": expected_class_id,
        })

    keep, duplicates, conflicts = [], [], []
    split_rank = {"train": 0, "val": 1, "test": 2}
    for digest, records in groups.items():
        records.sort(key=lambda item: (split_rank[item["split"]], item["source_image"].name))
        source_classes = {item["source_class_id"] for item in records}
        merged = records[0]["converted"]
        min_iou = 1.0
        valid = len(source_classes) == 1
        for item in records[1:]:
            updated, iou = merge_duplicate_boxes(merged, item["converted"], threshold=0.85)
            min_iou = min(min_iou, iou)
            if updated is None:
                valid = False
                break
            merged = updated
        if not valid:
            conflicts.append({"sha256": digest, "records": [str(item["source_image"]) for item in records],
                              "source_class_ids": sorted(source_classes), "action": "exclude all exact duplicates; needs human label review",
                              "minimum_observed_box_iou": round(min_iou, 6)})
            continue
        canonical_split = max((item["split"] for item in records), key=split_rank.get)
        canonical = next(item for item in records if item["split"] == canonical_split)
        canonical = dict(canonical)
        canonical["converted"] = merged
        canonical["duplicate_sources"] = [str(item["source_image"]) for item in records
                                           if item["source_image"] != canonical["source_image"]]
        canonical["duplicate_iou"] = min_iou
        canonical["source_image_count_in_group"] = len(records)
        keep.append(canonical)
        if len(records) > 1:
            duplicates.append({"sha256": digest, "kept": str(canonical["source_image"]),
                               "kept_split": canonical_split,
                               "dropped": [str(item["source_image"]) for item in records
                                           if item["source_image"] != canonical["source_image"]],
                               "minimum_box_iou": round(min_iou, 6),
                               "action": "keep highest-priority split (test, then val, then train); union reviewed same-class boxes"})
    keep.sort(key=lambda item: (item["split"], item["source_image"].name))
    return keep, len(paths), source_boxes, duplicates, conflicts


def merge(base: Path, pet_path: Path, out: Path) -> dict[str, Any]:
    if out.exists():
        raise ValueError(f"Output already exists; choose a new directory: {out}")
    base_manifest_path = base / "dataset_manifest.json"
    if not base_manifest_path.is_file():
        raise ValueError(f"Audited base dataset manifest is missing: {base_manifest_path}")
    base_manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))
    classes = base_manifest["classes"]
    if "plastic" not in classes:
        raise ValueError("The reviewed base taxonomy does not include plastic")
    pet_root = pet_root_from(pet_path)
    pet_metadata = pet_root / "metadata" / "image_metadata.csv"
    pet_readme = pet_root / "README.md"
    pet_license = pet_root / "LICENSE.txt"
    for required in (pet_metadata, pet_readme, pet_license):
        if not required.is_file():
            raise ValueError(f"KNR-PET-7 source metadata missing: {required}")

    out.mkdir(parents=True)
    for split in ("train", "val", "test"):
        (out / split / "images").mkdir(parents=True)
        (out / split / "labels").mkdir(parents=True)

    rows: list[dict[str, Any]] = []
    exact_hashes: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    exact_duplicate_records: list[dict[str, str]] = []
    counts = {split: {category: {"images": 0, "boxes": 0} for category in classes}
              for split in ("train", "val", "test")}
    source_images: Counter[str] = Counter()

    # Preserve the previously audited TACO subset and its sealed split assignment.
    for item in base_manifest["images"]:
        split = item["split"]
        source_image = base / item["image"]
        source_label = base / item["label"]
        if split not in counts or not source_image.is_file() or not source_label.is_file():
            raise ValueError(f"Incomplete TACO row: {item}")
        digest = sha256(source_image)
        if item.get("sha256") and digest != item["sha256"]:
            raise ValueError(f"TACO image hash changed: {source_image}")
        label_rows = tuple(line for line in source_label.read_text(encoding="utf-8").splitlines() if line.strip())
        if digest in exact_hashes:
            prior_path, prior_split, prior_labels = exact_hashes[digest]
            if prior_split != split:
                raise ValueError(f"Exact duplicate crosses splits: {source_image} and {prior_path}")
            merged_labels, iou = merge_duplicate_boxes(prior_labels, label_rows, threshold=1.0)
            if merged_labels is None:
                raise ValueError(f"Exact duplicate has conflicting labels; manual review required: {source_image} and {prior_path}")
            exact_duplicate_records.append({"duplicate": str(source_image), "kept": prior_path,
                                            "split": split, "minimum_box_iou": f"{iou:.6f}",
                                            "action": "identical image; duplicate dropped, retained same-class box with IoU >= 0.90"})
            continue
        exact_hashes[digest] = (str(source_image), split, label_rows)
        target_stem = f"taco_{source_image.stem}"
        target_image = out / split / "images" / f"{target_stem}.jpg"
        target_label = out / split / "labels" / f"{target_stem}.txt"
        shutil.copy2(source_image, target_image)
        shutil.copy2(source_label, target_label)
        with Image.open(target_image) as image:
            image.verify()
        label_rows = [line for line in target_label.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in label_rows:
            class_id = int(line.split()[0])
            counts[split][classes[class_id]]["boxes"] += 1
        for category in {classes[int(line.split()[0])] for line in label_rows}:
            counts[split][category]["images"] += 1
        row = dict(item)
        row.update({"image": target_image.relative_to(out).as_posix(),
                    "label": target_label.relative_to(out).as_posix(),
                    "sha256": digest,
                    "source_split_preserved": split})
        rows.append(row)
        source_images["taco_odbl"] += 1

    # Audit and deduplicate all PET records before writing output, prioritizing test > val > train.
    pet_records, source_pet_image_count, source_pet_label_count, pet_duplicates, pet_conflicts = audit_pet_records(pet_root)
    pet_label_count = 0
    pet_cross_source_duplicates = []
    for record in pet_records:
        source_image = record["source_image"]
        source_label = record["source_label"]
        split = record["split"]
        digest = record["sha256"]
        converted = list(record["converted"])
        box_provenance = record["provenance"]
        converted_signature = tuple(converted)
        if digest in exact_hashes:
            prior_path, prior_split, _ = exact_hashes[digest]
            pet_cross_source_duplicates.append({"dropped": str(source_image), "matching_source": prior_path,
                                                "pet_split": split, "matching_split": prior_split,
                                                "action": "drop PET record to preserve already-audited TACO subset and prevent duplicate leakage"})
            continue
        exact_hashes[digest] = (str(source_image), split, converted_signature)
        target_stem = f"knr_pet7_{source_image.stem}"
        target_image = out / split / "images" / f"{target_stem}.jpg"
        target_label = out / split / "labels" / f"{target_stem}.txt"
        if source_image.suffix.lower() in {".jpg", ".jpeg"}:
            shutil.copy2(source_image, target_image)
        else:
            with Image.open(source_image) as original:
                original.convert("RGB").save(target_image, format="JPEG", quality=95, subsampling=0)
        with target_label.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(converted) + "\n")
        with Image.open(target_image) as image:
            if image.size != (1920, 1200):
                raise ValueError(f"Unexpected KNR image dimensions {image.size}: {source_image}")
            image.verify()
        counts[split]["plastic"]["images"] += 1
        counts[split]["plastic"]["boxes"] += len(converted)
        pet_label_count += len(converted)
        rows.append({
            "image": target_image.relative_to(out).as_posix(),
            "label": target_label.relative_to(out).as_posix(),
            "source": "knr_pet7_v2",
            "source_file": source_image.relative_to(pet_root).as_posix(),
            "source_url": PET_SOURCE_URL,
            "license": PET_LICENSE,
            "sha256": sha256(target_image),
            "source_sha256": digest,
            "source_split": split,
            "source_split_preserved": split,
            "group": f"knr_pet7_v2:{source_image.stem}",
            "duplicate_sources": [Path(path).relative_to(pet_root).as_posix()
                                  for path in record["duplicate_sources"]],
            "duplicate_box_min_iou": record["duplicate_iou"],
            "source_image_count_in_duplicate_group": record["source_image_count_in_group"],
            "source_annotation_format": "YOLO OBB 4-corner polygon",
            "target_annotation_format": "YOLO axis-aligned xywh enclosing box",
            "boxes": box_provenance,
        })
        source_images["knr_pet7_v2"] += 1
    if source_pet_label_count != 5425:
        raise ValueError(f"KNR-PET-7 expected 5,425 source objects; audited {source_pet_label_count}")

    (out / "data.yaml").write_text(
        "path: .\ntrain: train/images\nval: val/images\ntest: test/images\n"
        f"nc: {len(classes)}\nnames: [{', '.join(classes)}]\n", encoding="utf-8")
    taxonomy = json.loads((base / "taxonomy.json").read_text(encoding="utf-8"))
    (out / "taxonomy.json").write_text(json.dumps({"version": taxonomy.get("version"),
        "classes": classes}, indent=2), encoding="utf-8")
    report = {
        "dataset_id": out.name,
        "classes": classes,
        "images": len(rows),
        "source_image_counts": dict(source_images),
        "counts_by_split_and_class": counts,
        "total_boxes": {category: sum(counts[s][category]["boxes"] for s in counts) for category in classes},
        "total_class_images": {category: sum(counts[s][category]["images"] for s in counts) for category in classes},
        "exact_duplicate_images_dropped": sum(len(group["dropped"]) for group in pet_duplicates) + len(pet_cross_source_duplicates),
        "taco_exact_duplicate_records_dropped": exact_duplicate_records,
        "cross_split_exact_duplicates_removed_by_split_priority": sum(
            1 for group in pet_duplicates if len({Path(p).parent.name for p in [group["kept"], *group["dropped"]]}) > 1),
        "pet_duplicate_groups": pet_duplicates,
        "pet_conflicting_duplicate_groups_excluded_for_manual_review": pet_conflicts,
        "pet_cross_source_duplicate_records_dropped": pet_cross_source_duplicates,
        "pet_source_images": source_pet_image_count,
        "pet_retained_images_before_cross_source_dedup": len(pet_records),
        "pet_retained_images_after_cross_source_dedup": source_images["knr_pet7_v2"],
        "pet_source_boxes": source_pet_label_count,
        "pet_retained_boxes": pet_label_count,
        "preserved_official_splits": True,
        "pet_source_sha256": "46dc8bbb3643d56bc4a8930137df23cfacb1c0c5607b86272052e19783dafbd3",
        "pet_source_license": PET_LICENSE,
        "pet_source_url": PET_SOURCE_URL,
        "mapping_note": "KNR-PET-7 B1/B2.1/B2.2/B3/B4/B5/B6 all denote post-consumer PET bottle categories; merged only into plastic, source codes retained per box.",
        "warnings": ["KNR-PET-7 uses a controlled industrial imaging setup, so its 5,424 images do not represent diverse household multi-waste scenes.",
                     "Axis-aligned rectangles enclose the original oriented bottle polygons and may include extra background pixels."],
    }
    manifest = {"schema_version": "2.0", "classes": classes, "seed": base_manifest.get("seed"),
                "split_policy": "preserve audited TACO assignments and official KNR-PET-7 train/val/test assignments",
                "images": rows, "readiness": report}
    (out / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "readiness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("datasets/multiclass_v2"))
    parser.add_argument("--pet-root", type=Path, default=Path("datasets/knr_pet7/extracted"))
    parser.add_argument("--out", type=Path, default=Path("datasets/multiclass_v3"))
    args = parser.parse_args()
    result = merge(args.base, args.pet_root, args.out)
    print(json.dumps(result, indent=2))
