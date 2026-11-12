"""Small, deterministic visual fingerprint for SWiM3 leakage checks."""
from pathlib import Path

from PIL import Image, ImageOps


def dhash(path: Path) -> int:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        return sum((image.getpixel((x, y)) > image.getpixel((x + 1, y))) << (y * 8 + x)
                   for y in range(8) for x in range(8))


def distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()
