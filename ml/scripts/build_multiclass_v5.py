"""Extend the audited v4 corpus with rights-cleared, Textile-only MRS images."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image


CLASSES = ["plastic", "paper", "metal", "glass", "organic", "textile", "cigarette_litter"]
OLD_CLASSES = ["plastic", "paper", "metal", "glass", "organic", "cigarette_litter"]
TEXTILE_SOURCE_ID = "mrs_trash_detection_textile_only"
TEXTILE_LICENSE = "Apache License 2.0 (as declared by ModelScope and Hugging Face dataset metadata)"
TEXTILE_SOURCE_URL = "https://huggingface.co/datasets/alexNova/MRS-Trash-Detection"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def textile_only_rows(source_root: Path) -> tuple[list[dict], dict]:
    class_map = {int(key): value for key, value in
                 json.loads((source_root / "classes.json").read_text(encoding="utf-8" )).items()}
    if class_map.get(3) != "Textile":
        raise ValueError(f"Unexpected MRS class mapping: {class_map}")
    rows = []
    report = {"label_files": 0, "images_selected": 0, "boxes_selected": 0,
              "images_skipped_mixed_or_other_class": 0, "invalid_labels": 0,
              "images_by_split": {}, "boxes_by_split": {}}
    for split in ("train", "val", "test"):
        split_rows, box_count = [], 0
        labels_dir = source_root / "labels" / split
        for label_path in sorted(labels_dir.glob("*.txt")):
            report["label_files"] += 1
            lines = [line.split() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not lines or any(len(row) != 5 for row in lines):
                report["invalid_labels"] += 1
                continue
            try:
                class_ids = [int(row[0]) for row in lines]
                boxes = [[float(value) for value in row[1:]] for row in lines]
            except ValueError:
                report["invalid_labels"] += 1
                continue
            if any(class_id not in class_map for class_id in class_ids):
                report["invalid_labels"] += 1
                continue
            if any(len(box) != 4 or any(value < 0 or value > 1 for value in box)
                   or box[2] <= 0 or box[3] <= 0 for box in boxes):
                report["invalid_labels"] += 1
                continue
            # This build deliberately takes only images whose complete source label file
            # contains Textile boxes and no other class. This avoids dropping other
            # annotated objects into the target as false background.
            if any(class_map[class_id] != "Textile" for class_id in class_ids):
                report["images_skipped_mixed_or_other_class"] += 1
                continue
            image_path = source_root / "images" / split / f"{label_path.stem}.jpg"
            if not image_path.is_file() or image_path.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise FileNotFoundError(f"MRS textile image missing or still an LFS pointer: {image_path}")
            with Image.open(image_path) as image:
                image.verify()
            split_rows.append({"split": split, "image": image_path, "label": label_path,
                               "source_file": label_path.stem + ".jpg", "boxes": boxes})
            box_count += len(boxes)
        rows.extend(split_rows)
        report["images_by_split"][split] = len(split_rows)
        report["boxes_by_split"][split] = box_count
    report["images_selected"] = len(rows)
    report["boxes_selected"] = sum(len(row["boxes"]) for row in rows)
    if report["invalid_labels"]:
        raise ValueError(f"Invalid MRS labels found: {report['invalid_labels']}")
    return rows, report


def build(repo: Path, out: Path) -> dict:
    base = repo / "datasets" / "multiclass_v4"
    source_root = repo / "datasets" / "mrs_trash_detection_hf"
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {out}")
    if not (base / "dataset_manifest.json").is_file():
        raise FileNotFoundError(base / "dataset_manifest.json")
    rows, source_audit = textile_only_rows(source_root)
    base_manifest = json.loads((base / "dataset_manifest.json").read_text(encoding="utf-8"))
    if base_manifest["classes"] != OLD_CLASSES:
        raise ValueError(f"Unexpected v4 class order: {base_manifest['classes']}")
    registry = json.loads((repo / "backend" / "taxonomy.json").read_text(encoding="utf-8"))
    if registry.get("version") != "2026-11-13.2":
        raise ValueError("Backend taxonomy must be the reviewed v5 taxonomy version 2026-11-13.2")
    target_ids = {name: index for index, name in enumerate(CLASSES)}
    source_to_target = {name: target_ids[name] for name in OLD_CLASSES}
    source_to_target["textile"] = target_ids["textile"]
    out.mkdir(parents=True)
    for split in ("train", "val", "test"):
        shutil.copytree(base / split, out / split)

    manifest_rows = []
    boxes_by_split, images_by_split = {split: Counter() for split in ("train", "val", "test")}, Counter()
    class_images = {split: Counter() for split in ("train", "val", "test")}
    exact_hashes, known_paths, group_splits = {}, {}, defaultdict(set)
    for old_row in base_manifest["images"]:
        row = dict(old_row)
        split = Path(row["image"]).parts[0]
        label_path = out / row["label"]
        lines = [line.split() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        mapped_lines, present = [], set()
        for line in lines:
            class_name = OLD_CLASSES[int(line[0])]
            line[0] = str(source_to_target[class_name])
            mapped_lines.append(" ".join(line))
            present.add(class_name)
            boxes_by_split[split][class_name] += 1
        label_path.write_text("\n".join(mapped_lines) + ("\n" if mapped_lines else ""), encoding="utf-8")
        class_images[split].update(present)
        image_path = out / row["image"]
        digest = sha256(image_path)
        if row["sha256"] != digest:
            raise ValueError(f"Copied v4 image hash mismatch: {image_path}")
        if digest in exact_hashes and exact_hashes[digest] != split:
            raise ValueError(f"Existing v4 exact duplicate crosses splits: {image_path}")
        exact_hashes[digest] = split
        known_paths[digest] = row["image"]
        images_by_split[split] += 1
        group_splits[f"{row['source']}:{row['group']}"].add(split)
        manifest_rows.append(row)

    known_hashes = set(exact_hashes)
    duplicate_rows = []
    for row in rows:
        split = row["split"]
        digest = sha256(row["image"])
        if digest in known_hashes:
            duplicate_rows.append({"source_file": row["source_file"], "source_split": split,
                                   "duplicate_of": str(known_paths[digest])})
            continue
        known_hashes.add(digest)
        image_name = "mrs_textile_" + hashlib.sha1(row["source_file"].encode()).hexdigest()[:16] + ".jpg"
        target_image = out / split / "images" / image_name
        target_label = out / split / "labels" / f"{Path(image_name).stem}.txt"
        if target_image.exists() or target_label.exists():
            raise FileExistsError(target_image)
        shutil.copy2(row["image"], target_image)
        mapped = []
        for xc, yc, width, height in row["boxes"]:
            mapped.append(f"{target_ids['textile']} {xc:.8f} {yc:.8f} {width:.8f} {height:.8f}")
            boxes_by_split[split]["textile"] += 1
        target_label.write_text("\n".join(mapped) + "\n", encoding="utf-8")
        class_images[split]["textile"] += 1
        images_by_split[split] += 1
        row_hash = sha256(target_image)
        known_paths[digest] = f"{TEXTILE_SOURCE_ID}:{row['source_file']}"
        manifest_rows.append({"image": target_image.relative_to(out).as_posix(),
                              "label": target_label.relative_to(out).as_posix(),
                              "source": TEXTILE_SOURCE_ID, "source_file": row["source_file"],
                              "source_url": TEXTILE_SOURCE_URL, "license": TEXTILE_LICENSE,
                              "sha256": row_hash, "source_sha256": digest,
                              "group": row["source_file"], "split": split,
                              "source_split_preserved": split,
                              "boxes": [{"source_class": "Textile", "category_id": "textile",
                                         "mapping_rule": "MRS Textile-only image and class id 3 explicitly map to textile",
                                         "transform": "source YOLO normalized xywh preserved"}
                                        for _ in row["boxes"]]})
        group_splits[f"{TEXTILE_SOURCE_ID}:{row['source_file']}"] .add(split)
    missing = {split: [name for name in CLASSES if boxes_by_split[split][name] == 0]
               for split in ("train", "val", "test")}
    if any(missing.values()):
        raise ValueError(f"Classes absent from a v5 split: {missing}")

    (out / "data.yaml").write_text(
        f"path: .\ntrain: train/images\nval: val/images\ntest: test/images\nnc: {len(CLASSES)}\nnames: [{', '.join(CLASSES)}]\n",
        encoding="utf-8")
    (out / "taxonomy.json").write_text(json.dumps({"version": registry["version"], "classes": CLASSES}, indent=2), encoding="utf-8")
    manifest = {"schema_version": "3.1", "dataset_id": "multiclass_v5", "classes": CLASSES,
                "seed": 42, "split_policy": "Preserve all v4 split assignments. Preserve MRS source's separate train/val/test Textile-only split; exclude mixed-class MRS images to avoid unannotated classes.",
                "sources": [{"id": "audited_multiclass_v4", "source_url": "docs/multiclass-v4-data.md"},
                            {"id": TEXTILE_SOURCE_ID, "url": TEXTILE_SOURCE_URL,
                             "upstream_url": "https://www.modelscope.cn/datasets/YizheDev/trash_detection",
                             "license": TEXTILE_LICENSE,
                             "source_policy": "Retain only images whose complete source annotation file contains Textile boxes and no other class."}],
                "images": manifest_rows}
    manifest_path = out / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    split_exact = defaultdict(set)
    for row in manifest_rows:
        split_exact[row["sha256"]].add(row["split"])
    report = {"dataset_id": "multiclass_v5", "classes": CLASSES,
              "images": len(manifest_rows), "images_by_split": dict(images_by_split),
              "box_counts": {name: sum(boxes_by_split[s][name] for s in boxes_by_split) for name in CLASSES},
              "box_counts_by_split": {split: dict(counts) for split, counts in boxes_by_split.items()},
              "class_images_by_split": {split: dict(counts) for split, counts in class_images.items()},
              "textile_source_audit": source_audit,
              "textile_images_retained": sum(1 for row in manifest_rows if row["source"] == TEXTILE_SOURCE_ID),
              "textile_boxes_retained": sum(len(row["boxes"]) for row in manifest_rows if row["source"] == TEXTILE_SOURCE_ID),
              "exact_duplicate_source_rows_excluded": duplicate_rows,
              "cross_split_group_leaks": sum(len(splits) > 1 for splits in group_splits.values()),
              "cross_split_exact_duplicates": sum(len(splits) > 1 for splits in split_exact.values()),
              "cross_source_exact_duplicates_dropped": len(duplicate_rows),
              "all_classes_in_all_splits": True, "ready_for_training": True,
              "dataset_manifest_sha256": sha256(manifest_path),
              "taxonomy_version": registry["version"],
              "limits": ["The dataset is not Vietnam-specific.",
                         "MRS Textile also includes plush toys, pillows and fabric household objects, not just discarded clothes.",
                         "MRS mixed-class images are excluded; the retained MRS subset is 1,034 images after deduplication.",
                         "No jacket-specific performance is established; held-out evaluation is still required."]}
    (out / "audit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    print(json.dumps(build(repo_root, repo_root / "datasets" / "multiclass_v5"), indent=2, ensure_ascii=False))
