"""Generic extractor that applies shared helpers to extract title, description, author, date, and media.
Uses structured data (JSON-LD/OG) and the section-weighting helpers to produce a
normalized output with confidence scores.
"""
from ai.services.extractors.common import (
    extract_json_ld,
    extract_og,
    compute_section_scores,
    assemble_weighted_output,
    normalize_text,
)
from bs4 import BeautifulSoup
import json


def extract_from_html(html):
    # structured data first
    jsonlds = extract_json_ld(html)
    structured = None
    if jsonlds:
        parsed = None
        for txt in jsonlds:
            try:
                obj = json.loads(txt)
            except Exception:
                obj = None
            if obj:
                # normalize common shapes (could be list or dict)
                if isinstance(obj, list) and len(obj) > 0:
                    obj = obj[0]
                structured = obj
                break
    # open graph
    og = extract_og(html) or {}

    # compute scored sections
    sections = compute_section_scores(html)

    # prefer structured if present
    prefer_structured = None
    if structured:
        # if structured is a dict and contains useful fields, pass a simple mapping
        prefer_structured = {}
        if isinstance(structured, dict):
            prefer_structured[
                "headline"
            ] = structured.get("headline") or structured.get("name") or structured.get(
                "title"
            )
            # also expose description and articleBody if present
            prefer_structured["description"] = (
                structured.get("description") or structured.get("articleBody")
            )

    # assemble final weighted output
    out = assemble_weighted_output(sections, prefer_structured=prefer_structured)

    # if structured provides higher-confidence fields, incorporate
    if structured and isinstance(structured, dict):
        if structured.get("headline") and (not out.get("title")):
            out["title"] = normalize_text(structured.get("headline"))
            out["confidence"] = max(out["confidence"], 0.95)
            out.setdefault("sources", []).append(
                {"type": "structured", "confidence": 0.95}
            )
        if structured.get("description") and (not out.get("description")):
            out["description"] = normalize_text(structured.get("description"))

    # fallback to OG title/description
    if (not out.get("title")) and og.get("og:title"):
        out["title"] = normalize_text(og.get("og:title"))
        out["sources"].append({"type": "og", "key": "og:title"})
    if (not out.get("description")) and og.get("og:description"):
        out["description"] = normalize_text(og.get("og:description"))
        out["sources"].append({"type": "og", "key": "og:description"})

    # ensure content present
    if not out.get("content") and sections:
        out["content"] = sections[0]["text"]

    return out


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: generic_extractor.py <html_file>")
        sys.exit(2)
    with open(sys.argv[1], "r", encoding="utf-8", errors="replace") as f:
        html = f.read()
        print(json.dumps(extract_from_html(html), indent=2, ensure_ascii=False))
