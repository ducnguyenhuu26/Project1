"""Resumably download the public RiverPlasticDataset Zenodo release and verify its MD5."""
import argparse
import hashlib
from pathlib import Path
import time

import requests

URL = "https://zenodo.org/api/records/20811562/files/KhimCathleenSaddi/RiverPlasticDataset-v1.0.1.zip/content"
SIZE = 680_388_727
MD5 = "403759b09e095b2d8173c08dabed81b5"


def download(root: Path, retries: int = 5) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / "RiverPlasticDataset-v1.0.1.zip"
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
                response.close()
                continue
            with response, partial.open("ab" if offset else "wb") as out:
                for block in response.iter_content(4 * 1024 * 1024):
                    if block:
                        out.write(block)
            if partial.stat().st_size != SIZE:
                raise OSError(f"Size mismatch: {partial.stat().st_size} != {SIZE}")
            digest = hashlib.md5()
            with partial.open("rb") as archive:
                for block in iter(lambda: archive.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != MD5:
                partial.unlink(missing_ok=True)
                raise OSError(f"MD5 mismatch: {digest.hexdigest()}")
            partial.replace(target)
            return target
        except (requests.RequestException, OSError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f"Download failed after {retries} attempts: {exc}") from exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError("Download did not finish")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets/riverplastic/raw"))
    args = parser.parse_args()
    path = download(args.root)
    print(f"Verified {path} ({path.stat().st_size} bytes, MD5 {MD5})")
