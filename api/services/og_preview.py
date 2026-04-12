"""OpenGraph preview service — extract og:title, og:description, og:image from URLs."""

from typing import Optional

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel


class OGPreview(BaseModel):
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    site_name: Optional[str] = None
    og_type: Optional[str] = None
    favicon: Optional[str] = None


_HEADERS = {
    "User-Agent": "ContentFlow-Preview/1.0 (bot; +https://contentflow.com)",
    "Accept": "text/html",
}
_TIMEOUT = 8.0


async def fetch_og_preview(url: str) -> OGPreview:
    """Fetch a URL and extract OpenGraph metadata with fallbacks.

    Falls back to <title> and <meta name="description"> when OG tags are missing.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_HEADERS)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    def og(prop: str) -> Optional[str]:
        tag = soup.find("meta", property=f"og:{prop}")
        return tag["content"].strip() if tag and tag.get("content") else None

    def meta_name(name: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"name": name})
        return tag["content"].strip() if tag and tag.get("content") else None

    title = og("title") or (soup.title.string.strip() if soup.title and soup.title.string else None)
    description = og("description") or meta_name("description")

    # Resolve relative image URLs
    image = og("image")
    if image and not image.startswith(("http://", "https://")):
        from urllib.parse import urljoin
        image = urljoin(url, image)

    # Favicon: look for <link rel="icon">
    favicon = None
    icon_link = soup.find("link", rel=lambda v: v and "icon" in v)
    if icon_link and icon_link.get("href"):
        favicon = icon_link["href"]
        if not favicon.startswith(("http://", "https://")):
            from urllib.parse import urljoin
            favicon = urljoin(url, favicon)

    return OGPreview(
        url=url,
        title=title,
        description=description,
        image=image,
        site_name=og("site_name"),
        og_type=og("type"),
        favicon=favicon,
    )
