import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from install_model import install, validate_manifest


def sample_manifest(checkpoint: bytes) -> dict:
    taxonomy = json.loads((ROOT / "backend" / "taxonomy.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "1.0", "model_id": "local-smoke-v2", "model_family": "YOLO26", "task": "detect",
        "taxonomy_version": taxonomy["version"],
        "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
        "class_map": [
            {"class_id": 0, "name": "Plastic", "category_id": "plastic"},
            {"class_id": 1, "name": "Glass", "category_id": "glass"},
        ],
    }


def test_install_model_validates_checksum_and_preserves_previous_versions(tmp_path: Path):
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"fake test weights, not a model")
    manifest = sample_manifest(checkpoint.read_bytes())
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    installed = install(checkpoint, manifest_path, tmp_path / "weights")
    assert installed.read_bytes() == checkpoint.read_bytes()
    assert json.loads(installed.with_name("model_manifest.json").read_text())["class_map"] == manifest["class_map"]
    with pytest.raises(FileExistsError, match="preserved"):
        install(checkpoint, manifest_path, tmp_path / "weights")
    checkpoint.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_manifest(checkpoint, manifest_path)


def test_install_model_rejects_unmapped_class_and_old_taxonomy(tmp_path: Path):
    checkpoint = tmp_path / "best.pt"
    checkpoint.write_bytes(b"test weights")
    manifest = sample_manifest(checkpoint.read_bytes())
    manifest["class_map"][1]["category_id"] = "unregistered_category"
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported or unknown taxonomy category"):
        validate_manifest(checkpoint, manifest_path)
    manifest["class_map"][1]["category_id"] = "glass"
    manifest["taxonomy_version"] = "old-taxonomy"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="taxonomy_version"):
        validate_manifest(checkpoint, manifest_path)
