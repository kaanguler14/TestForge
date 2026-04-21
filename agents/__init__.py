import os

MODEL_NAME = os.getenv("AUTOTEST_MODEL", "llama3.1")

WRITER_MODEL = os.getenv("AUTOTEST_WRITER_MODEL", "qwen2.5-coder:7b")
ANALYZER_MODEL = os.getenv("AUTOTEST_ANALYZER_MODEL", "qwen3:8b")
SUGGESTER_MODEL = os.getenv("AUTOTEST_SUGGESTER_MODEL", "qwen3:8b")

_llm_cache = {}

def get_llm(model: str = MODEL_NAME):
    if model not in _llm_cache:
        from langchain_ollama import OllamaLLM
        _llm_cache[model] = OllamaLLM(model=model, temperature=0.05)
    return _llm_cache[model]