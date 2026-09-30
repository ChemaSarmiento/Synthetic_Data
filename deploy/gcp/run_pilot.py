"""Bounded Cloud Run pilot; metadata credentials, create-only GCS objects."""
import json
import hashlib
import base64
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from synthetic_engine.config import Config
from synthetic_engine.engine import generate


def token():
    request = Request("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
                      headers={"Metadata-Flavor": "Google"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def upload(bucket, name, path):
    if path.stat().st_size > 64 * 1024**2:
        raise ValueError("Pilot uploader limits individual files to 64 MiB")
    query = urlencode({"uploadType": "media", "name": name, "ifGenerationMatch": "0"})
    url = f"https://storage.googleapis.com/upload/storage/v1/b/{quote(bucket, safe='')}/o?{query}"
    data = path.read_bytes()
    digest = base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode()
    request = Request(url, data=data, method="POST",
                      headers={"Authorization": "Bearer " + token(), "Content-Type": "application/octet-stream"})
    with urlopen(request, timeout=120) as response:
        result = json.load(response)
    if int(result["size"]) != path.stat().st_size:
        raise ValueError("Uploaded object size differs from local artifact")
    if result.get("md5Hash") != digest:
        raise ValueError("Uploaded object checksum differs from local artifact")


def main():
    bucket = os.environ["OUTPUT_BUCKET"]
    execution = os.environ["CLOUD_RUN_EXECUTION"]
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", execution):
        raise ValueError("Invalid execution name")
    config = Config.load(Path("/app/config.json"))
    if config.rows > 1_000_000:
        raise ValueError("This memory-backed pilot is capped at 1 million rows")
    root = Path("/tmp/dataset")
    manifest = generate(config, root)
    prefix = f"pilots/{execution}"
    paths = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "manifest.json")
    # The completed manifest is the last object, serving as the publication marker.
    paths.append(root / "manifest.json")
    for path in paths:
        upload(bucket, prefix + "/" + path.relative_to(root).as_posix(), path)
    print(json.dumps({"status": "uploaded", "uri": f"gs://{bucket}/{prefix}/",
                      "rows": config.rows, "metrics": manifest["metrics"]}), flush=True)


if __name__ == "__main__":
    main()
