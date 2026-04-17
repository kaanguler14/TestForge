import os
import logging
from . import get_llm
from .context import TestContext

logger = logging.getLogger(__name__)

COT_PROMPT = """You are a Python code reviewer. Find ONLY real bugs in the source code.

Follow these 3 steps:

STEP 1 - FIND DANGEROUS INPUTS:
For each function, list inputs that would crash it. Use the pytest output to see what already failed.
Only list inputs where the code has NO protection (no if-check, no try/except).

STEP 2 - TRACE EACH ONE:
For each dangerous input from Step 1, run through the code line by line.
Write: the input, what each line does, and whether it crashes or is handled.
If the code has an if-check or try/except that catches it, write "HANDLED" and move on.

STEP 3 - VERDICT:
List ONLY the issues where Step 2 proved the code crashes. For each one write:
- The exact input that causes the crash
- The exact line that crashes
- How to fix it (short, code only)
If everything is handled, write: "No issues found. Code is solid."

RULES:
- ONLY report bugs you proved in Step 2 with a specific input and a specific crashing line
- If the code has an if/try that catches the input, it is NOT a bug
- Do NOT suggest type checking unless the function truly crashes with wrong types
- Do NOT mention floating-point precision — it is never a bug
- Do NOT suggest changes to tests — only review the source code
- Do NOT suggest renaming, comments, docstrings, logging, or style changes
- Do NOT recommend tools, frameworks, or alternative implementations
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
