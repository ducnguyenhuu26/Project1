import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "ml" / "scripts" / "merge_knr_pet7.py"
SPEC = importlib.util.spec_from_file_location("merge_knr_pet7", SCRIPT)
MERGER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MERGER)


def test_obb_converts_to_enclosing_yolo_detection_box():
    class_id, converted, provenance = MERGER.convert_obb_line(
        "6 0.1 0.2 0.3 0.2 0.3 0.8 0.1 0.8", 1, Path("sample.txt"))
    assert class_id == 6
    assert converted == "0 0.20000000 0.50000000 0.20000000 0.60000000"
    assert provenance["source_class"] == "B6"
    assert "OBB" in provenance["transform"]


@pytest.mark.parametrize("line", [
    "7 0.1 0.2 0.3 0.2 0.3 0.8 0.1 0.8",
    "6 0.1 0.2 0.3 0.2 0.3 1.2 0.1 0.8",
    "6 0.1 0.2 0.3",
])
def test_rejects_invalid_source_class_or_box(line):
    with pytest.raises(ValueError):
        MERGER.convert_obb_line(line, 1, Path("sample.txt"))


def test_exact_duplicate_box_union_and_class_conflict_policy():
    same = ("0 0.5 0.5 0.4 0.4",)
    merged, iou = MERGER.merge_duplicate_boxes(same, same)
    assert [float(value) for value in merged[0].split()] == pytest.approx([0, 0.5, 0.5, 0.4, 0.4])
    assert iou == pytest.approx(1.0)

    jittered, iou = MERGER.merge_duplicate_boxes(
        ("0 0.5 0.5 0.4 0.4",), ("0 0.5 0.5 0.42 0.42",))
    assert jittered is not None
    assert iou >= 0.85
    assert float(jittered[0].split()[3]) == pytest.approx(0.42)

    conflict, _ = MERGER.merge_duplicate_boxes(
        ("0 0.5 0.5 0.4 0.4",), ("1 0.5 0.5 0.4 0.4",))
    assert conflict is None


@pytest.mark.parametrize("stem,class_id", [
    ("B1_000001", 0), ("B21_000001", 1), ("B22_000001", 2),
    ("B3_000001", 3), ("B4_000001", 4), ("B5_000001", 5), ("B6_000001", 6),
])
def test_filename_class_code_mapping(stem, class_id):
    assert MERGER.pet_filename_class(stem) == class_id
