"""
Geçici performans ölçüm altyapısı.

Bu modül silindiğinde + graph.py ve app.py'deki importlar temizlendiğinde
proje eski haline döner. Ajan dosyalarına dokunmaz.
"""
import csv
import os
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from functools import wraps

from langchain_ollama import OllamaLLM

TIMINGS_CSV = os.path.join("logs", "timings.csv")

HEADERS = [
    "run_id", "ts", "source_type", "iteration", "agent", "skipped",
    "node_sec", "llm_sec", "subprocess_sec", "overhead_sec",
    "model", "passed", "failed", "coverage",
]

_local = threading.local()


def _get_state():
    return getattr(_local, "state", None)


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


def start_run(run_id: str, source_type: str) -> None:
    """Yeni bir run başlatır; thread-local sayaçları sıfırlar."""
    _local.state = {
        "run_id": run_id,
        "source_type": source_type,
        "llm_sec": 0.0,
        "subprocess_sec": 0.0,
    }


def end_run() -> None:
    _local.state = None


def _reset_node_counters() -> None:
    st = _get_state()
    if st is not None:
        st["llm_sec"] = 0.0
        st["subprocess_sec"] = 0.0


@contextmanager
def stopwatch():
    box = {"elapsed": 0.0}
    t0 = time.perf_counter()
    try:
        yield box
    finally:
        box["elapsed"] = time.perf_counter() - t0


def _ensure_file() -> None:
    os.makedirs(os.path.dirname(TIMINGS_CSV), exist_ok=True)
    if not os.path.exists(TIMINGS_CSV):
        with open(TIMINGS_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADERS)


def append_row(row: dict) -> None:
    _ensure_file()
    full = {h: row.get(h, "") for h in HEADERS}
    for k, v in list(full.items()):
        if isinstance(v, float):
            full[k] = round(v, 4)
    with open(TIMINGS_CSV, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=HEADERS).writerow(full)


_MODEL_FIELD = {
    "writer": "writer_model",
    "analyzer": "analyzer_model",
    "suggester": "suggester_model",
    "runner": None,
}


def timed_node(agent: str):
    """
    Node wrapper dekoratörü. node_sec'i ölçer, thread-local'den llm_sec ve
    subprocess_sec'i alır, CSV'ye bir satır yazar.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(state: dict) -> dict:
            _reset_node_counters()
            t0 = time.perf_counter()
            result = fn(state)
            node_sec = time.perf_counter() - t0

            st = _get_state()
            if st is None:
                return result

            llm_sec = st["llm_sec"]
            sub_sec = st["subprocess_sec"]
            overhead = max(0.0, node_sec - llm_sec - sub_sec)

            model_field = _MODEL_FIELD.get(agent)
            model = result.get(model_field, "") if model_field else ""
            skipped = (agent == "analyzer" and llm_sec == 0.0)

            append_row({
                "run_id": st["run_id"],
                "ts": datetime.now().isoformat(timespec="seconds"),
                "source_type": st["source_type"],
                "iteration": result.get("iteration", ""),
                "agent": agent,
                "skipped": "yes" if skipped else "",
                "node_sec": node_sec,
                "llm_sec": llm_sec,
                "subprocess_sec": sub_sec,
                "overhead_sec": overhead,
                "model": model,
                "passed": result.get("passed", ""),
                "failed": result.get("failed", ""),
                "coverage": result.get("coverage", ""),
            })
            return result
        return wrapper
    return decorator


# --- Monkey patches (idempotent) ---

def _install_patches() -> None:
    # OllamaLLM.invoke
    if not getattr(OllamaLLM, "_autotest_patched", False):
        _orig_invoke = OllamaLLM.invoke

        def timed_invoke(self, *args, **kwargs):
            st = _get_state()
            if st is None:
                return _orig_invoke(self, *args, **kwargs)
            t0 = time.perf_counter()
            try:
                return _orig_invoke(self, *args, **kwargs)
            finally:
                st["llm_sec"] += time.perf_counter() - t0

        OllamaLLM.invoke = timed_invoke
        OllamaLLM._autotest_patched = True

    # subprocess.run
    if not getattr(subprocess, "_autotest_patched", False):
        _orig_run = subprocess.run

        def timed_run(*args, **kwargs):
            st = _get_state()
            if st is None:
                return _orig_run(*args, **kwargs)
            t0 = time.perf_counter()
            try:
                return _orig_run(*args, **kwargs)
            finally:
                st["subprocess_sec"] += time.perf_counter() - t0

        subprocess.run = timed_run
        subprocess._autotest_patched = True


_install_patches()
