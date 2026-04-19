import re
import logging
from . import get_llm
from .context import TestContext

logger = logging.getLogger(__name__)

FUNCTION_PROMPT = """You are a senior test engineer.
Write pytest tests for the given source code.

Your job is to test what the code SHOULD do, not what it currently does.
For any input that is logically invalid — negative percentage, negative quantity / price / age,
None where a value is required, empty collection where items are required, out-of-range value —
write a test that expects `pytest.raises(ValueError)` (or the appropriate exception).
If the source code silently accepts a nonsensical input, the test MUST fail — that failure is
the intended signal that the source code is missing validation.

Also write:
- Happy-path tests with expected values
- Boundary tests (0, 1, maximum allowed value)
- Tests for None / wrong-type inputs where appropriate

CRITICAL — how to compute expected values:
- Do NOT hardcode the expected number as a literal (e.g. `assert result == 41.135`).
  You will get the math wrong and the test will fail for the wrong reason.
- Instead, compute the expected value INSIDE the test using the same formula the
  source code follows, with the input values as variables. Example:
      items = [{'price': 10, 'quantity': 4}]
      discount_percent = 5
      tax_rate = 8
      subtotal = sum(i['price'] * i['quantity'] for i in items)
      discount = subtotal * discount_percent / 100
      total_after_discount = subtotal - discount
      expected = total_after_discount + total_after_discount * tax_rate / 100
      assert process_order(items, discount_percent, tax_rate) == pytest.approx(expected)
- This way the test documents the intended formula and avoids arithmetic mistakes.

Float comparison rule:
- ANY assertion involving a float (or arithmetic that could yield a float) MUST use
  pytest.approx(...). Never compare floats with ==.

Rules:
- Only output raw Python code, no explanations
- No markdown, no code blocks, no backticks
- Always import pytest at the top
- Do NOT redefine or include the source code in tests
- The source code is already imported via: from source_code import *
- Use only valid Python syntax
"""

API_PROMPT = """You are a senior API test engineer.
Write pytest tests for the given API endpoint code.

Your job is to test what the endpoint SHOULD do, not what it currently does.
For any input that is logically invalid — missing required field, negative price / quantity / age,
wrong type (string where number expected), empty string, out-of-range value — assert that the
endpoint returns a 4xx status code (usually 400). If the endpoint silently accepts a nonsensical
input and returns 2xx, the test MUST fail — that failure is the intended signal that the endpoint
is missing validation.

Also write:
- Happy-path tests with correct payloads → assert 2xx + response body shape
- Not-found scenarios → assert 404
- Auth / permission scenarios where applicable → assert 401 / 403

CRITICAL — how to assert numeric response fields:
- Do NOT hardcode computed numeric expectations as literals. If the endpoint
  returns a calculated value, compute the expected value INSIDE the test using
  the same formula, with the request payload as variables. Example:
      payload = {'price': 10, 'quantity': 4, 'tax_rate': 8}
      expected_total = payload['price'] * payload['quantity'] * (1 + payload['tax_rate']/100)
      resp = client.post('/orders', json=payload)
      assert resp.json()['total'] == pytest.approx(expected_total)
- ANY assertion involving a float MUST use pytest.approx(...). Never compare
  floats with ==.

Rules:
- Only output raw Python code, no explanations
- No markdown, no code blocks, no backticks
- Always import pytest at the top
- Do NOT redefine or include the source code in tests
- The source code is already imported via: from source_code import *
- Test HTTP status codes (200, 201, 400, 404, 500, etc.)
- Test request / response body structure
- Use only valid Python syntax
"""

def write_tests(ctx: TestContext) -> TestContext:
    logger.info("Writer starting — iteration %d, source_type=%s", ctx.iteration + 1, ctx.source_type)
    system_prompt = API_PROMPT if ctx.source_type == "api" else FUNCTION_PROMPT
    prompt = system_prompt + "\n" + ctx.build_writer_context()

    llm = get_llm(ctx.writer_model)
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