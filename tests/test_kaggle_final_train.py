from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
import yaml
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "kaggle"))

import final_train


CLASSES = ["plastic", "paper", "metal", "glass", "organic", "textile"]


def make_dataset(root: Path) -> Path:
    root.mkdir(parents=True)
    for split in ("train", "val", "test"):
        (root / split / "images").mkdir(parents=True)
    (root / "data.yaml").write_text(yaml.safe_dump({
        "path": ".", "train": "train/images", "val": "val/images", "test": "test/images",
        "nc": len(CLASSES), "names": CLASSES,
    }, sort_keys=False), encoding="utf-8")
    (root / "taxonomy.json").write_text(json.dumps({"version": "test", "classes": CLASSES}), encoding="utf-8")
    (root / "dataset_manifest.json").write_text(json.dumps({"dataset_id": "multiclass_final_v7", "images": []}), encoding="utf-8")
    return root


@pytest.mark.parametrize("nested", [False, True], ids=["direct-input-root", "nested-dataset-directory"])
def test_find_data_resolves_direct_and_nested_kaggle_input_layouts(tmp_path: Path, nested: bool) -> None:
    input_root = tmp_path / "input"
    mount = input_root / "wastewise-dataset"
    dataset_root = mount / "multiclass_final_v7" if nested else mount
    make_dataset(dataset_root)

    assert final_train.find_data(data_override=mount, input_root=input_root) == dataset_root.resolve()


@pytest.mark.parametrize("nested", [False, True], ids=["direct-input-root", "nested-dataset-directory"])
def test_runtime_yaml_is_absolute_and_ultralytics_resolves_mounted_root(tmp_path: Path, nested: bool) -> None:
    mount = tmp_path / "input" / "wastewise-dataset"
    data_root = mount / "multiclass_final_v7" if nested else mount
    make_dataset(data_root)

    runtime_yaml = final_train.prepare_runtime_data(data_root, tmp_path / "working")
    config = yaml.safe_load(runtime_yaml.read_text(encoding="utf-8"))
    assert runtime_yaml == (tmp_path / "working" / "runtime_data.yaml").resolve()
    assert Path(config["path"]).is_absolute()
    assert Path(config["path"]).resolve() == data_root.resolve()
    assert config["path"] != "."

    from ultralytics.data.utils import check_det_dataset
    checked = check_det_dataset(str(runtime_yaml), autodownload=False)
    assert Path(checked["path"]).resolve() == data_root.resolve()
    assert checked["names"] == dict(enumerate(CLASSES))


def test_smoke_full_train_and_resume_all_receive_runtime_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = make_dataset(tmp_path / "dataset")
    runtime_yaml = final_train.prepare_runtime_data(data_root, tmp_path / "working")
    monkeypatch.setattr(final_train, "WORKING_ROOT", tmp_path / "working")
    calls = []

    class FakeYOLO:
        def __init__(self, _model: str):
            pass

        def train(self, **kwargs):
            calls.append(kwargs)
            if not kwargs.get("resume"):
                run = Path(kwargs["project"]) / kwargs["name"]
                (run / "weights").mkdir(parents=True, exist_ok=True)
                (run / "weights" / "best.pt").write_bytes(b"best")
                (run / "weights" / "last.pt").write_bytes(b"last")
                (run / "results.csv").write_text("epoch\n0\n", encoding="utf-8")

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    packaged = []
    monkeypatch.setattr(final_train, "validate_and_package", lambda *args: packaged.append(args[1]))

    final_train.train(data_root, runtime_yaml, [0], [], smoke_only=True)
    assert calls[-1]["data"] == str(runtime_yaml)

    final_train.train(data_root, runtime_yaml, [0], [], smoke_only=False)
    assert calls[-1]["data"] == str(runtime_yaml)
    assert packaged[-1] == runtime_yaml

    current_config = {
        **final_train.config,
        "dataset_manifest_sha256": final_train.sha256(data_root / "dataset_manifest.json"),
        "initial_checkpoint_sha256": final_train.INITIAL_SHA256,
        "gpu_devices": [0],
    }
    resume_source = tmp_path / "saved-run"
    (resume_source / "weights").mkdir(parents=True)
    (resume_source / "weights" / "last.pt").write_bytes(b"last")
    (resume_source / "weights" / "best.pt").write_bytes(b"best")
    (resume_source / "results.csv").write_text("epoch\n0\n", encoding="utf-8")
    (resume_source / "run_config.json").write_text(json.dumps(current_config), encoding="utf-8")
    monkeypatch.setattr(final_train, "WORKING_ROOT", tmp_path / "resume-working")
    monkeypatch.setenv("WASTEWISE_RESUME_RUN", str(resume_source))
    final_train.train(data_root, runtime_yaml, [0], [], smoke_only=False)
    assert calls[-1]["data"] == str(runtime_yaml)
    assert calls[-1]["resume"] is True
    assert packaged[-1] == runtime_yaml


def test_ddp_fallback_is_explicit_and_reuses_runtime_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path / "dataset"
    runtime_yaml = tmp_path / "working" / "runtime_data.yaml"
    calls = []

    def fake_train(root, runtime, devices, _description, smoke_only=False):
        calls.append((root, runtime, devices[:], smoke_only))
        if devices == [0, 1] and smoke_only:
            raise RuntimeError("DDP smoke fixture failure")

    monkeypatch.setattr(final_train, "train", fake_train)
    monkeypatch.setenv("WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK", "1")
    selected = final_train.run_gpu_smoke_and_train(data_root, runtime_yaml, [0, 1], [])
    assert selected == [0]
    assert calls == [
        (data_root, runtime_yaml, [0, 1], True),
        (data_root, runtime_yaml, [0], True),
        (data_root, runtime_yaml, [0], False),
    ]


def test_ddp_failure_without_explicit_fallback_stops_before_full_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def failed_smoke(_root, _runtime, devices, _description, smoke_only=False):
        calls.append((devices[:], smoke_only))
        raise RuntimeError("DDP smoke fixture failure")

    monkeypatch.setattr(final_train, "train", failed_smoke)
    monkeypatch.delenv("WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK", raising=False)
    with pytest.raises(RuntimeError, match="explicitly run one-GPU smoke"):
        final_train.run_gpu_smoke_and_train(tmp_path, tmp_path / "runtime_data.yaml", [0, 1], [])
    assert calls == [([0, 1], True)]


def test_notebook_pins_commit_installs_pinned_ultralytics_and_keeps_artifact_checks() -> None:
    notebook = json.loads((ROOT / "ml" / "notebooks" / "wastewise_final_kaggle.ipynb").read_text(encoding="utf-8"))
    code = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    match = re.search(r"REVIEWED_COMMIT = '([^']+)'", code)
    assert match
    reviewed_commit = match.group(1)
    if reviewed_commit != "SET_TO_FINAL_COMMIT_FROM_READINESS_REPORT":
        assert re.fullmatch(r"[0-9a-f]{40}", reviewed_commit)
        subprocess.run(["git", "cat-file", "-e", f"{reviewed_commit}^{{commit}}"], cwd=ROOT, check=True)
    assert "git','checkout','--detach',REVIEWED_COMMIT" in code
    assert "pip', 'install', '--no-deps', 'ultralytics==8.4.210'" in code
    assert "WASTEWISE_ALLOW_SINGLE_GPU_FALLBACK" in code
    assert "SHA256SUMS.txt" in code and "wastewise_yolo26s_v7_artifacts.zip" in code


def test_artifact_packaging_uses_runtime_yaml_and_keeps_unique_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = make_dataset(tmp_path / "dataset")
    runtime_yaml = final_train.prepare_runtime_data(data_root, tmp_path / "working")
    working = tmp_path / "working"
    monkeypatch.setattr(final_train, "WORKING_ROOT", working)
    (working / "dataset_audit.json").write_text("{}", encoding="utf-8")
    run = working / "wastewise_runs" / "run1"
    (run / "weights").mkdir(parents=True)
    best, last = run / "weights" / "best.pt", run / "weights" / "last.pt"
    best.write_bytes(b"best-checkpoint")
    last.write_bytes(b"last-checkpoint")
    results = run / "results.csv"
    results.write_text("epoch\n0\n", encoding="utf-8")

    calls = []

    class FakeYOLO:
        names = dict(enumerate(CLASSES))

        def __init__(self, _checkpoint: str):
            pass

        def val(self, **kwargs):
            calls.append(kwargs)
            val_dir = Path(kwargs["project"]) / kwargs["name"]
            val_dir.mkdir(parents=True)
            (val_dir / "PR_curve.png").write_bytes(b"plot")
            return SimpleNamespace(box=SimpleNamespace(
                p=[0.5] * 6, r=[0.5] * 6, ap50=[0.5] * 6,
                ap=[np.full(10, 0.25) for _ in range(6)],
            ))

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYOLO))
    final_train.validate_and_package(data_root, runtime_yaml, best, last, results, run, [0], [], 8)
    assert calls[0]["data"] == str(runtime_yaml)

    archive_path = working / "wastewise_artifacts" / "wastewise_yolo26s_v7_artifacts.zip"
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert "run/weights/best.pt" in names
        assert "run/weights/last.pt" in names
        assert "validation/run1_validation/PR_curve.png" in names
        assert len(names) == len(set(names))
        manifest = json.loads(archive.read("run/model_manifest.json"))
        assert manifest["class_map"][0]["name"] == "plastic"
        assert manifest["checkpoint_sha256"] == hashlib.sha256(best.read_bytes()).hexdigest()
    expected_sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    sums = (working / "wastewise_artifacts" / "SHA256SUMS.txt").read_text(encoding="utf-8")
    assert sums.startswith(expected_sha)
