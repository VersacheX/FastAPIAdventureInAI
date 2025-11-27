"""Extractor for costumerealm.com article pages.

Returns a dict with keys: 'html', 'text', 'data' when available.
This focuses on extracting the article `entry-content` block, the title,
meta description, images and named sections (h2/h3 headings).
"""
from typing import Optional, Dict, Any, List
import re
from ai.services.http_service import fetch_html, _strip_html


async def extract_costumerealm(url: str) -> Optional[Dict[str, Any]]:
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
            m = re.search(r'<h1[^>]*class=["\']?entry-title["\']?[^>]*>(.*?)</h1>', html, re.I | re.S)
        if not m:
            m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
        if m:
            title = re.sub(r"\s+", " ", m.group(1)).strip()

        # Meta description
        meta_desc = None
        m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html, re.I)
        if not m:
            m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.I)
        if m:
            meta_desc = re.sub(r"\s+", " ", m.group(1)).strip()

        # Images (prefer og:image then images inside entry-content)
        images: List[str] = []
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
        if m:
            images.append(m.group(1).strip())

        # images inside entry-content
        for match in re.finditer(r'<div[^>]+class=["\']?entry-content["\']?[^>]*>([\s\S]*?)</div>', html, re.I | re.S):
            block = match.group(1)
            for im in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', block, re.I):
                src = im.group(1).strip()
                if src:
                    images.append(src)

        # dedupe order-preserving
        seen = set()
        uniq_images: List[str] = []
        for i in images:
            if i and i not in seen:
                seen.add(i)
                uniq_images.append(i)

        # Extract entry-content block
        entry_html = None
        m = re.search(r'<div[^>]+class=["\']?entry-content["\']?[^>]*>([\s\S]*?)</div>\s*<div[^>]+class=["\']?fl-module', html, re.I | re.S)
        if not m:
            m = re.search(r'<div[^>]+class=["\']?entry-content["\']?[^>]*>([\s\S]*?)</div>', html, re.I | re.S)
        if m:
            entry_html = m.group(1)

        lead_text = None
        sections: Dict[str, str] = {}

        if entry_html:
            # collect first series of <p> tags as lead
            lead_pars: List[str] = []
            for p in re.finditer(r'<p[^>]*>([\s\S]*?)</p>', entry_html, re.I | re.S):
                txt = _strip_html(p.group(1))
                if txt:
                    lead_pars.append(txt)
                if len(lead_pars) >=3:
                    break
            if lead_pars:
                lead_text = "\n\n".join(lead_pars)

            # find headings and their following paragraphs
            node_re = re.compile(r'(<h[2-4][^>]*>[\s\S]*?</h[2-4]>)|(<p[^>]*>[\s\S]*?</p>)', re.I | re.S)
            current_title = None
            section_paras: Dict[str, List[str]] = {}
            # lead_pars already collected earlier from top <p> tags; continue adding up to3
            for m2 in node_re.finditer(entry_html):
                heading = m2.group(1)
                paragraph = m2.group(2)
                if heading:
                    # extract heading text and start a new section
                    ht = re.sub(r'<[^>]+>', '', heading)
                    ht = re.sub(r'\s+', ' ', ht).strip()
                    current_title = ht
                    if current_title and current_title not in section_paras:
                        section_paras[current_title] = []
                elif paragraph:
                    ptext = _strip_html(paragraph)
                    if not ptext:
                        continue
                    if current_title is None:
                        # still part of the lead/introduction
                        if ptext not in lead_pars and len(lead_pars) <3:
                            lead_pars.append(ptext)
                    else:
                        # append paragraph to the current section
                        section_paras.setdefault(current_title, []).append(ptext)
            # rebuild lead_text from collected lead_pars
            if lead_pars:
                lead_text = "\n\n".join(lead_pars)

            # join section paragraphs
            for t, paras in section_paras.items():
                if paras:
                    sections[t] = "\n\n".join(paras)[:2000]

        # fallback: if no entry_html, strip whole page body for text
        full_text = _strip_html(entry_html) if entry_html else _strip_html(html)

        # Build best text to return: prefer lead+sections assembled, else meta_desc, else full_text preview
        pieces: List[str] = []
        if title:
            pieces.append(f"Title: {title}")
        if meta_desc:
            pieces.append(f"MetaDescription: {meta_desc}")
        if lead_text:
            pieces.append(f"Lead:\n{lead_text}")
        if sections:
            # include up to first3 sections
            count =0
            for k, v in sections.items():
                pieces.append(f"{k}:\n{v[:800]}")
                count +=1
                if count >=3:
                    break
        if not pieces and full_text:
            pieces.append(full_text[:2000])

        out_text = "\n\n---\n\n".join(pieces)

        data: Dict[str, Any] = {
            "title": title,
            "meta_description": meta_desc,
            "lead": lead_text,
            "full_text": full_text,
        }
        # Build simplified return structure: html, sections, text
        # Ensure images are not embedded into sections (images are kept separate if needed)
        return {"html": html, "sections": data, "text": out_text}

    except Exception:
        return None


__all__ = ["extract_costumerealm"]
