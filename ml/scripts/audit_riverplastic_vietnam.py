"""Audit the Vietnam-only YOLO subset inside RiverPlasticDataset without extraction."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import zipfile


ARCHIVE_MD5 = "403759b09e095b2d8173c08dabed81b5"
CLASSES = [
    "unclassified_plastic", "plastic_bottle", "plastic_bag", "food_container_cutlery",
    "plastic_straw", "transparent_bag", "food_wrapper", "bottle_cap_container",
    "polystyrene", "drink_carton", "glass_bottle", "metallic_can", "rubber_ball",
]
SPLITS = ("train", "valid", "test")


def audit(archive: Path) -> dict:
    md5 = hashlib.md5()
    with archive.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            md5.update(chunk)
    if md5.hexdigest() != ARCHIVE_MD5:
        raise ValueError(f"Archive MD5 mismatch: {md5.hexdigest()}")

    with zipfile.ZipFile(archive) as zipped:
        bad_file = zipped.testzip()
        if bad_file:
            raise ValueError(f"ZIP CRC failure: {bad_file}")
        root = next((name.split("/")[0] for name in zipped.namelist() if name.startswith("KhimCathleenSaddi-RiverPlasticDataset-")), None)
        if not root:
            raise ValueError("Expected RiverPlasticDataset archive structure")
        counts = {}
        total_images = total_boxes = total_bytes = 0
        for split in SPLITS:
            image_prefix = f"{root}/ds_merge/images/{split}/"
            label_prefix = f"{root}/ds_merge/labels/{split}/"
            images = {Path(name).stem: name for name in zipped.namelist()
                      if name.startswith(image_prefix) and Path(name).stem.startswith("viet_")
                      and Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}}
            labels = {Path(name).stem: name for name in zipped.namelist()
                      if name.startswith(label_prefix) and Path(name).stem.startswith("viet_")
                      and Path(name).suffix.lower() == ".txt"}
            missing_labels = sorted(images.keys() - labels.keys())
            orphan_labels = sorted(labels.keys() - images.keys())
            class_boxes: Counter[str] = Counter()
            boundary_rounding = []
            hard_invalid = []
            for stem, name in labels.items():
                for line_number, line in enumerate(zipped.read(name).decode("utf-8-sig").splitlines(), 1):
                    if not line.strip():
                        continue
                    values = line.split()
                    try:
                        class_id = int(values[0])
                        x, y, width, height = map(float, values[1:])
                        if (len(values) != 5 or class_id not in range(len(CLASSES))
                                or not all(math.isfinite(value) for value in (x, y, width, height))
                                or not (0 < width <= 1 and 0 < height <= 1)):
                            raise ValueError("invalid class, size, or non-finite box")
                        edges = (x-width/2, x+width/2, y-height/2, y+height/2)
                        overshoot = max(0.0, -edges[0], edges[1]-1, -edges[2], edges[3]-1)
                        if overshoot > 0:
                            row = {"file": name, "line": line_number, "max_edge_overshoot": overshoot}
                            if overshoot <= 3e-6:
                                boundary_rounding.append(row)
                            else:
                                raise ValueError(f"box exceeds image edges by {overshoot:.8g}")
                        class_boxes[CLASSES[class_id]] += 1
                    except (ValueError, TypeError) as exc:
                        hard_invalid.append({"file": name, "line": line_number, "error": str(exc)})
            total_images += len(images)
            total_boxes += sum(class_boxes.values())
            total_bytes += sum(zipped.getinfo(name).file_size for name in images.values())
            counts[split] = {"images": len(images), "labels": len(labels), "boxes": dict(class_boxes),
                             "missing_labels": missing_labels, "orphan_labels": orphan_labels,
                             "boundary_rounding_rows": boundary_rounding,
                             "hard_invalid_rows": hard_invalid}
        return {"archive": str(archive), "archive_size_bytes": archive.stat().st_size,
                "archive_md5": md5.hexdigest(), "dataset": "RiverPlasticDataset mixed release, Vietnam-only subset",
                "source_classes": CLASSES, "splits": counts, "total_images": total_images,
                "total_boxes": total_boxes, "vietnam_image_bytes": total_bytes,
                "all_pairs_present": all(not row["missing_labels"] and not row["orphan_labels"] for row in counts.values()),
                "boundary_rounding_rows": sum(len(row["boundary_rounding_rows"]) for row in counts.values()),
                "hard_invalid_rows": sum(len(row["hard_invalid_rows"]) for row in counts.values()),
                "all_boxes_recoverable_by_boundary_clipping": all(not row["hard_invalid_rows"] for row in counts.values())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path,
                        default=Path("datasets/riverplastic/raw/RiverPlasticDataset-v1.0.1.zip"))
    parser.add_argument("--out", type=Path, default=Path("datasets/riverplastic/vietnam_audit.json"))
    args = parser.parse_args()
    report = audit(args.archive)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    split_summary = {
        split: {
            "images": row["images"],
            "labels": row["labels"],
            "boxes": row["boxes"],
            "missing_labels": len(row["missing_labels"]),
            "orphan_labels": len(row["orphan_labels"]),
            "boundary_rounding_rows": len(row["boundary_rounding_rows"]),
            "max_boundary_overshoot": max(
                (item["max_edge_overshoot"] for item in row["boundary_rounding_rows"]),
                default=0.0,
            ),
            "hard_invalid_rows": len(row["hard_invalid_rows"]),
        }
        for split, row in report["splits"].items()
    }
    print(json.dumps({"report": str(args.out), "total_images": report["total_images"],
                      "total_boxes": report["total_boxes"], "splits": split_summary,
                      "boundary_rounding_rows": report["boundary_rounding_rows"],
                      "hard_invalid_rows": report["hard_invalid_rows"],
                      "all_pairs_present": report["all_pairs_present"],
                      "all_boxes_recoverable_by_boundary_clipping": report["all_boxes_recoverable_by_boundary_clipping"]}, indent=2))
