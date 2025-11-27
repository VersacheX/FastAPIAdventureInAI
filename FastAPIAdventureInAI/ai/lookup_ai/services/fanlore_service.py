"""Fanlore content extractor.

Lightweight extractor for pages under `fanlore.org/wiki/*`.
Returns raw HTML plus cleaned text, lead paragraphs and named sections.

Designed to be similar to `fandom_service.extract_fandom` so the describer
can treat Fanlore results consistently.
"""
from typing import Optional, Dict, Any
import re
import sys
from bs4 import BeautifulSoup, Tag

from ai.services.http_service import fetch_html, _strip_html


async def _extract_fanlore(url: str) -> Optional[Dict[str, Any]]:
    try:
        payload = await fetch_html(url)
        if not payload or not isinstance(payload, dict):
            return None
        html = payload.get("html")
        if not html:
            return None

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

        # Parse the main content with BeautifulSoup to reliably extract
        # the intro (we prefer the 'Canon' paragraph when present) and
        # named sections like 'Reception and Popularity'.
        parser = 'lxml' if 'lxml' in sys.modules else 'html.parser'
        soup = BeautifulSoup(html, parser)
        mw_div = soup.find('div', class_='mw-parser-output')
        search_root = mw_div if isinstance(mw_div, Tag) else soup

        # Prefer the paragraph under the 'Canon' heading as the lead intro.
        lead_text = None
        try:
            canon_h2 = None
            for h2 in search_root.find_all('h2'):
                span = h2.find('span', class_='mw-headline')
                title = (span.get_text(strip=True) if span else h2.get_text(strip=True)) or ''
                if title and 'canon' == title.lower():
                    canon_h2 = h2
                    break
            if canon_h2:
                # first paragraph after the Canon header
                for sib in canon_h2.next_siblings:
                    if isinstance(sib, Tag) and sib.name == 'p':
                        txt = sib.get_text(separator=' ', strip=True)
                        if txt:
                            lead_text = txt
                        break
                    # stop at next section header
                    if isinstance(sib, Tag) and sib.name == 'h2':
                        break
        except Exception:
            lead_text = None

        # fallback: first sizable paragraph in the content area
        if not lead_text:
            for p in search_root.find_all('p'):
                txt = p.get_text(separator=' ', strip=True)
                if txt and len(txt) >50:
                    lead_text = txt
                    break
        if lead_text:
            out['lead'] = lead_text

        # sections: collect h2 headings and gather following <p> until next h2
        sections: Dict[str, str] = {}
        # map normalized key -> original title for text rendering
        titles_map: Dict[str, str] = {}

        def _normalize_key(s: str) -> str:
            # keep only ascii alphanumerics and lower-case them
            if not s:
                return ''
            k = s.lower()
            k = re.sub(r'[^a-z0-9]', '', k)
            return k

        try:
            for h2 in search_root.find_all('h2'):
                span = h2.find('span', class_='mw-headline')
                title = (span.get_text(strip=True) if span else h2.get_text(strip=True)) or ''
                if not title:
                    continue
                paras = []
                for sib in h2.next_siblings:
                    if isinstance(sib, Tag) and sib.name == 'h2':
                        break
                    if isinstance(sib, Tag) and sib.name == 'p':
                        txt = sib.get_text(separator=' ', strip=True)
                        if txt:
                            paras.append(txt)
                    elif isinstance(sib, Tag):
                        for p in sib.find_all('p'):
                            txt = p.get_text(separator=' ', strip=True)
                            if txt:
                                paras.append(txt)
                    if len(paras) >=10:
                        break
                if paras:
                    norm = _normalize_key(title.strip())
                    content = '\n\n'.join(paras)[:1500]
                    if norm in sections:
                        # merge duplicate normalized keys
                        sections[norm] = sections[norm] + '\n\n' + content
                    else:
                        sections[norm] = content
                    # store the first-seen original title for this normalized key
                    titles_map[norm] = title.strip()
        except Exception:
            pass

        if sections:
            # Debug print: list all gathered sections with their inner text
            try:
                print("[fanlore_service] Sections found:")
                for _title, _content in sections.items():
                    print(f" - Section key: {_title}")
                    print(f" Content: {_content}")
            except Exception:
                pass
            out["sections"] = sections

        # Build fallback text
        pieces = []
        if out.get("lead"):
            pieces.append("CONTENT:\n" + out.get("lead"))
        if sections:
            try:
                top = []
                c =0
                for norm_key, body in sections.items():
                    # use original heading text when building the text output
                    display_title = titles_map.get(norm_key, norm_key)
                    top.append(f"{display_title}:\n{body}")
                    c +=1
                    if c >=2:
                        break
                if top:
                    pieces.append("SECTIONS:\n" + "\n\n".join(top))
            except Exception:
                pass

        if not pieces:
            body_text = _strip_html(html)[:2000]
            if body_text:
                pieces.append(body_text)

        if pieces:
            pieces.append(f"(Source: {url})")
            out_text = "\n\n---\n\n".join(pieces)
        else:
            out_text = f"Source: {url}"

        out["text"] = out_text
        return out

    except Exception as e:
        print(f"[fanlore_service] extractor failed for {url}: {e}")
        return None


# convenience wrapper
async def extract_fanlore(url: str) -> Optional[Dict[str, Any]]:
    return await _extract_fanlore(url)
