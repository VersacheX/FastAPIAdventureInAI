"""Generic HTML extractor service.

Provides an async `extract_generic_html(url)` function that fetches the URL
and returns a normalized extraction using the generic extractor logic.

Returns dict with keys: 'html' (raw HTML), 'text' (best-effort plaintext summary),
and 'extract' (normalized fields from the extractor: title/description/content/confidence).
"""
from typing import Optional, Dict, Any
import asyncio
import re
import sys
from bs4 import BeautifulSoup, Tag

# Use shared HTTP helpers for fetching/stripping HTML
from ai.services.http_service import fetch_html, _strip_html
from ai.services.extractors.generic_extractor import extract_from_html


def _normalize_key(title: str) -> str:
    if not title:
        return ""
    k = title.lower()
    k = re.sub(r'[^a-z0-9]', '', k)
    return k


async def extract_generic_html(url: str) -> Optional[Dict[str, Any]]:
    """Fetch URL and return a generic extraction.

    The function returns None on failure, otherwise a dict with keys:
    - html: raw HTML string
    - text: best-effort plaintext summary (description or snippet)
    - extract: normalized structured fields from the generic extractor
    - sections: discovered large text blocks by normalized key -> text
    """
    if not url:
        return None

    try:
        payload = await fetch_html(url)
        if not payload:
            return None
        html = payload.get("html")
        if not html:
            return None

        # Run the extractor synchronously (it's pure-CPU and fast)
        try:
            extract = extract_from_html(html)
        except Exception:
            extract = {}

        # See if we can find any other sections of large bod of texts with headings we can add to sections
        sections = { }
        # Discover large content sections using BeautifulSoup heuristics.
        sections: Dict[str, str] = {}
        titles_map: Dict[str, str] = {}
        try:
            parser = 'lxml' if 'lxml' in sys.modules else 'html.parser'
            soup = BeautifulSoup(html, parser)

            consumed_paragraphs = set()

            #1) Header-based extraction: h1..h4 -> collect following <p> (or paragraphs inside containers)
            for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                # get readable title
                title = header.get_text(separator=' ', strip=True)
                if not title:
                    continue
                paras = []
                for sib in header.next_siblings:
                    if isinstance(sib, Tag) and sib.name in ['h1', 'h2', 'h3', 'h4']:
                        break
                    if isinstance(sib, Tag) and sib.name == 'p':
                        txt = sib.get_text(separator=' ', strip=True)
                        if txt:
                            paras.append(txt)
                            consumed_paragraphs.add(sib)
                    elif isinstance(sib, Tag):
                        # collect paragraphs inside other containers (div, section, article, figure)
                        for p in sib.find_all('p'):
                            if p in consumed_paragraphs:
                                continue
                            t = p.get_text(separator=' ', strip=True)
                            if t:
                                paras.append(t)
                                consumed_paragraphs.add(p)
                    # stop if we collected a lot to avoid huge sections
                    if len(paras) >=20:
                        break

                if paras:
                    norm = _normalize_key(title) or f"section{len(sections) +1}"
                    base = norm
                    i =1
                    while norm in sections:
                        i +=1
                        norm = f"{base}_{i}"
                    text_block = "\n\n".join(paras).strip()
                    sections[norm] = text_block[:3000]
                    titles_map[norm] = title

            #2) Divs/containers that have several paragraphs but weren't captured above
            # Find div/section/article nodes with >=3 p children and add them if their paragraphs
            # weren't already consumed.
            for container in soup.find_all(['div', 'section', 'article']):
                ps = container.find_all('p')
                if not ps or len(ps) <3:
                    continue
                paras = []
                added_any = False
                for p in ps:
                    if p in consumed_paragraphs:
                        continue
                    t = p.get_text(separator=' ', strip=True)
                    if t:
                        paras.append(t)
                        consumed_paragraphs.add(p)
                        added_any = True
                    if len(paras) >=20:
                        break
                if added_any and paras:
                    # attempt to get a title from preceding header or container id/class
                    title = None
                    # try previous header sibling inside the same parent
                    prev = container.find_previous(['h1', 'h2', 'h3', 'h4'])
                    if prev:
                        title = prev.get_text(separator=' ', strip=True)
                    else:
                        # fallback to id/class
                        cid = container.get('id')
                        if cid:
                            title = cid
                        else:
                            cl = container.get('class')
                            if cl:
                                title = ' '.join(cl)
                    norm = _normalize_key(title or f"block{len(sections) +1}")
                    if not norm:
                        norm = f"block{len(sections) +1}"
                    base = norm
                    i =1
                    while norm in sections:
                        i +=1
                        norm = f"{base}_{i}"
                    sections[norm] = "\n\n".join(paras)[:3000]
                    titles_map[norm] = title or ''

            #3) Remaining loose paragraphs: group consecutive unconsumed <p> into chunks
            loose_paras = [p for p in soup.find_all('p') if p not in consumed_paragraphs]
            chunk = []
            for p in loose_paras:
                txt = p.get_text(separator=' ', strip=True)
                if not txt:
                    continue
                # determine whether to append to current chunk or start new one
                if not chunk:
                    chunk.append(txt)
                else:
                    # if paragraphs are adjacent siblings, keep them together
                    prev = chunk[-1]
                    # heuristic: always group consecutive loose paragraphs up to6
                    if len(chunk) <6:
                        chunk.append(txt)
                    else:
                        # flush
                        norm = f"loose{len(sections) +1}"
                        sections[norm] = "\n\n".join(chunk)[:3000]
                        titles_map[norm] = ""
                        chunk = [txt]
            if chunk:
                norm = f"loose{len(sections) +1}"
                sections[norm] = "\n\n".join(chunk)[:3000]
                titles_map[norm] = ""

            #if there are other sections we can build final text with more context
        except Exception:
            # non-fatal: fall back to empty sections
            sections = {}

        # Build a plaintext summary: prefer extractor description -> content snippet -> stripped body
        MAX_TEXT =3000
        if extract.get("description"):
            text = extract.get("description")
        elif extract.get("content"):
            text = extract.get("content")[:MAX_TEXT]
        else:
            # prefer joining a couple of discovered sections for more context
            if sections:
                # include up to two largest sections in deterministic order
                ordered = sorted(sections.items(), key=lambda kv: -len(kv[1]))[:2]
                text = "\n\n---\n\n".join([v for _, v in ordered])
                if len(text) > MAX_TEXT:
                    text = text[:MAX_TEXT]
            else:
                text = _strip_html(html)[:MAX_TEXT]

        # Append discovered sections in display (insertion) order to the summary text
        if sections:
            # ensure text isn't empty and add separator
            if text and not text.strip().endswith('\n'):
                text = text.rstrip()
            for key, body in sections.items():
                title = titles_map.get(key, '')
                if title:
                    add_block = f"\n\n{title}:\n{body}"
                else:
                    add_block = f"\n\n{body}"
                # append and trim to MAX_TEXT
                if not text:
                    text = add_block.strip()
                else:
                    text = (text + add_block).strip()
                if len(text) >= MAX_TEXT:
                    text = text[:MAX_TEXT]
                    break

        return {"html": html, "sections": sections, "text": text, "extract": extract}
    except Exception:
        return None
