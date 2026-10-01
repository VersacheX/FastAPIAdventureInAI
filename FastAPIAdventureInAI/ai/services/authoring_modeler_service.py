"""
Authoring model service.

Loads a llama.cpp (GGUF) instruct model (e.g. Hermes 2 / Qwen2.5-Instruct) for
structured story authoring. This mirrors the app.state + dependency structure of
ai_modeler_service.py so routers can depend on it the same way, but the underlying
model is a chat-capable llama_cpp.Llama instead of a GPTQ + HF tokenizer pair.
"""
import sys

from llama_cpp import Llama
from fastapi import Request

from config import (
    AUTHORING_MODEL_PATH,
    AUTHORING_MODEL_CTX,
    AUTHORING_MODEL_GPU_LAYERS,
)


def silent_authoring_model_load():
    print(f"[AUTHORING] Loading model from {AUTHORING_MODEL_PATH}...", file=sys.stderr)
    llm = Llama(
        model_path=AUTHORING_MODEL_PATH,
        n_ctx=AUTHORING_MODEL_CTX,
        n_gpu_layers=AUTHORING_MODEL_GPU_LAYERS,
        seed=0,
        verbose=False,
    )
    print("[AUTHORING] Model loaded successfully", file=sys.stderr)
    return llm


def load_authoring_model_to_app_state(app):
    app.state.authoring_model = silent_authoring_model_load()


def get_authoring_model(request: Request) -> Llama:
    # Return the llama.cpp model stored in app.state
    return request.app.state.authoring_model


def generate_authoring_json(
    llm: Llama,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float = 0.3,
    top_p: float = 0.9,
    force_json: bool = True,
) -> str:
    """
    Run a chat completion against the authoring model and return the raw text.

    When force_json is True, the model is constrained to emit a JSON object via
    llama.cpp's response_format grammar, which is far more reliable than parsing
    free-form output.
    """
    kwargs = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }
    if force_json:
        kwargs["response_format"] = {"type": "json_object"}

    output = llm.create_chat_completion(**kwargs)
    return output["choices"][0]["message"]["content"]
