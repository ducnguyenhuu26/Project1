from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "kaggle"))

from kaggle_prepare import inspect_archive
from kernel import extract_source
from train import choose_weights, validate_data
from train_multiclass import inspect_dataset


def test_train_data_preflight_rejects_wrong_classes(tmp_path: Path) -> None:
    for split in ("train", "valid", "test"):
        image_dir = tmp_path / split / "images"
        image_dir.mkdir(parents=True)
        (image_dir / "example.jpg").touch()
    data = tmp_path / "data.yaml"
    data.write_text(
        "train: train/images\nval: valid/images\ntest: test/images\n"
        "names: [Plastic, Paper, Metal]\nnc: 3\n", encoding="utf-8")
    assert len(validate_data(data)) == 3
    data.write_text(data.read_text(encoding="utf-8").replace("Paper", "Glass"), encoding="utf-8")
    with pytest.raises(ValueError, match="0=Plastic"):
        validate_data(data)


def test_dataset_inspection_accepts_empty_negative_label_files(tmp_path: Path) -> None:
    for split in ("train", "val", "test"):
        image_dir = tmp_path / split / "images"
        label_dir = tmp_path / split / "labels"
        image_dir.mkdir(parents=True)
        label_dir.mkdir()
        (image_dir / "negative.jpg").touch()
        (label_dir / "negative.txt").write_text("\n", encoding="utf-8")
    data = tmp_path / "data.yaml"
    data.write_text("path: .\ntrain: train/images\nval: val/images\ntest: test/images\n"
                    "nc: 3\nnames: [Plastic, Paper, Metal]\n", encoding="utf-8")
    (tmp_path / "taxonomy.json").write_text(
        '{"version":"test","classes":["plastic","paper","metal"]}', encoding="utf-8")
    assert inspect_dataset(data)[1] == ["Plastic", "Paper", "Metal"]


def test_archive_preflight_and_windows_separator_extraction(tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.zip"
    with ZipFile(archive_path, "w") as archive:
        for split in ("train", "valid", "test"):
            prefix = f"Splitted_Dataset\\{split}\\"
            archive.writestr(prefix + "images\\example.jpg", b"image")
            archive.writestr(prefix + "labels\\example.txt", "0 0.5 0.5 0.2 0.2\n")
    info = inspect_archive(archive_path)
    assert info["images"] == {"train": 1, "valid": 1, "test": 1}
    root = extract_source(archive_path, tmp_path / "extracted")
    assert (root / "valid" / "labels" / "example.txt").is_file()


def test_archive_rejects_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("Splitted_Dataset/../outside.txt", "x")
    with pytest.raises(RuntimeError, match="Unsafe"):
        extract_source(archive_path, tmp_path / "extracted")


def test_domain_adaptation_is_new_run_not_resume(tmp_path: Path) -> None:
    checkpoint = tmp_path / "best.pt"
    checkpoint.touch()
    weights, resume = choose_weights("yolo26s.pt", checkpoint, None)
    assert weights == str(checkpoint.resolve()) and not resume
    weights, resume = choose_weights("yolo26s.pt", None, checkpoint)
    assert weights == str(checkpoint.resolve()) and resume
    with pytest.raises(ValueError, match="mutually exclusive"):
        choose_weights("yolo26s.pt", checkpoint, checkpoint)
