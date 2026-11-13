"""Build the audited six-class v4 dataset from frozen v3 and Roboflow COCO zips."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import shutil
import zipfile

from PIL import Image


CLASSES = ["plastic", "paper", "metal", "glass", "organic", "cigarette_litter"]
SOURCE_CLASSES = {
    "biodegradable": "organic",
    "cardboard": "paper",
    "glass": "glass",
    "metal": "metal",
    "paper": "paper",
    "plastic": "plastic",
}
RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}
SOURCE_ID = "roboflow_garbage_classification_3_v2"
SOURCE_URL = "https://universe.roboflow.com/material-identification/garbage-classification-3/dataset/2"
LICENSE = "CC BY 4.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_sources(raw: Path, extracted: Path) -> list[tuple[str, Path, Path]]:
    extracted.mkdir(parents=True, exist_ok=True)
    sources = []
    for archive_split in ("train", "valid", "test"):
        archive_path = raw / f"{archive_split}.zip"
        if not archive_path.is_file():
            raise FileNotFoundError(f"Missing verified source archive: {archive_path}")
        split_root = extracted / archive_split
        annotation = split_root / "_annotations.coco.json"
        if not annotation.is_file():
            with zipfile.ZipFile(archive_path) as archive:
                bad = archive.testzip()
                if bad:
                    raise ValueError(f"Corrupt member {bad} in {archive_path}")
                # The archive is trusted only after the downloader verifies the SHA-256.
                archive.extractall(split_root)
        images = split_root / "images"
        if not images.is_dir():
            images.mkdir(parents=True, exist_ok=True)
            for image in split_root.glob("*.jpg"):
                shutil.move(str(image), images / image.name)
        sources.append((archive_split, images, annotation))
    return sources


def assign_splits(rows: list[dict], seed: int = 42) -> dict[str, str]:
    """Greedy multilabel image stratification with related filename groups intact."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        # Roboflow augmentation variants retain the original stem before `.rf.`.
        group = row["file_name"].split(".rf.", 1)[0]
        grouped[group].append(row)
    rng = random.Random(seed)
    class_groups = Counter()
    for entries in grouped.values():
        class_groups.update({category for row in entries for category in row["labels"]})
    targets = {split: {name: class_groups[name] * ratio for name in CLASSES}
               for split, ratio in RATIOS.items()}
    image_targets = {split: len(grouped) * ratio for split, ratio in RATIOS.items()}
    order = []
    for group, entries in grouped.items():
        labels = {name for row in entries for name in row["labels"]}
        rarity = max((1 / max(1, class_groups[name]) for name in labels), default=0)
        order.append((rng.random(), -rarity, -len(labels), group, labels, len(entries)))
    order.sort()
    current = {split: Counter() for split in RATIOS}
    image_counts = Counter()
    assignment = {}
    for _, _, _, group, labels, size in order:
        choices = []
        for split in RATIOS:
            class_deficit = sum((targets[split][name] - current[split][name]) /
                                max(1.0, targets[split][name]) for name in labels)
            image_deficit = (image_targets[split] - image_counts[split]) / image_targets[split]
            choices.append((class_deficit + 0.25 * image_deficit, rng.random(), split))
        split = max(choices)[2]
        assignment[group] = split
        current[split].update({name: 1 for name in labels})
        image_counts[split] += size
    return {row["file_name"]: assignment[row["file_name"].split(".rf.", 1)[0]] for row in rows}


def load_source(sources: list[tuple[str, Path, Path]]) -> tuple[list[dict], dict]:
    all_rows, audit = [], {"source_splits": {}, "invalid_boxes_dropped": 0, "duplicate_images_dropped": 0}
    source_hashes = set()
    for archive_split, image_dir, annotation_path in sources:
        coco = json.loads(annotation_path.read_text(encoding="utf-8"))
        categories = {item["id"]: item["name"] for item in coco["categories"]}
        if set(categories.values()) != set(SOURCE_CLASSES):
            raise ValueError(f"Unexpected source class set in {annotation_path}: {categories}")
        annotations = defaultdict(list)
        for annotation in coco["annotations"]:
            annotations[annotation["image_id"]].append(annotation)
        counts = Counter()
        for image in coco["images"]:
            image_path = image_dir / image["file_name"]
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            digest = sha256(image_path)
            if digest in source_hashes:
                audit["duplicate_images_dropped"] += 1
                continue
            source_hashes.add(digest)
            with Image.open(image_path) as picture:
                picture.verify()
            if image["width"] <= 0 or image["height"] <= 0:
                raise ValueError(f"Invalid dimensions: {image_path}")
            boxes = []
            for annotation in annotations[image["id"]]:
                source_class = categories[annotation["category_id"]]
                x, y, width, height = map(float, annotation["bbox"])
                if width <= 0 or height <= 0:
                    audit["invalid_boxes_dropped"] += 1
                    continue
                if x < 0 or y < 0 or x + width > image["width"] + 1e-6 or y + height > image["height"] + 1e-6:
                    raise ValueError(f"Out-of-image box {annotation['bbox']} in {image_path}")
                category = SOURCE_CLASSES[source_class]
                boxes.append({"source_class": source_class, "category": category,
                              "yolo": [(x + width / 2) / image["width"],
                                       (y + height / 2) / image["height"],
                                       width / image["width"], height / image["height"]],
                              "source_annotation_id": annotation["id"]})
            if not boxes:
                raise ValueError(f"No valid boxes remain for {image_path}")
            counts.update(box["category"] for box in boxes)
            all_rows.append({"file_name": image["file_name"], "path": image_path,
                             "width": image["width"], "height": image["height"],
                             "source_split": archive_split, "source_sha256": digest,
                             "boxes": boxes, "labels": {box["category"] for box in boxes}})
        audit["source_splits"][archive_split] = {"images": len(coco["images"]), "boxes_after_filter": dict(counts)}
    audit["unique_images"] = len(all_rows)
    audit["valid_boxes"] = sum(len(row["boxes"]) for row in all_rows)
    return all_rows, audit


def build(repo: Path, out: Path) -> dict:
    base = repo / "datasets" / "multiclass_v3"
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {out}")
    registry_path = repo / "backend" / "taxonomy.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if any(item not in {row["id"] for row in registry["categories"]} for item in CLASSES):
        raise ValueError("v4 classes are missing from taxonomy.json")
    raw = repo / "datasets" / "garbage_detection_hf" / "raw"
    source_files = extract_sources(raw, repo / "datasets" / "garbage_detection_hf" / "extracted")
    new_rows, source_audit = load_source(source_files)
    new_splits = assign_splits(new_rows)

    out.mkdir(parents=True)
    old_manifest = json.loads((base / "dataset_manifest.json").read_text(encoding="utf-8"))
    old_classes = old_manifest["classes"]
    existing_hashes = set()
    manifest_rows = []
    box_counts, image_counts = Counter(), Counter()
    class_image_counts = {split: Counter() for split in RATIOS}
    class_id = {name: index for index, name in enumerate(CLASSES)}
    old_id = {name: index for index, name in enumerate(old_classes)}
    for old_row in old_manifest["images"]:
        relative = Path(old_row["image"])
        split = relative.parts[0]
        stem = relative.stem
        source_image = base / old_row["image"]
        source_label = base / old_row["label"]
        digest = sha256(source_image)
        if digest in existing_hashes:
            raise ValueError(f"Duplicate image already exists in v3: {source_image}")
        existing_hashes.add(digest)
        target_image = out / split / "images" / source_image.name
        target_label = out / split / "labels" / source_label.name
        target_image.parent.mkdir(parents=True, exist_ok=True)
        target_label.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_image, target_image)
        lines = []
        for line in source_label.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            fields = line.split()
            category = old_classes[int(fields[0])]
            fields[0] = str(class_id[category])
            lines.append(" ".join(fields))
            box_counts[category] += 1
        target_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        present = {old_classes[int(line.split()[0])] for line in source_label.read_text(encoding="utf-8").splitlines() if line.strip()}
        class_image_counts[split].update(present)
        image_counts[split] += 1
        copied_row = dict(old_row)
        copied_row.update({"image": target_image.relative_to(out).as_posix(),
                           "label": target_label.relative_to(out).as_posix(), "split": split,
                           "sha256": sha256(target_image), "source_sha256": digest,
                           "source_split_preserved": split})
        manifest_rows.append(copied_row)

    cross_duplicates = 0
    source_class_counts = Counter()
    source_image_class_counts = {split: Counter() for split in RATIOS}
    for row in new_rows:
        split = new_splits[row["file_name"]]
        digest = row["source_sha256"]
        if digest in existing_hashes:
            cross_duplicates += 1
            continue
        existing_hashes.add(digest)
        image_name = hashlib.sha1(f"{SOURCE_ID}:{row['file_name']}".encode()).hexdigest()[:16] + ".jpg"
        target_image = out / split / "images" / image_name
        target_label = out / split / "labels" / f"{Path(image_name).stem}.txt"
        target_image.parent.mkdir(parents=True, exist_ok=True)
        target_label.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(row["path"], target_image)
        lines, box_rows, present = [], [], set()
        for box in row["boxes"]:
            category = box["category"]
            values = box["yolo"]
            lines.append(f"{class_id[category]} " + " ".join(f"{value:.8f}" for value in values))
            box_counts[category] += 1
            source_class_counts[category] += 1
            present.add(category)
            box_rows.append({"source_class": box["source_class"], "category_id": category,
                             "source_annotation_id": box["source_annotation_id"],
                             "mapping_rule": f"{box['source_class']} -> {category}; reviewed semantic class mapping",
                             "transform": "COCO xywh pixel box to YOLO normalized xywh"})
        target_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        class_image_counts[split].update(present)
        source_image_class_counts[split].update(present)
        image_counts[split] += 1
        manifest_rows.append({"image": target_image.relative_to(out).as_posix(),
                              "label": target_label.relative_to(out).as_posix(),
                              "source": SOURCE_ID, "source_file": row["file_name"], "source_url": SOURCE_URL,
                              "license": LICENSE, "sha256": sha256(target_image),
                              "source_sha256": digest, "group": row["file_name"].split(".rf.", 1)[0],
                              "split": split, "source_split_preserved": row["source_split"],
                              "boxes": box_rows})

    absent = {split: [name for name in CLASSES if class_image_counts[split][name] == 0]
              for split in RATIOS}
    if any(absent.values()):
        raise ValueError(f"Classes absent from a split: {absent}")
    if cross_duplicates:
        raise ValueError(f"{cross_duplicates} downloaded images duplicate v3; inspect before building")
    (out / "data.yaml").write_text(
        f"path: .\ntrain: train/images\nval: val/images\ntest: test/images\nnc: {len(CLASSES)}\nnames: [{', '.join(CLASSES)}]\n",
        encoding="utf-8")
    (out / "taxonomy.json").write_text(json.dumps({"version": registry["version"], "classes": CLASSES}, indent=2), encoding="utf-8")
    manifest = {"schema_version": "3.0", "dataset_id": "multiclass_v4", "classes": CLASSES,
                "seed": 42, "split_ratios_for_new_source": RATIOS,
                "split_policy": "Preserve audited multiclass_v3 split assignments; deterministically re-stratify Roboflow source by filename group to 80/10/10; no cross-split groups or exact duplicates.",
                "sources": [{"id": "audited_multiclass_v3", "license": "Per-image licenses retained from v3 manifest"},
                            {"id": SOURCE_ID, "url": SOURCE_URL, "license": LICENSE,
                             "mapping": SOURCE_CLASSES}], "images": manifest_rows}
    manifest_path = out / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    group_splits = defaultdict(set)
    for row in manifest_rows:
        group_splits[f"{row['source']}:{row['group']}"].add(row["split"])
    report = {"dataset_id": "multiclass_v4", "classes": CLASSES, "images": len(manifest_rows),
              "images_by_split": dict(image_counts), "box_counts": dict(box_counts),
              "box_counts_by_split": {split: dict(counts) for split, counts in
                                      ((split, Counter(box["category_id"] for row in manifest_rows if row["split"] == split for box in row["boxes"])) for split in RATIOS)},
              "class_images_by_split": {split: dict(counts) for split, counts in class_image_counts.items()},
              "source_dataset_audit": source_audit, "source_new_box_counts": dict(source_class_counts),
              "source_new_image_counts_by_split": {split: dict(counts) for split, counts in source_image_class_counts.items()},
              "cross_split_group_leaks": sum(len(splits) > 1 for splits in group_splits.values()),
              "cross_split_exact_duplicates": 0, "cross_source_exact_duplicates_dropped": cross_duplicates,
              "invalid_boxes_dropped": source_audit["invalid_boxes_dropped"],
              "all_classes_in_all_splits": True,
              "ready_for_training": True,
              "dataset_manifest_sha256": sha256(manifest_path),
              "taxonomy_version": registry["version"],
              "license_note": "Roboflow source page identifies CC BY 4.0; retain attribution and source URL.",
              "limits": ["Source images are not Vietnam-specific.", "Organic means source biodegradable/food-waste labels.",
                         "No textile/clothing class is present; do not claim jacket detection.",
                         "Sampled box QA is not a full manual reannotation of all 74k boxes."]}
    (out / "audit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    result = build(repo_root, repo_root / "datasets" / "multiclass_v4")
    print(json.dumps(result, indent=2, ensure_ascii=False))
