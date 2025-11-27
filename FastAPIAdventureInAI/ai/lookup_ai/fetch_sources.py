"""Fetch and run extractors for a list of URLs.

Provides `fetch_and_extract(urls)` which runs the extractor for each URL in
parallel and returns a list of tuples (url, weight, result) where result is
either a dict returned by the extractor or an Exception.
"""
from typing import List, Tuple, Any
import asyncio
from urllib import parse

from ai.lookup_ai.services.extractor_factory import get_extractor_for_url


async def fetch_and_extract(urls: List[str], priority_weights: dict) -> List[Tuple[str, int, Any]]:
    tasks = []
    metas = []
    for u in urls:
        extractor = get_extractor_for_url(u)
        hostname = parse.urlparse(u).hostname or ""
        weight = 1
        for d, w in priority_weights.items():
            if hostname.endswith(d):
                weight = w
                break
        tasks.append(extractor(u))
        metas.append((u, weight))

    raw = await asyncio.gather(*tasks, return_exceptions=True)
    results = []
    for (u, weight), r in zip(metas, raw):
        results.append((u, weight, r))
    return results
