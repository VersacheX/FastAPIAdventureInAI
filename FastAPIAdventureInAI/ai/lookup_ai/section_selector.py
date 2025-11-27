"""Section selection helpers.

Provides logic to choose which sections to include from an extractor's
`sections` dict given a list of normalized query terms.
"""
import re


def select_sections(sections, query_terms, max_sections=3):
    """Return up to `max_sections` matching (title, body) pairs.

    Matching prefers titles that contain any of the normalized query_terms
    (matching against both the title lowered and a no-space variant).
    If no query_terms are provided, selects the first `max_sections`.
    """
    if not sections:
        return []

    items = list(sections.items())
    if not query_terms:
        return items[:max_sections]

    filtered = []
    for title, body in items:
        tl = title.lower()
        tnos = re.sub(r'[^0-9a-zA-Z]', '', tl)
        for term in query_terms:
            if term in tl or term in tnos:
                filtered.append((title, body))
                break

    if filtered:
        return filtered[:max_sections]

    return items[:max_sections]
