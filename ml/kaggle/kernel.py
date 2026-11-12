"""Kaggle GPU entry point. Reads an attached SWiM3 archive, never uploads data."""
import json
import hashlib
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import zipfile


HERE = Path(__file__).parent
WORK = Path("/kaggle/working")


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_source(archive_path: Path, destination: Path) -> Path:
    """Normalize Windows ZIP separators and reject traversal/duplicate entries."""
    destination = destination.resolve()
    seen = set()
    with zipfile.ZipFile(archive_path) as archive:
        members = []
        for info in archive.infolist():
            normalized = info.filename.replace("\\", "/")
            parts = normalized.rstrip("/").split("/")
            if (normalized.startswith("/") or len(parts) < 2 or parts[0] != "Splitted_Dataset"
                    or any(part in {"", ".", ".."} or ":" in part for part in parts)
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise RuntimeError(f"Unsafe or unexpected ZIP member: {info.filename}")
            target = destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination):
                raise RuntimeError(f"ZIP path escapes destination: {info.filename}")
            if target in seen:
                raise RuntimeError(f"Duplicate ZIP member: {info.filename}")
            seen.add(target)
            members.append((info, target))
        for info, target in members:
            if info.is_dir() or info.filename.endswith("\\"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=4 * 1024 * 1024)
    return destination / "Splitted_Dataset"


def main():
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    archives = sorted(Path("/kaggle/input").rglob("*.zip"))
    if len(archives) != 1:
        raise RuntimeError(f"Expected one attached SWiM3 ZIP, found {len(archives)}. Attach only the source archive.")
    archive_digest = sha256(archives[0])
    expected = config.get("archive_sha256")
    if expected and archive_digest != expected:
        raise RuntimeError("Attached ZIP checksum differs from reviewed local archive")
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("Kaggle GPU is not enabled; turn on a GPU accelerator before running")
    extracted = WORK / "swim3_source"
    source = extract_source(archives[0], extracted)
    run("-m", "pip", "install", "ultralytics==8.4.210")
    clean = WORK / "swim3_clean"
    run(HERE / "prepare_clean_split.py", "--source", source, "--out", clean)
    run(HERE / "audit_dataset.py", "--root", clean, "--hash-images",
        "--out", WORK / "clean_audit.json")
    audit = json.loads((WORK / "clean_audit.json").read_text(encoding="utf-8"))
    if (audit["issues"] or audit["family_overlap"] or audit["exact_overlap"]
            or any(row["unlabeled_images"] for row in audit["splits"].values())):
        raise RuntimeError("Clean dataset audit failed; see /kaggle/working/clean_audit.json")
    run(HERE / "train.py", "--data", clean / "data.yaml", "--model", config["model"],
        "--epochs", config["epochs"], "--batch", config["batch"], "--imgsz", 640,
        "--device", 0, "--workers", 2, "--project", WORK / "runs", "--name", config["name"])
    best = WORK / "runs" / config["name"] / "weights" / "best.pt"
    if not best.exists():
        # Ultralytics may nest a relative project under runs/detect; fail clearly.
        raise RuntimeError(f"Training ended without checkpoint at {best}")
    run(HERE / "evaluate.py", "--model", best, "--data", clean / "data.yaml",
        "--split", "val", "--device", 0, "--out", WORK / "validation.json")
    import ultralytics
    (WORK / "model_metadata.json").write_text(json.dumps({
        "model": config["model"], "classes": ["Plastic", "Paper", "Metal"],
        "data_split_seed": 42, "archive_sha256": archive_digest,
        "best_sha256": sha256(best), "checkpoint": str(best),
        "ultralytics_version": ultralytics.__version__,
        "training_config": config,
        "note": "Validation only; SWiM3 test and VN-Field test remain sealed."
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
