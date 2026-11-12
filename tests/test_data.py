import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "ml" / "scripts"))
from audit_dataset import family
from prepare_clean_split import clean_box


def test_family_normalization():
    assert family("bottle_jpg.rf.0123456789abcdef_aug1") == family("bottle_jpg.rf.fedcba9876543210_aug0")


def test_box_clipping_preserves_positive_region():
    fixed, change = clean_box("2 0.541015625 0.5026041666666666 0.59765625 1")
    assert change == "clipped"
    _, x, y, w, h = fixed.split()
    assert float(y) + float(h)/2 <= 1.00000001
    assert clean_box("5 .5 .5 .2 .2")[0] is None
