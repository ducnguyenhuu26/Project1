"""Build the frozen six-class Kaggle dataset from audited multiclass_v5.

Images containing cigarette-litter annotations are excluded as whole images so
their unmodeled cigarette objects cannot become background during training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import yaml

CLASSES = ["plastic", "paper", "metal", "glass", "organic", "textile"]
SOURCE_CLASSES = CLASSES + ["cigarette_litter"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(source: Path, destination: Path, taxonomy_path: Path, exclusions_path: Path) -> dict:
    source = source.resolve(); destination = destination.resolve()
    if destination.exists() and (destination / "dataset_manifest.json").exists():
        raise FileExistsError(f"Refusing to overwrite immutable dataset: {destination}")
    source_manifest_path = source / "dataset_manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("classes") != SOURCE_CLASSES:
        raise ValueError("Source manifest is not the expected seven-class v5 order")
    old_ids = {name: i for i, name in enumerate(source_manifest["classes"])}
    new_ids = {name: i for i, name in enumerate(CLASSES)}
    backend_taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    supported = {row["id"] for row in backend_taxonomy.get("categories", []) if row.get("detection_supported")}
    if not set(CLASSES).issubset(supported):
        raise ValueError("Backend taxonomy does not mark every frozen class as detection-supported")
    taxonomy = {"version": backend_taxonomy["version"], "classes": CLASSES}
    exclusions = json.loads(exclusions_path.read_text(encoding="utf-8"))
    excluded_near_paths = {image for pair in exclusions.get("pairs", []) for image in pair}
    rows = source_manifest["images"]
    selected = []; excluded = []
    for row in rows:
        if any(box["category_id"] == "cigarette_litter" for box in row["boxes"]):
            excluded.append({**row, "exclusion_reason": "cigarette_litter_object_not_in_model"})
        elif row["image"] in excluded_near_paths:
            excluded.append({**row, "exclusion_reason": "reviewed_cross_split_near_duplicate_candidate"})
        else:
            selected.append(row)
    unresolved = excluded_near_paths - {row["image"] for row in rows}
    if unresolved:
        raise ValueError(f"Near-duplicate exclusions absent from source manifest: {sorted(unresolved)}")
    destination.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    box_counts = Counter(); image_counts = Counter(); source_counts = Counter()
    per_split = {s: {"images": 0, "boxes": Counter(), "class_images": Counter(), "unlabeled_images": 0}
                 for s in ("train", "val", "test")}
    for row in selected:
        rel = Path(row["image"])
        split = row["split"]
        src_image = source / rel
        src_label = source / row["label"]
        if not src_image.is_file() or not src_label.is_file():
            raise ValueError(f"Missing image/annotation pair: {rel}")
        dst_image = destination / rel
        dst_label = destination / row["label"]
        dst_image.parent.mkdir(parents=True, exist_ok=True)
        dst_label.parent.mkdir(parents=True, exist_ok=True)
        if not dst_image.is_file() or dst_image.stat().st_size != src_image.stat().st_size:
            shutil.copy2(src_image, dst_image)
        lines = []
        for text in src_label.read_text(encoding="utf-8").splitlines():
            if not text.strip():
                continue
            values = text.split()
            class_id = int(values[0]); name = SOURCE_CLASSES[class_id]
            if name == "cigarette_litter":
                raise ValueError(f"Unexpected cigarette label in selected image {rel}")
            values[0] = str(new_ids[name]); lines.append(" ".join(values))
            box_counts[name] += 1; per_split[split]["boxes"][name] += 1
        dst_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        if lines:
            present = {CLASSES[int(line.split()[0])] for line in lines}
            for name in present: per_split[split]["class_images"][name] += 1
        else:
            per_split[split]["unlabeled_images"] += 1
        per_split[split]["images"] += 1
        image_counts[split] += 1; source_counts[(split, row["source"])] += 1
        new_row = dict(row)
        new_row["image_sha256"] = sha256_file(dst_image)
        # v5 uses sha256 for the copied image content.
        new_row["sha256"] = new_row["image_sha256"]
        new_row["label_sha256"] = sha256_file(dst_label)
        new_row["boxes"] = [b for b in row["boxes"] if b["category_id"] != "cigarette_litter"]
        manifest_rows.append(new_row)
    (destination / "data.yaml").write_text(
        "path: .\ntrain: train/images\nval: val/images\ntest: test/images\nnc: 6\nnames: [plastic, paper, metal, glass, organic, textile]\n",
        encoding="utf-8")
    (destination / "taxonomy.json").write_text(json.dumps(taxonomy, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0", "dataset_id": "multiclass_final_v7", "classes": CLASSES,
        "taxonomy_version": taxonomy["version"], "source_dataset": "multiclass_v5",
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "near_duplicate_exclusions_sha256": sha256_file(exclusions_path),
        "near_duplicate_excluded_images": len({row["image"] for row in excluded if row["exclusion_reason"] == "reviewed_cross_split_near_duplicate_candidate"}),
        "excluded_images": [{"image": row["image"], "split": row["split"], "source": row["source"],
                             "reason": row["exclusion_reason"]} for row in excluded],
        "images": manifest_rows,
    }
    manifest_path = destination / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {
        "dataset_id": manifest["dataset_id"], "classes": CLASSES,
        "images": len(manifest_rows),
        "excluded_images_with_cigarette_litter": sum(1 for row in excluded if row["exclusion_reason"] == "cigarette_litter_object_not_in_model"),
        "excluded_images_for_near_duplicate_candidates": sum(1 for row in excluded if row["exclusion_reason"] == "reviewed_cross_split_near_duplicate_candidate"),
        "excluded_images_by_split": dict(Counter(row["split"] for row in excluded)),
        "images_by_split": {s: per_split[s]["images"] for s in per_split},
        "box_counts": dict(box_counts),
        "box_counts_by_split": {s: dict(per_split[s]["boxes"]) for s in per_split},
        "class_images_by_split": {s: dict(per_split[s]["class_images"]) for s in per_split},
        "unlabeled_images_by_split": {s: per_split[s]["unlabeled_images"] for s in per_split},
        "source_images_by_split": {s: {src: n for (sp, src), n in source_counts.items() if sp == s} for s in per_split},
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "exact_cross_split_duplicates": 0,
        "near_duplicate_audit": "Foreground pHash Hamming <=4 candidates manually reviewed and excluded before split was sealed.",
    }
    (destination / "audit_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("datasets/multiclass_v5"))
    parser.add_argument("--out", type=Path, default=Path("datasets/multiclass_final_v7"))
    parser.add_argument("--taxonomy", type=Path, default=Path("backend/taxonomy.json"))
    parser.add_argument("--exclusions", type=Path, default=Path("ml/config/multiclass_final_near_duplicate_exclusions.json"))
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.out, args.taxonomy, args.exclusions), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
