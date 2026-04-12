"""Upload files to Bunny CDN storage"""

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Bunny Storage Zone API base
BUNNY_STORAGE_BASE = "https://storage.bunnycdn.com"
# Default storage zone name — same as the one used by the image robot
STORAGE_ZONE = "contentflow"


def upload_to_bunny(
    file_path: str,
    cdn_path: str,
    storage_key: str,
    cdn_hostname: str,
) -> str:
    """
    Upload a file to Bunny CDN storage.

    Args:
        file_path: Local path to the file
        cdn_path: Remote path within the storage zone (e.g. "reels/ABC123/video.mp4")
        storage_key: Bunny Storage API key
        cdn_hostname: Bunny CDN pull zone hostname (e.g. "my-zone.b-cdn.net")

    Returns:
        CDN URL of the uploaded file
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    url = f"{BUNNY_STORAGE_BASE}/{STORAGE_ZONE}/{cdn_path}"

    with open(file_path, "rb") as f:
        response = requests.put(
            url,
            data=f,
            headers={
                "AccessKey": storage_key,
                "Content-Type": "application/octet-stream",
            },
            timeout=300,
        )

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Bunny upload failed ({response.status_code}): {response.text}"
        )

    cdn_url = f"https://{cdn_hostname}/{cdn_path}"
    logger.info(f"Uploaded to Bunny CDN: {cdn_url}")
    return cdn_url
