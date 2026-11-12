"""Exercise the packaged Kaggle data path without starting a GPU job."""
from io import BytesIO
import json
from pathlib import Path
import random
import sys
from zipfile import ZipFile, ZipInfo

from PIL import Image
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "kaggle"))

from audit_dataset import audit
from kaggle_prepare import inspect_archive, main as package_kernel
from kernel import extract_source
from prepare_clean_split import prepare
from backend.main import build_app
from backend.services import Detection


def image_bytes(seed: int, *, compress_level: int = 6) -> bytes:
    values = random.Random(seed).randbytes(32 * 32 * 3)
    output = BytesIO()
    Image.frombytes("RGB", (32, 32), values).save(output, format="PNG", compress_level=compress_level)
    return output.getvalue()


def test_windows_archive_to_clean_audit(tmp_path: Path, monkeypatch) -> None:
    archive_path = tmp_path / "swim3.zip"
    with ZipFile(archive_path, "w") as archive:
        for split in ("train", "valid", "test"):
            for kind in ("images", "labels"):
                entry = ZipInfo(f"Splitted_Dataset/{split}/{kind}/")
                entry.create_system = 0
                archive.writestr(entry, b"")
        for index in range(36):
            split = ("train", "valid", "test")[index % 3]
            prefix = f"Splitted_Dataset/{split}/"
            archive.writestr(prefix + f"images/photo_{index}.png", image_bytes(index))
            archive.writestr(prefix + f"labels/photo_{index}.txt", f"{index % 3} 0.5 0.5 0.5 0.5\n")
        # Identical pixels with different ZIP bytes and unrelated names.
        archive.writestr("Splitted_Dataset/test/images/recompressed.png", image_bytes(0, compress_level=0))
        archive.writestr("Splitted_Dataset/test/labels/recompressed.txt", "0 0.5 0.5 0.5 0.5\n")
    assert inspect_archive(archive_path)["images"] == {"train": 12, "valid": 12, "test": 13}
    bundle = tmp_path / "kernel"
    monkeypatch.setattr(sys, "argv", ["kaggle_prepare.py", "--username", "tester",
                        "--dataset-source", "tester/swim3", "--archive", str(archive_path),
                        "--out", str(bundle)])
    package_kernel()
    assert (bundle / "perceptual_hash.py").is_file()
    assert json.loads((bundle / "config.json").read_text())["archive_sha256"] == inspect_archive(archive_path)["sha256"]
    extracted = extract_source(archive_path, tmp_path / "extracted")
    clean = tmp_path / "clean"
    report = prepare(extracted, clean)
    checked = audit(clean, hash_images=True, perceptual=True)
    manifest = json.loads((clean / "manifest.json").read_text(encoding="utf-8"))["manifest"]
    copies = [row for row in manifest if row["source_name"] in {"photo_0.png", "recompressed.png"}]
    assert len({row["target_split"] for row in copies}) <= 1
    assert 36 <= sum(report["splits"].values()) <= 37
    assert not checked["issues"] and not checked["family_overlap"]
    assert not checked["exact_overlap"] and not checked["perceptual_overlap"]


class ContractDetector:
    mode = "real"
    model_version = "fixture.pt"

    def predict(self, image, filename):
        return [Detection(0, 0.72, [1.0, 2.0, image.width - 1.0, image.height - 2.0])]


def test_scan_contract_consumed_by_frontend() -> None:
    client = TestClient(build_app(detector=ContractDetector()))
    response = client.post("/api/v1/scans", files={"image": ("scene.png", image_bytes(99), "image/png")})
    assert response.status_code == 200
    scan = response.json()
    knowledge = client.get("/api/v1/waste-types").json()
    material_ids = {item["id"] for item in knowledge["materials"]}
    assert scan["mode"] == "real" and scan["model_version"] == "fixture.pt"
    assert scan["image_width"] == scan["image_height"] == 32
    assert scan["detections"][0]["class_id"] == 0
    assert scan["detections"][0]["material_id"] == "plastic"
    assert scan["detections"][0]["category_id"] == "plastic"
    assert scan["detections"][0]["bbox_xyxy"] == [1.0, 2.0, 31.0, 30.0]
    assert scan["detections"][0]["origin"] == "ai"
    assert scan["summary"] == [{"category_id": "plastic", "material_id": "plastic", "advice_id": "plastic", "name": "Nhựa", "estimated_count": 1}]
    assert scan["advice"][0]["id"] in material_ids
    assert scan["advice"][0]["do"] and scan["advice"][0]["caution"]
