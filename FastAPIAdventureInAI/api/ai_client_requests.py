import requests
import jwt
import os
from datetime import timedelta
from config import SECRET_KEY, ALGORITHM, AI_SERVER_URL
from business.converters import serialize_for_json


# Server-to-server tokens are minted fresh per request and only need to survive
# the lifetime of a single AI call. A short expiry bounds the replay window if a
# token is captured on the plain-HTTP LAN link.
_AI_TOKEN_EXPIRE = timedelta(minutes=5)


def _get_ai_auth_headers(username: str = None):
    """Generate auth headers for AI server requests.

    The AI server resolves per-user settings from the token's user_id (it runs
    DB-less in WSL and cannot look the user up itself). So for real user calls we
    resolve the id here, on the data server, and embed it in the token. Without
    this, summarization/inference routes would silently fall back to the Basic
    (default) settings row instead of the user's account level.
    """
    # Always create a token - use provided username or 'system' for internal calls
    user = username if username else "system"
    claims = {"sub": user}

    if username:
        try:
            from shared.services.orm_service import SessionLocal
            from shared.services.auth_service import get_user_by_username
            db = SessionLocal()
            try:
                db_user = get_user_by_username(db, username)
                if db_user is not None and db_user.id is not None:
                    claims["user_id"] = db_user.id
            finally:
                db.close()
        except Exception as e:
            # Non-fatal: fall back to a sub-only token (Basic settings).
            print(f"[ai_client_requests] WARNING: could not resolve user_id for '{username}': {e}")

    # Mint through the shared helper so the token carries an exp claim and cannot
    # be replayed indefinitely as this user.
    from shared.services.auth_service import create_access_token
    token = create_access_token(claims, expires_delta=_AI_TOKEN_EXPIRE)
    return {"Authorization": f"Bearer {token}"}

# def ai_prime_narrator(username: str = None):
#     headers = _get_ai_auth_headers(username)
#     resp = requests.post(f"{AI_SERVER_URL}/prime_narrator/", headers=headers)
#     resp.raise_for_status()
#     return resp.json()["status"]

# def ai_generate_story(context, user_input="", include_initial=False, username: str = None):
#     headers = _get_ai_auth_headers(username)
#     payload = {
#         "context": context,
#         "user_input": user_input,
#         "include_initial": include_initial
#     }
#     resp = requests.post(f"{AI_SERVER_URL}/generate_story/", json=serialize_for_json(payload), headers=headers)
#     resp.raise_for_status()
#     return resp.json()["story"]

# def ai_count_tokens(text, username: str = None):
#     """Count tokens in a given text using the AI server."""
#     headers = _get_ai_auth_headers(username)
#     payload = {"text": text}
    
#     try:
#         resp = requests.post(f"{AI_SERVER_URL}/tokens/count_tokens/", json=serialize_for_json(payload), headers=headers)
#         resp.raise_for_status()
#         return resp.json()["token_count"]
#     except Exception as e:
#         return len(text) // 4

def ai_summarize_chunk(chunk, max_tokens, previous_summary=None, username: str = None):
    headers = _get_ai_auth_headers(username)
    payload = {
        "chunk": chunk,
        "max_tokens": max_tokens,
        "previous_summary": previous_summary
    }
    
    try:
        resp = requests.post(f"{AI_SERVER_URL}/summarize_chunk/", json=serialize_for_json(payload), headers=headers)
        print("[ai_summarize_chunk] Response status:", resp.status_code)
        print("[ai_summarize_chunk] Response text:", resp.text)
        resp.raise_for_status()
        return resp.json()["summary"]
    except Exception as e:
        print("[ai_summarize_chunk] Exception:", e)
        raise

def ai_deep_summarize_chunk(chunk, max_tokens, previous_summary=None, username: str = None):
    headers = _get_ai_auth_headers(username)
    payload = {
        "chunk": chunk,
        "max_tokens": max_tokens,
        "previous_summary": previous_summary
    }
    print("[ai_summarize_chunk] Sending payload:", payload)
    try:
        resp = requests.post(f"{AI_SERVER_URL}/deep_summarize_chunk/", json=serialize_for_json(payload), headers=headers)
        print("[ai_deep_summarize_chunk] Response status:", resp.status_code)
        print("[ai_deep_summarize_chunk] Response text:", resp.text)
        resp.raise_for_status()
        return resp.json()["summary"]
    except Exception as e:
        print("[ai_deep_summarize_chunk] Exception:", e)
        raise

def ai_count_tokens_batch(texts: list[str], username: str = None) -> list[int]:
    """
    Count tokens for multiple texts in a single request.
    Returns a list of token counts in the same order as input texts.
    """
    try:
        response = requests.post(
            f"{AI_SERVER_URL}/tokens/count_tokens_batch/",
            json={"texts": texts},
            headers=_get_ai_auth_headers(username),
            timeout=10
        )
        response.raise_for_status()
        return response.json()["token_counts"]
    except Exception as e:
        # Fallback to rough estimate
        return [len(text) // 4 for text in texts]

def ai_calculate_token_count(text: str, username: str = None) -> int:
    """
    Calculate token count for a single text using batch tokenizer.
    
    Args:
        text: Text to count tokens for
        
    Returns:
        Number of tokens in the text
    """
    return ai_count_tokens_batch([text], username=username)[0]