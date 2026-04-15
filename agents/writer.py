import re
import logging
from langchain_ollama import OllamaLLM
from . import MODEL_NAME
from .context import TestContext

logger = logging.getLogger(__name__)

llm = OllamaLLM(model=MODEL_NAME)

FUNCTION_PROMPT = """You are a senior test engineer.
Write pytest tests for the given source code.
Rules:
- Only output raw Python code, no explanations
- No markdown, no code blocks, no backticks
- Always import pytest at the top
- Do NOT redefine or include the source code in tests
- The source code is already imported via: from source_code import *
- Test both happy path and edge cases
- Use only valid Python syntax
"""

API_PROMPT = """You are a senior API test engineer.
Write pytest tests for the given API endpoint code.
Rules:
- Only output raw Python code, no explanations
- No markdown, no code blocks, no backticks
- Always import pytest at the top
- Do NOT redefine or include the source code in tests
- The source code is already imported via: from source_code import *
- Test HTTP status codes (200, 400, 404, 500 etc.)
- Test request/response body structure
- Test error handling and edge cases (missing fields, invalid input)
- Test both successful and failed scenarios
- Use only valid Python syntax
"""

def write_tests(ctx: TestContext) -> TestContext:
    logger.info("Writer starting — iteration %d, source_type=%s", ctx.iteration + 1, ctx.source_type)
    system_prompt = API_PROMPT if ctx.source_type == "api" else FUNCTION_PROMPT
    prompt = system_prompt + "\n" + ctx.build_writer_context()

    try:
        response = llm.invoke(prompt)
    except Exception as e:
        logger.error("Writer LLM call failed: %s", e)
        ctx.generated_tests = None
        ctx.test_output = f"LLM ERROR (writer): {e}"
        ctx.failed = 1
        ctx.iteration += 1
        return ctx

    # LLM bazen yine de markdown ekler, temizleyelim
    code = re.sub(r"```(?:python)?\n?", "", response).strip()

    ctx.generated_tests = code
    ctx.iteration += 1
    logger.info("Writer done — generated %d lines of test code", code.count("\n") + 1)
    return ctx