import logging
from . import get_llm
from .context import TestContext

logger = logging.getLogger(__name__)

FAILURE_PROMPT = """You are a Python debugging expert.
Analyze the pytest output, source code, and generated tests together.

CRITICAL CONTEXT — how the tests were written:
The tests follow a "should-be" philosophy: they test what the code SHOULD do,
not what it currently does. This means:
- If a test expects pytest.raises(ValueError / TypeError / KeyError / etc.)
  for a logically invalid input (negative value, None, missing key, out-of-range,
  empty collection where items are required) and the code does NOT raise —
  this is SOURCE_BUG, NOT test_error. The test is correct; the source code is
  missing validation.
- If a test asserts a 4xx status for an invalid API payload and the endpoint
  returns 2xx — this is SOURCE_BUG. The endpoint is missing validation.
- Do NOT suggest "recalculate the expected value using the code's current
  behavior" when the input is logically invalid. The test is intentionally
  failing to signal the missing validation.

First, decide: is the failure caused by a wrong TEST or a real BUG in the source code?

- TEST_ERROR means: the test itself is broken. Examples:
  wrong import, typo in function name, syntax issue, wrong expected value
  for a VALID input (e.g. happy-path arithmetic mistake).
- SOURCE_BUG means: the source code has a real bug and the test correctly
  caught it. Examples:
  code silently accepts an invalid input and produces a wrong / impossible
  result, code crashes on input it should have validated, endpoint returns
  2xx for invalid payload.

You MUST start your response with exactly one of these two lines:
VERDICT: TEST_ERROR
VERDICT: SOURCE_BUG

Then explain:
1. Why exactly did the test fail?
2. If TEST_ERROR: how should the test be fixed?
   If SOURCE_BUG: what is the bug in the source code?
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

    llm = get_llm(ctx.analyzer_model)
    try:
        response = llm.invoke(prompt)
    except Exception as e:
        ctx.analysis = f"LLM ERROR (analyzer): {e}"
        ctx.add_to_history()
        return ctx

    ctx.analysis = response

    # Failure type sınıflandırmasını parse et
    if ctx.failed > 0:
        first_line = response.strip().split("\n")[0].upper()
        if "SOURCE_BUG" in first_line:
            ctx.failure_type = "source_bug"
            logger.info("Analyzer verdict: SOURCE_BUG")
        else:
            ctx.failure_type = "test_error"
            logger.info("Analyzer verdict: TEST_ERROR")

    ctx.add_to_history()
    return ctx