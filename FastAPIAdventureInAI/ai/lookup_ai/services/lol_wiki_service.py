"""Extractor for wiki.leagueoflegends.com (MediaWiki) pages.

This is a lightweight, targeted extractor that prefers the page's
`mw-parser-output` lead paragraphs, infobox content (when present) and
named sections. It returns a dict with at least `html` and `text` and
adds `meta` and `sections` when available.
"""
from typing import Optional, Dict, Any
import re
import sys
from bs4 import BeautifulSoup, Tag

from ai.services.http_service import fetch_html, _strip_html


def _normalize_key(title: str) -> str:
    # normalize to lower-case alphanumeric-only key to avoid collisions
    if not title:
        return ""
    k = title.lower()
    k = re.sub(r'[^a-z0-9]', '', k)
    return k


def _crop(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[:limit].rsplit(" ", 1)[0] + "..."


async def extract_lol_wiki(url: str) -> Optional[Dict[str, Any]]:
    try:
        payload = await fetch_html(url)
        if not payload or not isinstance(payload, dict):
            return None
        html = payload.get("html")
        if not html:
            return None

        out: Dict[str, Any] = {"html": html}

        # meta: title/description
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

        parser = 'lxml' if 'lxml' in sys.modules else 'html.parser'
        soup = BeautifulSoup(html, parser)

        # Find mw-parser-output lead paragraphs
        lead_pars = []
        mw = soup.find('div', class_='mw-parser-output')
        if mw:
            # prefer top-level paragraphs inside mw-parser-output
            for p in mw.find_all('p', recursive=False):
                txt = p.get_text(separator=' ', strip=True)
                if txt:
                    lead_pars.append(txt)
                if len(lead_pars) >= 4:
                    break
        # fallback generic paragraphs in document
        if not lead_pars:
            for p in soup.find_all('p'):
                txt = p.get_text(separator=' ', strip=True)
                if txt:
                    lead_pars.append(txt)
                if len(lead_pars) >= 3:
                    break
        if lead_pars:
            out['lead'] = '\n\n'.join(lead_pars[:4])

        # Infobox extraction: common MediaWiki infobox div/table
        infobox_text = None
        infobox_map: Dict[str, str] = {}
        ib = soup.find(attrs={"class": re.compile(r"\\binfobox\\b", re.I)})
        if ib:
            infobox_text = _strip_html(str(ib))
            try:
                # dl (dt/dd) pairs
                for dl in ib.find_all('dl'):
                    dts = dl.find_all('dt')
                    dds = dl.find_all('dd')
                    for dt, dd in zip(dts, dds):
                        k = dt.get_text(separator=' ', strip=True)
                        v = dd.get_text(separator=' ', strip=True)
                        if k:
                            infobox_map[k] = v
                # table rows
                for tr in ib.find_all('tr'):
                    th = tr.find('th')
                    td = tr.find('td')
                    if th and td:
                        k = th.get_text(separator=' ', strip=True)
                        v = td.get_text(separator=' ', strip=True)
                        if k:
                            infobox_map[k] = v
                # fallback: labeled divs with strong/b tags
                if not infobox_map:
                    for row in ib.find_all('div'):
                        strong = row.find('b') or row.find('strong')
                        if strong:
                            k = strong.get_text(separator=' ', strip=True)
                            # remove the strong from row to get the remainder
                            strong.extract()
                            v = row.get_text(separator=' ', strip=True)
                            if k:
                                infobox_map[k] = v
            except Exception:
                # non-fatal
                pass

        if infobox_map:
            out['infobox'] = infobox_map
        elif infobox_text:
            out['infobox_text'] = infobox_text[:1000]

        # Sections: collect h2/h3/h4 headers and their paragraph content
        sections: Dict[str, str] = {}
        titles_map: Dict[str, str] = {}
        try:
            search_root = mw if mw else soup
            for header in search_root.find_all(['h2', 'h3', 'h4']):
                span = header.find('span', class_='mw-headline')
                title = span.get_text(strip=True) if span else header.get_text(strip=True)
                if not title:
                    continue
                paras = []
                for sib in header.next_siblings:
                    if isinstance(sib, Tag) and sib.name in ['h2', 'h3', 'h4']:
                        break
                    if isinstance(sib, Tag) and sib.name == 'p':
                        txt = sib.get_text(separator=' ', strip=True)
                        if txt:
                            paras.append(txt)
                    elif isinstance(sib, Tag):
                        for p in sib.find_all('p'):
                            t = p.get_text(separator=' ', strip=True)
                            if t:
                                paras.append(t)
                    if len(paras) >= 12:
                        break
                if paras:
                    body = '\n\n'.join(paras)
                    # crop stored section content to reasonable size
                    norm = _normalize_key(title)
                    # avoid key collisions by appending a counter if needed
                    base = norm
                    i = 1
                    while norm in sections:
                        i += 1
                        norm = f"{base}_{i}"
                    sections[norm] = _crop(body, 3000)
                    # store original title for display
                    titles_map[norm] = title
        except Exception:
            pass

        if sections:
            out['sections'] = sections
            # do not expose section_titles separately; callers can use `sections`.
            # preserve `titles_map` for internal use only.

        # Build a concise text summary prioritizing infobox -> lead -> key sections
        pieces = []
        if 'infobox' in out:
            try:
                items = []
                for i, (k, v) in enumerate(out['infobox'].items()):
                    items.append(f"{k}: {v}")
                    if i >= 6:
                        break
                if items:
                    pieces.append('INFOBOX:\n' + '; '.join(items))
            except Exception:
                pass
        elif out.get('infobox_text'):
            pieces.append('INFOBOX:\n' + out.get('infobox_text'))

        if out.get('lead'):
            pieces.append('CONTENT:\n' + _crop(out.get('lead'), 2000))

        # include Appearance/Personality/Abilities/Story if present
        preferred = ['Appearance', 'Personality', 'Abilities', 'Story', 'Background', 'Recent Events', 'Relations', 'Trivia']
        if out.get('sections'):
            sec = out.get('sections', {})
            titles = titles_map
            for p in preferred:
                p_norm = _normalize_key(p)
                for key, body in sec.items():
                    if p_norm in key.lower():
                        display_title = titles.get(key, key)
                        pieces.append(f"{display_title}:\n{_crop(body, 1500)}")
                        break

        # include up to two other sections if nothing else
        if not pieces and out.get('sections'):
            cnt = 0
            sec = out.get('sections', {})
            titles = titles_map
            for key, body in sec.items():
                display_title = titles.get(key, key)
                pieces.append(f"{display_title}:\n{_crop(body, 1500)}")
                cnt += 1
                if cnt >= 2:
                    break

        if not pieces:
            # fallback to meta description or stripped html
            if meta.get('description'):
                pieces.append(meta['description'])
            else:
                body_text = _strip_html(html)
                if body_text and body_text.strip():
                    pieces.append(body_text.strip()[:3000])

        out_text = '\n\n'.join(pieces)
        out['text'] = out_text

        return out

    except Exception:
        return None
