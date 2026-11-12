"""Evaluate a fine-tuned checkpoint; keep test untouched until model selection ends."""
import argparse
import json
from pathlib import Path
from ultralytics import YOLO


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--split", choices=["val", "test"], default="val")
    p.add_argument("--device", default="cpu")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--out", type=Path, default=Path("outputs/evaluation.json"))
    args = p.parse_args()
    if not args.model.is_file() or not args.data.is_file():
        p.error("model and data must exist")
    model = YOLO(str(args.model.resolve()))
    if list(model.names.values()) != ["Plastic", "Paper", "Metal"]:
        p.error("checkpoint is not the fine-tuned 3-class waste detector")
    result = model.val(data=str(args.data.resolve()), split=args.split, imgsz=args.imgsz,
                       device=args.device, plots=True, project=str(args.out.parent.resolve()), name=args.split)
    per_class = {}
    for index, class_id in enumerate(result.box.ap_class_index):
        per_class[model.names[int(class_id)]] = {
            "precision": float(result.box.p[index]), "recall": float(result.box.r[index]),
            "map50": float(result.box.ap50[index]), "map50_95": float(result.box.ap[index])}
    metrics = {"model": str(args.model), "split": args.split, "map50": float(result.box.map50),
               "map50_95": float(result.box.map), "precision": float(result.box.mp),
               "recall": float(result.box.mr), "per_class": per_class}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
