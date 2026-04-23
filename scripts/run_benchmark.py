"""Run all benchmark cases and produce an accuracy/latency report.

Usage:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --filter 01          # only cases starting with 01
    python scripts/run_benchmark.py --filter clean       # works on substrings too
    python scripts/run_benchmark.py --max-iter 2

Outputs:
    benchmarks/results/<timestamp>/
        summary.json     aggregate metrics
        summary.md       readable report
        per_case.json    per-case raw results + scoring
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _lazy_imports():
    """Heavy imports only when actually running a case (not in parent orchestrator)."""
    from agents.artifacts import finalize_run_artifacts, initialize_run_artifacts
    from agents.context import TestContext
    from agents.timing import end_run, new_run_id, start_run
    from graph import app as graph_app

    return {
        "finalize_run_artifacts": finalize_run_artifacts,
        "initialize_run_artifacts": initialize_run_artifacts,
        "TestContext": TestContext,
        "end_run": end_run,
        "new_run_id": new_run_id,
        "start_run": start_run,
        "graph_app": graph_app,
    }


def load_case(case_dir: Path) -> dict:
    source = (case_dir / "source.py").read_text(encoding="utf-8")
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    return {"source": source, "expected": expected, "case_dir": case_dir.name}


def run_case(case: dict, max_iter: int, coverage_threshold: int) -> dict:
    imp = _lazy_imports()
    TestContext = imp["TestContext"]

    run_id = imp["new_run_id"]()
    source_type = case["expected"]["source_type"]
    imp["start_run"](run_id, source_type)

    initial_ctx = TestContext(
        source_code=case["source"],
        source_type=source_type,
        run_id=run_id,
        max_iterations=max_iter,
        coverage_threshold=coverage_threshold,
    )
    imp["initialize_run_artifacts"](initial_ctx)
    initial_state = asdict(initial_ctx)

    t0 = time.perf_counter()
    final_state = initial_state
    try:
        for event in imp["graph_app"].stream(initial_state):
            node_name = list(event.keys())[0]
            final_state = event[node_name]
    finally:
        imp["end_run"]()
    latency = time.perf_counter() - t0

    final_ctx = TestContext(**final_state)
    imp["finalize_run_artifacts"](final_ctx)

    return {
        "case_id": case["expected"]["case_id"],
        "latency_sec": latency,
        "iterations": final_ctx.iteration,
        "failure_type": final_ctx.failure_type,
        "passed": final_ctx.passed,
        "failed": final_ctx.failed,
        "coverage": final_ctx.coverage,
        "run_id": run_id,
        "artifact_dir": final_ctx.artifact_dir,
        "suggestions_structured": final_ctx.suggestions_structured,
        "analysis_structured": final_ctx.analysis_structured,
    }


def run_case_subprocess(case_dir: Path, max_iter: int, coverage_threshold: int, timeout_sec: int) -> dict:
    """Run one case in a child process so we can enforce a wall-clock deadline.

    Parent uses subprocess.run(timeout=N). On timeout the child is killed,
    its Ollama HTTP connection drops, and we move on with a TIMEOUT record.
    """
    result_file = Path(tempfile.mkstemp(prefix="autotest_case_", suffix=".json")[1])
    try:
        proc = subprocess.run(
            [
                sys.executable, __file__,
                "--single-case", str(case_dir),
                "--result-file", str(result_file),
                "--max-iter", str(max_iter),
                "--coverage-threshold", str(coverage_threshold),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(ROOT),
        )
        if result_file.exists() and result_file.stat().st_size > 0:
            return json.loads(result_file.read_text(encoding="utf-8"))
        return {
            "case_id": case_dir.name,
            "error": f"child exited without result (code={proc.returncode})",
            "stderr_tail": (proc.stderr or "")[-500:],
            "latency_sec": 0.0,
            "iterations": 0,
            "failure_type": None,
            "suggestions_structured": {},
            "analysis_structured": {},
        }
    except subprocess.TimeoutExpired:
        return {
            "case_id": case_dir.name,
            "error": f"TIMEOUT after {timeout_sec}s",
            "latency_sec": float(timeout_sec),
            "iterations": 0,
            "failure_type": None,
            "suggestions_structured": {},
            "analysis_structured": {},
        }
    finally:
        try:
            result_file.unlink()
        except OSError:
            pass


def score_case(result: dict, expected: dict) -> dict:
    expected_ft = expected.get("expected_failure_type")
    # TIMEOUT / ERROR cases must not silently pass verdict check.
    if result.get("error"):
        verdict_match = False
    else:
        verdict_match = result.get("failure_type") == expected_ft

    findings = (result.get("suggestions_structured") or {}).get("findings") or []
    expected_bugs = expected.get("expected_bugs") or []

    matched = []
    unmatched = []
    for exp_bug in expected_bugs:
        cat = exp_bug.get("category")
        keywords = [k.lower() for k in exp_bug.get("keywords") or []]
        was_found = False
        for finding in findings:
            if finding.get("category") != cat:
                continue
            haystack = " ".join(
                str(finding.get(k) or "") for k in ("input", "problem", "fix_hint")
            ).lower()
            if all(k in haystack for k in keywords):
                was_found = True
                break
        (matched if was_found else unmatched).append(exp_bug)

    is_clean = len(expected_bugs) == 0
    false_positives = len(findings) if is_clean else 0

    return {
        "verdict_match": verdict_match,
        "expected_failure_type": expected_ft,
        "actual_failure_type": result.get("failure_type"),
        "expected_bug_count": len(expected_bugs),
        "matched_bug_count": len(matched),
        "unmatched_bugs": unmatched,
        "bug_recall": len(matched) / max(1, len(expected_bugs)) if expected_bugs else None,
        "false_positives": false_positives,
        "findings_count": len(findings),
        "is_clean_case": is_clean,
    }


def aggregate(entries: list) -> dict:
    n = len(entries)
    verdict_hits = sum(1 for e in entries if e["score"]["verdict_match"])
    total_expected = sum(e["score"]["expected_bug_count"] for e in entries)
    total_matched = sum(e["score"]["matched_bug_count"] for e in entries)
    clean_entries = [e for e in entries if e["score"]["is_clean_case"]]
    total_fp = sum(e["score"]["false_positives"] for e in clean_entries)

    return {
        "n_cases": n,
        "verdict_accuracy": verdict_hits / max(1, n),
        "bug_recall": total_matched / max(1, total_expected) if total_expected else None,
        "false_positive_rate": total_fp / max(1, len(clean_entries)) if clean_entries else None,
        "avg_latency_sec": sum(e["result"]["latency_sec"] for e in entries) / max(1, n),
        "avg_iterations": sum(e["result"]["iterations"] for e in entries) / max(1, n),
        "error_cases": sum(1 for e in entries if e["result"].get("error")),
    }


def render_markdown(summary: dict, entries: list) -> str:
    def pct(v):
        return f"{v:.1%}" if v is not None else "-"

    lines = [
        "# Benchmark Results",
        "",
        f"- Timestamp: {summary.get('timestamp')}",
        f"- Cases: {summary['n_cases']}",
        f"- Verdict accuracy: {pct(summary['verdict_accuracy'])}",
        f"- Bug recall: {pct(summary['bug_recall'])}",
        f"- False positive rate (per clean case): "
        f"{summary['false_positive_rate']:.2f}"
        if summary["false_positive_rate"] is not None else "- False positive rate: -",
        f"- Avg latency: {summary['avg_latency_sec']:.1f}s",
        f"- Avg iterations: {summary['avg_iterations']:.2f}",
        f"- Error cases: {summary['error_cases']}",
        "",
        "| case | verdict | bugs matched | findings | FP | latency (s) | iterations |",
        "|------|---------|--------------|----------|----|-------------|------------|",
    ]
    for entry in entries:
        r = entry["result"]
        s = entry["score"]
        verdict_cell = "OK" if s["verdict_match"] else "MISS"
        bugs_cell = (
            f"{s['matched_bug_count']}/{s['expected_bug_count']}"
            if s["expected_bug_count"] else "-"
        )
        fp_cell = s["false_positives"] if s["is_clean_case"] else "-"
        lat = r.get("latency_sec", 0)
        lines.append(
            f"| {r.get('case_id', '?')} "
            f"| {verdict_cell} ({s['actual_failure_type']}) "
            f"| {bugs_cell} | {s['findings_count']} | {fp_cell} "
            f"| {lat:.0f} | {r.get('iterations', 0)} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", default="benchmarks/cases")
    parser.add_argument("--results-dir", default="benchmarks/results")
    parser.add_argument("--filter", help="Run only cases whose dir name contains this substring")
    parser.add_argument(
        "--category",
        choices=["clean", "crash", "logic"],
        help="Run only cases whose expected.json has this expected_category",
    )
    parser.add_argument("--max-iter", type=int, default=3)
    parser.add_argument("--coverage-threshold", type=int, default=80)
    parser.add_argument(
        "--case-timeout",
        type=int,
        default=120,
        help="Per-case wall-clock deadline in seconds; child process is killed if exceeded",
    )
    # Internal child-mode args (used when this script spawns itself per case):
    parser.add_argument("--single-case", help=argparse.SUPPRESS)
    parser.add_argument("--result-file", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # Child mode: run one case, write result JSON to file, exit
    if args.single_case:
        case_dir = Path(args.single_case)
        case = load_case(case_dir)
        result = run_case(case, args.max_iter, args.coverage_threshold)
        out_path = Path(args.result_file) if args.result_file else case_dir / "_result.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return

    cases_root = Path(args.cases_dir)
    if not cases_root.is_dir():
        print(f"Cases dir not found: {cases_root}")
        sys.exit(1)

    case_dirs = sorted(d for d in cases_root.iterdir() if d.is_dir())
    if args.filter:
        case_dirs = [d for d in case_dirs if args.filter in d.name]
    if args.category:
        filtered = []
        for d in case_dirs:
            try:
                exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
                if exp.get("expected_category") == args.category:
                    filtered.append(d)
            except Exception:
                continue
        case_dirs = filtered

    if not case_dirs:
        print("No cases selected.")
        return

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir = Path(args.results_dir) / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running {len(case_dirs)} case(s) -> {out_dir}")
    print(f"Per-case timeout: {args.case_timeout}s")
    print("-" * 60)

    entries = []
    for case_dir in case_dirs:
        print(f"[{case_dir.name}] running (timeout {args.case_timeout}s)...", flush=True)
        try:
            case = load_case(case_dir)
        except Exception as e:
            print(f"  -> LOAD ERROR: {e}")
            continue

        result = run_case_subprocess(
            case_dir, args.max_iter, args.coverage_threshold, args.case_timeout
        )
        score = score_case(result, case["expected"])
        entries.append({"result": result, "score": score})

        if result.get("error"):
            print(f"  -> {result['error']}")
        else:
            verdict = "OK" if score["verdict_match"] else "MISS"
            bugs = (
                f"{score['matched_bug_count']}/{score['expected_bug_count']}"
                if score["expected_bug_count"] else "-"
            )
            print(f"  -> verdict {verdict}, bugs {bugs}, {result['latency_sec']:.0f}s")

        # Persist running state so a mid-run crash still leaves useful artifacts
        (out_dir / "per_case.json").write_text(
            json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    summary = aggregate(entries)
    summary["timestamp"] = stamp

    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "per_case.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "summary.md").write_text(
        render_markdown(summary, entries), encoding="utf-8"
    )

    print("-" * 60)
    print(f"Done. Results in: {out_dir}")
    print(f"Verdict accuracy: {summary['verdict_accuracy']:.1%}")
    if summary["bug_recall"] is not None:
        print(f"Bug recall: {summary['bug_recall']:.1%}")
    print(f"Avg latency: {summary['avg_latency_sec']:.1f}s")


if __name__ == "__main__":
    main()
