import csv
import json
import os
import uuid
from dataclasses import asdict

from .context import TestContext
from .timing import TIMINGS_CSV

RUNS_DIR = "runs"


def ensure_artifact_dir(ctx: TestContext) -> str:
    if not ctx.run_id:
        ctx.run_id = uuid.uuid4().hex[:8]

    artifact_dir = ctx.artifact_dir or os.path.join(RUNS_DIR, f"{ctx.run_id}_{ctx.source_type}")
    os.makedirs(artifact_dir, exist_ok=True)
    ctx.artifact_dir = os.path.abspath(artifact_dir)
    return ctx.artifact_dir


def _write_text(path: str, content: str | None) -> None:
    if content is None:
        return
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def _write_json(path: str, payload: dict | list) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def initialize_run_artifacts(ctx: TestContext) -> str:
    artifact_dir = ensure_artifact_dir(ctx)

    _write_text(os.path.join(artifact_dir, "source_code.py"), ctx.source_code)
    _write_json(
        os.path.join(artifact_dir, "run_config.json"),
        {
            "run_id": ctx.run_id,
            "source_type": ctx.source_type,
            "coverage_threshold": ctx.coverage_threshold,
            "max_iterations": ctx.max_iterations,
            "writer_model": ctx.writer_model,
            "analyzer_model": ctx.analyzer_model,
            "suggester_model": ctx.suggester_model,
        },
    )
    _write_json(os.path.join(artifact_dir, "context_latest.json"), asdict(ctx))
    return artifact_dir


def persist_node_artifacts(ctx: TestContext, node_name: str) -> None:
    artifact_dir = initialize_run_artifacts(ctx)

    if node_name == "writer":
        _write_text(os.path.join(artifact_dir, "generated_tests.py"), ctx.generated_tests)
    elif node_name == "runner":
        _write_text(os.path.join(artifact_dir, "pytest_output.txt"), ctx.test_output)
        _write_json(
            os.path.join(artifact_dir, "runner_metrics.json"),
            {
                "iteration": ctx.iteration,
                "passed": ctx.passed,
                "failed": ctx.failed,
                "coverage": ctx.coverage,
            },
        )
    elif node_name == "analyzer":
        _write_text(os.path.join(artifact_dir, "analysis.txt"), ctx.analysis)
        if ctx.analysis_structured:
            _write_json(os.path.join(artifact_dir, "analysis_structured.json"), ctx.analysis_structured)
    elif node_name == "suggester":
        _write_text(os.path.join(artifact_dir, "suggestions.txt"), ctx.suggestions)
        if ctx.suggestions_structured:
            _write_json(os.path.join(artifact_dir, "suggestions_structured.json"), ctx.suggestions_structured)

    _write_json(os.path.join(artifact_dir, "history.json"), ctx.history)
    _write_json(os.path.join(artifact_dir, "context_latest.json"), asdict(ctx))


def _load_timing_rows(run_id: str) -> list[dict]:
    try:
        with open(TIMINGS_CSV, newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
    except FileNotFoundError:
        return []

    return [row for row in rows if row.get("run_id") == run_id]


def _safe_float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def build_timings_summary(run_id: str | None) -> dict:
    if not run_id:
        return {}

    rows = _load_timing_rows(run_id)
    if not rows:
        return {}

    summary = {
        "run_id": run_id,
        "row_count": len(rows),
        "total_node_sec": 0.0,
        "total_llm_sec": 0.0,
        "total_subprocess_sec": 0.0,
        "total_overhead_sec": 0.0,
        "by_agent": [],
    }

    agent_totals: dict[str, dict] = {}
    for row in rows:
        node_sec = _safe_float(row.get("node_sec"))
        llm_sec = _safe_float(row.get("llm_sec"))
        subprocess_sec = _safe_float(row.get("subprocess_sec"))
        overhead_sec = _safe_float(row.get("overhead_sec"))

        summary["total_node_sec"] += node_sec
        summary["total_llm_sec"] += llm_sec
        summary["total_subprocess_sec"] += subprocess_sec
        summary["total_overhead_sec"] += overhead_sec

        agent = row.get("agent", "unknown")
        bucket = agent_totals.setdefault(
            agent,
            {
                "agent": agent,
                "calls": 0,
                "node_sec": 0.0,
                "llm_sec": 0.0,
                "subprocess_sec": 0.0,
                "overhead_sec": 0.0,
            },
        )
        bucket["calls"] += 1
        bucket["node_sec"] += node_sec
        bucket["llm_sec"] += llm_sec
        bucket["subprocess_sec"] += subprocess_sec
        bucket["overhead_sec"] += overhead_sec

    summary["by_agent"] = sorted(agent_totals.values(), key=lambda item: item["node_sec"], reverse=True)
    return summary


def finalize_run_artifacts(ctx: TestContext) -> dict:
    artifact_dir = initialize_run_artifacts(ctx)
    ctx.timings_summary = build_timings_summary(ctx.run_id)

    _write_json(os.path.join(artifact_dir, "history.json"), ctx.history)
    _write_json(os.path.join(artifact_dir, "context_latest.json"), asdict(ctx))
    _write_json(
        os.path.join(artifact_dir, "summary.json"),
        {
            "run_id": ctx.run_id,
            "artifact_dir": ctx.artifact_dir,
            "source_type": ctx.source_type,
            "iteration": ctx.iteration,
            "passed": ctx.passed,
            "failed": ctx.failed,
            "coverage": ctx.coverage,
            "failure_type": ctx.failure_type,
            "analysis_structured": ctx.analysis_structured,
            "suggestions_structured": ctx.suggestions_structured,
            "timings_summary": ctx.timings_summary,
        },
    )
    return ctx.timings_summary


def list_artifact_files(artifact_dir: str | None) -> list[dict]:
    if not artifact_dir or not os.path.isdir(artifact_dir):
        return []

    rows = []
    for name in sorted(os.listdir(artifact_dir)):
        path = os.path.join(artifact_dir, name)
        if not os.path.isfile(path):
            continue
        rows.append(
            {
                "name": name,
                "bytes": os.path.getsize(path),
                "path": os.path.abspath(path),
            }
        )
    return rows
