"""Fetch only MRS Trash Detection images fully labeled as Textile."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


REPO = "https://huggingface.co/datasets/alexNova/MRS-Trash-Detection"


def fetch(repo_root: Path) -> dict:
    checkout = repo_root / "datasets" / "mrs_trash_detection_hf"
    if not (checkout / ".git").is_dir():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["GIT_LFS_SKIP_SMUDGE"] = "1"
        subprocess.run(["git", "clone", "--depth", "1", REPO, str(checkout)], check=True, env=env)
    class_map = {int(key): value for key, value in
                 json.loads((checkout / "classes.json").read_text(encoding="utf-8")).items()}
    if class_map.get(3) != "Textile":
        raise ValueError(f"Unexpected MRS class order: {class_map}")
    result = {"selected_images": 0, "selected_boxes": 0, "images_by_split": {}}
    for split in ("train", "val", "test"):
        selected, boxes = [], 0
        for label_path in sorted((checkout / "labels" / split).glob("*.txt")):
            lines = [line.split() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines and all(len(row) == 5 and int(row[0]) in class_map and class_map[int(row[0])] == "Textile"
                             for row in lines):
                selected.append(f"images/{split}/{label_path.stem}.jpg")
                boxes += len(lines)
        if selected:
            include = ",".join(selected)
            subprocess.run(["git", "lfs", "pull", f"--include={include}"], cwd=checkout, check=True)
        result["selected_images"] += len(selected)
        result["selected_boxes"] += boxes
        result["images_by_split"][split] = len(selected)
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    fetch(Path(__file__).resolve().parents[2])
