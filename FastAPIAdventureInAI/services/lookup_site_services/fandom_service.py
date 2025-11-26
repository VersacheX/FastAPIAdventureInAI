"""Fandom (Wikia) content extractor.

Provides an extractor for pages under `*.fandom.com/wiki/*` that returns
both the raw HTML and a cleaned, concise plaintext excerpt.

The extractor prefers the portable-infobox (if present) and the first few
paragraphs of the article body to produce a useful summary for downstream
AI consumption. It also extracts named sections and returns a structured
infobox map when possible.
"""
from typing import Optional, Dict, Any
import re
import sys
from bs4 import BeautifulSoup, Tag

# Use shared http helpers
from services.http_service import fetch_html, _strip_html


async def _extract_fandom(url: str) -> Optional[Dict[str, Any]]:
    """Async extractor for fandom wiki pages.

    Returns a dict containing:
    - html: raw HTML (string)
    - text: concise combined summary (string)
    - meta: metadata like title/description
    - infobox: mapping of key->value (if parsed)
    - infobox_text: fallback textual infobox
    - lead: lead paragraph(s)
    - sections: mapping title->text for section excerpts
    """
    try:
        payload = await fetch_html(url)
        if not payload or not isinstance(payload, dict):
            return None
        html = payload.get("html")
        if not html:
            return None

        # Ignore known noisy Fandom root/portal paths and album pages.
        try:
            ulow = url.lower()
            # Check against public ignore list
            for pat in IGNORED_FANDOM_PATHS:
                if ulow.startswith(pat.lower()):
                    print(f"[fandom_service] ignoring fandom root/portal page {url}")
                    return None

            # Album / soundtrack noise (vocal collection) anywhere in path
            if "vocal_collection" in ulow or "vocal-collection" in ulow or "vocal collection" in ulow:
                print(f"[fandom_service] ignoring vocal collection page {url}")
                return None

            # also check title meta for noisy album pages
            title_m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
            if title_m:
                title_txt = title_m.group(1).lower()
                if "vocal collection" in title_txt or "vocal_collection" in title_txt:
                    print(f"[fandom_service] ignoring vocal collection page by title {url}")
                    return None
        except Exception:
            pass

        out: Dict[str, Any] = {"html": html}

        # meta: title / description
        meta: Dict[str, str] = {}
        m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            meta["title"] = _strip_html(m.group(1))
        else:
            m2 = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
            if m2:
                meta["title"] = _strip_html(m2.group(1))
        m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            meta["description"] = m.group(1).strip()
        if meta:
            out["meta"] = meta

        # Attempt infobox extraction (portable-infobox aside preferred)
        infobox_html = None
        m = re.search(r'<aside[^>]*class=["\'][^"\']*portable-infobox[^"\']*["\'][^>]*>([\s\S]*?)</aside>', html, re.I)
        if m:
            infobox_html = m.group(0)
        else:
            m2 = re.search(r'<table[^>]*class=["\'][^"\']*infobox[^"\']*["\'][^>]*>([\s\S]*?)</table>', html, re.I)
            if m2:
                infobox_html = m2.group(0)

        infobox_map: Dict[str, str] = {}
        infobox_text: Optional[str] = None
        if infobox_html:
            infobox_text = _strip_html(infobox_html)
            try:
                # portable-infobox label/value pairs
                for row in re.finditer(
                    r'<h3[^>]*class=["\']?pi-data-label[^"\']*[/"\']?[^>]*>([\s\S]*?)</h3>\s*<div[^>]*class=["\']?pi-data-value[^"\']*[/"\']?[^>]*>([\s\S]*?)</div>',
                    infobox_html,
                    re.I,
                ):
                    k = _strip_html(row.group(1))
                    v = _strip_html(row.group(2))
                    if k:
                        infobox_map[k] = v

                # fallback simple rows
                if not infobox_map:
                    for item in re.finditer(r'<div[^>]*class=["\']?pi-item[^"\']*[/"\']?[^>]*>([\s\S]*?)</div>', infobox_html, re.I):
                        inner = item.group(1)
                        lab = re.search(r'<h3[^>]*>([\s\S]*?)</h3>', inner, re.I)
                        val = re.search(r'<div[^>]*class=["\']?pi-data-value[^"\']*[/"\']?[^>]*>([\s\S]*?)</div>', inner, re.I)
                        if lab and val:
                            kk = _strip_html(lab.group(1))
                            vv = _strip_html(val.group(1))
                            if kk:
                                infobox_map[kk] = vv
            except Exception:
                # non-fatal
                pass

        # cap textual infobox
        if infobox_text and len(infobox_text) >1000:
            infobox_text = infobox_text[:1000] + "..."

        if infobox_map:
            out["infobox"] = infobox_map
        elif infobox_text:
            out["infobox_text"] = infobox_text

        # Extract main content block (mw-parser-output) and lead paragraphs.
        # Use BeautifulSoup to find the div with class 'mw-parser-output' directly
        # because the previous regex approach is fragile and can truncate nested
        # HTML in large pages.
        main_block = None
        parser = 'lxml' if 'lxml' in sys.modules else 'html.parser'
        soup = BeautifulSoup(html, parser)
        mw_div = soup.find('div', class_='mw-parser-output')
        if mw_div:
            main_block = str(mw_div)
            # expose the Tag for downstream section extraction
            soup_main = mw_div
        else:
            # fallback: use full HTML soup as the search surface
            main_block = None
            soup_main = soup

        lead_pars = []
        if main_block:
            # parse paragraphs from the mw-parser-output Tag (soup_main) when available
            for p in (soup_main.find_all('p') if isinstance(soup_main, Tag) else []):
                txt = p.get_text(separator=' ', strip=True)
                if txt:
                    lead_pars.append(txt)
                if len(lead_pars) >=4:
                    break
        if not lead_pars:
            for p in re.finditer(r'<p[^>]*>([\s\S]*?)</p>', html, re.I):
                txt = _strip_html(p.group(1))
                if txt:
                    lead_pars.append(txt)
                if len(lead_pars) >=4:
                    break
        if lead_pars:
            out["lead"] = "\n\n".join(lead_pars)

        # Extract named sections (h2..h4 with mw-headline inside main_block)
        sections: Dict[str, str] = {}
        # map normalized key -> original title for text rendering
        titles_map: Dict[str, str] = {}

        def _normalize_key(s: str) -> str:
            if not s:
                return ''
            k = s.lower()
            k = re.sub(r'[^a-z0-9]', '', k)
            return k

        try:
            # If soup_main was set above from the mw-parser-output div, reuse it.
            # Otherwise fallback to parsing the full HTML.
            if 'soup_main' not in locals() or soup_main is None:
                parser = 'lxml' if 'lxml' in sys.modules else 'html.parser'
                soup_main = BeautifulSoup(html, parser)

            # Only treat h2 and h3 as section boundaries. h4 and lower are considered part of the
            # surrounding section content.
            for header in soup_main.find_all(['h2', 'h3']):
                # prefer span.mw-headline text when available
                span = header.find('span', class_='mw-headline')
                title = span.get_text(strip=True) if span else header.get_text(strip=True)
                if not title:
                    continue

                # collect all <p> text until the next h2 or h3
                paras = []
                for sib in header.next_siblings:
                    # stop at the next top-level section header
                    if isinstance(sib, Tag) and sib.name in ['h2', 'h3']:
                        break
                    if isinstance(sib, Tag):
                        # if the sibling itself is a paragraph, include it
                        if sib.name == 'p':
                            pt = sib.get_text(separator=' ', strip=True)
                            if pt:
                                paras.append(pt)
                        else:
                            # capture paragraphs inside this sibling container (figures, divs, blockquotes, etc.)
                            for p in sib.find_all('p'):
                                pt = p.get_text(separator=' ', strip=True)
                                if pt:
                                    paras.append(pt)

                # Join paragraphs; if none found, try a short text fallback from the following nodes
                if paras:
                    section_text = "\n\n".join(paras)
                else:
                    # fallback: collect text nodes (non-tags) and trimmed text of next few Tag siblings
                    nxt = []
                    for sib in header.next_siblings:
                        if isinstance(sib, Tag) and sib.name in ['h2', 'h3']:
                            break
                        if isinstance(sib, Tag):
                            txt = sib.get_text(separator=' ', strip=True)
                            if txt:
                                nxt.append(txt)
                        else:
                            txt = str(sib).strip()
                            if txt:
                                nxt.append(txt)
                        if len(nxt) >=6:
                            break
                    section_text = "\n\n".join([x for x in nxt if x]).strip()

                if section_text:
                    norm = _normalize_key(title.strip())
                    sections[norm] = section_text[:1500]
                    # store first-seen original title for this normalized key
                    if norm not in titles_map:
                        titles_map[norm] = title.strip()
        except Exception:
            pass

        # Targeted extraction: Appearance and Personality often live as h3 under a
        # "Profile" h2. If they weren't captured earlier, explicitly extract
        # their <p> contents. Also handle Story specially: some wikis place it in
        # a collapsible container directly after the Story header.
        try:
            # PROFILE -> look for h2 with 'profile' and then its h3 children
            for h2 in soup_main.find_all('h2'):
                span2 = h2.find('span', class_='mw-headline')
                h2_title = (span2.get_text(strip=True) if span2 else h2.get_text(strip=True)) or ''
                if 'profile' in h2_title.lower():
                    # iterate siblings until next h2 and inspect h3 nodes
                    for node in h2.next_siblings:
                        if isinstance(node, Tag) and node.name == 'h2':
                            break
                        if isinstance(node, Tag) and node.name == 'h3':
                            span3 = node.find('span', class_='mw-headline')
                            h3_title = (span3.get_text(strip=True) if span3 else node.get_text(strip=True)) or ''
                            if not h3_title:
                                continue
                            low = h3_title.lower()
                            if 'appearance' in low or 'personality' in low:
                                # collect paragraphs until next h3/h2
                                ptexts = []
                                for sib in node.next_siblings:
                                    if isinstance(sib, Tag) and sib.name in ['h2', 'h3']:
                                        break
                                    if isinstance(sib, Tag):
                                        if sib.name == 'p':
                                            t = sib.get_text(separator=' ', strip=True)
                                            if t:
                                                ptexts.append(t)
                                        else:
                                            for p in sib.find_all('p'):
                                                t = p.get_text(separator=' ', strip=True)
                                                if t:
                                                    ptexts.append(t)
                                if ptexts:
                                    norm = _normalize_key(h3_title.strip())
                                    if norm not in sections:
                                        sections[norm] = "\n\n".join(ptexts)[:1500]
                                        titles_map[norm] = h3_title
                                        # once profile processed, no need to search other h2 profile blocks
                                        # (some pages may contain multiple profiles but we prefer the first)
                                        break
        except Exception:
            pass

        # STORY: extract from collapsible blocks following the Story header
        try:
            if not any('story' in k for k in sections.keys()):
                for header in soup_main.find_all(['h2', 'h3']):
                    span = header.find('span', class_='mw-headline')
                    title = (span.get_text(strip=True) if span else header.get_text(strip=True)) or ''
                    if 'story' in title.lower():
                        # look for an immediate collapsible container
                        for sib in header.next_siblings:
                            if isinstance(sib, Tag):
                                cls = ' '.join(sib.get('class') or [])
                                # common collapsible classes
                                if 'mw-collapsible' in cls or 'mw-collapsible-content' in cls or 'mw-collapsible-body' in cls:
                                    texts = []
                                    for p in sib.find_all('p'):
                                        t = p.get_text(separator=' ', strip=True)
                                        if t:
                                            texts.append(t)
                                    if texts:
                                        norm = _normalize_key(title.strip())
                                        sections[norm] = "\n\n".join(texts)[:1500]
                                        titles_map[norm] = title
                                        break
                                # nested collapsible
                                inner = sib.find('div', class_='mw-collapsible-content') if isinstance(sib, Tag) else None
                                if inner:
                                    texts = [p.get_text(separator=' ', strip=True) for p in inner.find_all('p') if p.get_text(strip=True)]
                                    if texts:
                                        norm = _normalize_key(title.strip())
                                        sections[norm] = "\n\n".join(texts)[:1500]
                                        titles_map[norm] = title
                                        break
                            # stop if next real header found
                            if isinstance(sib, Tag) and sib.name in ['h2', 'h3']:
                                break
        except Exception:
            pass

        if sections:
            # Debug print: list all gathered sections with their inner text
            # try:
            #     print("[fandom_service] Sections found:")
            #     for _title, _content in sections.items():
            #         print(f" - Section: {_title}")
            #         # print a short preview and then full content on separate line for easier debugging
            #         preview = (_content[:300] + "...") if len(_content) >300 else _content
            #         print(f" Preview: {preview}")
            #         print(f" Full: {_content}")
            # except Exception:
            #     pass
            out["sections"] = sections

        # Build concise summary text
        pieces = []

        #1) INFOBOX (preferred first)
        if "infobox" in out:
            try:
                items = []
                for i, (k, v) in enumerate(out["infobox"].items()):
                    items.append(f"{k}: {v}")
                    if i >=7:
                        break
                if items:
                    pieces.append("INFOBOX:\n" + "; ".join(items))
            except Exception:
                pass
        elif out.get("infobox_text"):
            pieces.append("INFOBOX:\n" + out.get("infobox_text"))

        #2) Lead / content (preferred start) - put the lead first so summaries begin with it
        if out.get("lead"):
            pieces.append("CONTENT:\n" + out.get("lead"))

        #3) Preferred sections in deterministic order: Appearance, Personality, Story
        if sections:
            try:
                # Prefer Appearance / Personality / Abilities / Story in that order.
                # Abilities can appear under a variety of headings ("Abilities", "Kit", "Skills", "Gameplay", etc.)
                preferred_groups = [
                    ["appearance"],
                    ["personality"],
                    ["ability", "abilities", "kit", "skills", "gameplay", "powers"],
                    ["story"],
                ]
                ordered_sections = []

                # add preferred matches in the explicit order requested (support synonyms)
                added = set()
                for group in preferred_groups:
                    for key, body in sections.items():
                        low = (key or "").lower()
                        if key in added:
                            continue
                        for keyword in group:
                            if keyword in low:
                                # include a per-section source marker so downstream callers
                                # can attribute the exact section to the original URL.
                                display_title = titles_map.get(key, key)
                                ordered_sections.append(f"{display_title}:\n{body}\n\n(Source: {url})")
                                added.add(key)
                                break
                    if key in added:
                        break

                # If no preferred sections found (or some missing), also include up to
                # two of the remaining sections to provide context.
                if len(ordered_sections) <3:
                    for key, body in sections.items():
                        if key in added:
                            continue
                        display_title = titles_map.get(key, key)
                        ordered_sections.append(f"{display_title}:\n{body}\n\n(Source: {url})")
                        added.add(key)
                        if len(ordered_sections) >=3:
                            break

                if ordered_sections:
                    pieces.append("SECTIONS:\n" + "\n\n".join(ordered_sections))
            except Exception:
                pass

        #4) If no lead or infobox/sections were included earlier, lead may already be present.
        # (lead is already added above when present)
        if pieces:
            pieces.append(f"(Source: {url})")
            out_text = "\n\n---\n\n".join(pieces)
        else:
            out_text = f"Source: {url}"
        
        print(f"[fandom_service] constructed summary text for {url} ({len(out_text)} chars)")
        out["text"] = out_text
        return out

    except Exception as e:
        print(f"[fandom_service] extractor failed for {url}: {e}")
        return None


# Convenience wrappers
async def fetch_fandom_excerpt(url: str) -> Optional[str]:
    try:
        res = await _extract_fandom(url)
        if not res:
            return None
        return res.get("text")
    except Exception:
        return None


async def extract_fandom(url: str) -> Optional[Dict[str, Any]]:
    return await _extract_fandom(url)


# Public list of Fandom root paths / URL prefixes to ignore. This is
# intended to be imported by other modules/tests if they need to inspect
# or extend the set of known noisy Fandom entry points. Patterns are
# substrings checked against the lowercase URL.
IGNORED_FANDOM_PATHS = [
    "https://www.fandom.com/explore",
    "https://www.fandom.com/fancentral",
    "https://www.fandom.com/explore-",
]
