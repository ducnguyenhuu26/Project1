"""Download the public, CC BY 4.0 KNR-PET-7 archive with resume and SHA-256 verification."""
import hashlib
from pathlib import Path
import time

import requests

URL = "https://data.mendeley.com/public-files/datasets/5x9bzrk9ch/files/e6f2494c-d5d4-456b-9401-964511d52da6/file_downloaded"
SHA256 = "46dc8bbb3643d56bc4a8930137df23cfacb1c0c5607b86272052e19783dafbd3"
SIZE = 3_274_375_338


def download(root: Path, retries: int = 5) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / "KNR-PET-7_dataset_v2.rar"
    partial = target.with_suffix(target.suffix + ".part")
    session = requests.Session()
    for attempt in range(retries):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            response = session.get(URL, headers=headers, stream=True, timeout=(30, 120))
            response.raise_for_status()
            if offset and response.status_code != 206:
                partial.unlink(missing_ok=True)
                offset = 0
                response.close()
                continue
            mode = "ab" if offset else "wb"
            with response, partial.open(mode) as out:
                for block in response.iter_content(4 * 1024 * 1024):
                    if block:
                        out.write(block)
            size = partial.stat().st_size
            if size != SIZE:
                raise IOError(f"Archive size mismatch: {size} != {SIZE}")
            digest = hashlib.sha256()
            with partial.open("rb") as archive:
                for block in iter(lambda: archive.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != SHA256:
                partial.unlink(missing_ok=True)
                raise IOError(f"Archive SHA-256 mismatch: {digest.hexdigest()}")
            partial.replace(target)
            return target
        except (requests.RequestException, OSError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f"Download failed after {retries} attempts: {exc}") from exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError("Download did not finish")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets/knr_pet7/raw"))
    args = parser.parse_args()
    path = download(args.root)
    print(f"Verified {path} ({path.stat().st_size} bytes, SHA-256 {SHA256})")
