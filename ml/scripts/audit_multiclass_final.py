"""Full integrity, decode, label, provenance, and cross-split near-duplicate audit."""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from perceptual_hash import dhash_image, phash_image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cross_split_near_pairs(hash_rows: dict[int, list[tuple[str, str]]], max_distance: int) -> tuple[int, list[list[str]]]:
    samples = {}
    for value, entries in hash_rows.items():
        by_split = defaultdict(list)
        for split, path in entries:
            by_split[split].append(path)
        samples[value] = by_split
    bands = defaultdict(set)
    for value in samples:
        for band in range(8):
            bands[(band, (value >> (band * 8)) & 0xff)].add(value)
    pairs = set(); examples = []
    for value, entries in samples.items():
        candidates = set()
        for band in range(8):
            candidates.update(bands[(band, (value >> (band * 8)) & 0xff)])
        for neighbor in candidates:
            if neighbor < value or (value ^ neighbor).bit_count() > max_distance:
                continue
            different = [(paths, samples[neighbor][other_split])
                         for split, paths in entries.items()
                         for other_split in samples[neighbor] if split != other_split]
            if different:
                pairs.add((value, neighbor))
                for left_paths, right_paths in different:
                    for left in left_paths:
                        for right in right_paths:
                            if len(examples) < 100:
                                examples.append([left, right])
    return len(pairs), examples


def audit(root: Path, max_distance: int = 4) -> dict:
    root = root.resolve()
    manifest_path = root / "dataset_manifest.json"
    taxonomy_path = root / "taxonomy.json"
    yaml_path = root / "data.yaml"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    backend_taxonomy_path = Path(__file__).resolve().parents[2] / "backend" / "taxonomy.json"
    backend_taxonomy = json.loads(backend_taxonomy_path.read_text(encoding="utf-8"))
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    names = manifest["classes"]
    if taxonomy.get("classes") != names or cfg.get("names") != names or cfg.get("nc") != len(names):
        raise ValueError("data.yaml, taxonomy.json, and manifest class order/count differ")
    if taxonomy.get("version") != backend_taxonomy.get("version") or manifest.get("taxonomy_version") != backend_taxonomy.get("version"):
        raise ValueError("Dataset and backend taxonomy versions differ")
    backend_categories = {row["id"]: row for row in backend_taxonomy.get("categories", [])}
    for name in names:
        item = backend_categories.get(name)
        if not item or not item.get("detection_supported") or name.casefold() not in {v.casefold() for v in item.get("model_names", [])}:
            raise ValueError(f"Dataset class is unsupported or does not map in backend taxonomy: {name}")
    if cfg.get("path") != ".":
        raise ValueError("Portable dataset YAML must use path: .")
    manifest_hash = sha256_file(manifest_path)
    rows_by_split = defaultdict(list)
    for row in manifest.get("images", []):
        rows_by_split[row["split"]].append(row)
    listed_paths = {row["image"] for row in manifest["images"]}
    image_paths = {p.relative_to(root).as_posix() for split in ("train", "val", "test")
                   for p in (root / split / "images").rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES}
    if image_paths != listed_paths:
        raise ValueError(f"Manifest/image path mismatch: unlisted={len(image_paths-listed_paths)}, missing={len(listed_paths-image_paths)}")
    class_rows = {name: {} for name in names}
    exact_splits = defaultdict(set); group_splits = defaultdict(set)
    hash_rows: dict[int, list[tuple[str, str]]] = defaultdict(list)
    phash_rows_by_class = defaultdict(lambda: defaultdict(list))
    per_split = {}
    decode_errors = []; missing_labels = []; bad_boxes = []; manifest_hash_errors = []
    count_by_source = defaultdict(Counter)
    for split in ("train", "val", "test"):
        rows = rows_by_split[split]
        box_counts = Counter(); class_images = Counter(); unlabeled = 0
        for row in rows:
            rel_image = row["image"]; rel_label = row["label"]
            if Path(rel_image).parts[0] != split or Path(rel_label).parts[0] != split:
                raise ValueError(f"Manifest split/path mismatch: {split} {rel_image} {rel_label}")
            image = root / Path(rel_image); label = root / Path(rel_label)
            if not image.is_file() or not label.is_file():
                missing_labels.append(rel_image); continue
            try:
                raw = image.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                with Image.open(BytesIO(raw)) as source_image:
                    im = ImageOps.exif_transpose(source_image).copy()
                    im.load()
                    width, height = im.size
                    if width < 1 or height < 1: raise ValueError("empty image")
                    hash_rows[dhash_image(im)].append((split, rel_image))
            except Exception as exc:
                decode_errors.append({"image": rel_image, "error": str(exc)}); continue
            if row.get("sha256") != digest:
                manifest_hash_errors.append(rel_image)
            exact_splits[digest].add(split)
            group_splits[f"{row.get('source')}:{row.get('group')}"] .add(split)
            count_by_source[split][row.get("source", "unknown")] += 1
            lines = [line.strip() for line in label.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            expected = row.get("boxes", [])
            if len(lines) != len(expected):
                raise ValueError(f"Manifest/label box count mismatch: {rel_image} {len(lines)} != {len(expected)}")
            seen = set(); foreground_boxes = []
            for i, line in enumerate(lines):
                fields = line.split()
                try:
                    class_id = int(fields[0]); coords = [float(v) for v in fields[1:]]
                    if len(fields) != 5 or class_id < 0 or class_id >= len(names) or not all(map(math.isfinite, coords)):
                        raise ValueError
                    x, y, w, h = coords
                    if not all(0 <= v <= 1 for v in coords) or w <= 0 or h <= 0 or x-w/2 < -1e-6 or x+w/2 > 1+1e-6 or y-h/2 < -1e-6 or y+h/2 > 1+1e-6:
                        raise ValueError
                except (ValueError, IndexError):
                    bad_boxes.append(f"{rel_label}:{i+1}"); continue
                category = names[class_id]
                if expected[i].get("category_id") != category:
                    raise ValueError(f"Manifest class mapping mismatch: {rel_image} box {i}")
                box_counts[category] += 1; seen.add(category)
                foreground_boxes.append((w * h, class_id, x, y, w, h))
            if foreground_boxes:
                _, class_id, x, y, w, h = max(foreground_boxes)
                pad_x, pad_y = w * 0.05, h * 0.05
                crop = im.crop((max(0, int((x-w/2-pad_x)*width)), max(0, int((y-h/2-pad_y)*height)),
                                min(width, int((x+w/2+pad_x)*width)), min(height, int((y+h/2+pad_y)*height))))
                phash_rows_by_class[names[class_id]][phash_image(crop)].append((split, rel_image))
            for category in seen: class_images[category] += 1
            if not lines: unlabeled += 1
        per_split[split] = {"images": len(rows), "boxes": dict(box_counts), "class_images": dict(class_images),
                            "unlabeled_images": unlabeled}
    exact_leaks = [digest for digest, splits in exact_splits.items() if len(splits) > 1]
    group_leaks = [group for group, splits in group_splits.items() if len(splits) > 1]
    dhash_pairs, dhash_examples = cross_split_near_pairs(hash_rows, 2)
    phash_class_reports = {name: cross_split_near_pairs(rows, max_distance) for name, rows in phash_rows_by_class.items()}
    phash_pairs = sum(count for count, _ in phash_class_reports.values())
    phash_examples = [item for _, examples in phash_class_reports.values() for item in examples]
    report = {
        "dataset_id": manifest.get("dataset_id"), "classes": names,
        "taxonomy_version": taxonomy.get("version"), "dataset_manifest_sha256": manifest_hash,
        "images": sum(len(v) for v in rows_by_split.values()), "splits": per_split,
        "source_images_by_split": {s: dict(count_by_source[s]) for s in ("train", "val", "test")},
        "all_images_decoded": not decode_errors, "decode_errors": decode_errors,
        "all_images_have_label_files": not missing_labels, "missing_labels": missing_labels,
        "valid_yolo_boxes": not bad_boxes, "invalid_boxes": bad_boxes,
        "all_manifest_image_hashes_match": not manifest_hash_errors, "manifest_hash_errors": manifest_hash_errors,
        "exact_cross_split_duplicate_pairs": len(exact_leaks), "cross_split_group_leaks": len(group_leaks),
        "dhash_screen_hamming_threshold": 2, "cross_split_dhash_candidate_hash_pairs": dhash_pairs,
        "dhash_candidate_examples": dhash_examples[:20],
        "foreground_phash_hamming_threshold": max_distance,
        "cross_split_foreground_phash_pairs_by_class": {name: count for name, (count, _) in phash_class_reports.items()},
        "cross_split_foreground_phash_candidate_hash_pairs": phash_pairs,
        "near_duplicate_examples": phash_examples[:100],
        "all_classes_present_each_split": all(all(per_split[s]["boxes"].get(name, 0) for name in names) for s in per_split),
        "pass": not (decode_errors or missing_labels or bad_boxes or manifest_hash_errors or exact_leaks or group_leaks or phash_pairs),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets/multiclass_final_v7"))
    parser.add_argument("--max-phash-distance", type=int, default=4)
    args = parser.parse_args()
    report = audit(args.root, args.max_phash_distance)
    (args.root / "audit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
