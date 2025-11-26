"""Scan a directory of HTML dumps and produce an inventory report.

Usage:
 python tools/scan_site_dumps.py <dump_dir> [--output report.json] [--sample N]

This script walks <dump_dir> recursively, finds .html/.htm files, and for each
file collects: size, a small HTML snippet, script tag count, presence of
JSON-LD (<script type="application/ld+json">), presence of OpenGraph meta tags,
and attempts to extract a canonical/og:url to infer hostname.

Outputs a JSON report with a summary, per-file entries, and per-host aggregates.

Note: run this locally where your dumps are located (e.g., "C:\\temp\\site_html_dump").
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from urllib.parse import urlparse

EXTENSIONS = ('.html', '.htm')


def sniff_html(text, max_snippet=2048):
 """Return a small summary of the HTML text for indexing."""
 # Count script tags
 script_count = len(re.findall(r'<script\b', text, flags=re.I))

 # JSON-LD blocks
 json_ld_matches = re.findall(
 r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
 text,
 flags=re.I | re.S,
 )
 has_json_ld = bool(json_ld_matches)

 # OpenGraph / og: tags
 og_match = re.search(
 r'<meta[^>]+property=["\']og:([^"\']+)["\'][^>]*content=["\']([^"\']+)["\']',
 text,
 flags=re.I,
 )
 has_og = bool(og_match)

 og_url = None
 if has_og:
 # try to capture og:url specifically
 m = re.search(
 r'<meta[^>]+property=["\']og:url["\'][^>]*content=["\']([^"\']+)["\']',
 text,
 flags=re.I,
 )
 if m:
 og_url = m.group(1)

 # canonical link
 canonical = None
 m = re.search(
 r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
 text,
 flags=re.I,
 )
 if m:
 canonical = m.group(1)

 # title
 title = None
 m = re.search(r'<title>(.*?)</title>', text, flags=re.I | re.S)
 if m:
 title = re.sub(r"\s+", " ", m.group(1)).strip()

 snippet = text[:max_snippet]

 return {
 'script_count': script_count,
 'has_json_ld': has_json_ld,
 'json_ld_samples': json_ld_matches[:2] if has_json_ld else [],
 'has_og': has_og,
 'og_url': og_url,
 'canonical': canonical,
 'title': title,
 'snippet': snippet,
 }


def infer_hostname(og_url, canonical, text):
 """Attempt to infer hostname from og_url, canonical, or raw text."""
 for candidate in (og_url, canonical):
 if candidate:
 try:
 p = urlparse(candidate)
 if p.hostname:
 return p.hostname
 except Exception:
 pass

 # fallback: search for common host patterns in text
 m = re.search(r'https?://([\w.-]+)', text)
 if m:
 return m.group(1)

 return None


def scan_folder(root_path, output_path=None, sample_count=3):
 report = {
 'root': os.path.abspath(root_path),
 'total_files':0,
 'total_bytes':0,
 'files': [],
 'host_counts': {},
 }

 host_counter = Counter()

 for dirpath, dirnames, filenames in os.walk(root_path):
 for fname in filenames:
 if not fname.lower().endswith(EXTENSIONS):
 continue

 fp = os.path.join(dirpath, fname)
 try:
 size = os.path.getsize(fp)
 with open(fp, 'r', encoding='utf-8', errors='replace') as f:
 data = f.read()
 except Exception as e:
 print(f"Failed to read {fp}: {e}", file=sys.stderr)
 continue

 info = sniff_html(data)
 hostname = infer_hostname(info.get('og_url'), info.get('canonical'), data)
 if hostname:
 host_counter[hostname] +=1

 report['files'].append({
 'path': os.path.relpath(fp, root_path),
 'size_bytes': size,
 'script_count': info['script_count'],
 'has_json_ld': info['has_json_ld'],
 'has_og': info['has_og'],
 'title': info['title'],
 'hostname': hostname,
 'snippet': info['snippet'][:1024],
 })
 report['total_files'] +=1
 report['total_bytes'] += size

 report['host_counts'] = dict(host_counter.most_common())

 # sort files by size desc for largest files
 report['largest_files'] = sorted(report['files'], key=lambda x: x['size_bytes'], reverse=True)[:20]

 # Recommend candidates: hosts without existing extractors (best-effort)
 host_features = {}
 for f in report['files']:
 h = f.get('hostname') or 'unknown'
 hf = host_features.setdefault(h, {'count':0, 'json_ld':0, 'og':0, 'script_heavy':0, 'samples': []})
 hf['count'] +=1
 if f['has_json_ld']:
 hf['json_ld'] +=1
 if f['has_og']:
 hf['og'] +=1
 if f['script_count'] >5:
 hf['script_heavy'] +=1
 if len(hf['samples']) < sample_count:
 hf['samples'].append({'path': f['path'], 'title': f['title']})

 report['hosts'] = host_features

 if output_path:
 try:
 with open(output_path, 'w', encoding='utf-8') as out:
 json.dump(report, out, indent=2, ensure_ascii=False)
 print(f"Report written to {output_path}")
 except Exception as e:
 print(f"Failed to write report to {output_path}: {e}", file=sys.stderr)
 else:
 print(json.dumps(report, indent=2, ensure_ascii=False))

 return report


if __name__ == '__main__':
 parser = argparse.ArgumentParser(description='Scan HTML dump directory and produce inventory report')
 parser.add_argument('dump_dir', help='Path to directory containing HTML dump files')
 parser.add_argument('--output', '-o', help='Path to write JSON report', default='site_dumps_report.json')
 parser.add_argument('--sample', '-s', help='Number of samples per host', type=int, default=3)
 args = parser.parse_args()

 if not os.path.isdir(args.dump_dir):
 print(f"Provided dump_dir is not a directory: {args.dump_dir}", file=sys.stderr)
 sys.exit(2)

 scan_folder(args.dump_dir, output_path=args.output, sample_count=args.sample)
