"""Build an audited YOLO dataset from reviewed COCO sources (never downloads data)."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
from typing import Any

from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
from perceptual_hash import dhash, distance


def box_yolo(bbox: list[float], width: int, height: int) -> tuple[float, float, float, float] | None:
    if len(bbox) != 4:
        return None
    x, y, w, h = map(float, bbox)
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width or y + h > height:
        return None
    return ((x + w / 2) / width, (y + h / 2) / height, w / width, h / height)


def build(config: dict[str, Any], out: Path) -> dict:
    if out.exists():
        raise ValueError(f"Output already exists; choose a new path: {out}")
    classes = config.get("classes", [])
    if not classes or len(set(classes)) != len(classes):
        raise ValueError("classes must be a non-empty unique list of taxonomy IDs")
    registry_path = Path(config.get("taxonomy_registry", Path(__file__).resolve().parents[2] / "backend" / "taxonomy.json"))
    if not registry_path.is_file():
        raise ValueError(f"Taxonomy registry does not exist: {registry_path}")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_items = {item["id"]: item for item in registry.get("categories", [])}
    for category in classes:
        if category not in registry_items:
            raise ValueError(f"Unknown taxonomy class: {category}")
        if registry_items[category].get("training_readiness") != "ready_for_training":
            raise ValueError(f"Taxonomy class is not ready for training: {category}")
    if config.get("taxonomy_version") and config["taxonomy_version"] != registry.get("version"):
        raise ValueError("Configured taxonomy version does not match taxonomy registry")
    class_ids = {category: index for index, category in enumerate(classes)}
    seed = int(config.get("seed", 42))
    ratios = config.get("split", {"train": 0.8, "val": 0.1, "test": 0.1})
    if set(ratios) != {"train", "val", "test"} or abs(sum(ratios.values()) - 1) > 1e-8:
        raise ValueError("split must have train, val, test ratios summing to 1")
    rows, issues, class_counts, seen_hash, seen_dhash = [], [], Counter(), {}, []
    scene_groups: dict[str, list[dict]] = {}
    for source in config.get("sources", []):
        source_id = source["id"]
        if not source.get("license_reviewed"):
            raise ValueError(f"Source license must be reviewed before build: {source_id}")
        if not source.get("mapping_reviewed"):
            raise ValueError(f"Source class mapping must be reviewed before build: {source_id}")
        annotation_file = Path(source["annotations"])
        image_dir = Path(source["image_dir"])
        if not annotation_file.is_file() or not image_dir.is_dir():
            issues.append({"source": source_id, "issue": "source_files_missing", "decision": "blocked"})
            continue
        coco = json.loads(annotation_file.read_text(encoding="utf-8"))
        categories = {item["id"]: item["name"] for item in coco.get("categories", [])}
        mapping = source.get("mapping", {})
        annotations: dict[int, list[dict]] = {}
        for annotation in coco.get("annotations", []):
            annotations.setdefault(annotation["image_id"], []).append(annotation)
        for image in coco.get("images", []):
            image_path = image_dir / image["file_name"]
            if not image_path.is_file():
                issues.append({"source": source_id, "image": image["file_name"], "issue": "image_missing"})
                continue
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            width, height = int(image["width"]), int(image["height"])
            try:
                with Image.open(image_path) as im:
                    actual_width, actual_height = im.size
            except OSError:
                issues.append({"source": source_id, "image": image["file_name"], "issue": "image_unreadable"})
                continue
            if (width, height) != (actual_width, actual_height):
                issues.append({"source": source_id, "image": image["file_name"], "issue": "image_dimensions_mismatch"})
                continue
            if digest in seen_hash:
                issues.append({"source": source_id, "image": image["file_name"], "duplicate_of": seen_hash[digest], "issue": "exact_duplicate"})
                continue
            visual_hash = dhash(image_path)
            near = next((prior for prior in seen_dhash if distance(prior[0], visual_hash) <= 2), None)
            if near:
                issues.append({"source": source_id, "image": image["file_name"], "near_duplicate_of": near[1],
                               "dhash_distance": distance(near[0], visual_hash), "issue": "perceptual_near_duplicate"})
                continue
            seen_dhash.append((visual_hash, f"{source_id}:{image['file_name']}"))
            seen_hash[digest] = f"{source_id}:{image['file_name']}"
            labels = []
            bad = False
            for annotation in annotations.get(image["id"], []):
                source_class = categories.get(annotation["category_id"], "<unknown>")
                rule = mapping.get(source_class, {"decision": "unmappable"})
                if isinstance(rule, str):
                    rule = {"decision": "map", "category_id": rule}
                decision, category_id = rule.get("decision", "unmappable"), rule.get("category_id")
                if decision in {"exclude", "unmappable", "needs_review"}:
                    issues.append({"source": source_id, "image": image["file_name"], "source_class": source_class,
                                   "issue": decision, "reason": rule.get("reason")})
                    if decision != "exclude":
                        bad = True
                    continue
                if decision != "map" or category_id not in class_ids:
                    issues.append({"source": source_id, "image": image["file_name"], "source_class": source_class,
                                   "issue": "invalid_mapping"})
                    bad = True
                    continue
                normalized = box_yolo(annotation.get("bbox", []), width, height)
                if normalized is None:
                    issues.append({"source": source_id, "image": image["file_name"], "source_class": source_class,
                                   "bbox": annotation.get("bbox"), "issue": "invalid_box"})
                    bad = True
                    continue
                labels.append((class_ids[category_id], normalized, source_class, category_id, rule.get("reason", "reviewed explicit mapping")))
            # Do not train an image with target objects hidden behind unmapped/uncertain annotations.
            if bad:
                if not source.get("fully_annotated", False):
                    issues.append({"source": source_id, "image": image["file_name"],
                                   "issue": "partial_annotation_dropped"})
                continue
            if not labels and not source.get("fully_annotated", False):
                issues.append({"source": source_id, "image": image["file_name"], "issue": "empty_or_partial_annotation_dropped"})
                continue
            if not labels:
                issues.append({"source": source_id, "image": image["file_name"], "issue": "empty_image_included_as_negative"})
            group = f"{source_id}:{image['scene_id']}" if image.get("scene_id") else f"{source_id}:{digest}"
            scene_groups.setdefault(group, []).append({"source": source, "image": image, "path": image_path,
                                                       "digest": digest, "labels": labels})
    group_names = sorted(scene_groups)
    random.Random(seed).shuffle(group_names)
    split_names = []
    cumulative = {"train": ratios["train"], "val": ratios["train"] + ratios["val"]}
    for index, _ in enumerate(group_names):
        fraction = (index + 0.5) / max(1, len(group_names))
        split_names.append("train" if fraction < cumulative["train"] else "val" if fraction < cumulative["val"] else "test")
    assignments = dict(zip(group_names, split_names))
    out.mkdir(parents=True)
    manifest_rows, split_counts = [], Counter()
    visualized = 0
    for group, entries in scene_groups.items():
        split = assignments[group]
        for entry in entries:
            source, image, image_path, labels = entry["source"], entry["image"], entry["path"], entry["labels"]
            safe_name = hashlib.sha1(f"{source['id']}:{image['file_name']}".encode()).hexdigest()[:16]
            dest_img = out / split / "images" / f"{safe_name}{image_path.suffix.lower()}"
            dest_lbl = out / split / "labels" / f"{safe_name}.txt"
            dest_img.parent.mkdir(parents=True, exist_ok=True); dest_lbl.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image_path, dest_img)
            lines = []
            for class_id, (xc, yc, w, h), source_class, category_id, reason in labels:
                lines.append(f"{class_id} {xc:.8f} {yc:.8f} {w:.8f} {h:.8f}")
                class_counts[category_id] += 1
            dest_lbl.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            if visualized < 12:
                with Image.open(image_path) as source_image:
                    preview = source_image.convert("RGB").copy()
                draw = ImageDraw.Draw(preview)
                for class_id, (xc, yc, box_w, box_h), _, _, _ in labels:
                    left, top = (xc - box_w / 2) * width, (yc - box_h / 2) * height
                    right, bottom = (xc + box_w / 2) * width, (yc + box_h / 2) * height
                    draw.rectangle((left, top, right, bottom), outline="#e45f39", width=max(2, width // 300))
                    draw.text((left, max(0, top - 14)), classes[class_id], fill="#e45f39")
                preview_dir = out / "visualizations"
                preview_dir.mkdir(exist_ok=True)
                preview.save(preview_dir / f"{safe_name}.jpg", quality=88)
                visualized += 1
            split_counts[split] += 1
            manifest_rows.append({"image": dest_img.relative_to(out).as_posix(), "label": dest_lbl.relative_to(out).as_posix(),
                                  "source": source["id"], "source_file": image["file_name"], "source_url": source.get("url"),
                                  "license": source.get("license_status", "unverified"), "sha256": entry["digest"],
                                  "group": group, "split": split,
                                  "boxes": [{"source_class": src_class, "category_id": cid,
                                             "handling_group": registry_items[cid].get("handling_group"),
                                             "mapping_rule": reason,
                                             "transform": "COCO xywh pixel box → YOLO normalized xywh"}
                                            for _, _, src_class, cid, reason in labels]})
    (out / "data.yaml").write_text(f"path: {out.resolve().as_posix()}\ntrain: train/images\nval: val/images\ntest: test/images\nnc: {len(classes)}\nnames: [{', '.join(classes)}]\n", encoding="utf-8")
    (out / "taxonomy.json").write_text(json.dumps({"version": registry.get("version"), "classes": classes}, indent=2), encoding="utf-8")
    (out / "dataset_manifest.json").write_text(json.dumps({"schema_version": "1.0", "seed": seed, "classes": classes,
        "split_ratios": ratios, "images": manifest_rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    report = {"images": len(manifest_rows), "split_counts": dict(split_counts), "class_counts": dict(class_counts),
              "visualization_samples": visualized,
              "issues": issues, "source_count": len(config.get("sources", [])), "seed": seed}
    (out / "audit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    print(json.dumps(build(config, args.out), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
