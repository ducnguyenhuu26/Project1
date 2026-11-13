"""Download the CC BY 4.0 Roboflow-hosted garbage object detection splits."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import time

import requests


BASE = "https://huggingface.co/datasets/keremberke/garbage-object-detection/resolve/main/data"
FILES = {
    "train.zip": (137_708_705, "9b69a508febe33f1b317bb288c768e87ec129598112451c2e8ee40ba3797d17e"),
    "valid.zip": (38_312_703, "1d9dbe38f5d291ccd33ee6981c12fe003aea37c0b2a43382ad2a7c492a09c3eb"),
    "test.zip": (19_639_153, "31e66c695f3e5a32891a18a60231dfcbf80087af9c7671ac68a260360584b0ab"),
}


def download_one(root: Path, name: str, retries: int = 5) -> Path:
    size, sha256 = FILES[name]
    root.mkdir(parents=True, exist_ok=True)
    target = root / name
    partial = target.with_suffix(target.suffix + ".part")
    url = f"{BASE}/{name}?download=true"
    for attempt in range(retries):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(30, 120)) as response:
                if offset and response.status_code != 206:
                    partial.unlink(missing_ok=True)
                    continue
                response.raise_for_status()
                with partial.open("ab" if offset else "wb") as output:
                    for chunk in response.iter_content(2 * 1024 * 1024):
                        if chunk:
                            output.write(chunk)
            if partial.stat().st_size != size:
                raise IOError(f"{name} size mismatch: {partial.stat().st_size} != {size}")
            digest = hashlib.sha256()
            with partial.open("rb") as data:
                for chunk in iter(lambda: data.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != sha256:
                partial.unlink(missing_ok=True)
                raise IOError(f"{name} SHA-256 mismatch: {digest.hexdigest()}")
            partial.replace(target)
            return target
        except (requests.RequestException, OSError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f"{name} failed after {retries} attempts: {exc}") from exc
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"{name} download did not finish")


def download(root: Path) -> list[Path]:
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(download_one, root, name): name for name in FILES}
        for future in as_completed(futures):
            path = future.result()
            print(f"Verified {path.name}: {path.stat().st_size} bytes", flush=True)
            results.append(path)
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets/garbage_detection_hf/raw"))
    args = parser.parse_args()
    download(args.root)
