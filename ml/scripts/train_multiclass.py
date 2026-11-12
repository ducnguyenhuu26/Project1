"""Prepare or train a new taxonomy-driven YOLO26 run; never resumes legacy optimizers."""
import argparse
import json
from pathlib import Path
import shutil
import yaml


def inspect_dataset(path: Path) -> tuple[dict, list[str], dict[str, Path]]:
    if not path.is_file():
        raise ValueError(f"Dataset YAML does not exist: {path}")
    config = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("Dataset YAML must be a mapping")
    names = config.get("names")
    if isinstance(names, dict):
        names = [names.get(i, names.get(str(i))) for i in range(len(names))]
    if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("Dataset names must define a non-empty ordered class list")
    if config.get("nc", len(names)) != len(names):
        raise ValueError("Dataset nc does not match names length")
    base = Path(config.get("path", path.parent))
    if not base.is_absolute():
        base = (path.parent / base).resolve()
    dirs = {}
    for split, key in (("train", "train"), ("val", "val"), ("test", "test")):
        value = config.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Dataset YAML requires {key}")
        candidate = Path(value)
        candidate = candidate if candidate.is_absolute() else base / candidate
        if not candidate.exists() or not (candidate.is_dir() or candidate.is_file()):
            raise ValueError(f"Missing {split} images: {candidate}")
        if candidate.is_dir() and not any(f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} for f in candidate.rglob("*")):
            raise ValueError(f"No images in {split}: {candidate}")
        dirs[split] = candidate.resolve()
    if len(set(dirs.values())) != 3:
        raise ValueError("Train, validation, and test inputs must be distinct")
    for split in ("train", "val", "test"):
        images = list(dirs[split].rglob("*")) if dirs[split].is_dir() else [
            Path(row.strip()) for row in dirs[split].read_text(encoding="utf-8").splitlines() if row.strip()]
        for image in images:
            if image.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            label = image.parents[1] / "labels" / f"{image.stem}.txt" if image.parent.name == "images" else image.with_suffix(".txt")
            if not label.is_file():
                raise ValueError(f"Missing {split} label: {label}")
            for line_no, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
                fields = line.split()
                try:
                    values = [float(value) for value in fields]
                    class_id = int(values[0])
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid label {label}:{line_no}")
                if len(values) != 5 or not 0 <= class_id < len(names) or any(not 0 <= v <= 1 for v in values[1:]) or values[3] <= 0 or values[4] <= 0:
                    raise ValueError(f"Invalid YOLO box/class at {label}:{line_no}")
    tax_path = path.parent / "taxonomy.json"
    if not tax_path.is_file():
        raise ValueError("taxonomy.json beside data.yaml is required for category mapping")
    taxonomy = json.loads(tax_path.read_text(encoding="utf-8"))
    categories = taxonomy.get("classes", [])
    if len(categories) != len(names) or len(set(categories)) != len(categories):
        raise ValueError("taxonomy.json classes must match data.yaml order and count")
    return config, names, {**dirs, "taxonomy": tax_path}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--model", choices=["yolo26s.pt", "yolo26n.pt"], default="yolo26s.pt")
    p.add_argument("--name", required=True)
    p.add_argument("--project", type=Path, default=Path("runs/multiclass"))
    p.add_argument("--epochs", type=int, default=80); p.add_argument("--batch", type=int, default=8)
    p.add_argument("--imgsz", type=int, default=640); p.add_argument("--device", default="0")
    p.add_argument("--workers", type=int, default=2); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-free-gb", type=float, default=5.0, help="Minimum available disk required before a run")
    p.add_argument("--preflight-only", action="store_true", help="Validate paths, taxonomy, disk, and optional GPU without starting training")
    args = p.parse_args()
    try:
        _, names, paths = inspect_dataset(args.data)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    run_dir = args.project.resolve() / args.name
    if run_dir.exists():
        p.error(f"Run directory exists; use a new name: {run_dir}")
    if args.epochs < 1 or args.batch < 1 or args.imgsz < 32:
        p.error("epochs/batch must be positive and imgsz >= 32")
    free_bytes = shutil.disk_usage(args.project.resolve().parent if args.project.exists() else Path.cwd()).free
    if args.min_free_gb < 0 or free_bytes < args.min_free_gb * (1024 ** 3):
        p.error(f"Insufficient free disk: {free_bytes / (1024 ** 3):.2f} GiB available, {args.min_free_gb:.2f} GiB required")
    if args.device != "cpu":
        try:
            import torch
            gpu_available = torch.cuda.is_available()
        except ImportError:
            gpu_available = False
        if not gpu_available:
            p.error("CUDA device requested but no GPU/PyTorch CUDA runtime is available")
    else:
        gpu_available = False
    report = {"dataset": str(args.data.resolve()), "classes": names, "taxonomy": str(paths["taxonomy"]),
              "inputs": {key: str(value) for key, value in paths.items() if key != "taxonomy"},
              "disk_free_bytes": free_bytes, "gpu_requested": args.device != "cpu",
              "gpu_available": gpu_available, "training_started": False}
    if args.preflight_only:
        print(json.dumps(report, indent=2)); return
    args.project.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=False)
    config = {**report, "model": args.model, "epochs": args.epochs, "batch": args.batch,
              "imgsz": args.imgsz, "device": args.device, "workers": args.workers, "seed": args.seed}
    (run_dir / "run_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    from ultralytics import YOLO
    model = YOLO(args.model)
    model.train(data=str(args.data.resolve()), epochs=args.epochs, batch=args.batch, imgsz=args.imgsz,
                device=args.device, workers=args.workers, project=str(args.project.resolve()), name=args.name,
                exist_ok=True, seed=args.seed, deterministic=True, plots=True, patience=15)
    class_map = []
    for class_id, (name, category_id) in enumerate(zip(names, json.loads(paths["taxonomy"].read_text())["classes"])):
        class_map.append({"class_id": class_id, "name": name, "category_id": category_id})
    manifest = {"schema_version": "1.0", "model_id": args.name, "model_family": "YOLO26",
                "task": "detect", "taxonomy_version": json.loads(paths["taxonomy"].read_text()).get("version"),
                "class_map": class_map, "dataset_version": str(args.data.resolve()),
                "preprocessing": {"imgsz": args.imgsz}, "benchmark_status": "unbenchmarked"}
    (run_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    weights_dir = run_dir / "weights"
    if weights_dir.is_dir():
        (weights_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
