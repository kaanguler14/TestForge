from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional
from agents.context import TestContext
from agents.writer import write_tests
from agents.runner import run_tests
from agents.analyzer import analyze_results
from agents.suggester import suggest_improvements
from dataclasses import asdict

# LangGraph dict-tabanlı state bekliyor
class GraphState(TypedDict):
    source_code: str
    source_type: str
    generated_tests: Optional[str]
    test_output: Optional[str]
    passed: int
    failed: int
    coverage: int
    coverage_threshold: int
    analysis: Optional[str]
    suggestions: Optional[str]
    iteration: int
    max_iterations: int
    history: list

def _to_ctx(state: dict) -> TestContext:
    return TestContext(**state)

def _to_dict(ctx: TestContext) -> dict:
    return asdict(ctx)

def writer_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    ctx = write_tests(ctx)
    return _to_dict(ctx)

def runner_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    ctx = run_tests(ctx)
    return _to_dict(ctx)

def analyzer_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    ctx = analyze_results(ctx)
    return _to_dict(ctx)

def suggester_node(state: dict) -> dict:
    ctx = _to_ctx(state)
    ctx = suggest_improvements(ctx)
    return _to_dict(ctx)

def should_continue(state: dict) -> str:
    ctx = _to_ctx(state)
    if ctx.should_retry():
        return "writer"
    return "suggester"

graph = StateGraph(GraphState)
graph.add_node("writer",   writer_node)
graph.add_node("runner",   runner_node)
graph.add_node("analyzer", analyzer_node)
graph.add_node("suggester", suggester_node)

graph.set_entry_point("writer")
graph.add_edge("writer",   "runner")
graph.add_edge("runner",   "analyzer")
graph.add_conditional_edges("analyzer", should_continue)
graph.add_edge("suggester", END)

app = graph.compile()