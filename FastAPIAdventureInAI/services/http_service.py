"""Shared HTTP helpers and HTML utilities used by extractors.

Provides generic `fetch_html` and `_fetch_url` helpers and `_strip_html` so
all extractor services use the same network code and consistent logging tag.
"""
from typing import Optional, Dict
import asyncio
import re
import html as _html
from urllib import request


def _strip_html(text: str) -> str:
    # very small sanitizer for basic tags
    text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.S | re.I)
    # Replace tags with a space to avoid concatenating adjacent text fragments
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    # Decode HTML entities (e.g. &amp;, &#39;)
    try:
        text = _html.unescape(text)
    except Exception:
        pass
    return text


async def _fetch_url(url: str) -> Optional[str]:
    def _get():
        try:
            req = request.Request(url, headers={"User-Agent": "FastAPIAdventureInAI/1.0"})
            print(f"[http_service] _fetch_url: fetching {url}")
            with request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                print(f"[http_service] _fetch_url: received {len(data)} bytes")
            return data.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[http_service] _fetch_url: failed to fetch {url}: {e}")
            return None

    return await asyncio.to_thread(_get)


async def fetch_html(url: str) -> Optional[dict]:
    """Fetch raw HTML and return a dict with keys: html, status, headers.

    Returns None on failure.
    """
    def _get():
        try:
            req = request.Request(url, headers={"User-Agent": "FastAPIAdventureInAI/1.0"})
            print(f"[http_service] fetch_html: fetching {url}")
            with request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                html = data.decode("utf-8", errors="ignore")
                status = resp.getcode()
                try:
                    headers = dict(resp.getheaders())
                except Exception:
                    headers = {}
                print(f"[http_service] fetch_html: received {len(data)} bytes status={status}")
                return {"html": html, "status": status, "headers": headers}
        except Exception as e:
            print(f"[http_service] fetch_html: failed to fetch {url}: {e}")
            return None

    return await asyncio.to_thread(_get)
