import json
import os
import urllib.request

MODEL_NAME = os.getenv("AUTOTEST_MODEL", "llama3.1")

WRITER_MODEL = os.getenv("AUTOTEST_WRITER_MODEL", "qwen2.5-coder:7b")
ANALYZER_MODEL = os.getenv("AUTOTEST_ANALYZER_MODEL", "qwen3:8b")
SUGGESTER_MODEL = os.getenv("AUTOTEST_SUGGESTER_MODEL", "qwen3:8b")

LLM_TIMEOUT = float(os.getenv("AUTOTEST_LLM_TIMEOUT", "180"))
_raw_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip()
OLLAMA_HOST = _raw_host if _raw_host.startswith(("http://", "https://")) else f"http://{_raw_host}"

_llm_cache = {}
_last_used_model = None


def _unload_model(model: str) -> None:
    # Ollama'da explicit unload endpoint yok; keep_alive=0 ile boş generate standart pattern.
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0, "prompt": ""}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass  # best-effort; asıl akışı bozma


def get_llm(model: str = MODEL_NAME):
    global _last_used_model
    if _last_used_model and _last_used_model != model:
        _unload_model(_last_used_model)
    _last_used_model = model
    if model not in _llm_cache:
        from langchain_ollama import OllamaLLM
        _llm_cache[model] = OllamaLLM(
            model=model,
            temperature=0.05,
            client_kwargs={"timeout": LLM_TIMEOUT},
        )
    return _llm_cache[model]