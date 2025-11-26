"""Generate compact DOM JSON for each HTML dump.

Writes files under: tools/site_dumps_json/<hostname>/<original_filename>.json
Also writes an index: tools/site_dumps_json/index.json

Uses BeautifulSoup if installed; otherwise falls back to lightweight regex extraction.
Run locally: python tools/generate_dom_json.py <dump_dir> --out tools/site_dumps_json
"""
import os
import sys
import json
import re
from collections import Counter
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except Exception:
    _HAS_BS4 = False


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def extract_with_bs4(html):
    soup = BeautifulSoup(html, "lxml") if "lxml" in sys.modules else BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    metas = {}
    for m in soup.find_all('meta'):
        # consider name, property, itemprop
        key = m.get('property') or m.get('name') or m.get('itemprop')
        if key:
            metas[key.lower()] = m.get('content')

    json_ld = []
    for s in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        txt = s.string or s.get_text(separator=' ')
        txt = txt.strip()
        if txt:
            json_ld.append(txt)

    h1 = [h.get_text(strip=True) for h in soup.find_all('h1')][:3]
    h2 = [h.get_text(strip=True) for h in soup.find_all('h2')][:5]

    # collect top candidate blocks: find elements with id/class and text-length
    candidates = []
    for el in soup.find_all(True):
        cls = ' '.join(el.get('class') or [])
        elid = el.get('id')
        text = el.get_text(separator=' ', strip=True)
        if not text:
            continue
        tl = len(text)
        if tl <40:
            continue
        candidates.append({'tag': el.name, 'id': elid, 'class': cls, 'text_len': tl})

    # sort candidates by text_len desc and take top10
    candidates = sorted(candidates, key=lambda x: x['text_len'], reverse=True)[:10]

    # collect frequent classes/ids
    class_counter = Counter()
    id_counter = Counter()
    for el in soup.find_all(True):
        for c in el.get('class') or []:
            class_counter[c] +=1
        if el.get('id'):
            id_counter[el.get('id')] +=1

    return {
        'title': title,
        'metas': metas,
        'json_ld_samples': json_ld[:3],
        'h1': h1,
        'h2': h2,
        'candidate_blocks': candidates,
        'class_counts': class_counter.most_common(30),
        'id_counts': id_counter.most_common(30),
    }


def extract_with_regex(html):
    # fallback minimal extraction
    title = None
    m = re.search(r'<title>(.*?)</title>', html, flags=re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()

    metas = {}
    for tag_m in re.finditer(r'<meta[^>]+>', html, flags=re.I):
        tag = tag_m.group(0)
        name = re.search(r'name=["\']([^"\']+)["\']', tag, flags=re.I)
        prop = re.search(r'property=["\']([^"\']+)["\']', tag, flags=re.I)
        content = re.search(r'content=["\']([^"\']+)["\']', tag, flags=re.I)
        key = None
        if prop:
            key = prop.group(1)
        elif name:
            key = name.group(1)
        if key and content:
            metas[key.lower()] = content.group(1)

    json_ld = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, flags=re.I | re.S)
    h1 = [re.sub(r"\s+", " ", t).strip() for t in re.findall(r'<h1[^>]*>(.*?)</h1>', html, flags=re.I | re.S)][:3]
    h2 = [re.sub(r"\s+", " ", t).strip() for t in re.findall(r'<h2[^>]*>(.*?)</h2>', html, flags=re.I | re.S)][:5]

    # candidate blocks: large <p> or <div>
    candidates = []
    for tagname in ('p', 'div', 'article'):
        for t in re.findall(rf'<{tagname}[^>]*>(.*?)</{tagname}>', html, flags=re.I | re.S):
            txt = re.sub(r'<[^>]+>', '', t)
            txt = re.sub(r"\s+", " ", txt).strip()
            if len(txt) >120:
                candidates.append({'tag': tagname, 'text_len': len(txt)})

    candidates = sorted(candidates, key=lambda x: x['text_len'], reverse=True)[:10]

    # class/id counts
    class_counter = Counter(re.findall(r'class=["\']([^"\']+)["\']', html, flags=re.I))
    id_counter = Counter(re.findall(r'id=["\']([^"\']+)["\']', html, flags=re.I))

    return {
        'title': title,
        'metas': metas,
        'json_ld_samples': json_ld[:3],
        'h1': h1,
        'h2': h2,
        'candidate_blocks': candidates,
        'class_counts': class_counter.most_common(30),
        'id_counts': id_counter.most_common(30),
    }


def generate(dump_dir, out_dir='tools/site_dumps_json'):
    ensure_dir(out_dir)
    index = {}
    total =0
    for root, dirs, files in os.walk(dump_dir):
        for fname in files:
            if not fname.lower().endswith(('.html', '.htm')):
                continue
            total +=1
            fp = os.path.join(root, fname)
            rel = os.path.relpath(fp, dump_dir)
            with open(fp, 'r', encoding='utf-8', errors='replace') as f:
                html = f.read()

            # attempt to infer hostname
            host = None
            m = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]*content=["\']([^"\']+)["\']', html, flags=re.I)
            if m:
                try:
                    host = urlparse(m.group(1)).hostname
                except Exception:
                    host = None
            if not host:
                m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, flags=re.I)
                if m:
                    try:
                        host = urlparse(m.group(1)).hostname
                    except Exception:
                        host = None
            if not host:
                m = re.search(r'https?://([\w.-]+)', html)
                if m:
                    host = m.group(1)
            host = host or 'unknown'

            out_host_dir = os.path.join(out_dir, host)
            ensure_dir(out_host_dir)
            try:
                if _HAS_BS4:
                    data = extract_with_bs4(html)
                else:
                    data = extract_with_regex(html)
            except Exception:
                data = extract_with_regex(html)

            data.update({'source_path': rel, 'hostname': host})
            out_file = os.path.join(out_host_dir, fname + '.json')
            with open(out_file, 'w', encoding='utf-8') as o:
                json.dump(data, o, indent=2, ensure_ascii=False)
            index.setdefault(host, []).append({'path': rel, 'json': os.path.relpath(out_file, out_dir)})

    # write index
    with open(os.path.join(out_dir, 'index.json'), 'w', encoding='utf-8') as idxf:
        json.dump({'total_files': total, 'hosts': index}, idxf, indent=2, ensure_ascii=False)
    print(f"Wrote DOM JSON for {total} files to {out_dir}")


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Generate DOM JSON for HTML dumps')
    p.add_argument('dump_dir', help='Directory with HTML dumps')
    p.add_argument('--out', '-o', default='tools/site_dumps_json', help='Output directory')
    args = p.parse_args()
    if not os.path.isdir(args.dump_dir):
        print('dump_dir not found:', args.dump_dir, file=sys.stderr)
        sys.exit(2)
    generate(args.dump_dir, args.out)
