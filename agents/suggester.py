import os
import logging
from . import get_llm
from .context import TestContext

logger = logging.getLogger(__name__)

COT_PROMPT = """You are a Python code reviewer. Find real bugs in the source code.

There are TWO categories of bugs you must report:

CATEGORY A - CRASH BUGS:
Inputs that cause an unhandled exception (KeyError, TypeError, ZeroDivisionError, AttributeError, IndexError, etc.).

CATEGORY B - LOGIC / VALIDATION BUGS (silent misbehavior):
Inputs that the code accepts without error but produce nonsensical, impossible, or clearly wrong results.
Examples:
- A percentage parameter accepts negative or >100 values and is used directly in math
- A quantity / price / age / count accepts negative values silently
- A function that should reject a value returns an impossible result (e.g., negative total, negative balance)
- Business rules violated silently (e.g., discount makes total negative)
These are bugs even though nothing crashes — the code "works" but the output is wrong.

Follow these 3 steps:

STEP 1 - FIND DANGEROUS INPUTS:
For each function, list inputs from BOTH categories.
For A: inputs that would crash (no if-check or try/except protects them).
For B: inputs that are accepted silently but produce wrong output (no if-check rejects them).

STEP 2 - TRACE EACH ONE:
For each dangerous input from Step 1, run through the code line by line.
Write: the input, what each line does, and the final result.
- If code has an if-check / try-except that catches it → write "HANDLED" and skip.
- If it crashes → note the exception and line (Category A bug).
- If it runs but returns a wrong / impossible value → note the bad output (Category B bug).

STEP 3 - VERDICT:
List ALL issues proved in Step 2. For each one write:
- The exact input that triggers it
- What goes wrong (crash OR the wrong value returned)
- How to fix it (short, code only — usually an if-check that raises ValueError)
If everything is handled, write: "No issues found. Code is solid."

RULES:
- Report a bug ONLY if Step 2 proves it with a specific input and a specific outcome
- If the code has an if/try that catches the input, it is NOT a bug
- Do NOT mention floating-point precision — it is never a bug
- Do NOT suggest changes to tests — only review the source code
- Do NOT suggest renaming, comments, docstrings, logging, or style changes
- Do NOT recommend tools, frameworks, or alternative implementations
- Do NOT suggest generic type checking unless the function truly misbehaves with wrong types
- When in doubt, say "No issues found. Code is solid."
"""

def _load_examples() -> str:
    try:
        examples_path = os.path.join(os.path.dirname(__file__), "prompts", "suggester_examples.txt")
        with open(examples_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

def suggest_improvements(ctx: TestContext) -> TestContext:
    logger.info("Suggester starting — passed=%d, failed=%d", ctx.passed, ctx.failed)
    examples = _load_examples()
    prompt = f"""{COT_PROMPT}

--- EXAMPLES START (for reference only, do NOT analyze these) ---
{examples}
--- EXAMPLES END ---

Now analyze ONLY the following source code. Ignore all code in the examples above.

### Source Code to Analyze
{ctx.source_code}

### Test Results
Passed: {ctx.passed}, Failed: {ctx.failed}

### Coverage
{ctx.coverage}%

### Pytest Output
{ctx.test_output or "No test output available"}
"""

    llm = get_llm(ctx.suggester_model)
    try:
        response = llm.invoke(prompt)
    except Exception as e:
        ctx.suggestions = f"LLM ERROR (suggester): {e}"
        return ctx

    ctx.suggestions = response
    return ctx
