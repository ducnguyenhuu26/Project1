from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.scripts.evaluate_vn_field import match_image, read_labels


def test_matching_counts_duplicate_box_and_missed_class() -> None:
    truth = [(0, (0.0, 0.0, 10.0, 10.0)), (1, (20.0, 20.0, 30.0, 30.0))]
    predictions = [(0, 0.9, (0.0, 0.0, 10.0, 10.0)),
                   (0, 0.8, (0.0, 0.0, 10.0, 10.0)),
                   (2, 0.7, (20.0, 20.0, 30.0, 30.0))]
    counts = match_image(predictions, truth, 0.5)
    assert counts[0] == {"tp": 1, "fp": 1, "fn": 0}
    assert counts[1] == {"tp": 0, "fp": 0, "fn": 1}
    assert counts[2] == {"tp": 0, "fp": 1, "fn": 0}


def test_negative_image_requires_explicit_empty_label(tmp_path: Path) -> None:
    label = tmp_path / "negative.txt"
    with pytest.raises(ValueError, match="Missing label file"):
        read_labels(label, 100, 100)
    label.touch()
    assert read_labels(label, 100, 100) == []
    label.write_text("0 0.5 0.5 0.2 0.4", encoding="utf-8")
    assert read_labels(label, 100, 100) == [(0, (40.0, 30.0, 60.0, 70.0))]
