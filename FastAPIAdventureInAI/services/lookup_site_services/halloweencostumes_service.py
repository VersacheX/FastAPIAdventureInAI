"""Extractor for halloweencostumes.com product pages.

Returns a dict with keys: 'html', 'text', 'data'.
"""
from typing import Optional, Dict, Any, List
import re
import json
from urllib import parse
from services.http_service import fetch_html, _strip_html


async def extract_halloweencostumes(url: str) -> Optional[Dict[str, Any]]:
    """Extract product info from a HalloweenCostumes product page.

    Returns a dict: { 'html': raw_html, 'text': summary, 'data': structured }
    """
    try:
        payload = await fetch_html(url)
        if not payload:
            return None
        html = payload.get("html")
        if not html:
            return None

        # Title
        title = None
        m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.I)
        if not m:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()

        # Price
        price = None
        m = re.search(
            r'<meta\s+property="product:price:amount"\s+content="([^"]+)"', html, re.I
        )
        if m:
            price = m.group(1).strip()
        else:
            m = re.search(r'([\$]\s?\d[\d,]*\.?\d{0,2})', html)
            if m:
                price = m.group(1).strip()

        # Availability
        availability = None
        m = re.search(
            r'<meta\s+property="product:availability"\s+content="([^"]+)"', html, re.I
        )
        if m:
            availability = m.group(1).strip()

        # Images
        images: List[str] = []
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
        if m:
            images.append(m.group(1).strip())
        for match in re.finditer(r'data-url=[\'"]([^\'"]+)[\'"]', html, re.I):
            images.append(match.group(1).strip())
        for match in re.finditer(r'<img[^>]+src=[\'"]([^\'"]+)[\'"]', html, re.I):
            src = match.group(1).strip()
            if src:
                images.append(src)
        # dedupe preserving order
        seen = set()
        uniq_images: List[str] = []
        for i in images:
            if i and i not in seen:
                seen.add(i)
                uniq_images.append(i)

        # SKU
        sku = None
        m = re.search(r'Item\s*#\s*([A-Z0-9-]+)', html, re.I)
        if m:
            sku = m.group(1).strip()

        # JSON-LD parsing (best-effort)
        jsonld_objs: List[Any] = []
        for jl in re.finditer(
            r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>',
            html,
            re.I | re.S,
        ):
            txt = jl.group(1).strip()
            try:
                parsed = json.loads(txt)
                jsonld_objs.append(parsed)
            except Exception:
                # ignore malformed JSON-LD
                continue

        # Description
        description = None
        m = re.search(
            r'<div[^>]+class="col-lg description"[^>]*>(.*?)</div>', html, re.I | re.S
        )
        if m:
            description = _strip_html(m.group(1))
        else:
            for obj in jsonld_objs:
                if isinstance(obj, dict):
                    desc = obj.get("description") or (obj.get("mainEntity") or {}).get(
                        "description"
                    )
                    if desc:
                        description = desc
                        break
        if not description:
            body = _strip_html(html)
            description = body if body else None

        # Ratings/reviews
        avg_rating = None
        review_count = None
        reviews: List[Dict[str, Any]] = []
        for obj in jsonld_objs:
            if isinstance(obj, dict):
                agg = obj.get("aggregateRating")
                if isinstance(agg, dict):
                    avg_rating = agg.get("ratingValue") or avg_rating
                    review_count = agg.get("reviewCount") or review_count
                rv = obj.get("review")
                if isinstance(rv, list):
                    for r in rv:
                        if isinstance(r, dict):
                            author = None
                            if isinstance(r.get("author"), dict):
                                author = r.get("author").get("name")
                            else:
                                author = r.get("author")
                            rating = None
                            if isinstance(r.get("reviewRating"), dict):
                                rating = r.get("reviewRating").get("ratingValue")
                            reviews.append(
                                {
                                    "author": author,
                                    "rating": rating,
                                    "body": r.get("reviewBody"),
                                }
                            )

        # Build summary and data
        parts: List[str] = []
        if title:
            parts.append(f"Title: {title}")
        if sku:
            parts.append(f"SKU/Item#: {sku}")
        if price:
            parts.append(f"Price: {price}")
        if availability:
            parts.append(f"Availability: {availability}")
        if uniq_images:
            parts.append(f"Images: {len(uniq_images)} found")
        if description:
            # keep a short preview for summary
            parts.append(f"DescriptionPreview: {description[:800]}")
        if avg_rating or review_count:
            parts.append(
                f"Rating: {avg_rating or 'N/A'} ({review_count or '0'} reviews)"
            )

        summary = "\n".join(parts)

        data: Dict[str, Any] = {
            "title": title,
            "sku": sku,
            "price": price,
            "availability": availability,
            "images": uniq_images,
            "description": description,
            "avg_rating": avg_rating,
            "review_count": review_count,
            "reviews": reviews,
        }

        # Prefer returning the full cleaned description as top-level text when available
        text_value = description if description else summary

        return {"html": html, "text": text_value, "data": data}

    except Exception:
        return None


__all__ = ["extract_halloweencostumes"]