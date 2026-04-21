from dataclasses import asdict
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from agents.analyzer import analyze_results
from agents.artifacts import initialize_run_artifacts, persist_node_artifacts
from agents.context import TestContext
from agents.runner import run_tests
from agents.suggester import suggest_improvements
from agents.timing import timed_node
from agents.writer import write_tests


class GraphState(TypedDict):
    source_code: str
    source_type: str
    run_id: Optional[str]
    artifact_dir: Optional[str]
    generated_tests: Optional[str]
    test_output: Optional[str]
    passed: int
    failed: int
    coverage: int
    coverage_threshold: int
    analysis: Optional[str]
    analysis_structured: dict
    failure_type: Optional[str]
    suggestions: Optional[str]
    suggestions_structured: dict
    writer_model: str
    analyzer_model: str
    suggester_model: str
    iteration: int
    max_iterations: int
    history: list
    timings_summary: dict


def _to_ctx(state: dict) -> TestContext:
    return TestContext(**state)


def _to_dict(ctx: TestContext) -> dict:
    return asdict(ctx)


@timed_node("writer")
def writer_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    initialize_run_artifacts(ctx)
    ctx = write_tests(ctx)
    persist_node_artifacts(ctx, "writer")
    return _to_dict(ctx)


@timed_node("runner")
def runner_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    initialize_run_artifacts(ctx)
    ctx = run_tests(ctx)
    persist_node_artifacts(ctx, "runner")
    return _to_dict(ctx)


@timed_node("analyzer")
def analyzer_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    initialize_run_artifacts(ctx)
    ctx = analyze_results(ctx)
    persist_node_artifacts(ctx, "analyzer")
    return _to_dict(ctx)


@timed_node("suggester")
def suggester_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    initialize_run_artifacts(ctx)
    ctx = suggest_improvements(ctx)
    persist_node_artifacts(ctx, "suggester")
    return _to_dict(ctx)


def should_continue(state: dict) -> str:
    ctx = _to_ctx(state)
    if ctx.should_retry():
        return "writer"
    return "suggester"


graph = StateGraph(GraphState)
graph.add_node("writer", writer_node)
graph.add_node("runner", runner_node)
graph.add_node("analyzer", analyzer_node)
graph.add_node("suggester", suggester_node)

graph.set_entry_point("writer")
graph.add_edge("writer", "runner")
graph.add_edge("runner", "analyzer")
graph.add_conditional_edges("analyzer", should_continue)
graph.add_edge("suggester", END)

app = graph.compile()
