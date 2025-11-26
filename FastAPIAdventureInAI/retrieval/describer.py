"""AI-driven entity/world description generation.

Uses existing AI server summarize endpoints to transform raw lore sentences
into a structured JSON description with the following keys:
 appearance: physical traits (face, hair, build, distinguishing marks)
 clothing: typical attire / notable outfit elements
 personality: temperament, motivations, behavioral traits
 skills: abilities, powers, combat / professional strengths
 overview: concise high-level summary sentence or two
Fallback behavior: if AI server call fails, returns heuristic extraction.
"""
from business.models import User
from ai.ai_helpers import perform_deep_summarize_chunk, get_user_ai_settings
from ai.schemas_ai_server import DeepSummarizeChunkRequest
from services.ddgs_service import ddgs_search_urls
from services.extractor_factory import get_extractor_for_url
from services.http_service import _strip_html
from services.lookup_site_services.html_store import save_html
from urllib import parse
import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

PROMPT_INSTRUCTION = (
 "You are a concise describer.\n"
 "You are responsible for using the sourced information as well as meta data to come up with a good reponse to the user's query.\n"
 "Paraphrase sources instead of quoting them.\n"
 "If the query asks for creativity, merge the concept with sourced resources.\n"
 "Do not repeat meta data, but use it for context."
)

# How many top search results to include as sources
TOP_K_SOURCES =50
# Max characters to include from each excerpt to avoid exceeding AI token budget
MAX_EXCERPT_CHARS =1000
# How many characters of the original excerpt to include in logs for inspection
EXCERPT_LOG_PREVIEW =1000

# Domains we prioritize for richer extraction and their weight
PRIORITY_WEIGHTS = {
 "fandom.com":4,
 "gluwee.com":5,
 "wikipedia.org":4,
}

# How many tokens to request for the summarization generation (per-call configurable)
MAX_SUMMARY_TOKENS =800


def _get_priority_weight(hostname: str) -> int:
    if not hostname:
        return 1
    for d, w in PRIORITY_WEIGHTS.items():
        if hostname.endswith(d):
            return w
    return 1


# Map weight to default excerpt length
def _allowed_chars_for_weight(weight: int) -> int:
    if weight >=3:
        # give Wikipedia (weight4) a bit more budget
        return MAX_EXCERPT_CHARS +200 if weight >=4 else MAX_EXCERPT_CHARS
    if weight ==2:
        return 700
    return 300


async def describe_entity_ai(
    name: str,
    current_user: User,
    STORY_TOKENIZER,
    STORY_GENERATOR,
    command_prompt: Optional[str] = None,
    meta_data: Optional[str] = None,
) -> str:
    """Generate structured description for an entity using AI server.

    Parameters:
    name: canonical entity or world name
    sentences: cleaned source sentences
    max_sentences: cap for AI context size
    deep: use deep summarization endpoint if True
    command_prompt: optional user-specified instruction to shape the AI response
    """
    # Prepend instruction & entity line to chunk list for AI server
    chunk = ""

    # Minimal retrieval: call service helpers, print responses, attach sources
    try:
        urls = await ddgs_search_urls(name, limit=50)
        # select top-K sources
        selected_urls = (urls or [])[:TOP_K_SOURCES]

        # collect tuples of (weight, text)
        collected = []
        seen_texts = set()
        analysis_items = [] # For source analysis logging

        # detect if user query requests specific section groups (e.g. appearance, personality)
        query_text = (command_prompt or name or "").lower()
        SECTION_KEYWORDS = [
            "appearance",
            "physical",
            "personality",
            "story",
            "history",
            "skills",
            "ability",
            "occupation",
            "profile",
            "dimensions",
            "height",
            "weight",
            "hair",
            "eye",
        ]
        requested_section_terms = [k for k in SECTION_KEYWORDS if k in query_text]

        if selected_urls:
            # categorize urls by priority and prepare tasks
            tasks = []
            meta = [] # parallel list of (url, weight)
            for u in selected_urls:
                extractor = get_extractor_for_url(u)
                hostname = parse.urlparse(u).hostname or ""
                weight = _get_priority_weight(hostname)
                tasks.append(extractor(u))
                meta.append((u, weight))

            raw_excerpts = await asyncio.gather(*tasks, return_exceptions=True)

            logger.info(f"[describe_entity_ai] retrieved {len(raw_excerpts)} excerpts for entity '{name}' from {len(selected_urls)} URLs")
            # Metrics for logging
            metrics = {
                "processed":0,
                "by_weight": {},
                "failures":0,
                "empties":0,
                "html_saved":0,
                "snippets_collected":0,
                "duplicates":0,
                "parts_used": {"infobox":0, "sections":0, "text":0, "html":0},
                "total_excerpt_chars":0,
                "max_excerpt_chars":0,
            }

            # truncate and keep only non-empty excerpts
            for (u, weight), e in zip(meta, raw_excerpts):
                logger.info(f"[describe_entity_ai] processing excerpt for url={u} weight={weight} type={type(e)}")
                metrics["processed"] +=1
                metrics["by_weight"][weight] = metrics["by_weight"].get(weight,0) +1

                if isinstance(e, Exception):
                    snippet = f"Source: {u} (failed to fetch excerpt)"
                    collected.append((weight, snippet))
                    metrics["failures"] +=1
                    try:
                        logger.info(f"[describe_entity_ai][metrics] fail fetch url={u} weight={weight} err={e}")
                    except Exception:
                        pass
                    analysis_items.append({
                        "url": u,
                        "weight": weight,
                        "status": "failed",
                        "excerpt_length":0,
                        "available_sections": [],
                        "used_sections": [],
                        "parts": [],
                    })
                    continue
                if not e:
                    collected.append((weight, f"Source: {u}"))
                    metrics["empties"] +=1
                    try:
                        logger.info(f"[describe_entity_ai][metrics] empty excerpt url={u} weight={weight}")
                    except Exception:
                        pass
                    analysis_items.append({
                        "url": u,
                        "weight": weight,
                        "status": "empty",
                        "excerpt_length":0,
                        "available_sections": [],
                        "used_sections": [],
                        "parts": [],
                    })
                    continue

                # Support extractors returning a dict with 'html' and 'text'
                html = None
                text = None
                sections = None
                infobox = None
                available_section_titles = []
                if isinstance(e, dict):
                    html = e.get("html")
                    text = e.get("text")
                    sections = e.get("sections")
                    infobox = e.get("infobox")
                    logger.info(f"[describe_entity_ai] excerpt for {u} has text_len={len(text) if text else 0} html_len={len(html) if html else 0} sections={list(sections.keys()) if sections else None} infobox_items={len(infobox) if infobox else 0}")
                    try:
                        if isinstance(sections, dict):
                            available_section_titles = list(sections.keys())
                    except Exception:
                        available_section_titles = []
                else:
                    # legacy: treat e as text
                    text = str(e)

                logger.info(f"[describe_entity_ai] processing excerpt for url={u} weight={weight} text_len={len(text) if text else 0} html_len={len(html) if html else 0}")

                # Decide which original content to preview in logs
                original_for_preview = text or (html or "")
                try:
                    preview = original_for_preview[:EXCERPT_LOG_PREVIEW].replace("\n", " ")
                except Exception:
                    preview = ""

                # print(f"[describe_entity_ai] original excerpt for {u} length={len(original_for_preview)} preview={preview!r}")

                # If HTML is available, save it to disk instead of printing
                if html:
                    try:
                        hostname = parse.urlparse(u).hostname or "unknown"
                        saved_path = save_html(hostname, u, html, headers=None)
                        # print(f"[describe_entity_ai] saved HTML for {u} -> {saved_path}")
                        metrics["html_saved"] +=1
                        logger.info(f"[describe_entity_ai] saved HTML for {u} -> {saved_path}")
                    except Exception as ex_save:
                        logger.info(f"[describe_entity_ai] failed to save HTML for {u}: {ex_save}")

                # Build chosen excerpt depending on weight
                allowed = _allowed_chars_for_weight(weight)
                chosen = ""

                # bookkeeping for analysis: which parts we used
                parts_from = []
                used_section_titles = []

                logger.info(f"[describe_entity_ai] building excerpt for url={u} weight={weight} allowed_chars={allowed}")
                if weight >=3:
                    # High-priority: include infobox and selected sections if available
                    parts = []
                    if infobox and isinstance(infobox, dict):
                        try:
                            items = []
                            for i, (k, v) in enumerate(infobox.items()):
                                items.append(f"{k}: {v}")
                                if i >=7:
                                    break
                            if items:
                                parts.append("INFOBOX:\n" + "; ".join(items))
                                parts_from.append("infobox")
                        except Exception:
                            pass
                    # If the user requested specific section keywords, prefer those sections
                    if sections and isinstance(sections, dict):
                        try:
                            sec_parts = []
                            count =0
                            # Build ordered candidate list; prefer matches to requested_section_terms
                            candidates = list(sections.items())
                            if requested_section_terms:
                                filtered = []
                                for title, body in candidates:
                                    tl = title.lower()
                                    for term in requested_section_terms:
                                        if term in tl:
                                            filtered.append((title, body))
                                            break
                                if filtered:
                                    candidates = filtered
                            for title, body in candidates:
                                sec_parts.append(f"{title}:\n{body}")
                                used_section_titles.append(title)
                                count +=1
                                if count >=3:
                                    break

                            if sec_parts:
                                parts.append("SECTIONS:\n" + "\n\n".join(sec_parts))
                                parts_from.append("sections")
                        except Exception:
                            pass
                    # Include plain text lead/body only if we didn't already include sections
                    if not parts and text and len(text) >100:
                        parts.append(text)
                        parts_from.append("text")
                    chosen = "\n\n---\n\n".join(parts)[:allowed]

                elif weight ==2:
                    logger.info(f"[describe_entity_ai] medium priority excerpt for url={u} weight={weight} allowed_chars={allowed}")
                    # Medium priority: prefer text + one section
                    parts = []
                    if text:
                        parts.append(text[:allowed])
                        parts_from.append("text")
                    elif html:
                        parts.append(_strip_html(html)[:allowed])
                        parts_from.append("html")
                    if sections and isinstance(sections, dict):
                        # add first matching section (prefer requested_section_terms), else first section
                        try:
                            first_title = None
                            if requested_section_terms:
                                for title in sections.keys():
                                    tl = title.lower()
                                    for term in requested_section_terms:
                                        if term in tl:
                                            first_title = title
                                            break
                            if first_title:
                                parts.append(f"{first_title}:\n{sections[first_title][:400]}")
                                used_section_titles.append(first_title)
                                parts_from.append("sections")
                            else:
                                first_title = next(iter(sections.keys()))
                                parts.append(f"{first_title}:\n{sections[first_title][:400]}")
                                used_section_titles.append(first_title)
                                parts_from.append("sections")
                        except Exception:
                            pass
                    chosen = "\n\n---\n\n".join(parts)[:allowed]

                else:
                    logger.info(f"[describe_entity_ai] low priority excerpt for url={u} weight={weight} allowed_chars={allowed}")
                    # Low-priority: short snippet
                    source_text = text or (html and _strip_html(html)) or ""
                    chosen = (source_text or "")[:allowed]
                    if text:
                        parts_from.append("text")
                    elif html:
                        parts_from.append("html")

                # Print a short preview of the chosen snippet for easier troubleshooting (for all weights)
                try:
                    preview_snip = (chosen or "")[:200].replace("\n", " ")
                except Exception:
                    preview_snip = ""
                # also print progress index if possible
                try:
                    # attempt to show current processed count using metrics
                    proc = metrics.get("processed", "?")
                    total = len(selected_urls)
                    print(f"[describe_entity_ai][SNIPPET] #{proc}/{total} url={u} weight={weight} preview={preview_snip!r} parts_from={parts_from} used_sections={used_section_titles}")
                except Exception:
                    print(f"[describe_entity_ai][SNIPPET] url={u} weight={weight} preview={preview_snip!r} parts_from={parts_from} used_sections={used_section_titles}")

                # de-duplicate similar snippets
                key = chosen.strip()
                if key:
                    # duplicate check
                    if key in seen_texts:
                        metrics["duplicates"] +=1
                        try:
                            logger.info(f"[describe_entity_ai][metrics] duplicate skipped url={u} weight={weight} excerpt_len={len(key)}")
                        except Exception:
                            pass
                    else:
                        # new unique snippet
                        seen_texts.add(key)
                        if chosen:
                            collected.append((weight, f"{chosen}\n\n(Source: {u})"))
                            excerpt_len = len(key)
                            metrics["snippets_collected"] +=1
                            metrics["total_excerpt_chars"] += excerpt_len
                            if excerpt_len > metrics["max_excerpt_chars"]:
                                metrics["max_excerpt_chars"] = excerpt_len
                        else:
                            # no chosen text, record source placeholder
                            collected.append((weight, f"Source: {u}"))
                            metrics["empties"] +=1
                else:
                    # completely empty excerpt
                    collected.append((weight, f"Source: {u}"))
                    metrics["empties"] +=1
                    try:
                        logger.info(f"[describe_entity_ai][metrics] no chosen text url={u} weight={weight}")
                    except Exception:
                        pass
                    analysis_items.append({
                        "url": u,
                        "weight": weight,
                        "status": "empty_excerpt",
                        "excerpt_length":0,
                        "parts": parts_from,
                        "available_sections": available_section_titles,
                        "used_section_titles": used_section_titles,
                    })
        else:
            collected = []

        # sort collected to descending order by weight (higher priority first)
        collected.sort(key=lambda x: -int(x[0]))

        # Attach only non-empty excerpts but enforce token budget
        try:
            settings = get_user_ai_settings(current_user.id) if current_user else {}
        except Exception:
            settings = {}

        safe_limit = settings.get("SAFE_PROMPT_LIMIT",3900)
        # Ensure we reserve at least the per-call summary/generation tokens
        reserved_for_output = MAX_SUMMARY_TOKENS
        # leave a small reserve for safety
        margin =50

        # Build header that will always be sent after sources so we can count its tokens
        logger.info(f"[describe_entity_ai] reserving {reserved_for_output} tokens for generation (max_summary_tokens={MAX_SUMMARY_TOKENS})")
        user_query_line = command_prompt.strip() if command_prompt and command_prompt.strip() else name
        header_text = (
        f"\n\n# Describer Prompt:\n{PROMPT_INSTRUCTION}\n\n"
        f"# User included Metadata:\n{meta_data}\n\n"
        f"User Query: {user_query_line}\n"
        )

        try:
            header_tokens = len(STORY_TOKENIZER.encode(header_text))
        except Exception:
            header_tokens = int(len(header_text) /4)

        # tokens available for source excerpts
        available_tokens = max(0, safe_limit - reserved_for_output - margin - header_tokens)

        logger.info(f"[describe_entity_ai] token budget: safe_limit={safe_limit} reserved_for_output={reserved_for_output} margin={margin} header_tokens={header_tokens} -> available_tokens={available_tokens}")
        logger.info(f"[describe_entity_ai] collected snippets count={len(collected)}")

        prefix = "\n\nSOURCES:\n"
        included = []
        removed_sources = []

        def _extract_url(t: str) -> str:
        # try patterns like '(Source: url)' or 'Source: url'
            idx = t.rfind("Source:")
            if idx == -1:
                return ""
            part = t[idx + len("Source:"):].strip()
            # strip surrounding parentheses
            if part.startswith("(") and part.endswith(")"):
                part = part[1:-1].strip()
            # if contains')' cut
            if ")" in part:
                part = part.split(")")[0].strip()
            return part

        # Include excerpts until we hit token budget (collected already sorted by weight)
        for i, (weight, text) in enumerate(collected):
            if not text:
                continue
            # current prompt tokens (prefix + already included)
            current_body = prefix + "\n\n---\n\n".join(included) if included else prefix
            candidate_body = current_body + ("\n\n---\n\n" if included else "") + text
            try:
                current_tokens = len(STORY_TOKENIZER.encode(current_body))
                candidate_tokens = len(STORY_TOKENIZER.encode(candidate_body))
            except Exception:
                # fallback estimation via char count
                current_tokens = int(len(current_body) /4)
                candidate_tokens = int(len(candidate_body) /4)

            delta = max(0, candidate_tokens - current_tokens)

            # Log the token estimation for this candidate
            try:
                logger.info(f"[describe_entity_ai] candidate #{i} weight={weight} url={_extract_url(text)} current_tokens={current_tokens} candidate_tokens={candidate_tokens} delta={delta} available={available_tokens}")
            except Exception:
                logger.info(f"[describe_entity_ai] candidate #{i} weight={weight} delta={delta} available={available_tokens}")

            if delta <= available_tokens:
                included.append(text)
                available_tokens -= delta
                logger.info(f"[describe_entity_ai] INCLUDED candidate #{i} ({_extract_url(text)}) now available_tokens={available_tokens}")
            else:
                # record removed source URL for reporting
                removed_sources.append(_extract_url(text) or text[:120])
                logger.info(f"[describe_entity_ai] EXCLUDED candidate #{i} ({_extract_url(text)}) due to budget (needs {delta})")

        # Build chunk sources section
        if included:
            joined = "\n\n---\n\n".join(included)
            chunk += "\n\nSOURCES:\n" + joined
        else:
            chunk += (
                "\n\nSources: None found. Use only the provided sources to answer. "
                "If no factual information is available for this query, respond: 'No factual information available for this query.'"
            )
            logger.info("[describe_entity_ai] no wiki excerpts found; added fallback source instruction")

        # Log trimming
        if removed_sources:
            try:
                logger.info(f"[describe_entity_ai] trimmed {len(removed_sources)} sources to fit token budget: {removed_sources}")
            except Exception:
                pass
    except Exception as e:
        logger.info(f"[describe_entity_ai] retrieval failed: {e}")

    # If a command_prompt was provided, prefer it in the AI instruction section (per client request)
    user_query_line = command_prompt.strip() if command_prompt and command_prompt.strip() else name

    chunk += f"\n\n# Describer Prompt:\n{PROMPT_INSTRUCTION}"
    chunk += f"\n\n# User included Metadata:\n{meta_data}"
    chunk += f"\n\nUser Query: {user_query_line}\n"
    try:
        # Log chunk size before AI call to detect token budget issues
        #print(f"*****************************POST DATA *********************\n\n{chunk}")
        logger.info(f"[describe_entity_ai] calling deep summarize with max_tokens={MAX_SUMMARY_TOKENS}")
        raw = await perform_deep_summarize_chunk(
            DeepSummarizeChunkRequest(
                chunk=chunk,
                max_tokens=MAX_SUMMARY_TOKENS,
                previous_summary=None,
            ),
            user=current_user,
            STORY_TOKENIZER=STORY_TOKENIZER,
            STORY_GENERATOR=STORY_GENERATOR,
        )
        print("[describe_entity_ai] AI call returned raw keys: " + str(list(raw.keys()) if isinstance(raw, dict) else type(raw)))
        result = raw.get("summary", "")

        if len(result) ==0:
            raise ValueError("Empty response from AI server")

        print(f"[describe_entity_ai] summary length={len(result)}")
        # return plain text summary
        return raw
    except Exception as e:
        print(f"[describe_entity_ai] error: {e}")
        return f"Error: {e}"


__all__ = ["describe_entity_ai"]
