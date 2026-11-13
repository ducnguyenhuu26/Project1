"""Small, deterministic visual fingerprint for SWiM3 leakage checks."""
from pathlib import Path
import numpy as np

from PIL import Image, ImageOps


def dhash(path: Path) -> int:
    with Image.open(path) as source:
        return dhash_image(source)


def dhash_image(source: Image.Image) -> int:
    image = ImageOps.exif_transpose(source).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    return sum((image.getpixel((x, y)) > image.getpixel((x + 1, y))) << (y * 8 + x)
               for y in range(8) for x in range(8))


def distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def phash_image(image: Image.Image) -> int:
    """64-bit low-frequency DCT hash; less sensitive than dHash to a shared flat background."""
    pixels = np.asarray(ImageOps.exif_transpose(image).convert("L").resize((32, 32, ), Image.Resampling.LANCZOS), dtype=np.float32)
    n = 32
    cos = np.cos(np.pi / n * (np.arange(n, dtype=np.float32) + 0.5)[:, None] * np.arange(n, dtype=np.float32)[None, :])
    dct = cos.T @ pixels @ cos
    low = dct[:8, :8].reshape(-1)[1:]
    median = float(np.median(low))
    bits = low > median
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def phash(path: Path) -> int:
    with Image.open(path) as source:
        return phash_image(source)
