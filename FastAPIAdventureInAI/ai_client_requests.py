import requests
import jwt
import os
from config import SECRET_KEY, ALGORITHM, AI_SERVER_URL
from aiadventureinpythonconstants import TOKENIZED_HISTORY_BLOCK_SIZE
from converters import serialize_for_json

def _get_ai_auth_headers(username: str = None):
    """Generate auth headers for AI server requests"""
    # Always create a token - use provided username or 'system' for internal calls
    user = username if username else "system"
    token = jwt.encode({"sub": user}, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}

def ai_prime_narrator(username: str = None):
    headers = _get_ai_auth_headers(username)
    resp = requests.post(f"{AI_SERVER_URL}/prime_narrator/", headers=headers)
    resp.raise_for_status()
    return resp.json()["status"]

def ai_generate_story(context, user_input="", include_initial=False, username: str = None):
    headers = _get_ai_auth_headers(username)
    payload = {
        "context": context,
        "user_input": user_input,
        "include_initial": include_initial
    }
    resp = requests.post(f"{AI_SERVER_URL}/generate_story/", json=serialize_for_json(payload), headers=headers)
    resp.raise_for_status()
    return resp.json()["story"]


def ai_count_tokens(text, username: str = None):
    """Count tokens in a given text using the AI server."""
    headers = _get_ai_auth_headers(username)
    payload = {"text": text}
    resp = requests.post(f"{AI_SERVER_URL}/count_tokens/", json=serialize_for_json(payload), headers=headers)
    resp.raise_for_status()
    return resp.json()["token_count"]

def ai_summarize_chunk(chunk, max_tokens=TOKENIZED_HISTORY_BLOCK_SIZE, previous_summary=None, username: str = None):
    headers = _get_ai_auth_headers(username)
    payload = {
        "chunk": chunk,
        "max_tokens": max_tokens,
        "previous_summary": previous_summary
    }
    resp = requests.post(f"{AI_SERVER_URL}/summarize_chunk/", json=serialize_for_json(payload), headers=headers)
    resp.raise_for_status()
    return resp.json()["summary"]