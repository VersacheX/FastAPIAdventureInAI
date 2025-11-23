"""Wikipedia content fetcher.

Provides a small async helper to retrieve excerpts from Wikipedia pages.
It prefers using the official Wikipedia REST API when a URL is recognized
as a wikipedia.org link. For non-wikipedia URLs it falls back to a best-effort
text extraction using a simple HTTP GET and naive HTML stripping.

The implementation uses blocking stdlib HTTP calls wrapped with
`asyncio.to_thread` to avoid extra runtime dependencies.
"""
from typing import Optional
import asyncio
import re
from urllib import parse, request

WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKI_QUERY_API = "https://en.wikipedia.org/w/api.php"

# Minimum extract length (characters) before we consider it "too short" and try a longer API
MIN_EXTRACT_CHARS = 250
MAX_RETURN_CHARS = 2000


def _strip_html(text: str) -> str:
    # very small sanitizer for basic tags
    text = re.sub(r"<script.*?>.*?</script>", "", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def _fetch_url(url: str) -> Optional[str]:
    def _get():
        try:
            req = request.Request(url, headers={"User-Agent": "FastAPIAdventureInAI/1.0"})
            print(f"[wikipedia_service] _fetch_url: fetching {url}")
            with request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                print(f"[wikipedia_service] _fetch_url: received {len(data)} bytes")
                return data.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[wikipedia_service] _fetch_url: failed to fetch {url}: {e}")
            return None

    return await asyncio.to_thread(_get)


async def _fetch_query_extract(title: str) -> Optional[str]:
    """Attempt to fetch a longer plaintext extract using the MediaWiki action=query API."""
    qs = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "titles": title,
        "explaintext": 1,
        "exintro": 0,
        "redirects": 1,
    }
    url = WIKI_QUERY_API + "?" + parse.urlencode(qs)
    print(f"[wikipedia_service] _fetch_query_extract: calling {url}")

    def _get():
        try:
            req = request.Request(url, headers={"User-Agent": "FastAPIAdventureInAI/1.0"})
            with request.urlopen(req, timeout=10) as resp:
                import json

                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            print(f"[wikipedia_service] _fetch_query_extract: request failed: {e}")
            return None

    payload = await asyncio.to_thread(_get)
    if not isinstance(payload, dict):
        return None
    try:
        pages = payload.get("query", {}).get("pages", {})
        if not isinstance(pages, dict):
            return None
        # pages is a dict keyed by pageid
        for pid, page in pages.items():
            extract = page.get("extract")
            if extract:
                print(f"[wikipedia_service] _fetch_query_extract: got extract length={len(extract)} for pageid={pid}")
                return extract.strip()
    except Exception as e:
        print(f"[wikipedia_service] _fetch_query_extract: parse failed: {e}")
        return None


async def fetch_wikipedia_excerpt(url: str) -> Optional[str]:
    """Return a concise excerpt given a wikipedia or general url.

    If the url is a wikipedia page, use the REST summary endpoint to get a
    clean extract. If that extract is short, try the MediaWiki `action=query`
    extracts API to retrieve more content. Otherwise, for non-wikipedia URLs
    fetch the page and return the first chunk of visible text.

    Returns None on failure.
    """
    if not url:
        print("[wikipedia_service] fetch_wikipedia_excerpt: no url provided")
        return None

    parsed = parse.urlparse(url)
    hostname = parsed.hostname or ""
    print(f"[wikipedia_service] fetch_wikipedia_excerpt: parsed url hostname={hostname} path={parsed.path}")
    try:
        if hostname.endswith("wikipedia.org"):
            # extract the page title from path or query
            title = parsed.path.rsplit("/", 1)[-1]
            title = parse.unquote(title)
            print(f"[wikipedia_service] fetch_wikipedia_excerpt: extracted title='{title}'")
            if not title:
                # try query param 'title'
                qs = parse.parse_qs(parsed.query)
                title = qs.get("title", [""])[0]
                print(f"[wikipedia_service] fetch_wikipedia_excerpt: title from query='{title}'")
            if not title:
                print("[wikipedia_service] fetch_wikipedia_excerpt: could not determine title")
                return None

            # Use the REST summary API; ensure we include a User-Agent to avoid being blocked
            api_url = WIKI_REST + parse.quote(title)
            print(f"[wikipedia_service] fetch_wikipedia_excerpt: calling REST API {api_url}")

            def _get_json():
                req = request.Request(api_url, headers={"User-Agent": "FastAPIAdventureInAI/1.0"})
                with request.urlopen(req, timeout=8) as resp:
                    import json

                    return json.loads(resp.read().decode("utf-8", errors="ignore"))

            try:
                payload = await asyncio.to_thread(_get_json)
            except Exception as e:
                print(f"[wikipedia_service] fetch_wikipedia_excerpt: REST fetch failed: {e}")
                payload = None

            print(f"[wikipedia_service] fetch_wikipedia_excerpt: payload type={type(payload)}")
            if isinstance(payload, dict):
                # prefer 'extract', fall back to 'extract_html'
                extract = payload.get("extract")
                if extract:
                    print(f"[wikipedia_service] fetch_wikipedia_excerpt: got 'extract' from REST API len={len(extract)}")
                    # If the extract is short, try the query API for a longer extract
                    if len(extract) < MIN_EXTRACT_CHARS:
                        print("[wikipedia_service] fetch_wikipedia_excerpt: extract short, trying query API for longer extract")
                        longer = await _fetch_query_extract(title)
                        if longer and len(longer) > len(extract):
                            print(f"[wikipedia_service] fetch_wikipedia_excerpt: using longer extract length={len(longer)}")
                            return longer[:MAX_RETURN_CHARS].strip()
                    return extract.strip()[:MAX_RETURN_CHARS]
                extract_html = payload.get("extract_html")
                if extract_html:
                    print("[wikipedia_service] fetch_wikipedia_excerpt: got 'extract_html' from REST API; stripping HTML")
                    # strip html tags and return
                    text = _strip_html(extract_html)
                    if len(text) < MIN_EXTRACT_CHARS:
                        # try query API
                        longer = await _fetch_query_extract(title)
                        if longer and len(longer) > len(text):
                            return longer[:MAX_RETURN_CHARS].strip()
                    return text[:MAX_RETURN_CHARS].strip()
                print("[wikipedia_service] fetch_wikipedia_excerpt: REST payload had no extract fields; trying query API")
                longer = await _fetch_query_extract(title)
                if longer:
                    return longer[:MAX_RETURN_CHARS].strip()
                return None
        else:
            # fallback: fetch page and strip HTML
            html = await _fetch_url(url)
            if not html:
                print(f"[wikipedia_service] fetch_wikipedia_excerpt: fallback fetch returned no html for {url}")
                return None
            text = _strip_html(html)
            if not text:
                print(f"[wikipedia_service] fetch_wikipedia_excerpt: strip_html produced no text for {url}")
                return None
            print(f"[wikipedia_service] fetch_wikipedia_excerpt: returning fallback text length={len(text)}")
            return text[:MAX_RETURN_CHARS].strip()
    except Exception as e:
        print(f"[wikipedia_service] fetch_wikipedia_excerpt: exception: {e}")
        return None
