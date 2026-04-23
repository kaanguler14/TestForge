# Project Progress

## Snapshot
- Project: `AutoTestLoop` / `TestForge`
- Last updated: 2026-04-23
- Current focus: Sprint 3 — benchmark/eval suite for repeatable quality measurement

## Completed
- **Sprint 1 — Artifact logging:** timing CSV in `logs/timings.csv`, per-run artifacts under `runs/<run_id>_<source_type>/` (source, generated tests, pytest output, analysis, suggestions, history, summary); Streamlit timings tab + artifact list.
- **Sprint 2 — Structured outputs:** analyzer and suggester now return JSON (`analysis_structured`, `suggestions_structured`); legacy-format fallback parser normalizes older shapes; suggester few-shot examples rewritten to teach the new `{verdict, summary, findings}` schema; root-level `{crash_bugs, logic_bugs}` shape also normalized as a safety net.
- **LLM timeout:** `OllamaLLM` constructed with `client_kwargs={"timeout": 180}` (override via `AUTOTEST_LLM_TIMEOUT`). Note: httpx per-read timeout, not total.

## In Progress
- Sprint 3 — benchmark/eval suite (not started yet, planning phase)

## Next
- Sprint 3: benchmark cases in `benchmarks/`, runner script, accuracy/latency report
- Sprint 4 (productization): README (EN), Docker sandbox, CI, basic CLI surface

## Deferred / Open Issues
- `keep_alive=0` for deterministic model swap on 6 GB VRAM (documented in CLAUDE.md TODO)
- `llm_sec=0` timing glitch (monkey-patch occasionally misses; node_sec is the reliable metric)
- Docker sandbox (Sprint 4)
- `requirements.txt` version pins (Sprint 4)

## Notes
- Function mode is the stable manual-testing path
- API mode is present but less battle-tested
