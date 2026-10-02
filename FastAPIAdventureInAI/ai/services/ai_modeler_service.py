"""
Story engine (llama.cpp / GGUF).

The AI server now runs a llama.cpp instruct model (e.g. Qwen2.5 / Hermes 2)
instead of the old GPTQ + HuggingFace pipeline. The StoryEngine wraps a
llama_cpp.Llama instance and exposes the small tool set the routers/services
need: text completion (generate) and tokenization (encode / count_tokens).

The public helpers keep their original names (load_story_generater_to_app_state,
get_model) so existing imports keep working. get_model now returns a single
StoryEngine; call sites that previously unpacked (generator, tokenizer) should
use the engine methods instead.
"""
import sys
import threading

from llama_cpp import Llama
from fastapi import Request

from config import (
    STORY_MODEL_PATH,
    STORY_MODEL_CTX,
    STORY_MODEL_GPU_LAYERS,
    STORY_MODEL_BATCH,
    STORY_MODEL_FLASH_ATTN,
)


class StoryEngine:
    """Thin wrapper around llama_cpp.Llama providing generation + tokenization."""

    def __init__(self, llm: Llama):
        self.llm = llm
        # llama_cpp.Llama is NOT thread-safe: it keeps a single shared KV cache
        # and token-position counter. Concurrent calls (overlapping story
        # requests, or a token-count call racing a generation) corrupt the
        # cache and crash with "inconsistent sequence positions" /
        # "llama_decode returned -1". This lock serialises ALL model access.
        self._lock = threading.Lock()

    # ?? Tokenization ?????????????????????????????????????????????
    def encode(self, text: str, add_special_tokens: bool = False):
        """Return the token ids for a piece of text (list of ints)."""
        if text is None:
            text = ""
        with self._lock:
            return self.llm.tokenize(text.encode("utf-8"), add_bos=add_special_tokens)

    def count_tokens(self, text: str) -> int:
        return len(self.encode(text))

    # ── Generation ───────────────────────────────────────────────
    def generate(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float = 0.75,
        top_p: float = 0.92,
        repetition_penalty: float = 1.05,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop=None,
        system_prompt: str = None,
    ) -> str:
        """Generate text using the model's chat template.

        Qwen2.5 (and most GGUF instruct models) are trained with a chat template.
        Using create_chat_completion makes llama.cpp wrap the prompt correctly,
        which avoids the degraded grammar and verbatim-repetition that raw
        create_completion produces on instruct models.

        Repetition controls default to gentle values. frequency_penalty and
        presence_penalty are OFF by default because they penalise *any* token
        that has already appeared -- including grammatical glue words like
        "the", "a", "her", "into" -- which produces telegraphic, article-dropped
        broken English. A light repeat_penalty is enough to stop verbatim loops
        while keeping the prose fluent.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        with self._lock:
            output = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repetition_penalty,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stop=stop or [],
            )
        return output["choices"][0]["message"]["content"]

    def generate_messages(
        self,
        messages,
        max_new_tokens: int,
        temperature: float = 0.8,
        top_p: float = 0.9,
        repetition_penalty: float = 1.05,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stop=None,
    ) -> str:
        """Generate from a pre-built chat message list (system/user/assistant).

        Preferred for story continuation: framing the recent story as the
        assistant's PRIOR turn stops the model from echoing it verbatim and
        makes it produce the NEXT beat instead.
        """
        with self._lock:
            output = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repetition_penalty,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stop=stop or [],
            )
        return output["choices"][0]["message"]["content"]


def silent_model_load() -> StoryEngine:
    print(f"[STORY ENGINE] Loading model from {STORY_MODEL_PATH}...", file=sys.stderr)
    print(
        f"[STORY ENGINE] n_ctx={STORY_MODEL_CTX} n_gpu_layers={STORY_MODEL_GPU_LAYERS} "
        f"n_batch={STORY_MODEL_BATCH} flash_attn={STORY_MODEL_FLASH_ATTN}",
        file=sys.stderr,
    )
    llm = Llama(
        model_path=STORY_MODEL_PATH,
        n_ctx=STORY_MODEL_CTX,
        n_gpu_layers=STORY_MODEL_GPU_LAYERS,
        # Larger logical batch speeds up prompt ingestion (prompt eval) on GPU.
        n_batch=STORY_MODEL_BATCH,
        # Flash attention shrinks the KV cache and speeds attention on CUDA,
        # freeing VRAM so more layers stay on the GPU.
        flash_attn=STORY_MODEL_FLASH_ATTN,
        seed=0,
        # Qwen2.5 uses ChatML. Force it explicitly: "uncensored" merges often
        # ship with stripped/broken chat_template metadata, which makes
        # llama.cpp silently fall back to a generic template and produce
        # degraded, instruction-ignoring prose. verbose=True logs the chosen
        # template so you can confirm "chatml" is active in the startup output.
        chat_format="chatml",
        verbose=True,
    )
    print("[STORY ENGINE] Model loaded successfully", file=sys.stderr)
    return StoryEngine(llm)


def load_story_generater_to_app_state(app):
    app.state.story_engine = silent_model_load()


def get_model(request: Request) -> StoryEngine:
    # Return the StoryEngine stored in app.state
    return request.app.state.story_engine
