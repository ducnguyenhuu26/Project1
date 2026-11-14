"""Go/no-go API probe using a representative real image and ROI."""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def get_json(url: str, *, data: bytes | None = None, content_type: str | None = None) -> dict:
    headers = {"Content-Type": content_type} if content_type else {}
    request = Request(url, data=data, headers=headers)
    try:
        with urlopen(request, timeout=90) as response:
            return json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"{url}: HTTP {exc.code}: {exc.read(500)!r}") from exc
    except URLError as exc:
        raise RuntimeError(f"{url}: {exc.reason}") from exc


def multipart(image: Path, fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"soicterra-{uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{image.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
    body.extend(image.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def check_scan(result: dict, name: str) -> None:
    assert result.get("mode") == "real", f"{name}: demo response"
    detections = result.get("detections")
    assert isinstance(detections, list) and detections, f"{name}: no detections in representative image"
    assert any(row.get("origin") == "ai" and row.get("category_id") for row in detections), f"{name}: no classified AI detection"
    print(f"{name}: {len(detections)} detection(s), model={result.get('model_version')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Backend HTTPS origin or local http://127.0.0.1:8000")
    parser.add_argument("--image", type=Path, required=True, help="Representative JPEG/PNG/WebP with a supported object")
    parser.add_argument("--roi", required=True, nargs=4, type=float, metavar=("X1", "Y1", "X2", "Y2"), help="Object-containing ROI in original image pixels")
    parser.add_argument("--min-catalog-count", type=int, default=1)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error("Image does not exist")
    base = args.base_url.rstrip("/")
    health = get_json(base + "/api/v1/health")
    assert health.get("mode") == "real" and health.get("model_status") == "ready", f"Health indicates no real model: {health}"
    ready = get_json(base + "/api/v1/ready")
    assert ready.get("status") == "ready" and ready.get("mode") == "real", f"Not ready: {ready}"
    catalog = get_json(base + "/api/v1/recommendations/catalog?limit=1")
    assert catalog.get("total_count", 0) >= args.min_catalog_count, f"Catalog count too low: {catalog.get('total_count')}"
    print(f"Real model ready; catalog total={catalog['total_count']}")
    body, content_type = multipart(args.image, {})
    check_scan(get_json(base + "/api/v1/scans", data=body, content_type=content_type), "Scan")
    fields = dict(zip(("x1", "y1", "x2", "y2"), (str(value) for value in args.roi)))
    body, content_type = multipart(args.image, fields)
    check_scan(get_json(base + "/api/v1/scans/region", data=body, content_type=content_type), "ROI scan")
    print("GO: API smoke checks passed")


if __name__ == "__main__":
    main()
