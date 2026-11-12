"""Fine tune YOLO26. Use --fraction only for CPU smoke training."""
import argparse
from pathlib import Path

import torch
import yaml
from ultralytics import YOLO


def validate_data(path: Path, *, smoke: bool = False) -> dict:
    """Fail before GPU allocation if the dataset cannot train the intended task."""
    if not path.is_file():
        raise ValueError(f"Dataset YAML does not exist: {path}")
    config = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("Dataset YAML must be a mapping")
    names = config.get("names")
    if isinstance(names, dict):
        names = [names.get(i, names.get(str(i))) for i in range(3)]
    if names != ["Plastic", "Paper", "Metal"] or config.get("nc", 3) != 3:
        raise ValueError("Dataset must use 0=Plastic, 1=Paper, 2=Metal")
    base = Path(config.get("path", path.parent))
    if not base.is_absolute():
        base = (path.parent / base).resolve()
    dirs = {}
    expected = (("train", "train"), ("validation", "val"))
    if not smoke:
        expected += (("test", "test"),)
    for split, key in expected:
        value = config.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Dataset YAML requires {key}: image directory")
        candidate = Path(value)
        dirs[split] = candidate if candidate.is_absolute() else base / candidate
        if dirs[split].is_dir():
            if not any(p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
                       for p in dirs[split].iterdir()):
                raise ValueError(f"No images in {split}: {dirs[split]}")
        elif smoke and dirs[split].suffix.lower() == ".txt" and dirs[split].is_file():
            if not dirs[split].read_text(encoding="utf-8").strip():
                raise ValueError(f"Image list is empty: {dirs[split]}")
        else:
            raise ValueError(f"Missing {split} image directory: {dirs[split]}")
    if len({p.resolve() for p in dirs.values()}) != len(dirs):
        raise ValueError("Train, validation and test must be distinct inputs")
    return {key: str(value.resolve()) for key, value in dirs.items()}


def choose_weights(model_name: str, init_checkpoint: Path | None,
                   resume_checkpoint: Path | None) -> tuple[str, bool]:
    """A new fine-tuning run loads weights; resume continues the old optimizer/run."""
    if init_checkpoint and resume_checkpoint:
        raise ValueError("--init-checkpoint and --resume-checkpoint are mutually exclusive")
    selected = resume_checkpoint or init_checkpoint
    if selected:
        if not selected.is_file():
            raise ValueError(f"Checkpoint does not exist: {selected}")
        return str(selected.resolve()), bool(resume_checkpoint)
    path = Path(model_name)
    return str(path.resolve()) if path.is_file() else model_name, False


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--model", choices=["yolo26n.pt", "yolo26s.pt"], default="yolo26s.pt")
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default="0")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--fraction", type=float, default=1.0)
    p.add_argument("--smoke", action="store_true", help="Allow a reduced train/val-only dataset for CPU checks")
    p.add_argument("--name", default="waste_yolo26s")
    p.add_argument("--project", default="runs/train")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--init-checkpoint", type=Path,
                   help="Start a NEW fine-tuning run from a trained checkpoint, e.g. SWiM3 → VN-Field")
    p.add_argument("--resume-checkpoint", type=Path, help="Existing last.pt from an interrupted run")
    p.add_argument("--lr0", type=float, help="Optional initial learning rate for a new run")
    args = p.parse_args()
    if not 0 < args.fraction <= 1 or args.epochs < 1 or args.batch < 1 or args.imgsz < 32:
        p.error("epochs and batch >= 1, imgsz >= 32, fraction in (0,1]")
    if args.fraction < 1 and not args.smoke:
        p.error("--fraction is reserved for smoke checks; add --smoke")
    if args.lr0 is not None and args.lr0 <= 0:
        p.error("--lr0 must be positive")
    if args.device.isdigit() and not torch.cuda.is_available():
        p.error(f"CUDA device {args.device} requested but no GPU is available")
    try:
        validate_data(args.data, smoke=args.smoke)
        weights, resume = choose_weights(args.model, args.init_checkpoint, args.resume_checkpoint)
    except ValueError as exc:
        p.error(str(exc))
    project = Path(args.project).resolve()
    run_dir = project / args.name
    if not args.resume_checkpoint and run_dir.exists():
        p.error(f"Run directory already exists: {run_dir}. Choose a new --name or resume last.pt")
    model = YOLO(weights)
    if args.init_checkpoint and list(model.names.values()) != ["Plastic", "Paper", "Metal"]:
        p.error("--init-checkpoint must be a fine-tuned Plastic/Paper/Metal checkpoint")
    train_options = {"lr0": args.lr0} if args.lr0 is not None else {}
    model.train(data=str(args.data.resolve()), epochs=args.epochs, batch=args.batch,
                imgsz=args.imgsz, device=args.device, workers=args.workers,
                fraction=args.fraction, project=str(project), name=args.name, exist_ok=True,
                seed=args.seed, deterministic=True, patience=15,
                mosaic=0.5, mixup=0.0, copy_paste=0.0, close_mosaic=10,
                fliplr=0.5, flipud=0.0, degrees=8.0, translate=0.1,
                scale=0.3, hsv_h=0.01, hsv_s=0.3, hsv_v=0.25,
                resume=resume, plots=True, **train_options)


if __name__ == "__main__":
    main()
