"""Download only TACO images with an explicit reusable license field.

Images are kept under datasets/ (gitignored). The TACO annotation JSON is
CC-BY-4.0; images retain their own recorded license and are filtered here.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, UnidentifiedImageError

ANNOTATIONS_URL = "https://raw.githubusercontent.com/pedropro/TACO/master/data/annotations.json"
ALLOWED_LICENSE = "ODBL (c) OpenLitterMap & Contributors"
IMAGE_HOSTS = {"img.tacodataset.org", "olm-s3.s3.eu-west-1.amazonaws.com"}
HF_IMAGE_BASE = "https://huggingface.co/datasets/pictograph/taco/resolve/main/train"


def get_bytes(url: str, attempts: int = 4) -> bytes:
    error = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "WasteWise-Project1/1.0"})
            with urlopen(request, timeout=60) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"Download failed after {attempts} attempts: {url}: {error}")


def download(root: Path, workers: int = 6, image_source: str = "huggingface") -> dict:
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    annotation_path = raw / "annotations.json"
    if not annotation_path.exists():
        payload = get_bytes(ANNOTATIONS_URL)
        temp = annotation_path.with_suffix(".json.part")
        temp.write_bytes(payload)
        temp.replace(annotation_path)
    annotations_sha = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    license_counts: dict[str, int] = {}
    selected = []
    rejected = 0
    for image in data["images"]:
        license_name = image.get("license")
        license_counts[str(license_name)] = license_counts.get(str(license_name), 0) + 1
        if license_name != ALLOWED_LICENSE:
            rejected += 1
            continue
        original_url = image.get("flickr_url") or image.get("flickr_640_url")
        if image_source == "huggingface":
            source_path = Path(image["file_name"])
            mirror_name = f"{source_path.parent.name}_{source_path.name}"
            url = f"{HF_IMAGE_BASE}/{mirror_name}"
        else:
            url = original_url
            if not url or not url.startswith("https://") or url.split("/", 3)[2] not in IMAGE_HOSTS:
                image["download_status"] = "blocked_untrusted_host_or_missing_url"
                continue
        selected.append((image, url))

    def fetch(row: tuple[dict, str]) -> tuple[int, str | None]:
        image, url = row
        destination = raw / image["file_name"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            try:
                with Image.open(destination) as check:
                    check.verify()
                return image["id"], None
            except (OSError, UnidentifiedImageError):
                destination.unlink()
        part = destination.with_suffix(destination.suffix + ".part")
        error = None
        for attempt in range(4):
            try:
                # Restart rather than append if an interrupted prior response
                # left bytes and the server does not support HTTP Range.
                headers = {"User-Agent": "WasteWise-Project1/1.0"}
                offset = part.stat().st_size if part.exists() else 0
                if offset:
                    headers["Range"] = f"bytes={offset}-"
                request = Request(url, headers=headers)
                with urlopen(request, timeout=90) as response:
                    append = offset > 0 and response.status == 206
                    if offset and not append:
                        offset = 0
                    mode = "ab" if append else "wb"
                    with part.open(mode) as output:
                        while block := response.read(1024 * 1024):
                            output.write(block)
                with Image.open(part) as check:
                    check.verify()
                with Image.open(part) as check:
                    raw_size = check.size
                    oriented_size = ImageOps.exif_transpose(check).size
                    expected = (int(image["width"]), int(image["height"]))
                    if raw_size != expected and oriented_size != expected:
                        raise ValueError(f"annotation/image dimensions differ: raw={raw_size}, exif={oriented_size}, annotation={expected}")
                part.replace(destination)
                return image["id"], None
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnidentifiedImageError) as exc:
                error = exc
                if isinstance(exc, HTTPError) and exc.code == 416 and part.exists():
                    # The previous attempt may have finished writing the file
                    # before interruption; accept it only after full validation.
                    try:
                        with Image.open(part) as check:
                            check.verify()
                        with Image.open(part) as check:
                            expected = (int(image["width"]), int(image["height"]))
                            if check.size == expected or ImageOps.exif_transpose(check).size == expected:
                                part.replace(destination)
                                return image["id"], None
                    except (OSError, UnidentifiedImageError):
                        pass
                    part.unlink(missing_ok=True)
                if attempt + 1 < 4:
                    time.sleep(min(2 ** attempt, 8))
        if part.exists():
            part.unlink()
        return image["id"], str(error)

    errors = []
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, row) for row in selected]
        for future in as_completed(futures):
            image_id, error = future.result()
            completed += 1
            if error:
                errors.append({"image_id": image_id, "error": error})
            if completed % 25 == 0 or completed == len(selected):
                print(f"downloaded/checked {completed}/{len(selected)}; failures={len(errors)}", flush=True)
    report = {"source": "TACO official annotations; public Pictograph mirror for image bytes" if image_source == "huggingface" else "TACO official repository",
              "image_source": image_source, "annotation_url": ANNOTATIONS_URL,
              "annotation_sha256": annotations_sha, "allowed_image_license": ALLOWED_LICENSE,
              "annotation_license": "CC BY 4.0 (TACO annotations; cite Proença & Simões, 2020)",
              "license_counts_before_filter": license_counts, "images_selected": len(selected),
              "images_downloaded_or_verified": len(selected) - len(errors),
              "images_rejected_for_license": rejected, "errors": errors}
    (root / "download_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("datasets/taco"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--image-source", choices=["huggingface", "official"], default="huggingface")
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 16:
        parser.error("--workers must be in 1..16")
    result = download(args.root, args.workers, args.image_source)
    print(json.dumps({k: v for k, v in result.items() if k != "errors"}, indent=2, ensure_ascii=False))
