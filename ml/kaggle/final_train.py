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


def find_data() -> Path:
    if (DATA / "dataset_manifest.json").is_file():
        return DATA
    matches = list(Path("/kaggle/input").glob("**/multiclass_final_v7/dataset_manifest.json"))
    if not matches:
        matches = list(Path("/kaggle/input").glob("*/dataset_manifest.json"))
    matches = [m.parent for m in matches if json.loads(m.read_text(encoding="utf-8")).get("dataset_id") == "multiclass_final_v7"]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one uploaded multiclass_final_v7 dataset, found {len(matches)}")
    return matches[0]


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
    sys.path.insert(0, str(ROOT / "ml" / "scripts"))
    from audit_multiclass_final import audit
    report = audit(data, max_distance=4)
    (Path("/kaggle/working") / "dataset_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def train(data: Path, devices: list[int], gpu_description: list[dict], smoke_only: bool = False):
    from ultralytics import YOLO
    yolo_devices = devices if len(devices) == 2 else devices[0]
    global_batch = 16 if len(devices) == 2 else 8
    project = Path("/kaggle/working/wastewise_runs")
    if smoke_only:
        model = YOLO(MODEL_NAME)
        model.train(data=str(data / "data.yaml"), epochs=1, fraction=0.01,
                    batch=global_batch, imgsz=IMGSZ, device=yolo_devices, workers=2,
                    seed=SEED, deterministic=True, amp=True, cache=False,
                    project="/kaggle/working/wastewise_smoke", name=f"smoke_{len(devices)}gpu",
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
        model.train(resume=True, device=yolo_devices, workers=2)
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "run_config.json").write_text(json.dumps(current_config, indent=2), encoding="utf-8")
        model.train(data=str(data / "data.yaml"), epochs=EPOCHS, batch=global_batch,
                    imgsz=IMGSZ, device=yolo_devices, workers=2, seed=SEED,
                    deterministic=True, patience=PATIENCE, optimizer="auto", amp=True,
                    cache=False, plots=True, save_period=1, close_mosaic=10,
                    project=str(project), name=run_name, exist_ok=True, verbose=True)
    best = run_dir / "weights" / "best.pt"
    last = run_dir / "weights" / "last.pt"
    results_csv = run_dir / "results.csv"
    if not (best.is_file() and last.is_file() and results_csv.is_file()):
        raise RuntimeError("Training output is incomplete: require best.pt, last.pt, and results.csv")
    validate_and_package(data, best, last, results_csv, run_dir, devices, gpu_description, global_batch)


def validate_and_package(data: Path, best: Path, last: Path, results_csv: Path,
                         run_dir: Path, devices: list[int], gpu_description: list[dict], batch: int):
    from ultralytics import YOLO
    model = YOLO(str(best))
    metrics = model.val(data=str(data / "data.yaml"), split="val", imgsz=IMGSZ, batch=batch,
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
    artifact_dir = Path("/kaggle/working/wastewise_artifacts")
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
    import torch
    devices, gpu_description = detect_devices(torch)
    print(json.dumps({"gpu_devices": devices, "gpus": gpu_description}, indent=2))
    weight_path = Path(MODEL_NAME)
    if not weight_path.exists():
        from ultralytics import YOLO
        YOLO(MODEL_NAME)
    if sha256(weight_path) != INITIAL_SHA256:
        raise RuntimeError("Pretrained yolo26s.pt checksum differs from reviewed local checkpoint")
    if len(devices) == 2:
        try:
            train(data, devices, gpu_description, smoke_only=True)
        except Exception as exc:
            print(f"DDP smoke failed: {type(exc).__name__}: {exc}")
            if os.environ.get("WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK") != "1":
                raise RuntimeError("Set WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK=1 to explicitly run one-GPU smoke before full training") from exc
            devices = [devices[0]]
            train(data, devices, gpu_description, smoke_only=True)
    else:
        train(data, devices, gpu_description, smoke_only=True)
    train(data, devices, gpu_description)


if __name__ == "__main__":
    main()
