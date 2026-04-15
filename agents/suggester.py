import os
import logging
from langchain_ollama import OllamaLLM
from . import MODEL_NAME
from .context import TestContext

logger = logging.getLogger(__name__)

llm = OllamaLLM(model=MODEL_NAME)

COT_PROMPT = """You are a senior Python code reviewer. Analyze the source code step by step.

You MUST follow these steps IN ORDER. Write your answer for each step.

STEP 1 - LIST FUNCTIONS:
List every function/method in the source code. For each one write its name and what it does in one sentence.

STEP 2 - DANGEROUS INPUTS:
For each function, list inputs that could cause a crash or unexpected behavior. Examples: zero, negative, None, empty string, wrong type, very large number, missing key.

STEP 3 - TRACE THE CODE:
For each dangerous input from Step 2, trace the code line by line:
- Write the input value
- Write what each line does with that input
- Write the final result: does it crash, or does the code already handle it?

STEP 4 - FINAL VERDICT:
Based ONLY on Step 3 traces, list issues where the code actually crashes or misbehaves.
Format: numbered list, each with: what goes wrong, with what input, and how to fix it.
If all dangerous inputs are already handled, write exactly: "No issues found. Code is solid."

IMPORTANT:
- Do NOT suggest renaming, comments, docstrings, or style changes
- Do NOT recommend tools or frameworks
- Do NOT suggest improvements to the tests, only to the source code
- If Step 3 shows the code handles it, do NOT list it in Step 4
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

{examples}

### Source Code
{ctx.source_code}

### Test Results
Passed: {ctx.passed}, Failed: {ctx.failed}

### Coverage
{ctx.coverage}%
"""

    try:
        response = llm.invoke(prompt)
    except Exception as e:
        ctx.suggestions = f"LLM ERROR (suggester): {e}"
        return ctx

    ctx.suggestions = response
    return ctx
