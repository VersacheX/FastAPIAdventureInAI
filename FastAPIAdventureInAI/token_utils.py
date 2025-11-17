"""
Utility functions for counting tokens using the AI model's tokenizer.
"""

def _get_auth_headers():
    """Generate auth headers for AI server requests"""
    import jwt
    from config import SECRET_KEY, ALGORITHM
    # Use 'system' user for internal server-to-server calls
    token = jwt.encode({"sub": "system"}, SECRET_KEY, algorithm=ALGORITHM)
    return {"Authorization": f"Bearer {token}"}

def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string using the AI model's tokenizer.
    This function calls the AI server to get accurate token counts.
    """
    import requests
    from config import AI_SERVER_URL
    
    try:
        response = requests.post(
            f"{AI_SERVER_URL}/count_tokens/",
            json={"text": text},
            headers=_get_auth_headers(),
            timeout=5
        )
        response.raise_for_status()
        return response.json()["token_count"]
    except Exception as e:
        # Fallback to rough estimate: ~4 characters per token
        return len(text) // 4

def count_tokens_batch(texts: list[str]) -> list[int]:
    """
    Count tokens for multiple texts in a single request.
    Returns a list of token counts in the same order as input texts.
    """
    import requests
    from config import AI_SERVER_URL
    
    try:
        response = requests.post(
            f"{AI_SERVER_URL}/count_tokens_batch/",
            json={"texts": texts},
            headers=_get_auth_headers(),
            timeout=10
        )
        response.raise_for_status()
        return response.json()["token_counts"]
    except Exception as e:
        # Fallback to rough estimate
        return [len(text) // 4 for text in texts]
