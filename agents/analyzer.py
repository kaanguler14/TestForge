import logging
from langchain_ollama import OllamaLLM
from . import MODEL_NAME
from .context import TestContext

logger = logging.getLogger(__name__)

llm = OllamaLLM(model=MODEL_NAME)

FAILURE_PROMPT = """You are a Python debugging expert.
Analyze the pytest output and source code together.
Answer these two questions only:
1. Why exactly did the test fail?
2. How should the test be fixed?
Be specific and concise. No markdown."""

COVERAGE_PROMPT = """You are a Python test coverage expert.
The tests pass but coverage is too low.
Analyze the source code and existing tests.
Answer these two questions only:
1. Which cases and branches are not being tested?
2. What new test cases should be added?
Be specific and concise. No markdown."""

def analyze_results(ctx: TestContext) -> TestContext:
    logger.info("Analyzer starting — failed=%d, coverage=%d%%", ctx.failed, ctx.coverage)
    # Her iki durumda da analiz gerekmiyorsa geç
    if ctx.failed == 0 and ctx.coverage >= ctx.coverage_threshold:
        logger.info("Analyzer skipping — all tests pass and coverage is sufficient")
        ctx.add_to_history()
        return ctx

    # Duruma göre doğru promptu seç
    if ctx.failed > 0:
        system_prompt = FAILURE_PROMPT
    else:
        system_prompt = COVERAGE_PROMPT

    prompt = f"""{system_prompt}

### Source Code
{ctx.source_code}

### Generated Tests
{ctx.generated_tests}

### Pytest Output
{ctx.test_output}

### Coverage
{ctx.coverage}%
"""

    try:
        response = llm.invoke(prompt)
    except Exception as e:
        ctx.analysis = f"LLM ERROR (analyzer): {e}"
        ctx.add_to_history()
        return ctx

    ctx.analysis = response
    ctx.add_to_history()
    return ctx