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
from ai.ai_helpers import perform_deep_summarize_chunk
from ai.schemas_ai_server import DeepSummarizeChunkRequest
from services.ddgs_service import ddgs_search_urls
from services.wikipedia_service import fetch_wikipedia_excerpt
import asyncio

PROMPT_INSTRUCTION = (
    "You are a concise encyclopedic describer. Given the users query come up with sourced factual information to repond to the user's query."
)

# How many top search results to include as sources
TOP_K_SOURCES =5
# Max characters to include from each excerpt to avoid exceeding AI token budget
MAX_EXCERPT_CHARS =1000

async def describe_entity_ai(name: str, current_user: User, STORY_TOKENIZER, STORY_GENERATOR) -> str:
    """Generate structured description for an entity using AI server.

    Parameters:
      name: canonical entity or world name
      sentences: cleaned source sentences
      max_sentences: cap for AI context size
      deep: use deep summarization endpoint if True
    """
    # Prepend instruction & entity line to chunk list for AI server
    chunk = PROMPT_INSTRUCTION + f"\nUser Query: {name}"

    # Minimal retrieval: call service helpers, print responses, attach sources
    try:
        print(f"[describe_entity_ai] start query={name} user={getattr(current_user,'id','unknown')}")

        urls = await ddgs_search_urls(name, limit=10)
        print(f"[describe_entity_ai] ddgs returned urls: {urls}")

        # select top-K sources
        selected_urls = (urls or [])[:TOP_K_SOURCES]
        print(f"[describe_entity_ai] selected top {len(selected_urls)} urls: {selected_urls}")

        wiki_excerpts = []
        if selected_urls:
            # fetch excerpts in parallel
            tasks = [fetch_wikipedia_excerpt(u) for u in selected_urls]
            raw_excerpts = await asyncio.gather(*tasks)
            # truncate and keep only non-empty excerpts
            for u, e in zip(selected_urls, raw_excerpts):
                if not e:
                    print(f"[describe_entity_ai] no excerpt for {u}")
                    wiki_excerpts.append(None)
                    continue
                truncated = e.strip()[:MAX_EXCERPT_CHARS]
                wiki_excerpts.append(truncated)
                print(f"[describe_entity_ai] excerpt for {u} length={len(e)} truncated_to={len(truncated)}")
        else:
            wiki_excerpts = []

        # attach only non-empty excerpts
        available = [e for e in wiki_excerpts if e]
        print(f"[describe_entity_ai] available excerpts count={len(available)}")

        if available:
            joined = "\n\n---\n\n".join(available)
            chunk += "\n\nSOURCES:\n" + joined
            print(f"[describe_entity_ai] attached SOURCES chunk length={len(joined)}")
        else:
            chunk += (
                "\n\nSources: None found. Use only the provided sources to answer. "
                "If no factual information is available for this query, respond: 'No factual information available for this query.'"
            )
            print("[describe_entity_ai] no wiki excerpts found; added fallback source instruction")
    except Exception as e:
        print(f"[describe_entity_ai] retrieval failed: {e}")

    try:
        # Log chunk size before AI call to detect token budget issues
        print("[describe_entity_ai] calling perform_deep_summarize_chunk with chunk length=" + str(len(chunk)))
        raw = await perform_deep_summarize_chunk(DeepSummarizeChunkRequest(
            chunk=chunk,
            max_tokens=400,
            previous_summary=None
        ), user=current_user, STORY_TOKENIZER=STORY_TOKENIZER, STORY_GENERATOR=STORY_GENERATOR)
        print("[describe_entity_ai] AI call returned raw keys: " + str(list(raw.keys()) if isinstance(raw, dict) else type(raw)))
        result = raw.get("summary", "")
        
        if len(result) ==0:
            raise ValueError("Empty response from AI server")

        print(f"[describe_entity_ai] summary length={len(result)}")
        # return plain text summary
        return result
    except Exception as e:
        print(f"[describe_entity_ai] error: {e}")
        return f"Error: {e}"

__all__ = ["describe_entity_ai"]
