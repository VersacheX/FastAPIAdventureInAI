"""Lookup AI service extracted from describer.

This module provides the heavy lifting for performing retrieval of sources,
selecting relevant sections based on query terms, building the sources chunk,
and calling the AI summarization endpoint. It mirrors the original
`describe_entity_ai` behaviour but is isolated for easier testing and
composition.
"""
from typing import Optional, Dict, Any, List, Tuple
import logging
import asyncio
import re
from urllib import parse

from business.models import User
from shared.helpers.ai_settings import get_user_ai_settings
from ai.schemas_ai_server import DeepSummarizeChunkRequest
from ai.services.ai_api_service import perform_deep_summarize_chunk
from ai.services.ddgs_service import ddgs_search_urls
from ai.services.http_service import _strip_html
from ai.lookup_ai.services.html_store_service import save_html
from ai.lookup_ai.query_terms import extract_query_terms
from ai.lookup_ai.section_selector import select_sections
from ai.lookup_ai.fetch_sources import fetch_and_extract

logger = logging.getLogger(__name__)

# Configuration shared with describer
TOP_K_SOURCES = 50
MAX_EXCERPT_CHARS = 1000
EXCERPT_LOG_PREVIEW = 1000
PRIORITY_WEIGHTS = {"fandom.com": 4, "gluwee.com": 4, "wikipedia.org": 4}
MAX_SUMMARY_TOKENS = 800


def _extract_url_from_text(t: str) -> str:
    idx = t.rfind("Source:")
    if idx == -1:
        return ""
    part = t[idx + len("Source:"):].strip()
    if part.startswith("(") and part.endswith(")"):
        part = part[1:-1].strip()
    if ")" in part:
        part = part.split(")")[0].strip()
    return part


async def describe_entity_ai(
    query_text: str,
    current_user: User,
    STORY_TOKENIZER,
    STORY_GENERATOR,
    command_prompt: Optional[str] = None,
    meta_data: Optional[str] = None,
    prompt_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve sources, build a sources chunk guided by query terms, and call AI.

    Returns the raw AI response (dict) or raises an exception.
    """
    # Build query-term list (do not mutate command_prompt)
    raw_query = query_text if query_text is not None else prompt_instruction
    requested_section_terms = extract_query_terms(raw_query)

    urls = await ddgs_search_urls(query_text, limit=TOP_K_SOURCES)
    selected_urls = (urls or [])[:TOP_K_SOURCES]

    # Fetch sources using helper
    fetched = await fetch_and_extract(selected_urls, PRIORITY_WEIGHTS)

    logger.info(f"[lookup_ai_service] retrieved {len(fetched)} excerpts for '{query_text}'")

    collected: List[Tuple[int, str]] = []
    seen_texts = set()

    # Process each excerpt and prefer matching sections when possible
    for u, weight, e in fetched:
        if isinstance(e, Exception) or not e:
            # record placeholder
            collected.append((weight, f"Source: {u}"))
            continue

        html = e.get("html") if isinstance(e, dict) else None
        text = e.get("text") if isinstance(e, dict) else (str(e) if e else None)
        sections = e.get("sections") if isinstance(e, dict) else None
        infobox = e.get("infobox") if isinstance(e, dict) else None

        parts: List[str] = []
        parts_from: List[str] = []

        allowed = MAX_EXCERPT_CHARS

        # prefer infobox for high-weight
        if weight >= 3 and infobox and isinstance(infobox, dict):
            try:
                items = []
                for i, (k, v) in enumerate(infobox.items()):
                    items.append(f"{k}: {v}")
                    if i >= 7:
                        break
                if items:
                    parts.append("INFOBOX:\n" + "; ".join(items))
                    parts_from.append("infobox")
            except Exception:
                pass
        
        # If sections exist, try to find matches using normalized terms
        if sections and isinstance(sections, dict) and requested_section_terms:
            candidates = select_sections(sections, requested_section_terms, max_sections=3)
            sec_parts = [f"{t}:\n{b}" for t, b in candidates]
            if sec_parts:
                parts.append("SECTIONS:\n" + "\n\n".join(sec_parts))
                parts_from.append("sections")

        # fallback to text/html if no sections chosen
        if not parts and text and len(text) > 80:
            parts.append(text)
            parts_from.append("text")
        elif not parts and html:
            parts.append(_strip_html(html)[:allowed])
            parts_from.append("html")

        chosen = "\n\n---\n\n".join(parts)[:allowed] if parts else ""

        key = chosen.strip() or f"Source: {u}"
        if key not in seen_texts:
            seen_texts.add(key)
            collected.append((weight, f"{chosen}\n\n(Source: {u})" if chosen else f"Source: {u}"))

    # sort by weight desc
    collected.sort(key=lambda x: -int(x[0]))

    # assemble sources into chunk with token budgeting
    # Determine user settings
    try:
        settings = get_user_ai_settings(current_user.id) if current_user else {}
    except Exception:
        settings = {}
    safe_limit = settings.get("SAFE_PROMPT_LIMIT", 3900)
    reserved_for_output = MAX_SUMMARY_TOKENS
    margin = 50

    # build header_text (prompt instruction passed in or default)
    prompt_instruction = prompt_instruction or "You are a concise describer."
    user_query_line = command_prompt.strip() if command_prompt and command_prompt.strip() else name
    header_text = (
        f"\n\n# Describer Prompt:\n{prompt_instruction}\n\n"
        f"# User included Metadata:\n{meta_data}\n\n"
        f"User Query: {user_query_line}\n"
    )

    try:
        header_tokens = len(STORY_TOKENIZER.encode(header_text))
    except Exception:
        header_tokens = int(len(header_text) / 4)

    available_tokens = max(0, safe_limit - reserved_for_output - margin - header_tokens)

    prefix = "\n\nSOURCES:\n"
    included: List[str] = []
    removed_sources: List[str] = []

    for i, (weight, text) in enumerate(collected):
        if not text:
            continue
        current_body = prefix + "\n\n---\n\n".join(included) if included else prefix
        candidate_body = current_body + ("\n\n---\n\n" if included else "") + text
        try:
            current_tokens = len(STORY_TOKENIZER.encode(current_body))
            candidate_tokens = len(STORY_TOKENIZER.encode(candidate_body))
        except Exception:
            current_tokens = int(len(current_body) / 4)
            candidate_tokens = int(len(candidate_body) / 4)
        delta = max(0, candidate_tokens - current_tokens)
        if delta <= available_tokens:
            included.append(text)
            available_tokens -= delta
            logger.info(f"[lookup_ai_service] INCLUDED candidate #{i} now available_tokens={available_tokens}")
        else:
            removed_sources.append(_extract_url_from_text(text) or text[:120])

    if included:
        joined = "\n\n---\n\n".join(included)
        chunk = prefix + joined
    else:
        chunk = (
            "\n\nSources: None found. Use only the provided sources to answer. "
            "If no factual information is available for this query, respond: 'No factual information available for this query.'"
        )

    #print (removed_sources)
    # final chunk includes header
    chunk += header_text

    print(chunk)
    # call AI
    raw = await perform_deep_summarize_chunk(
        DeepSummarizeChunkRequest(chunk=chunk, max_tokens=MAX_SUMMARY_TOKENS, previous_summary=None),
        user=current_user,
        STORY_TOKENIZER=STORY_TOKENIZER,
        STORY_GENERATOR=STORY_GENERATOR,
    )
    return raw
