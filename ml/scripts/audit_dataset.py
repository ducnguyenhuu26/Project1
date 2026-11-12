"""Read-only SWiM3 audit. Report exact and likely augmented-family split overlap."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError


NAMES = {0: "Plastic", 1: "Paper", 2: "Metal"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def family(stem: str) -> str:
    stem = re.sub(r"\.rf\.[0-9a-f]{16,}(?:_aug\d+)?$", "", stem, flags=re.I)
    return re.sub(r"_aug\d+$", "", stem, flags=re.I).lower()


def audit(root: Path, hash_images: bool = False) -> dict:
    report = {"splits": {}, "issues": [], "exact_overlap": [], "family_overlap": []}
    hashes, families = defaultdict(set), defaultdict(set)
    for split in ("train", "valid", "test"):
        image_dir, label_dir = root / split / "images", root / split / "labels"
        images = {p.stem: p for p in image_dir.iterdir() if p.suffix.lower() in IMAGE_EXT}
        labels = {p.stem: p for p in label_dir.glob("*.txt")}
        counts = Counter()
        for stem, image_path in images.items():
            families[family(stem)].add(split)
            try:
                with Image.open(image_path) as im:
                    im.verify()
            except (OSError, UnidentifiedImageError) as exc:
                report["issues"].append(f"{image_path}: unreadable ({exc})")
            if hash_images:
                hashes[hashlib.sha256(image_path.read_bytes()).hexdigest()].add(split)
        for stem, label_path in labels.items():
            if stem not in images:
                report["issues"].append(f"{label_path}: orphan label")
            for number, line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), 1):
                parts = line.split()
                try:
                    if len(parts) != 5:
                        raise ValueError("expected 5 columns")
                    class_id = int(parts[0])
                    x, y, w, h = map(float, parts[1:])
                    tolerance = 1e-6  # allow decimal serialization at an image edge
                    if class_id not in NAMES or not (0 < w <= 1+tolerance and 0 < h <= 1+tolerance and -tolerance <= x-w/2 and x+w/2 <= 1+tolerance and -tolerance <= y-h/2 and y+h/2 <= 1+tolerance):
                        raise ValueError("invalid class or box")
                    counts[class_id] += 1
                except ValueError as exc:
                    report["issues"].append(f"{label_path}:{number}: {exc}")
        report["splits"][split] = {"images": len(images), "labels": len(labels), "objects": dict(sorted(counts.items())), "unlabeled_images": len(images.keys()-labels.keys())}
    report["family_overlap"] = sorted([key for key, splits in families.items() if len(splits) > 1])
    if hash_images:
        report["exact_overlap"] = sorted([key for key, splits in hashes.items() if len(splits) > 1])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("datasets/swim3/Splitted_Dataset"))
    parser.add_argument("--hash-images", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.root, args.hash_images)
    content = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content, encoding="utf-8")
    print(content[:16000])
    print(f"issues={len(result['issues'])} family_overlap={len(result['family_overlap'])} exact_overlap={len(result['exact_overlap'])}")
