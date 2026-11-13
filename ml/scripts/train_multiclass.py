"""Prepare or train a new taxonomy-driven YOLO26 run; never resumes legacy optimizers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from collections import Counter
import yaml


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        if not dirs[split].is_dir():
            images = [image if image.is_absolute() else (base / image).resolve() for image in images]
        for image in images:
            if image.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            label = image.parents[1] / "labels" / f"{image.stem}.txt" if image.parent.name == "images" else image.with_suffix(".txt")
            if not label.is_file():
                raise ValueError(f"Missing {split} label: {label}")
            for line_no, line in enumerate(label.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
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


def audit_dataset(data_path: Path, names: list[str], paths: dict[str, Path]) -> dict:
    image_hash_splits: dict[str, set[str]] = {}
    image_hashes: dict[Path, str] = {}
    group_splits: dict[str, set[str]] = {}
    per_split = {}
    for split in ("train", "val", "test"):
        images = sorted((p for p in paths[split].rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
                        if paths[split].is_dir() else [])
        boxes = Counter()
        unlabeled = 0
        for image in images:
            label = image.parents[1] / "labels" / f"{image.stem}.txt" if image.parent.name == "images" else image.with_suffix(".txt")
            if not label.is_file():
                raise ValueError(f"Missing {split} label: {label}")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            image_hash_splits.setdefault(digest, set()).add(split)
            image_hashes[image.resolve()] = digest
            rows = [line.strip() for line in label.read_text(encoding="utf-8").splitlines() if line.strip()]
            if not rows:
                unlabeled += 1
            for row in rows:
                class_id = int(row.split()[0])
                boxes[class_id] += 1
        per_split[split] = {"images": len(images), "boxes": dict(sorted(boxes.items())), "unlabeled_images": unlabeled}
    manifest_path = data_path.parent / "dataset_manifest.json"
    manifest_hash = None
    if manifest_path.is_file():
        manifest_bytes = manifest_path.read_bytes()
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        manifest = json.loads(manifest_bytes)
        for row in manifest.get("images", []):
            group_splits.setdefault(f"{row.get('source')}:{row.get('group')}", set()).add(row.get("split"))
            manifest_image = (data_path.parent / row["image"]).resolve()
            if image_hashes.get(manifest_image) != row.get("sha256"):
                raise ValueError(f"Dataset image hash does not match manifest: {manifest_image}")
    exact_leakage = [key for key, splits in image_hash_splits.items() if len(splits) > 1]
    group_leakage = [key for key, splits in group_splits.items() if len(splits) > 1]
    absent = {split: [names[class_id] for class_id in range(len(names))
                      if per_split[split]["boxes"].get(class_id, 0) == 0]
              for split in ("train", "val", "test")}
    if exact_leakage or group_leakage:
        raise ValueError(f"Cross-split leakage: exact={len(exact_leakage)}, groups={len(group_leakage)}")
    if any(absent.values()):
        raise ValueError(f"Every training class must appear in train/val/test; missing={absent}")
    return {"splits": per_split, "dataset_manifest_sha256": manifest_hash,
            "exact_cross_split_duplicates": 0, "group_cross_split_leaks": 0,
            "taxonomy_classes_present_in_every_split": True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--model", default="yolo26s.pt", help="Existing YOLO26 .pt initialization checkpoint")
    p.add_argument("--name", required=True)
    p.add_argument("--project", type=Path, default=Path("runs/multiclass"))
    p.add_argument("--epochs", type=int, default=80); p.add_argument("--batch", type=int, default=8)
    p.add_argument("--imgsz", type=int, default=640); p.add_argument("--device", default="0")
    p.add_argument("--workers", type=int, default=2); p.add_argument("--seed", type=int, default=42)
    p.add_argument("--min-free-gb", type=float, default=5.0, help="Minimum available disk required before a run")
    p.add_argument("--patience", type=int, default=15)
    p.add_argument("--resume-from", type=Path, help="Resume only from a prior run's last.pt after taxonomy/data checks")
    p.add_argument("--preflight-only", action="store_true", help="Validate paths, taxonomy, disk, and optional GPU without starting training")
    args = p.parse_args()
    model_path = Path(args.model)
    if model_path.suffix.lower() != ".pt" or not model_path.is_file():
        p.error(f"YOLO26 initialization checkpoint must be an existing .pt file: {args.model}")
    try:
        _, names, paths = inspect_dataset(args.data)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    run_dir = args.project.resolve() / args.name
    if args.resume_from:
        resume_path = args.resume_from.resolve()
        resume_run = resume_path.parent.parent
        resume_config_path = resume_run / "run_config.json"
        if resume_path.name != "last.pt" or not resume_path.is_file() or not resume_config_path.is_file():
            p.error("--resume-from must point to <run>/weights/last.pt with the original run_config.json")
        prior = json.loads(resume_config_path.read_text(encoding="utf-8"))
        current_taxonomy = json.loads(paths["taxonomy"].read_text(encoding="utf-8")).get("version")
        current_manifest_hash = (paths["train"].parent.parent / "dataset_manifest.json")
        current_manifest_hash = sha256_file(current_manifest_hash) if current_manifest_hash.is_file() else None
        if (Path(prior.get("dataset", "")).resolve() != args.data.resolve()
                or prior.get("taxonomy_version") != current_taxonomy
                or prior.get("dataset_manifest_sha256") != current_manifest_hash):
            p.error("Resume blocked: dataset YAML, manifest, or taxonomy version differs from the saved run")
        if resume_run != run_dir:
            p.error(f"Resume name/project must match prior run directory: {resume_run}")
    elif run_dir.exists():
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
    try:
        dataset_audit = audit_dataset(args.data, names, paths)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.error(f"Dataset audit failed: {exc}")
    report = {"dataset": str(args.data.resolve()), "classes": names, "taxonomy": str(paths["taxonomy"]),
              "taxonomy_version": json.loads(paths["taxonomy"].read_text(encoding="utf-8")).get("version"),
              "model_selection": str(model_path.resolve()), "initial_checkpoint_sha256": sha256_file(model_path.resolve()),
              "inputs": {key: str(value) for key, value in paths.items() if key != "taxonomy"},
              "dataset_audit": dataset_audit,
              "dataset_manifest_sha256": dataset_audit["dataset_manifest_sha256"],
              "disk_free_bytes": free_bytes, "gpu_requested": args.device != "cpu",
              "gpu_available": gpu_available, "training_started": False}
    if args.preflight_only:
        print(json.dumps(report, indent=2)); return
    args.project.mkdir(parents=True, exist_ok=True)
    if not args.resume_from:
        run_dir.mkdir(parents=False)
    config = {**report, "model": args.model, "epochs": args.epochs, "batch": args.batch,
              "imgsz": args.imgsz, "device": args.device, "workers": args.workers,
              "seed": args.seed, "patience": args.patience}
    (run_dir / "run_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    from ultralytics import YOLO
    # Ultralytics resolves a relative `path: .` against its global datasets_dir
    # on Windows. Materialize an absolute runtime YAML while keeping the
    # checked-in/generated dataset YAML portable.
    runtime_data = dict(yaml.safe_load(args.data.read_text(encoding="utf-8-sig")))
    dataset_root = args.data.resolve().parent
    if runtime_data.get("path"):
        configured_root = Path(runtime_data["path"])
        dataset_root = configured_root.resolve() if configured_root.is_absolute() else (args.data.resolve().parent / configured_root).resolve()
    runtime_data["path"] = str(dataset_root)
    runtime_data_path = run_dir / "runtime_data.yaml"
    runtime_data_path.write_text(yaml.safe_dump(runtime_data, sort_keys=False), encoding="utf-8")
    model = YOLO(str(args.resume_from.resolve())) if args.resume_from else YOLO(str(model_path.resolve()))
    if args.resume_from:
        checkpoint_names = getattr(model, "names", {})
        if isinstance(checkpoint_names, dict):
            checkpoint_names = [checkpoint_names.get(i, checkpoint_names.get(str(i))) for i in range(len(checkpoint_names))]
        if [str(value).casefold() for value in checkpoint_names] != [value.casefold() for value in names]:
            raise RuntimeError("Resume blocked: checkpoint class order does not match data.yaml")
        training_results = model.train(resume=True, device=args.device, workers=args.workers)
    else:
        training_results = model.train(data=str(runtime_data_path.resolve()), epochs=args.epochs, batch=args.batch, imgsz=args.imgsz,
                    device=args.device, workers=args.workers, project=str(args.project.resolve()), name=args.name,
                    exist_ok=True, seed=args.seed, deterministic=True, plots=True, patience=args.patience)
    best_path = run_dir / "weights" / "best.pt"
    last_path = run_dir / "weights" / "last.pt"
    results_csv = run_dir / "results.csv"
    if not best_path.is_file() or not last_path.is_file() or not results_csv.is_file():
        raise RuntimeError("Training ended without best.pt, last.pt, and results.csv")
    validation = YOLO(str(best_path)).val(data=str(runtime_data_path.resolve()), split="val", imgsz=args.imgsz,
                                          batch=args.batch, device=args.device, plots=True,
                                          project=str(args.project.resolve()), name=f"{args.name}-validation", exist_ok=True)
    class_map = []
    for class_id, (name, category_id) in enumerate(zip(names, json.loads(paths["taxonomy"].read_text())["classes"])):
        class_map.append({"class_id": class_id, "name": name, "category_id": category_id})
    dataset_manifest = args.data.parent / "dataset_manifest.json"
    dataset_hash = sha256_file(dataset_manifest) if dataset_manifest.exists() else None
    metrics = getattr(validation, "results_dict", {})
    manifest = {"schema_version": "1.0", "model_id": args.name, "model_family": "YOLO26",
                "task": "detect", "taxonomy_version": json.loads(paths["taxonomy"].read_text()).get("version"),
                "class_map": class_map, "dataset_version": str(args.data.resolve()),
                "dataset_manifest_sha256": dataset_hash,
                "checkpoint_sha256": sha256_file(best_path),
                "preprocessing": {"imgsz": args.imgsz}, "validation_metrics": metrics,
                "validation_split": "val", "test_evaluated": False,
                "training_config": {"model": args.model, "epochs": args.epochs, "batch": args.batch,
                                    "imgsz": args.imgsz, "device": args.device, "seed": args.seed,
                                    "workers": args.workers, "patience": args.patience},
                "training_results": str(results_csv.resolve()),
                "initial_checkpoint_sha256": report["initial_checkpoint_sha256"],
                "training_summary": getattr(training_results, "results_dict", {}),
                "benchmark_status": "validation_only_not_tested"}
    weights_dir = run_dir / "weights"
    if weights_dir.is_dir():
        (weights_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2, default=float), encoding="utf-8")
    (run_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
