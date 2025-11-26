"""Shared extractor helpers.
Provides structured extraction (JSON-LD/OG), simple text-density scoring, normalization, and section weighting.
"""
import re
import sys
from bs4 import BeautifulSoup
from collections import Counter


def _make_soup(html):
    parser = 'lxml' if 'lxml' in sys.modules else 'html.parser'
    return BeautifulSoup(html, parser)


def extract_json_ld(html):
    soup = _make_soup(html)
    results = []
    for s in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        txt = s.string or s.get_text(separator=' ')
        if not txt:
            continue
        txt = txt.strip()
        if txt:
            results.append(txt)
    return results


def extract_og(html):
    soup = _make_soup(html)
    og = {}
    for m in soup.find_all('meta'):
        prop = m.get('property') or m.get('name')
        if prop and isinstance(prop, str) and prop.startswith('og:'):
            og[prop] = m.get('content')
    return og


def normalize_text(t):
    if not t:
        return None
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


# --- Scoring / weighting helpers ---

def score_text_density(el):
    """Score element by text density: longer text and fewer links => higher score."""
    text = el.get_text(separator=' ', strip=True) or ''
    text_len = len(text)
    if text_len == 0:
        return 0.0
    links = len(el.find_all('a'))
    # link density roughly links per 200 chars
    link_density = links / max(1, text_len / 200)
    score = text_len * (1 - min(0.9, link_density))
    return float(score)


def score_heading(el):
    """Boost if element contains prominent headings."""
    score = 0.0
    if el.find(['h1']):
        score += 30.0
    elif el.find(['h2']):
        score += 10.0
    return score


def score_metadata_presence(el, metas):
    """Boost if element text appears in page metadata (title, og, json-ld)."""
    text = (el.get_text(separator=' ', strip=True) or '').lower()
    score = 0.0
    # check title/og values
    for v in metas.values():
        if not v:
            continue
        if v.lower() in text:
            score += 25.0
    return score


def score_dom_location(el):
    """Prefer elements near top-level article/main or with semantic tags."""
    tag = el.name.lower() if el.name else ''
    if tag in ('article', 'main'):
        return 20.0
    if tag in ('section', 'div'):
        return 5.0
    return 0.0


def compute_section_scores(html, min_len=80):
    """Return list of candidate sections with combined weighted scores.

    Each entry: {selector (generated), score, text, text_len, reasons}
    """
    soup = _make_soup(html)
    # gather metas for metadata scoring
    metas = {}
    for m in soup.find_all('meta'):
        key = (m.get('property') or m.get('name') or m.get('itemprop'))
        if key and m.get('content'):
            metas[key.lower()] = m.get('content')
    candidates = []
    seen = 0
    # search for semantic containers first, then large divs/sections
    for el in soup.find_all(['article', 'main', 'section', 'div', 'p']):
        text = el.get_text(separator=' ', strip=True) or ''
        text_len = len(text)
        if text_len < min_len:
            continue
        # compute sub-scores
        td = score_text_density(el)
        h = score_heading(el)
        mscore = score_metadata_presence(el, metas)
        loc = score_dom_location(el)
        # class/id frequency heuristic: prefer elements with id or popular class names
        cls = ' '.join(el.get('class') or [])
        idv = el.get('id') or ''
        class_bonus = 5.0 if cls else 0.0
        id_bonus = 8.0 if idv else 0.0
        total = td * 0.6 + h * 1.0 + mscore * 0.8 + loc * 0.5 + class_bonus + id_bonus
        # produce a simple selector for identification (tag + id or classes)
        selector = el.name
        if idv:
            selector += f"#{idv}"
        elif cls:
            # use first class
            selector += f".{(cls.split()[0])}"
        reasons = {
            'text_density': td,
            'heading': h,
            'meta_match': mscore,
            'dom_location': loc,
            'class_bonus': class_bonus,
            'id_bonus': id_bonus,
        }
        candidates.append({
            'selector': selector,
            'score': float(total),
            'text': text[:2000],
            'text_len': text_len,
            'reasons': reasons,
        })
        seen += 1
    # sort by score desc
    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates


def assemble_weighted_output(sections, prefer_structured=None):
    """Aggregate section candidates into normalized fields with confidences.

    sections: output from compute_section_scores
    prefer_structured: dict from JSON-LD or OG to prefer
    Returns dict with fields: title, description, content, confidence, sources
    """
    out = {'title': None, 'description': None, 'content': None, 'confidence': 0.0, 'sources': []}
    if prefer_structured:
        # if structured contains a headline/name use it with high confidence
        h = prefer_structured.get('headline') or prefer_structured.get('name') or prefer_structured.get('title')
        if h:
            out['title'] = normalize_text(h)
            out['confidence'] = max(out['confidence'], 0.95)
            out['sources'].append({'type': 'structured', 'confidence': 0.95})
    if sections:
        best = sections[0]
        # fill missing fields
        if not out['title']:
            # try to extract H1 from reasons text heuristically
            out['title'] = normalize_text(best['text'].split('\n')[0][:200])
            out['confidence'] = max(out['confidence'], min(0.9, best['score'] / 1000))
            out['sources'].append({'type': 'section', 'selector': best['selector'], 'score': best['score']})
        # description: first 1-2 sentences
        desc = re.split(r'(?<=[.!?])\s+', best['text'])
        if desc:
            out['description'] = normalize_text(' '.join(desc[:2]))
            out['content'] = best['text']
            out['confidence'] = max(out['confidence'], min(0.9, best['score'] / 1000))
    return out
