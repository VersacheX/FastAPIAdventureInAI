"""Simple DuckDuckGo-based search service using the `ddgs` entrypoint.

This module exclusively imports `ddgs` from the installed package and
normalizes results to dicts with keys: "url", "title", "snippet".
If the local library is unavailable or returns no results we fall back to
DuckDuckGo instant-answer JSON API.
"""
from typing import List, Dict, Optional
import asyncio
import json
import types
from urllib import parse, request

try:
    # Prefer both the functional API and the class API if available
    from ddgs import ddgs, DDGS
except Exception:
    try:
        from ddgs import DDGS
        ddgs = None
    except Exception:
        ddgs = None
        DDGS = None

DUCKDUCKGO_API = "https://api.duckduckgo.com/"


def _normalize_item(item: Dict) -> Optional[Dict]:
    if not item or not isinstance(item, dict):
        return None
    # some libraries use 'href' or 'url' or 'first'
    url = item.get("url") or item.get("href") or item.get("FirstURL") or item.get("first")
    title = item.get("title") or item.get("Text") or item.get("heading") or ""
    snippet = item.get("snippet") or item.get("body") or item.get("Text") or ""
    if not url:
        return None
    return {"url": url, "title": title or "", "snippet": snippet or ""}


def ddgs_clean_query(query: str) -> str:
    if not query:
        return ""
    q = query.strip()
    q_lc = q.lower()
    for prefix in ["describe ", "what is ", "who is ", "tell me about ", "give me "]:
        if q_lc.startswith(prefix):
            q = q[len(prefix):].strip()
            break
    return q


async def _call_ddgs_lib(query: str, limit: int = 10) -> List[Dict]:
    """Call local ddgs() function or DDGS class in a thread and normalize results.

    Try DDGS().text(...) first (restores multi-result behavior), then
    probe the imported `ddgs` symbol: it may be a callable or a module.
    If it's a module, probe for common callables on it and invoke them.
    """
    if not ddgs and not globals().get('DDGS'):
        print("[ddgs_service] _call_ddgs_lib: no ddgs/DDGS available")
        return []

    def _process_raw(raw, out, seen, limit):
        try:
            # If raw is a dict containing list under common keys, extract
            if isinstance(raw, dict):
                for key in ('results', 'data', 'items'):
                    arr = raw.get(key)
                    if isinstance(arr, (list, tuple)):
                        raw = arr
                        break
            if hasattr(raw, '__iter__') and not isinstance(raw, (str, bytes, dict)):
                for r in raw:
                    if not r:
                        continue
                    n = _normalize_item(r)
                    if not n:
                        continue
                    key = (n.get('url'), n.get('title'))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(n)
                    if len(out) >= limit:
                        break
            else:
                n = _normalize_item(raw)
                if n:
                    key = (n.get('url'), n.get('title'))
                    if key not in seen:
                        seen.add(key)
                        out.append(n)
        except Exception as e:
            print(f"[ddgs_service] _process_raw error: {e}")

    def _call():
        out: List[Dict] = []
        seen = set()

        #1) Try DDGS class if available
        if globals().get('DDGS'):
            try:
                print(f"[ddgs_service] _call_ddgs_lib: trying DDGS().text(query, max_results={limit})")
                raw = DDGS().text(query, max_results=limit)
                print(f"[ddgs_service] _call_ddgs_lib: DDGS.raw type {type(raw)}")
                _process_raw(raw, out, seen, limit)
                print(f"[ddgs_service] _call_ddgs_lib: DDGS produced {len(out)} results (requested {limit})")
                # don't return immediately; if fewer than requested, continue to other attempts to fill
            except Exception as e:
                print(f"[ddgs_service] _call_ddgs_lib: DDGS call failed: {e}")

        #2) Handle `ddgs` symbol: it may be callable or a module
        if ddgs:
            # If ddgs is a module, probe for useful callables on it
            if isinstance(ddgs, types.ModuleType):
                print("[ddgs_service] _call_ddgs_lib: ddgs is module; probing attributes")
                candidates = ['ddg', 'ddgs', 'search', 'query', 'text']
                for name in candidates:
                    func = getattr(ddgs, name, None)
                    if not callable(func):
                        continue
                    try:
                        print(f"[ddgs_service] _call_ddgs_lib: calling ddgs.{name}(...)")
                        raw = func(query) if name in ('ddg', 'ddgs', 'search', 'query') else func(query, max_results=limit)
                        print(f"[ddgs_service] _call_ddgs_lib: ddgs.{name} returned type {type(raw)}")
                        _process_raw(raw, out, seen, limit)
                        if len(out) >= limit:
                            break
                    except TypeError:
                        try:
                            raw = func(query, limit)
                            _process_raw(raw, out, seen, limit)
                        except Exception as e:
                            print(f"[ddgs_service] _call_ddgs_lib: ddgs.{name} call failed: {e}")
                    except Exception as e:
                        print(f"[ddgs_service] _call_ddgs_lib: ddgs.{name} call failed: {e}")
                print(f"[ddgs_service] _call_ddgs_lib: collected {len(out)} results from ddgs module attributes")
            elif callable(ddgs):
                # ddgs is directly callable (some installs expose function)
                attempts = []
                attempts.append({'func': lambda: ddgs(query, max_results=limit), 'desc': 'ddgs(query, max_results=limit)'})
                attempts.append({'func': lambda: ddgs(query, limit=limit), 'desc': 'ddgs(query, limit=limit)'})
                attempts.append({'func': lambda: ddgs(query), 'desc': 'ddgs(query)'})

                for attempt in attempts:
                    try:
                        print(f"[ddgs_service] _call_ddgs_lib: trying {attempt['desc']}")
                        raw = attempt['func']()
                        print(f"[ddgs_service] _call_ddgs_lib: raw type {type(raw)}")
                    except TypeError as e:
                        print(f"[ddgs_service] _call_ddgs_lib: signature TypeError for {attempt['desc']}: {e}")
                        continue
                    except Exception as e:
                        print(f"[ddgs_service] _call_ddgs_lib: call failed for {attempt['desc']}: {e}")
                        continue

                    _process_raw(raw, out, seen, limit)
                    if len(out) >= limit:
                        break

        # If we still don't have enough results, return whatever we gathered
        print(f"[ddgs_service] _call_ddgs_lib: returning {len(out)} results")
        return out

    return await asyncio.to_thread(_call)


async def _fetch_json(url: str) -> Dict:
    def _get():
        with request.urlopen(url, timeout=10) as resp:
            data = resp.read()
            return json.loads(data.decode("utf-8", errors="ignore"))

    return await asyncio.to_thread(_get)


async def _instant_answer_fallback(query: str, limit: int = 10) -> List[Dict]:
    qs = {
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    }
    url = DUCKDUCKGO_API + "?" + parse.urlencode(qs)
    try:
        payload = await _fetch_json(url)
    except Exception:
        return []

    results: List[Dict] = []

    def _extract_from_topic(topic: Dict) -> Optional[Dict]:
        if not isinstance(topic, dict):
            return None
        text = topic.get("Text")
        first = topic.get("FirstURL")
        if not text or not first:
            return None
        title = text.split(" - ")[0]
        return {"url": first, "title": title, "snippet": text}

    if isinstance(payload.get("Results"), list):
        for r in payload.get("Results"):
            if len(results) >= limit:
                break
            item = _extract_from_topic(r)
            if item:
                results.append(item)

    rt = payload.get("RelatedTopics") or []
    for entry in rt:
        if len(results) >= limit:
            break
        if isinstance(entry, dict) and entry.get("FirstURL"):
            item = _extract_from_topic(entry)
            if item:
                results.append(item)
        elif isinstance(entry, dict) and entry.get("Topics"):
            for sub in entry.get("Topics"):
                if len(results) >= limit:
                    break
                item = _extract_from_topic(sub)
                if item:
                    results.append(item)

    return results[:limit]


async def ddgs_search(query: str, limit: int = 10) -> List[Dict]:
    if not query:
        return []
    q = ddgs_clean_query(query)

    # try library first
    try:
        lib_results = await _call_ddgs_lib(q, limit=limit)
        if lib_results:
            return lib_results[:limit]
    except Exception:
        pass

    # fallback
    return await _instant_answer_fallback(q, limit=limit)


async def ddgs_search_urls(query: str, limit: int = 10) -> List[str]:
    results = await ddgs_search(query, limit=limit)
    urls: List[str] = []
    for r in results:
        if isinstance(r, dict):
            u = r.get("url") or r.get("href")
            if u:
                urls.append(u)
        elif isinstance(r, str):
            urls.append(r)
    return urls
