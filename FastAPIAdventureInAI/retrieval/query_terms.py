"""Query term extraction helpers.

Provides a single helper `extract_query_terms` which returns normalized terms
(for matching section titles) without modifying the original query text.

Behavior changed: quoted phrases are normalized by removing non-alphanumeric
characters and whitespace (no-space lowercase). Unquoted tokens are returned
as lowercase words (punctuation removed). Order is preserved and duplicates
are removed.
"""
from typing import List, Optional
import re


def extract_query_terms(query_text: Optional[str]) -> List[str]:
    if not query_text:
        return []

    terms: List[str] = []

    # Extract quoted phrases (both single and double quotes). For quoted
    # phrases we want the no-space, lowercase form: "League of Legends" -> leagueoflegends
    try:
        for m in re.finditer(r'"([^\"]+)"|\'([^\']+)\'', query_text):
            grp = m.group(1) or m.group(2)
            if grp:
                # remove non-alphanumeric characters and whitespace, lowercase
                s = re.sub(r'[^0-9a-zA-Z]+', '', grp).lower().strip()
                if s:
                    terms.append(s)
    except Exception:
        # ignore malformed regex matches
        pass

    # Remove quoted phrases from the text, then split remaining into words.
    text_no_quotes = re.sub(r'"[^\"]+"|\'[^\']+\'', ' ', query_text)
    for w in re.findall(r"[0-9A-Za-z]+", text_no_quotes):
        s = w.lower().strip()
        if s:
            terms.append(s)

    # Deduplicate preserving order
    normalized: List[str] = []
    seen = set()
    for t in terms:
        if t in seen:
            continue
        seen.add(t)
        normalized.append(t)
    return normalized
