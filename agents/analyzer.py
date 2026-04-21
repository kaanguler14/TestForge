import json
import logging

from . import get_llm
from .context import TestContext

logger = logging.getLogger(__name__)

FAILURE_PROMPT = """You are a Python debugging expert.
Analyze the pytest output, source code, and generated tests together.

CRITICAL CONTEXT - how the tests were written:
The tests follow a "should-be" philosophy: they test what the code SHOULD do,
not what it currently does. This means:
- If a test expects pytest.raises(ValueError / TypeError / KeyError / etc.)
  for a logically invalid input (negative value, None, missing key, out-of-range,
  empty collection where items are required) and the code does NOT raise,
  this is SOURCE_BUG, NOT test_error. The test is correct; the source code is
  missing validation.
- If a test asserts a 4xx status for an invalid API payload and the endpoint
  returns 2xx, this is SOURCE_BUG. The endpoint is missing validation.
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

Return ONLY valid JSON with this exact shape:
{
  "mode": "failure_analysis",
  "verdict": "TEST_ERROR" or "SOURCE_BUG",
  "reason": "short explanation",
  "fix_hint": "If TEST_ERROR, how to fix the test. If SOURCE_BUG, what should be fixed in the source code.",
  "evidence": ["specific proof 1", "specific proof 2"]
}

Rules:
- Output JSON only
- No markdown
- Keep reason and fix_hint concise
- Evidence must be a JSON array of short strings
"""

COVERAGE_PROMPT = """You are a Python test coverage expert.
The tests pass but coverage is too low.
Analyze the source code and existing tests.

Return ONLY valid JSON with this exact shape:
{
  "mode": "coverage_analysis",
  "verdict": "COVERAGE_GAP",
  "reason": "short summary of the coverage gap",
  "untested_cases": ["case 1", "case 2"],
  "recommended_tests": ["test idea 1", "test idea 2"]
}

Rules:
- Output JSON only
- No markdown
- Keep all strings concise
"""


def _extract_json_object(text: str) -> dict:
    raw = text.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return _merge_payloads(parsed)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    idx = 0
    payloads = []
    while idx < len(raw):
        if raw[idx] != "{":
            idx += 1
            continue
        try:
            payload, end = decoder.raw_decode(raw, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
        idx = end

    if not payloads:
        raise ValueError("No JSON object found in analyzer response")
    return _merge_payloads(payloads)


def _merge_payloads(payloads: list[dict]) -> dict:
    if len(payloads) == 1:
        return payloads[0]

    mode = payloads[0].get("mode", "failure_analysis")
    if mode == "coverage_analysis":
        untested_cases = []
        recommended_tests = []
        for payload in payloads:
            untested_cases.extend(payload.get("untested_cases") or [])
            recommended_tests.extend(payload.get("recommended_tests") or [])
        return {
            "mode": "coverage_analysis",
            "verdict": "COVERAGE_GAP",
            "reason": "Multiple coverage gaps were identified.",
            "untested_cases": untested_cases,
            "recommended_tests": recommended_tests,
            "items": payloads,
        }

    verdict = "SOURCE_BUG" if any((p.get("verdict") or "").upper() == "SOURCE_BUG" for p in payloads) else "TEST_ERROR"
    evidence = []
    for payload in payloads:
        reason = payload.get("reason")
        if reason:
            evidence.append(reason)
        evidence.extend(payload.get("evidence") or [])
    return {
        "mode": "failure_analysis",
        "verdict": verdict,
        "reason": "Multiple failing cases were identified.",
        "fix_hint": "Review the itemized findings and fix the source or tests accordingly.",
        "evidence": evidence,
        "items": payloads,
    }


def _normalize_failure_type(verdict: str | None) -> str | None:
    if not verdict:
        return None
    verdict = verdict.strip().upper()
    if verdict == "SOURCE_BUG":
        return "source_bug"
    if verdict == "TEST_ERROR":
        return "test_error"
    return None


def _format_failure_analysis(payload: dict) -> str:
    lines = [f"VERDICT: {payload.get('verdict', 'UNKNOWN')}"]
    reason = payload.get("reason")
    if reason:
        lines.append(f"Reason: {reason}")

    evidence = payload.get("evidence") or []
    if evidence:
        lines.append("Evidence:")
        lines.extend(f"- {item}" for item in evidence)

    fix_hint = payload.get("fix_hint")
    if fix_hint:
        lines.append(f"Fix hint: {fix_hint}")
    return "\n".join(lines)


def _format_coverage_analysis(payload: dict) -> str:
    lines = [f"VERDICT: {payload.get('verdict', 'COVERAGE_GAP')}"]
    reason = payload.get("reason")
    if reason:
        lines.append(f"Reason: {reason}")

    untested_cases = payload.get("untested_cases") or []
    if untested_cases:
        lines.append("Untested cases:")
        lines.extend(f"- {item}" for item in untested_cases)

    recommended_tests = payload.get("recommended_tests") or []
    if recommended_tests:
        lines.append("Recommended tests:")
        lines.extend(f"- {item}" for item in recommended_tests)
    return "\n".join(lines)


def _fallback_failure_payload(response: str) -> dict:
    first_line = response.strip().split("\n")[0].upper()
    verdict = "SOURCE_BUG" if "SOURCE_BUG" in first_line else "TEST_ERROR"
    return {
        "mode": "failure_analysis",
        "verdict": verdict,
        "reason": "Analyzer returned non-JSON output, so a fallback parser was used.",
        "fix_hint": response.strip(),
        "evidence": [],
    }


def _fallback_coverage_payload(response: str) -> dict:
    return {
        "mode": "coverage_analysis",
        "verdict": "COVERAGE_GAP",
        "reason": "Analyzer returned non-JSON output, so a fallback parser was used.",
        "untested_cases": [],
        "recommended_tests": [response.strip()] if response.strip() else [],
    }


def analyze_results(ctx: TestContext) -> TestContext:
    logger.info("Analyzer starting - failed=%d, coverage=%d%%", ctx.failed, ctx.coverage)
    if ctx.failed == 0 and ctx.coverage >= ctx.coverage_threshold:
        logger.info("Analyzer skipping - all tests pass and coverage is sufficient")
        ctx.add_to_history()
        return ctx

    system_prompt = FAILURE_PROMPT if ctx.failed > 0 else COVERAGE_PROMPT

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
        ctx.analysis_structured = {
            "mode": "analyzer_error",
            "verdict": "ERROR",
            "reason": str(e),
        }
        ctx.add_to_history()
        return ctx

    try:
        payload = _extract_json_object(response)
    except Exception:
        payload = _fallback_failure_payload(response) if ctx.failed > 0 else _fallback_coverage_payload(response)

    ctx.analysis_structured = payload

    if ctx.failed > 0:
        ctx.failure_type = _normalize_failure_type(payload.get("verdict")) or "test_error"
        ctx.analysis = _format_failure_analysis(payload)
        if ctx.failure_type == "source_bug":
            logger.info("Analyzer verdict: SOURCE_BUG")
        else:
            logger.info("Analyzer verdict: TEST_ERROR")
    else:
        ctx.analysis = _format_coverage_analysis(payload)

    ctx.add_to_history()
    return ctx
