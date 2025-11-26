"""Simple HTML storage helper.

Saves raw HTML payloads to disk organized by domain so large pages don't
flood logs/terminals. Call `save_html(domain, url, html, headers=None)` to
persist the content. Returns the absolute path of the saved file.

Files are stored under: C:\temp\site_html_dump\<domain>.html
(Overwrites per-domain file each time, as requested.)
"""
from pathlib import Path
import os
import time
import hashlib
import urllib.parse
from typing import Optional, Dict
import json
import re

# Base directory for saved HTML (Windows temp as requested)
BASE_DIR = Path("C:/temp/site_html_dump")

# ensure base dir exists
os.makedirs(BASE_DIR, exist_ok=True)

# safe-domain sanitizer
re_safe = re.compile(r"[^a-z0-9.-]")


def _safe_domain(domain: str) -> str:
    if not domain:
        return "unknown"
    # keep only safe characters
    return re_safe.sub("-", domain.lower())


def _safe_filename_from_url(url: str) -> str:
    # use SHA1 of the URL to avoid filesystem problems and collisions if needed
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()
    # include a short, URL-quoted path fragment for readability
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip("/ ") or "root"
    path_snip = urllib.parse.quote_plus(path)[:40]
    ts = int(time.time())
    return f"{ts}_{path_snip}_{h}.html"


def save_html(domain: str, url: str, html: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Persist HTML to disk and return the file path (str) or None on error.

    This implementation writes one file per domain (overwriting previous),
    so saved files represent the latest dump for each domain. The file
    contains a JSON header (inside an HTML comment) with metadata.
    """
    try:
        dom = _safe_domain(domain)
        outdir = BASE_DIR
        outdir.mkdir(parents=True, exist_ok=True)
        # single file per domain (overwrite allowed)
        fname = f"{dom}.html"
        path = outdir / fname
        # write headers and html to the file (headers as commented JSON at top)
        with open(path, "w", encoding="utf-8", errors="ignore") as f:
            meta = {
                "domain": domain,
                "url": url,
                "saved_at": int(time.time()),
            }
            if headers:
                meta["response_headers"] = headers
            try:
                f.write("<!-- METADATA:\n")
                f.write(json.dumps(meta, ensure_ascii=False, indent=2))
                f.write("\n-->\n\n")
            except Exception:
                # fallback: write minimal metadata
                try:
                    f.write(f"<!-- METADATA: domain={domain} url={url} saved_at={meta['saved_at']} -->\n\n")
                except Exception:
                    pass
            f.write(html)
        # return absolute path as string
        return str(path.resolve())
    except Exception as e:
        # do not print large HTML to terminal; log minimal error
        print(f"[html_store] save_html failed: {e}")
        return None


def get_latest_for_domain(domain: str) -> Optional[str]:
    """Return the saved HTML file path for a domain or None."""
    dom = _safe_domain(domain)
    path = BASE_DIR / f"{dom}.html"
    if not path.exists():
        return None
    return str(path.resolve())
