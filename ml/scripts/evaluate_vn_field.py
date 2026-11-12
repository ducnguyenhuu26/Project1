"""Score a sealed Vietnamese field set at the deployment confidence threshold.

Expected layout: images/<scene>/<name>.jpg and labels/<scene>/<name>.txt.
Every image needs a label file; an empty file explicitly means no target objects.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from PIL import Image

CLASSES = ("Plastic", "Paper", "Metal")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def read_labels(path: Path, width: int, height: int) -> list[tuple[int, tuple[float, ...]]]:
    if not path.is_file():
        raise ValueError(f"Missing label file: {path}. Use an empty file for a negative image.")
    labels = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected class x_center y_center width height")
        try:
            class_id = int(fields[0])
            xc, yc, w, h = map(float, fields[1:])
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: invalid number") from exc
        if class_id not in range(len(CLASSES)) or not (0 <= xc-w/2 < xc+w/2 <= 1 and
                                                       0 <= yc-h/2 < yc+h/2 <= 1):
            raise ValueError(f"{path}:{line_number}: invalid class or box outside image")
        labels.append((class_id, ((xc-w/2)*width, (yc-h/2)*height,
                                  (xc+w/2)*width, (yc+h/2)*height)))
    return labels


def match_image(
    predictions: list[tuple[int, float, tuple[float, ...]]],
    ground_truth: list[tuple[int, tuple[float, ...]]],
    min_iou: float,
) -> dict[int, dict[str, int]]:
    """Greedy confidence-ordered, class-consistent one-to-one box matching."""
    counts = {k: {"tp": 0, "fp": 0, "fn": 0} for k in range(len(CLASSES))}
    unmatched = set(range(len(ground_truth)))
    for class_id, confidence, box in sorted(predictions, key=lambda row: row[1], reverse=True):
        if class_id not in counts:
            raise ValueError(f"Unexpected model class: {class_id}")
        candidates = [(iou(box, ground_truth[j][1]), j) for j in unmatched
                      if ground_truth[j][0] == class_id]
        overlap, j = max(candidates, default=(0.0, -1))
        if overlap >= min_iou:
            counts[class_id]["tp"] += 1
            unmatched.remove(j)
        else:
            counts[class_id]["fp"] += 1
    for j in unmatched:
        counts[ground_truth[j][0]]["fn"] += 1
    return counts


def new_bucket() -> dict:
    return {"images": 0, "negative_images": 0, "negative_images_with_fp": 0,
            "classes": {name: {"tp": 0, "fp": 0, "fn": 0} for name in CLASSES}}


def add_image(bucket: dict, counts: dict[int, dict[str, int]], is_negative: bool) -> None:
    bucket["images"] += 1
    if is_negative:
        bucket["negative_images"] += 1
        bucket["negative_images_with_fp"] += int(any(row["fp"] for row in counts.values()))
    for class_id, row in counts.items():
        for key in ("tp", "fp", "fn"):
            bucket["classes"][CLASSES[class_id]][key] += row[key]


def finalize(bucket: dict) -> dict:
    for row in bucket["classes"].values():
        tp, fp, fn = row["tp"], row["fp"], row["fn"]
        row["precision"] = tp / (tp + fp) if tp + fp else None
        row["recall"] = tp / (tp + fn) if tp + fn else None
        row["f1"] = 2*tp / (2*tp + fp + fn) if 2*tp + fp + fn else None
    return bucket


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True,
                        help="Sealed VN test/images directory; sibling labels directory is required")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Same operating confidence as deployed detector")
    parser.add_argument("--match-iou", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--out", type=Path, default=Path("outputs/vn_field_test.json"))
    args = parser.parse_args()
    if not args.model.is_file() or not args.images.is_dir() or args.images.name != "images":
        parser.error("model must be a file and --images must point to a directory named images")
    if not 0 < args.conf < 1 or not 0 < args.match_iou <= 1 or args.imgsz < 32:
        parser.error("require 0<conf<1, 0<match-iou<=1 and imgsz>=32")
    image_paths = sorted(p for p in args.images.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
    if not image_paths:
        parser.error("No images found")

    from ultralytics import YOLO
    model = YOLO(str(args.model.resolve()))
    if list(model.names.values()) != list(CLASSES):
        parser.error("checkpoint must have classes Plastic, Paper, Metal in that order")
    overall, scenes = new_bucket(), defaultdict(new_bucket)
    for image_path in image_paths:
        relative = image_path.relative_to(args.images)
        label_path = args.images.parent / "labels" / relative.with_suffix(".txt")
        with Image.open(image_path) as image:
            ground_truth = read_labels(label_path, image.width, image.height)
        result = model.predict(str(image_path), conf=args.conf, imgsz=args.imgsz,
                               device=args.device, verbose=False)[0]
        predictions = [(int(box.cls.item()), float(box.conf.item()),
                        tuple(float(v) for v in box.xyxy[0].tolist())) for box in result.boxes]
        counts = match_image(predictions, ground_truth, args.match_iou)
        scene = relative.parts[0] if len(relative.parts) > 1 else "unspecified"
        add_image(overall, counts, not ground_truth)
        add_image(scenes[scene], counts, not ground_truth)
    report = {"checkpoint": str(args.model.resolve()), "images": str(args.images.resolve()),
              "confidence_threshold": args.conf, "match_iou": args.match_iou,
              "image_size": args.imgsz, "device": args.device,
              "note": "Operating-point TP/FP/FN on sealed VN set; not mAP or calibrated accuracy",
              "overall": finalize(overall),
              "by_scene": {name: finalize(bucket) for name, bucket in sorted(scenes.items())}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
