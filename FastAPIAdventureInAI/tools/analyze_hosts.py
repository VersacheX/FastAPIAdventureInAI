"""Analyze generated DOM JSON and produce candidate selectors per host.

Reads tools/site_dumps_json/index.json and outputs tools/host_candidates.json
with suggestions for selecting title, main content, and media.
"""
import os
import json
from collections import Counter

IN_DIR = 'tools/site_dumps_json'
OUT_FILE = 'tools/host_candidates.json'


def analyze():
    index_path = os.path.join(IN_DIR, 'index.json')
    if not os.path.exists(index_path):
        print('Index not found, run generate_dom_json first')
        return

    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)

    hosts = index.get('hosts', {})
    candidates = {}

    for host, files in hosts.items():
        class_counter = Counter()
        id_counter = Counter()
        title_samples = Counter()
        h1_samples = Counter()
        candidate_blocks = Counter()

        for entry in files:
            json_path = os.path.join(IN_DIR, entry['json'])
            try:
                with open(json_path, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
            except Exception:
                continue

            for cls, cnt in data.get('class_counts', []):
                class_counter[cls] += cnt
            for idn, cnt in data.get('id_counts', []):
                id_counter[idn] += cnt
            if data.get('title'):
                title_samples[data['title']] +=1
            for h in data.get('h1', []):
                h1_samples[h] +=1
            for cb in data.get('candidate_blocks', []):
                candidate_blocks[f"{cb.get('tag')}:{cb.get('text_len')}"] +=1

        # propose selectors: top classes and ids
        top_classes = [c for c, _ in class_counter.most_common(20)]
        top_ids = [i for i, _ in id_counter.most_common(20)]
        candidates[host] = {
            'top_classes': top_classes[:10],
            'top_ids': top_ids[:10],
            'top_titles': [t for t, _ in title_samples.most_common(5)],
            'top_h1': [h for h, _ in h1_samples.most_common(5)],
            'candidate_blocks': list(candidate_blocks.most_common(10)),
        }

    with open(OUT_FILE, 'w', encoding='utf-8') as outf:
        json.dump(candidates, outf, indent=2, ensure_ascii=False)
        print(f'Wrote host candidates to {OUT_FILE}')


if __name__ == '__main__':
    analyze()
