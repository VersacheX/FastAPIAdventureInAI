"""Domain-aware content extractor factory.

Provides a simple registry that maps URL host patterns to extractor callables.
Each extractor is an `async function(url) -> Optional[dict]` that returns
both the raw HTML and a plaintext extraction for downstream consumers.

This lets callers choose a specialized parser for known domains (Wikipedia,
Fandom, product sites) and fall back to a generic HTML text extractor.
"""
from typing import Callable, Awaitable, Optional, List, Tuple, Dict, Any
import re
import json
from urllib import parse

from services.http_service import fetch_html, _strip_html
from services.lookup_site_services.wikipedia_service import fetch_wikipedia_excerpt, extract_wikipedia
from services.lookup_site_services.generic_html_service import extract_generic_html
from services.lookup_site_services.halloweencostumes_service import extract_halloweencostumes
from services.lookup_site_services.fandom_service import extract_fandom
from services.lookup_site_services.gluwee_service import extract_gluwee_physical_section
from services.lookup_site_services.fanlore_service import extract_fanlore
from services.lookup_site_services.animecharacters_service import extract_animecharacters
from services.lookup_site_services.costumerealm_service import extract_costumerealm
from services.lookup_site_services.leagueoflegends_service import extract_leagueoflegends_champion
from services.lookup_site_services.lol_wiki_service import extract_lol_wiki
from services.lookup_site_services.product_page_service import extract_product_page

Extractor = Callable[[str], Awaitable[Optional[Dict[str, Any]]]]

# Registry of (compiled_pattern, extractor)
_REGISTRY: List[Tuple[re.Pattern, Extractor]] = []

def register(pattern: str, extractor: Extractor) -> None:
    """Register an extractor for hostnames matching the given regex pattern."""
    _REGISTRY.append((re.compile(pattern, re.I), extractor))

# register known extractors
# Wikipedia family -> use the dedicated wikipedia_service extractor (wrapped)
register(r"(^|\.)wikipedia\.org$", extract_wikipedia)
# Fandom/Wikia -> use the specialized fandom extractor
register(r"(^|\.)fandom\.com$", extract_fandom)
register(r"(^|\.)wikia\.com$", extract_fandom)
# Fanlore wiki
register(r"(^|\.)fanlore\.org$", extract_fanlore)
# Gluwee biography pages (example: www.gluwee.com/<name>/)
register(r"(^|\.)gluwee\.com$", extract_gluwee_physical_section)
# AnimeCharactersDatabase character pages
register(r"(^|\.)animecharactersdatabase\.com$", extract_animecharacters)
# Common e-commerce/product sites - use product extractor
register(r"(^|\.)amazon\.com$", extract_product_page)
register(r"(^|\.)walmart\.com$", extract_product_page)
register(r"(^|\.)partycity\.com$", extract_product_page)
register(r"(^|\.)halloweencostumes\.com$", extract_halloweencostumes)
register(r"(^|\.)spirithalloween\.com$", extract_product_page)
register(r"(^|\.)by-the-sword\.com$", extract_product_page)
register(r"(^|\.)eyecandys\.com$", extract_product_page)
# costumerealm articles are richer — use specialized extractor (register only specialized)
register(r"(^|\.)costumerealm\.com$", extract_costumerealm)
# Community-run wiki (weirdgloop host) for League of Legends — prefer targeted extractor
register(r"(^|\.)wiki\.leagueoflegends\.com$", extract_lol_wiki)
# Riot Games champion pages
register(r"(^|\.)leagueoflegends\.com$", extract_leagueoflegends_champion)


def get_extractor_for_url(url: str) -> Extractor:
    """Return the best-matching extractor for `url`.

    Falls back to the enriched generic HTML extractor if no pattern matches.
    """
    host = parse.urlparse(url).hostname or ""
    for pattern, extractor in _REGISTRY:
        if pattern.search(host):
            return extractor
    return extract_generic_html
