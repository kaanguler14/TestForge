# Benchmarks

Repeatable quality measurement for the AutoTestLoop pipeline.

## Layout

```
benchmarks/
├── cases/
│   ├── 01_validated_divide/    # each case = one folder
│   │   ├── source.py           # code under test
│   │   └── expected.json       # expected verdict + bugs
│   └── ...
├── results/
│   └── <timestamp>/            # one folder per benchmark run
│       ├── summary.json
│       ├── summary.md
│       └── per_case.json
```

## Case categories (current set: 15)

| Range | Category | Expected |
|-------|----------|----------|
| 01-05 | clean | No bugs found, no source_bug verdict |
| 06-10 | crash | `source_bug` verdict, at least one `crash_bug` finding |
| 11-15 | logic | `source_bug` verdict, at least one `logic_bug` finding |

## `expected.json` schema

```json
{
  "case_id": "01_validated_divide",
  "description": "short human-readable summary",
  "source_type": "function" | "api",
  "expected_category": "clean" | "crash" | "logic",
  "expected_failure_type": null | "source_bug" | "test_error",
  "expected_bugs": [
    {
      "category": "crash_bug" | "logic_bug",
      "keywords": ["substring", "matchers"]
    }
  ]
}
```

A bug is considered "matched" if a suggester finding has the same `category` AND every keyword (case-insensitive, substring) appears somewhere in that finding's `input + problem + fix_hint`.

## Running

```bash
# All cases
python scripts/run_benchmark.py

# Filter by category (matches expected_category in expected.json)
python scripts/run_benchmark.py --category clean
python scripts/run_benchmark.py --category crash
python scripts/run_benchmark.py --category logic

# Filter by dir name substring
python scripts/run_benchmark.py --filter 11
python scripts/run_benchmark.py --filter api

# Custom iteration cap / coverage
python scripts/run_benchmark.py --max-iter 2 --coverage-threshold 70

# Per-case deadline (default 120s, child subprocess is killed if exceeded)
python scripts/run_benchmark.py --case-timeout 180
```

Each case runs in its own subprocess; if the deadline is exceeded the child is killed, the case is marked as TIMEOUT, and the suite continues with the next case. `per_case.json` is written incrementally — if the suite is interrupted, partial results are still readable.

Output goes to `benchmarks/results/<timestamp>/`. Also writes the usual per-run artifacts under `runs/` for each case (CSV timings + JSON artifacts).

## Metrics

| Metric | Meaning |
|--------|---------|
| `verdict_accuracy` | Fraction of cases where `ctx.failure_type` matches `expected_failure_type` |
| `bug_recall` | Across all expected bugs, fraction found via keyword match |
| `false_positive_rate` | Findings per clean case (should be near 0) |
| `avg_latency_sec` | Mean wall-clock per case |
| `avg_iterations` | Mean iteration count per case |

## Interpreting results

- **Clean case with findings > 0** → false positive; suggester is flagging non-issues
- **Crash/logic case with `verdict_match=MISS`** → analyzer misclassified; check `analysis_structured` in the case's run artifact
- **Low bug_recall on crash cases** → suggester is missing obvious issues; prompt or examples may need tightening
- **High latency variance** → likely VRAM thrashing (see CLAUDE.md TODO re: `keep_alive=0`)
