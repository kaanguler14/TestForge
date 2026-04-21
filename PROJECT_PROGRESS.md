# Project Progress

## Snapshot
- Project: `AutoTestLoop` / `TestForge`
- Last updated: 2026-04-22
- Current focus: Sprint 2, making analyzer decisions structured and more reliable

## Completed
- Added timing instrumentation and CSV logging in `logs/timings.csv`
- Added persistent run artifacts under `runs/<run_id>_<source_type>/`
- Saved source code, generated tests, pytest output, analysis, suggestions, history, and summary per run
- Added timing summary and artifact visibility to the Streamlit UI
- Verified artifact generation end-to-end with a function-mode smoke test

## In Progress
- Replace analyzer free-form parsing with structured JSON output
- Reduce fragile verdict parsing based on the first response line
- Extend the same structured-output pattern to the suggester

## Next
- Add benchmark/eval suite for repeatable quality measurement
- Productize the repo with better README, Docker, and CI

## Notes
- Function mode is the current stable path for manual testing
- Artifact logging is working and should stay in place while the analyzer is hardened
