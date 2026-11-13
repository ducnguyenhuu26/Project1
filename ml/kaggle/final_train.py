"""Kaggle-only final YOLO26s training runner for WasteWise VN multiclass_final_v7.

Training is never started unless the full local dataset audit, CUDA preflight,
dependency checks, and a short training smoke test pass.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("WASTEWISE_DATA", "/kaggle/input/wastewise-multiclass-final-v7"))
WORKING_ROOT = Path(os.environ.get("WASTEWISE_WORKING", "/kaggle/working"))
MODEL_NAME = "yolo26s.pt"
INITIAL_SHA256 = "646f8bc3fe0a656803d95c294f7852321748cb29d13466a1af8862e2db384a1b"
ULTRALYTICS_VERSION = "8.4.210"
EPOCHS = 50
IMGSZ = 640
SEED = 42
PATIENCE = 15


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _is_final_dataset(root: Path) -> bool:
    manifest_path = root / "dataset_manifest.json"
    if not (root / "data.yaml").is_file() or not manifest_path.is_file():
        return False
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("dataset_id") == "multiclass_final_v7"
    except (OSError, json.JSONDecodeError):
        return False


def find_data(data_override: Path | None = None, input_root: Path | None = None) -> Path:
    """Find the mounted dataset whether Kaggle exposes it at input root or nested."""
    requested = Path(data_override) if data_override is not None else DATA
    mounted = Path(input_root) if input_root is not None else Path("/kaggle/input")
    candidates = (requested, requested / "multiclass_final_v7")
    for candidate in candidates:
        if _is_final_dataset(candidate):
            return candidate.resolve()

    matches = set()
    if mounted.is_dir():
        manifests = [*mounted.glob("*/dataset_manifest.json"),
                     *mounted.glob("*/multiclass_final_v7/dataset_manifest.json")]
        for manifest in manifests:
            root = manifest.parent
            if _is_final_dataset(root):
                matches.add(root.resolve())
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one uploaded multiclass_final_v7 dataset, found {len(matches)}")
    return matches.pop()


def prepare_runtime_data(data_root: Path, working_root: Path | None = None) -> Path:
    """Write and verify an absolute-path Ultralytics YAML for the mounted dataset."""
    import yaml
    from ultralytics.data.utils import check_det_dataset

    data_root = Path(data_root).resolve()
    source_yaml = data_root / "data.yaml"
    if not source_yaml.is_file() or not (data_root / "dataset_manifest.json").is_file():
        raise FileNotFoundError(f"Dataset root must contain data.yaml and dataset_manifest.json: {data_root}")
    source = yaml.safe_load(source_yaml.read_text(encoding="utf-8-sig"))
    if not isinstance(source, dict):
        raise ValueError(f"Dataset YAML must contain a mapping: {source_yaml}")
    if source.get("path", ".") != ".":
        raise ValueError("Uploaded data.yaml must retain the portable path: . setting")
    dataset_manifest = json.loads((data_root / "dataset_manifest.json").read_text(encoding="utf-8"))
    if dataset_manifest.get("dataset_id") != "multiclass_final_v7":
        raise ValueError(f"Unexpected dataset_id in manifest: {dataset_manifest.get('dataset_id')}")
    expected_classes = json.loads((data_root / "taxonomy.json").read_text(encoding="utf-8"))["classes"]
    names = source.get("names")
    if isinstance(names, dict):
        names = [names.get(i, names.get(str(i))) for i in range(len(names))]
    if names != expected_classes or source.get("nc", len(expected_classes)) != len(expected_classes):
        raise ValueError(f"Dataset YAML classes/order do not match taxonomy.json: {names}")

    runtime = dict(source)
    runtime["path"] = str(data_root)
    working = Path(working_root) if working_root is not None else WORKING_ROOT
    working.mkdir(parents=True, exist_ok=True)
    runtime_yaml = working / "runtime_data.yaml"
    runtime_yaml.write_text(yaml.safe_dump(runtime, sort_keys=False), encoding="utf-8")

    checked = check_det_dataset(str(runtime_yaml), autodownload=False)
    checked_root = Path(checked["path"]).resolve()
    if checked_root != data_root:
        raise RuntimeError(f"Ultralytics resolved dataset root to {checked_root}, expected mounted root {data_root}")
    checked_names = checked["names"]
    checked_names = [checked_names[i] for i in range(len(checked_names))]
    if checked_names != expected_classes:
        raise RuntimeError(f"Ultralytics class order mismatch: {checked_names} != {expected_classes}")
    for split in ("train", "val", "test"):
        configured = runtime.get(split)
        resolved = checked.get(split)
        if configured is None or resolved is None:
            raise ValueError(f"Runtime dataset configuration requires {split}")
        configured_values = configured if isinstance(configured, list) else [configured]
        resolved_values = resolved if isinstance(resolved, list) else [resolved]
        expected_paths = [(data_root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
                          for value in configured_values]
        actual_paths = [Path(value).resolve() for value in resolved_values]
        if actual_paths != expected_paths or any(not path.exists() for path in actual_paths):
            raise RuntimeError(f"Ultralytics {split} paths mismatch/missing: {actual_paths} != {expected_paths}")
    return runtime_yaml.resolve()


def detect_devices(torch):
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Enable Kaggle GPU accelerator before training.")
    devices = []
    descriptions = []
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        free, total = torch.cuda.mem_get_info(i)
        name = props.name
        descriptions.append({"index": i, "name": name, "vram_total_bytes": total, "vram_free_bytes": free})
        if total >= 12 * 1024**3 and free >= 8 * 1024**3:
            devices.append(i)
    t4s = [x["index"] for x in descriptions if "t4" in x["name"].lower()
           and x["vram_total_bytes"] >= 12 * 1024**3 and x["vram_free_bytes"] >= 8 * 1024**3]
    selected = t4s[:2] if len(t4s) >= 2 else ([devices[0]] if devices else [])
    if not selected:
        raise RuntimeError(f"No usable CUDA GPU with >=12 GiB total and >=8 GiB free VRAM: {descriptions}")
    return selected, descriptions


def assert_runtime(commit: str) -> None:
    expected = os.environ.get("WASTEWISE_EXPECTED_COMMIT", "").strip()
    if not expected or commit != expected:
        raise RuntimeError(f"Git commit mismatch: running {commit}; set WASTEWISE_EXPECTED_COMMIT to the reviewed commit SHA")
    import ultralytics
    if ultralytics.__version__ != ULTRALYTICS_VERSION:
        raise RuntimeError(f"ultralytics=={ULTRALYTICS_VERSION} required, found {ultralytics.__version__}")
    import torch
    if not torch.distributed.is_available():
        raise RuntimeError("PyTorch distributed is unavailable; DDP compatibility check failed")
    import PIL, numpy, yaml
    config["package_versions"] = {"python": sys.version.split()[0], "torch": torch.__version__,
                                  "ultralytics": ultralytics.__version__, "pillow": PIL.__version__,
                                  "pyyaml": yaml.__version__, "numpy": numpy.__version__,
                                  "cuda_runtime": torch.version.cuda}
    return


def run_dataset_audit(data: Path) -> dict:
    WORKING_ROOT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "ml" / "scripts"))
    from audit_multiclass_final import audit
    report = audit(data, max_distance=4)
    (WORKING_ROOT / "dataset_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def train(data: Path, runtime_data: Path, devices: list[int], gpu_description: list[dict], smoke_only: bool = False):
    from ultralytics import YOLO
    yolo_devices = devices if len(devices) == 2 else devices[0]
    global_batch = 16 if len(devices) == 2 else 8
    project = WORKING_ROOT / "wastewise_runs"
    if smoke_only:
        model = YOLO(MODEL_NAME)
        model.train(data=str(runtime_data), epochs=1, fraction=0.01,
                    batch=global_batch, imgsz=IMGSZ, device=yolo_devices, workers=2,
                    seed=SEED, deterministic=True, amp=True, cache=False,
                    project=str(WORKING_ROOT / "wastewise_smoke"), name=f"smoke_{len(devices)}gpu",
                    exist_ok=True, save=False, plots=False, val=False, verbose=False)
        return
    run_name = "wastewise_yolo26s_v7_50ep"
    run_dir = project / run_name
    resume = os.environ.get("WASTEWISE_RESUME_RUN", "").strip()
    current_config = {**config, "dataset_manifest_sha256": sha256(data / "dataset_manifest.json"),
                      "initial_checkpoint_sha256": INITIAL_SHA256, "gpu_devices": devices}
    model = YOLO(MODEL_NAME)
    if resume:
        source = Path(resume).resolve()
        prior_cfg = json.loads((source / "run_config.json").read_text(encoding="utf-8"))
        for key, current in current_config.items():
            if prior_cfg.get(key) != current:
                raise RuntimeError(f"Resume blocked: saved {key} differs from the frozen run configuration")
        if not (source / "weights" / "last.pt").is_file():
            raise RuntimeError("Resume requires the persisted <run>/weights/last.pt checkpoint")
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        if run_dir.exists():
            raise RuntimeError(f"Resume target already exists: {run_dir}")
        shutil.copytree(source, run_dir)
        model = YOLO(str(run_dir / "weights" / "last.pt"))
        model.train(data=str(runtime_data), resume=True, device=yolo_devices, workers=2)
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "run_config.json").write_text(json.dumps(current_config, indent=2), encoding="utf-8")
        model.train(data=str(runtime_data), epochs=EPOCHS, batch=global_batch,
                    imgsz=IMGSZ, device=yolo_devices, workers=2, seed=SEED,
                    deterministic=True, patience=PATIENCE, optimizer="auto", amp=True,
                    cache=False, plots=True, save_period=1, close_mosaic=10,
                    project=str(project), name=run_name, exist_ok=True, verbose=True)
    best = run_dir / "weights" / "best.pt"
    last = run_dir / "weights" / "last.pt"
    results_csv = run_dir / "results.csv"
    if not (best.is_file() and last.is_file() and results_csv.is_file()):
        raise RuntimeError("Training output is incomplete: require best.pt, last.pt, and results.csv")
    validate_and_package(data, runtime_data, best, last, results_csv, run_dir, devices, gpu_description, global_batch)


def validate_and_package(data: Path, runtime_data: Path, best: Path, last: Path, results_csv: Path,
                         run_dir: Path, devices: list[int], gpu_description: list[dict], batch: int):
    from ultralytics import YOLO
    model = YOLO(str(best))
    metrics = model.val(data=str(runtime_data), split="val", imgsz=IMGSZ, batch=batch,
                        device=devices if len(devices) == 2 else devices[0], plots=True,
                        project=str(run_dir.parent), name=f"{run_dir.name}_validation", exist_ok=True)
    names = [model.names[i] for i in range(len(model.names))]
    expected = json.loads((data / "taxonomy.json").read_text(encoding="utf-8"))["classes"]
    if [n.casefold() for n in names] != [n.casefold() for n in expected]:
        raise RuntimeError(f"Checkpoint class order mismatch: {names} != {expected}")
    taxonomy = json.loads((ROOT / "backend" / "taxonomy.json").read_text(encoding="utf-8"))
    class_map = [{"class_id": i, "name": name,
                  "category_id": expected[i]} for i, name in enumerate(expected)]
    per_class = {}
    box = metrics.box
    for i, name in enumerate(expected):
        per_class[name] = {"precision": float(box.p[i]), "recall": float(box.r[i]),
                           "mAP50": float(box.ap50[i]), "mAP50_95": float(box.ap[i].mean())}
    output = {
        "schema_version": "1.0", "model_id": run_dir.name, "model_family": "YOLO26", "task": "detect",
        "taxonomy_version": taxonomy["version"], "class_map": class_map,
        "dataset_version": "multiclass_final_v7", "dataset_manifest_sha256": sha256(data / "dataset_manifest.json"),
        "checkpoint_sha256": sha256(best), "preprocessing": {"imgsz": IMGSZ},
        "validation_split": "val", "validation_metrics_by_class": per_class,
        "test_evaluated": False, "initial_checkpoint": MODEL_NAME,
        "initial_checkpoint_sha256": INITIAL_SHA256,
        "training_config": config, "gpu_devices": devices, "gpu_description": gpu_description,
        "benchmark_status": "validation_only_not_tested",
    }
    (run_dir / "model_manifest.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    shutil.copy2(run_dir / "model_manifest.json", best.parent / "model_manifest.json")
    artifact_dir = WORKING_ROOT / "wastewise_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "model_manifest.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    files = [best, last, results_csv, run_dir / "run_config.json", run_dir / "args.yaml",
             run_dir / "model_manifest.json", best.parent / "model_manifest.json",
             Path("/kaggle/working/dataset_audit.json")]
    files.extend(p for p in run_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".png", ".csv"})
    for candidate in run_dir.parent.glob(f"{run_dir.name}_validation*"):
        if candidate.is_file(): files.append(candidate)
        elif candidate.is_dir(): files.extend(p for p in candidate.rglob("*") if p.is_file())
    archive = artifact_dir / "wastewise_yolo26s_v7_artifacts.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        seen = set()
        for path in files:
            if path.is_file() and path.resolve() not in seen:
                seen.add(path.resolve())
                resolved = path.resolve()
                if resolved.is_relative_to(run_dir.resolve()):
                    archive_name = Path("run") / resolved.relative_to(run_dir.resolve())
                elif resolved.is_relative_to(run_dir.parent.resolve()):
                    archive_name = Path("validation") / resolved.relative_to(run_dir.parent.resolve())
                else:
                    archive_name = Path(path.name)
                zf.write(path, archive_name.as_posix())
    checksum = sha256(archive)
    (artifact_dir / "SHA256SUMS.txt").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"Artifact: {archive} sha256={checksum}")


def run_gpu_smoke_and_train(data: Path, runtime_data: Path, devices: list[int], gpu_description: list[dict]):
    """Only permit explicit two-to-one GPU fallback after a failed DDP smoke."""
    if len(devices) == 2:
        try:
            train(data, runtime_data, devices, gpu_description, smoke_only=True)
        except Exception as exc:
            print(f"DDP smoke failed: {type(exc).__name__}: {exc}")
            if os.environ.get("WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK") != "1":
                raise RuntimeError(
                    "Set WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK=1 to explicitly run one-GPU smoke before full training"
                ) from exc
            devices = [devices[0]]
            train(data, runtime_data, devices, gpu_description, smoke_only=True)
    else:
        train(data, runtime_data, devices, gpu_description, smoke_only=True)
    train(data, runtime_data, devices, gpu_description)
    return devices


config = {
    "dataset_id": "multiclass_final_v7", "classes": ["plastic", "paper", "metal", "glass", "organic", "textile"],
    "taxonomy_version": "2026-11-13.3", "model": MODEL_NAME, "epochs": EPOCHS, "batch_single_gpu": 8,
    "batch_dual_gpu": 16, "imgsz": IMGSZ, "seed": SEED, "patience": PATIENCE,
    "optimizer": "auto", "amp": True, "close_mosaic": 10, "workers": 2,
}


def main() -> None:
    commit = get_commit()
    assert_runtime(commit)
    data = find_data()
    print(f"Git commit: {commit}\nDataset: {data}")
    report = run_dataset_audit(data)
    if not report.get("pass"):
        raise RuntimeError("Final dataset audit did not pass")
    runtime_data = prepare_runtime_data(data)
    print(f"Ultralytics runtime dataset YAML: {runtime_data}")
    import torch
    devices, gpu_description = detect_devices(torch)
    print(json.dumps({"gpu_devices": devices, "gpus": gpu_description}, indent=2))
    weight_path = Path(MODEL_NAME)
    if not weight_path.exists():
        from ultralytics import YOLO
        YOLO(MODEL_NAME)
    if sha256(weight_path) != INITIAL_SHA256:
        raise RuntimeError("Pretrained yolo26s.pt checksum differs from reviewed local checkpoint")
    run_gpu_smoke_and_train(data, runtime_data, devices, gpu_description)


if __name__ == "__main__":
    main()
