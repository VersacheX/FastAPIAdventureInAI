from gptqmodel.models import GPTQModel
from transformers import AutoTokenizer
from fastapi import Request

AI_MODEL = "TheBloke/MythoMax-L2-13B-GPTQ"

def silent_model_load():
    import os, contextlib
    with open(os.devnull, 'w') as devnull:
        with contextlib.redirect_stdout(devnull):
            tokenizer = AutoTokenizer.from_pretrained(AI_MODEL, use_fast=True)
            model = GPTQModel.from_quantized(
                AI_MODEL,
                use_exllamav2=True,
                use_marlin=True,
                use_machete=True,
                use_triton=True,
                use_cuda_fp16=True,
                trust_remote_code=True,
                device="cuda:0",
                pad_token_id=50256,
                fuse_layers=True,
                disable_exllama=False,
                disable_exllamav2=False,
                disable_marlin=False,
                disable_machete=False,
                disable_triton=False,
                revision="main"
            )
            return model, tokenizer

def load_story_generater_to_app_state(app):
    (model, tokenizer) = silent_model_load()
    app.state.story_generator = model
    app.state.story_tokenizer = tokenizer

def get_model(request: Request):
    # Return the model and tokenizer names used in app.state
    return request.app.state.story_generator, request.app.state.story_tokenizer