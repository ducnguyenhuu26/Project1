"""Build a reviewable Kaggle kernel folder. Does not authenticate or submit."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import zipfile


def inspect_archive(path: Path) -> dict:
    """Check the archive index before uploading ~2 GB to Kaggle."""
    if not path.is_file():
        raise ValueError(f"Archive does not exist: {path}")
    counts = defaultdict(lambda: {"images": set(), "labels": set()})
    names = set()
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            name = member.filename.replace("\\", "/").rstrip("/")
            parts = name.split("/")
            if (name.startswith("/") or parts[0] != "Splitted_Dataset"
                    or any(part in {"", ".", ".."} or ":" in part for part in parts)):
                raise ValueError(f"Unexpected ZIP path: {member.filename}")
            if name in names:
                raise ValueError(f"Duplicate ZIP path: {member.filename}")
            names.add(name)
            if member.is_dir():
                continue
            if len(parts) != 4 or parts[1] not in {"train", "valid", "test"}:
                raise ValueError(f"Unexpected ZIP file: {member.filename}")
            split, kind, filename = parts[1:]
            suffix = Path(filename).suffix.lower()
            if kind == "images" and suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                counts[split]["images"].add(Path(filename).stem)
            elif kind == "labels" and suffix == ".txt":
                counts[split]["labels"].add(Path(filename).stem)
                for line_number, line in enumerate(archive.read(member).decode("utf-8-sig").splitlines(), 1):
                    if not line.strip():
                        continue
                    fields = line.split()
                    try:
                        class_id = int(fields[0])
                        numbers = [float(value) for value in fields[1:]]
                    except (ValueError, IndexError) as exc:
                        raise ValueError(f"Bad label {member.filename}:{line_number}") from exc
                    if (len(fields) != 5 or class_id not in (0, 1, 2)
                            or not all(map(math.isfinite, numbers)) or numbers[2] <= 0 or numbers[3] <= 0):
                        raise ValueError(f"Bad label {member.filename}:{line_number}")
            else:
                raise ValueError(f"Unexpected ZIP file: {member.filename}")
    summary = {}
    for split in ("train", "valid", "test"):
        images, labels = counts[split]["images"], counts[split]["labels"]
        if not images or images != labels:
            raise ValueError(f"{split}: images={len(images)}, labels={len(labels)}; every image needs a label")
        summary[split] = len(images)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "images": summary, "archive_name": path.name}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--username",required=True)
    p.add_argument("--dataset-source",required=True,help="Kaggle slug owner/dataset")
    p.add_argument("--model",choices=["yolo26n.pt","yolo26s.pt"],default="yolo26s.pt")
    p.add_argument("--epochs",type=int,default=80)
    p.add_argument("--batch",type=int,default=8)
    p.add_argument("--archive",type=Path,help="Local SWiM3 ZIP to preflight and checksum before upload")
    p.add_argument("--out",type=Path,default=Path("outputs/kaggle_kernel"))
    a=p.parse_args()
    if (a.epochs<1 or a.batch<1 or not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+", a.dataset_source)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", a.username)):
        p.error("invalid epochs, batch or dataset source")
    try:
        archive_info = inspect_archive(a.archive) if a.archive else None
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        p.error(str(exc))
    a.out.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).parents[1]
    shutil.copy2(source/"kaggle"/"kernel.py",a.out/"kernel.py")
    for name in ("audit_dataset.py","perceptual_hash.py","prepare_clean_split.py","train.py","evaluate.py"):
        shutil.copy2(source/"scripts"/name,a.out/name)
    slug=f"wastewise-{a.model.removesuffix('.pt')}"
    metadata={"id":f"{a.username}/{slug}","title":slug,"code_file":"kernel.py",
              "language":"python","kernel_type":"script","is_private":"true",
              "enable_gpu":"true","enable_internet":"true","dataset_sources":[a.dataset_source]}
    (a.out/"kernel-metadata.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    config={"model":a.model,"epochs":a.epochs,"batch":a.batch,"name":slug}
    if archive_info:
        config["archive_sha256"] = archive_info["sha256"]
        config["archive_name"] = archive_info["archive_name"]
        (a.out/"archive_preflight.json").write_text(json.dumps(archive_info, indent=2), encoding="utf-8")
    (a.out/"config.json").write_text(json.dumps(config,indent=2),encoding="utf-8")
    print(f"Prepared {a.out.resolve()}; review config and metadata before Kaggle submission.")


if __name__=="__main__":
    main()
