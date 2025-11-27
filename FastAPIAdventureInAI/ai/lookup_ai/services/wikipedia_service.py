"""Wikipedia content fetcher.

Provides a small async helper to retrieve excerpts from Wikipedia pages.
It prefers using the official Wikipedia REST API when a URL is recognized
as a wikipedia.org link. For non-wikipedia URLs it falls back to a best-effort
text extraction using a simple HTTP GET and naive HTML stripping.

The implementation uses blocking stdlib HTTP calls wrapped with
`asyncio.to_thread` to avoid extra runtime dependencies.
"""
from typing import Optional, Dict, Any
import asyncio
import re
import html as _html
from urllib import parse, request
from ai.services.http_service import fetch_html, _strip_html, _fetch_url

WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKI_QUERY_API = "https://en.wikipedia.org/w/api.php"

# Minimum extract length (characters) before we consider it "too short" and try a longer API
MIN_EXTRACT_CHARS = 250

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
                # decode HTML entities just in case
                try:
                    extract = _html.unescape(extract)
                except Exception:
                    pass
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
    fetch the page and return the visible text.

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
                    # decode html entities
                    try:
                        extract = _html.unescape(extract)
                    except Exception:
                        pass
                    print(f"[wikipedia_service] fetch_wikipedia_excerpt: got 'extract' from REST API len={len(extract)}")
                    # If the extract is short, try the query API for a longer extract
                    if len(extract) < MIN_EXTRACT_CHARS:
                        print("[wikipedia_service] fetch_wikipedia_excerpt: extract short, trying query API for longer extract")
                        longer = await _fetch_query_extract(title)
                        if longer and len(longer) > len(extract):
                            print(f"[wikipedia_service] fetch_wikipedia_excerpt: using longer extract length={len(longer)}")
                            return longer.strip()
                    return extract.strip()
                extract_html = payload.get("extract_html")
                if extract_html:
                    print("[wikipedia_service] fetch_wikipedia_excerpt: got 'extract_html' from REST API; stripping HTML")
                    # strip html tags and return
                    text = _strip_html(extract_html)
                    if len(text) < MIN_EXTRACT_CHARS:
                        # try query API
                        longer = await _fetch_query_extract(title)
                        if longer and len(longer) > len(text):
                            return longer.strip()
                    return text.strip()
                print("[wikipedia_service] fetch_wikipedia_excerpt: REST payload had no extract fields; trying query API")
                longer = await _fetch_query_extract(title)
                if longer:
                    return longer.strip()
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
            return text.strip()
    except Exception as e:
        print(f"[wikipedia_service] fetch_wikipedia_excerpt: exception: {e}")
        return None


# Structured extractor for wikipedia pages
async def extract_wikipedia(url: str) -> Optional[Dict[str, Any]]:
    """Return a structured extraction for a wikipedia.org URL.

    Returns dict with keys: html, text (combined summary), meta, lead, sections, infobox
    """
    try:
        lead_text = await fetch_wikipedia_excerpt(url)
        payload = await fetch_html(url)
        html = payload.get("html") if isinstance(payload, dict) else None
        if not html and not lead_text:
            return None

        out: Dict[str, Any] = {"html": html}

        # meta: title
        try:
            m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html or "", re.I)
            if m:
                out.setdefault("meta", {})["title"] = _strip_html(m.group(1))
            else:
                m2 = re.search(r'<title>(.*?)</title>', html or "", re.I | re.S)
                if m2:
                    out.setdefault("meta", {})["title"] = _strip_html(m2.group(1))
        except Exception:
            pass

        # Infobox extraction (table.infobox or portable-infobox)
        infobox_html = None
        try:
            m = re.search(r'<aside[^>]*class=["\']?[^"\']*portable-infobox[^"\']*["\']?[^>]*>([\s\S]*?)</aside>', html or "", re.I)
            if m:
                infobox_html = m.group(0)
            else:
                m2 = re.search(r'<table[^>]*class=["\']?[^"\']*infobox[^"\']*["\']?[^>]*>([\s\S]*?)</table>', html or "", re.I)
                if m2:
                    infobox_html = m2.group(0)
        except Exception:
            infobox_html = None

        infobox_map: Dict[str, str] = {}
        infobox_text: Optional[str] = None
        if infobox_html:
            infobox_text = _strip_html(infobox_html)
            try:
                # try table rows: <tr><th>Key</th><td>Value</td></tr>
                for tr in re.finditer(r'<tr[^>]*>([\s\S]*?)</tr>', infobox_html, re.I):
                    row_html = tr.group(1)
                    th = re.search(r'<th[^>]*>([\s\S]*?)</th>', row_html, re.I)
                    td = re.search(r'<td[^>]*>([\s\S]*?)</td>', row_html, re.I)
                    if th and td:
                        k = _strip_html(th.group(1))
                        v = _strip_html(td.group(1))
                        if k:
                            infobox_map[k] = v
                # fallback: portable-infobox pi-data-label/pi-data-value
                if not infobox_map:
                    for mrow in re.finditer(r'<h3[^>]*class=["\']?pi-data-label[^"\']*["]?[^>]*>([\s\S]*?)</h3>\s*<div[^>]*class=["\']?pi-data-value[^"\']*["]?[^>]*>([\s\S]*?)</div>', infobox_html, re.I):
                        k = _strip_html(mrow.group(1))
                        v = _strip_html(mrow.group(2))
                        if k:
                            infobox_map[k] = v
            except Exception:
                pass

        if infobox_map:
            out["infobox"] = infobox_map
            print(f"[wikipedia_service] extract_wikipedia: infobox_map keys={list(infobox_map.keys())[:8]}")
        elif infobox_text:
            out["infobox_text"] = infobox_text[:1000] if infobox_text else None
            print(f"[wikipedia_service] extract_wikipedia: infobox_text_len={len(infobox_text) if infobox_text else 0}")

        # Extract main block and sections from HTML (fallback)
        main_block = None
        try:
            # Robustly locate the opening mw-parser-output div
            m_start = re.search(r'<div[^>]*class=["\']?[^"\']*mw-parser-output[^"\']*["\']?[^>]*>', html or "", re.I)
            if m_start:
                start_idx = m_start.end()
                # Prefer to cut the lead at the 'mw:PageProp/toc' meta marker if present in the entire HTML
                toc_marker = '<meta property="mw:PageProp/toc"'
                toc_pos = (html or "").find(toc_marker, start_idx)
                if toc_pos != -1:
                    # slice up to the marker
                    main_block = (html or "")[start_idx:toc_pos]
                    lead_block = main_block
                    tail_block = (html or "")[toc_pos:]
                    print(f"[wikipedia_service] extract_wikipedia: located mw-parser-output start and toc marker; main_block len={len(main_block)}")
                else:
                    # If toc marker not found, attempt to slice up to the first <h2 id= or '<h2' following start
                    h2_match = re.search(r'<h2[^>]*>', (html or "")[start_idx:start_idx+20000], re.I)
                    if h2_match:
                        h2_pos = start_idx + h2_match.start()
                        main_block = (html or "")[start_idx:h2_pos]
                        lead_block = main_block
                        tail_block = (html or "")[h2_pos:]
                        print(f"[wikipedia_service] extract_wikipedia: sliced mw-parser-output up to first <h2>; main_block len={len(main_block)}")
                    else:
                        # fallback: try previous greedy regex fallback
                        m = re.search(r'<div[^>]*class=["\']?[^"\']*mw-parser-output[^"\']*["\']?[^>]*>([\s\S]*?)</div>\s*(?:<aside|<footer|<div class=)', html or "", re.I)
                        if not m:
                            m = re.search(r'<div[^>]*class=["\']?[^"\']*mw-parser-output[^"\']?[^>]*>([\s\S]*?)</div>', html or "", re.I)
                        if m:
                            main_block = m.group(1)
                            # try splitting by toc marker inside the main_block
                            inner_toc = re.search(r'<meta\s+property=["\']mw:PageProp/toc["\']', main_block, re.I)
                            if inner_toc:
                                cut = inner_toc.start()
                                lead_block = main_block[:cut]
                                tail_block = main_block[cut:]
                            else:
                                lead_block = main_block
                                tail_block = ''
                            print(f"[wikipedia_service] extract_wikipedia: fallback main_block len={len(main_block)}")
                        else:
                            print("[wikipedia_service] extract_wikipedia: no mw-parser-output main_block found")
            else:
                print("[wikipedia_service] extract_wikipedia: no mw-parser-output start tag found")
        except Exception as e:
            main_block = None
            print(f"[wikipedia_service] extract_wikipedia: exception finding main_block: {e}")

        sections: Dict[str, str] = {}
        lead_pars = []
        try:
            if main_block:
                # First, extract all <p> tags that appear in the lead_block (content before the toc/meta marker)
                if 'lead_block' in locals() and lead_block:
                    for p in re.finditer(r'<p[^>]*>[\s\S]*?</p>', lead_block, re.I):
                        txt = _strip_html(p.group(0))
                        if txt:
                            lead_pars.append(txt)

                # Then parse headings and subsequent paragraphs from the full main_block to build sections
                node_re = re.compile(r'(?P<heading>(?:<div[^>]*class=["\']?mw-heading[^"\']*["]?[^>]*>\s*)?<h(?P<hlvl>[2-4])[^>]*>(?:[\s\S]*?)</h(?P=hlvl)>\s*(?:</div>)?)|(?P<p><p[^>]*>[\s\S]*?</p>)', re.I | re.S)

                current_title = None
                section_paras: Dict[str, list] = {}
                for m in node_re.finditer(main_block):
                    if m.group('heading'):
                        # extract the inner text of the heading, prefer mw-headline span if present
                        h_html = m.group('heading')
                        mh = re.search(r'<span[^>]*class=["\']?mw-headline[^"\']*["\']?[^>]*>([\s\S]*?)</span>', h_html, re.I | re.S)
                        if mh:
                            title = _strip_html(mh.group(1))
                        else:
                            title = _strip_html(re.sub(r'^.*?<h[2-4][^>]*>|</h[2-4]>.*$', '', h_html, flags=re.I | re.S))
                        title = title.strip() if title else None
                        current_title = title if title else None
                        if current_title and current_title not in section_paras:
                            section_paras[current_title] = []
                    elif m.group('p'):
                        p_html = m.group('p')
                        txt = _strip_html(p_html)
                        if not txt:
                            continue
                        if current_title is None:
                            # avoid duplicating lead paragraphs already captured
                            if txt not in lead_pars:
                                lead_pars.append(txt)
                        else:
                            section_paras.setdefault(current_title, []).append(txt)

                # populate sections dict with joined paragraphs (limit length)
                for title, paras in section_paras.items():
                    if paras and title:
                        sections[title] = '\n\n'.join(paras)[:1500]

                # Debug logging about discovered sections and lead paragraphs
                try:
                    print(f"[wikipedia_service] extract_wikipedia: lead_pars_count={len(lead_pars)}")
                    print(f"[wikipedia_service] extract_wikipedia: sections_count={len(sections)}")
                    if sections:
                        titles = list(sections.keys())
                        print(f"[wikipedia_service] extract_wikipedia: section_titles={titles[:20]}")
                        for t in titles[:20]:
                            print(f"[wikipedia_service] extract_wikipedia: section '{t}' length={len(sections.get(t,'') or '')}")
                except Exception:
                    pass
        except Exception as e:
            print(f"[wikipedia_service] extract_wikipedia: exception during parsing main_block: {e}")
            pass

        if lead_text and not lead_pars:
            # REST extract provided lead; use it
            out["lead"] = lead_text
        elif lead_pars:
            out["lead"] = "\n\n".join(lead_pars)

        if sections:
            out["sections"] = sections

        # Build summary: prefer infobox + lead + top sections
        pieces = []
        if out.get("infobox"):
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

        if out.get("lead"):
            pieces.append("CONTENT:\n" + out.get("lead"))
            print(f"[wikipedia_service] extract_wikipedia: lead length={len(out.get('lead') or '')}")

        if sections:
            try:
                top = []
                c =0
                for title, body in sections.items():
                    top.append(f"{title}:\n{body}")
                    c +=1
                    if c >=2:
                        break
                if top:
                    pieces.append("SECTIONS:\n" + "\n\n".join(top))
            except Exception:
                pass

        if not pieces and html:
            body_text = _strip_html(html)[:2000]
            if body_text:
                pieces.append(body_text)

        if pieces:
            pieces.append(f"(Source: {url})")
            out_text = "\n\n---\n\n".join(pieces)
            print(f"[wikipedia_service] extract_wikipedia: out_text length={len(out_text)}")
        else:
            out_text = f"Source: {url}"

        out["text"] = out_text
        return out
    except Exception as e:
        print(f"[wikipedia_service] extract_wikipedia failed for {url}: {e}")
        return None
