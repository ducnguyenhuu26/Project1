"""Small, deterministic visual fingerprint for SWiM3 leakage checks."""
from pathlib import Path
import numpy as np

from PIL import Image, ImageOps

_PHASH_SIZE = 32
_PHASH_COS = np.cos(
    np.pi / _PHASH_SIZE
    * (np.arange(_PHASH_SIZE, dtype=np.float32) + 0.5)[:, None]
    * np.arange(_PHASH_SIZE, dtype=np.float32)[None, :]
)


def dhash(path: Path) -> int:
    with Image.open(path) as source:
        return dhash_image(source)


def dhash_image(source: Image.Image, exif_transpose: bool = True) -> int:
    oriented = ImageOps.exif_transpose(source) if exif_transpose else source
    image = oriented.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = np.asarray(image, dtype=np.uint8)
    bits = np.packbits(pixels[:, :-1] > pixels[:, 1:], axis=1, bitorder="little")[:, 0]
    return sum(int(value) << (row * 8) for row, value in enumerate(bits))


def distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def phash_image(image: Image.Image, exif_transpose: bool = True) -> int:
    """64-bit low-frequency DCT hash; less sensitive than dHash to a shared flat background."""
    oriented = ImageOps.exif_transpose(image) if exif_transpose else image
    pixels = np.asarray(
        oriented.convert("L").resize((_PHASH_SIZE, _PHASH_SIZE), Image.Resampling.LANCZOS),
        dtype=np.float32,
    )
    # The basis is constant; precomputing it preserves the original DCT/hash
    # while avoiding two 32x32 cosine allocations for every foreground crop.
    dct = _PHASH_COS.T @ pixels @ _PHASH_COS
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
