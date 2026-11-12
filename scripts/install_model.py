"""Validate and install a trained YOLO26 checkpoint without replacing old models."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(checkpoint: Path, manifest_path: Path, taxonomy_path: Path | None = None) -> dict:
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        raise ValueError(f"Checkpoint is missing or empty: {checkpoint}")
    if not manifest_path.is_file():
        raise ValueError(f"Model manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    taxonomy_file = taxonomy_path or ROOT / "backend" / "taxonomy.json"
    taxonomy = json.loads(taxonomy_file.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "1.0" or manifest.get("task") != "detect":
        raise ValueError("Unsupported model manifest schema/task")
    if manifest.get("model_family") != "YOLO26":
        raise ValueError("Only YOLO26 detector checkpoints may be installed by this helper")
    if manifest.get("taxonomy_version") != taxonomy.get("version"):
        raise ValueError("Model taxonomy_version does not match this backend")
    actual = sha256_file(checkpoint)
    if manifest.get("checkpoint_sha256") != actual:
        raise ValueError("Checkpoint SHA-256 does not match model_manifest.json")
    categories = {row["id"]: row for row in taxonomy.get("categories", [])}
    class_map = manifest.get("class_map")
    if not isinstance(class_map, list) or not class_map:
        raise ValueError("Model manifest class_map must be a non-empty list")
    ids = [row.get("class_id") for row in class_map]
    if ids != list(range(len(class_map))):
        raise ValueError("class_map indices must be contiguous and ordered from 0")
    category_ids = []
    for row in class_map:
        category_id = row.get("category_id")
        if category_id not in categories or not categories[category_id].get("detection_supported"):
            raise ValueError(f"Unsupported or unknown taxonomy category: {category_id}")
        expected = {str(value).casefold() for value in categories[category_id].get("model_names", [])}
        if str(row.get("name", "")).casefold() not in expected:
            raise ValueError(f"Checkpoint class name does not match taxonomy for {category_id}")
        category_ids.append(category_id)
    if len(set(category_ids)) != len(category_ids):
        raise ValueError("class_map contains duplicate taxonomy categories")
    return {**manifest, "checkpoint_sha256": actual}


def install(checkpoint: Path, manifest_path: Path, weights_dir: Path, taxonomy_path: Path | None = None) -> Path:
    manifest = validate_manifest(checkpoint, manifest_path, taxonomy_path)
    model_id = str(manifest.get("model_id", "")).strip()
    if not model_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", model_id):
        raise ValueError("model_id must be a safe filename token")
    destination_dir = weights_dir / model_id
    if destination_dir.exists():
        raise FileExistsError(f"Model version already exists; old artifacts are preserved: {destination_dir}")
    destination_dir.mkdir(parents=True)
    temporary = destination_dir / "best.pt.part"
    try:
        shutil.copy2(checkpoint, temporary)
        if sha256_file(temporary) != manifest["checkpoint_sha256"]:
            raise ValueError("Copied checkpoint failed SHA-256 verification")
        temporary.replace(destination_dir / "best.pt")
        shutil.copy2(manifest_path, destination_dir / "model_manifest.json")
    except Exception:
        shutil.rmtree(destination_dir, ignore_errors=True)
        raise
    return destination_dir / "best.pt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--weights-dir", type=Path, default=ROOT / "weights" / "models")
    parser.add_argument("--taxonomy", type=Path, default=ROOT / "backend" / "taxonomy.json")
    args = parser.parse_args()
    try:
        installed = install(args.checkpoint, args.manifest, args.weights_dir, args.taxonomy)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    relative = installed.relative_to(ROOT).as_posix() if installed.is_relative_to(ROOT) else str(installed)
    print(f"Installed checkpoint: {installed}")
    print("Set these values in .env, then restart the API:")
    print("DETECTOR_MODE=real")
    print(f"MODEL_PATH={relative}")
    print("INFERENCE_DEVICE=cpu")
    print("Rollback: restore the previous MODEL_PATH from your saved .env and restart the API.")


if __name__ == "__main__":
    main()
