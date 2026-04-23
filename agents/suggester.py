import json
import logging
import os
import re

from . import get_llm
from .context import TestContext

logger = logging.getLogger(__name__)

COT_PROMPT = """You are a Python code reviewer. Find real bugs in the source code.

There are TWO categories of bugs you must report:

CATEGORY A - CRASH BUGS:
Inputs that cause an unhandled exception (KeyError, TypeError, ZeroDivisionError, AttributeError, IndexError, etc.).

CATEGORY B - LOGIC / VALIDATION BUGS:
Inputs that the code accepts without error but produce nonsensical, impossible, or clearly wrong results.

Examples:
- A percentage parameter accepts negative or >100 values and is used directly in math
- A quantity / price / age / count accepts negative values silently
- A function that should reject a value returns an impossible result
- Business rules are violated silently

Return ONLY valid JSON with this exact shape:
{
  "verdict": "BUGS_FOUND" or "NO_ISSUES_FOUND",
  "summary": "short summary",
  "findings": [
    {
      "category": "crash_bug" or "logic_bug",
      "input": "exact triggering input",
      "problem": "what goes wrong",
      "fix_hint": "short code-level fix"
    }
  ]
}

Rules:
- Report a bug ONLY if there is a specific input and a specific bad outcome
- If everything is handled, return verdict NO_ISSUES_FOUND and an empty findings list
- Output JSON only
- No markdown
- Keep strings concise
- Do NOT suggest changes to tests, naming, comments, logging, frameworks, or style
"""


def _load_examples() -> str:
    try:
        examples_path = os.path.join(os.path.dirname(__file__), "prompts", "suggester_examples.txt")
        with open(examples_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return ""


def _extract_json_object(text: str) -> dict:
    raw = _strip_code_fences(text).strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            valid = [_normalize_payload(item) for item in parsed]
            valid = [item for item in valid if item]
            return _merge_payloads(valid) if valid else _fallback_payload(text)
        if isinstance(parsed, dict):
            normalized = _normalize_payload(parsed)
            if normalized:
                return normalized
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
            normalized = _normalize_payload(payload)
            if normalized:
                payloads.append(normalized)
        idx = end

    if not payloads:
        raise ValueError("No JSON object found in suggester response")
    return _merge_payloads(payloads)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped


def _is_suggestion_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    return "verdict" in payload and "findings" in payload


def _normalize_payload(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None

    if _is_suggestion_payload(payload):
        return payload

    analysis = payload.get("analysis")
    container = analysis if isinstance(analysis, dict) else payload

    crash_bugs = container.get("crash_bugs")
    logic_bugs = container.get("logic_bugs")
    if not isinstance(crash_bugs, list) and not isinstance(logic_bugs, list):
        return None

    findings = []
    findings.extend(_convert_legacy_findings(crash_bugs, "crash_bug"))
    findings.extend(_convert_legacy_findings(logic_bugs, "logic_bug"))

    summary = (
        payload.get("summary")
        or payload.get("conclusion")
        or container.get("summary")
        or "Normalized legacy suggester response."
    )
    return {
        "verdict": "BUGS_FOUND" if findings else "NO_ISSUES_FOUND",
        "summary": summary,
        "findings": findings,
    }


def _convert_legacy_findings(items: object, category: str) -> list[dict]:
    if not isinstance(items, list):
        return []

    findings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        problem = item.get("problem") or item.get("description") or "No problem description"
        error = item.get("error")
        if error and error not in problem:
            problem = f"{problem} ({error})"
        findings.append(
            {
                "category": category,
                "input": item.get("input") or item.get("input_example") or "unknown input",
                "problem": problem,
                "fix_hint": item.get("fix_hint") or item.get("fix") or "No fix hint",
            }
        )
    return findings


def _merge_payloads(payloads: list[dict]) -> dict:
    if len(payloads) == 1:
        return payloads[0]

    findings = []
    for payload in payloads:
        findings.extend(payload.get("findings") or [])

    verdict = "BUGS_FOUND" if findings else "NO_ISSUES_FOUND"
    return {
        "verdict": verdict,
        "summary": "Multiple review findings were identified." if findings else "No issues found. Code is solid.",
        "findings": findings,
        "items": payloads,
    }


def _fallback_payload(response: str) -> dict:
    cleaned = response.strip()
    verdict = "NO_ISSUES_FOUND" if "No issues found. Code is solid." in cleaned else "BUGS_FOUND"
    findings = []
    if cleaned and verdict == "BUGS_FOUND":
        findings.append(
            {
                "category": "logic_bug",
                "input": "See raw suggester output",
                "problem": cleaned,
                "fix_hint": "Review the raw suggester output manually.",
            }
        )
    return {
        "verdict": verdict,
        "summary": "Fallback parser was used for suggester output.",
        "findings": findings,
    }


def _format_suggestions(payload: dict) -> str:
    verdict = payload.get("verdict", "BUGS_FOUND")
    summary = payload.get("summary") or ""
    findings = payload.get("findings") or []

    if verdict == "NO_ISSUES_FOUND" and not findings:
        return summary or "No issues found. Code is solid."

    lines = [f"VERDICT: {verdict}"]
    if summary:
        lines.append(f"Summary: {summary}")

    if findings:
        lines.append("Findings:")
        for index, finding in enumerate(findings, start=1):
            category = finding.get("category", "issue")
            input_value = finding.get("input", "unknown input")
            problem = finding.get("problem", "No problem description")
            fix_hint = finding.get("fix_hint", "No fix hint")
            lines.append(f"{index}. [{category}] Input: {input_value}")
            lines.append(f"   Problem: {problem}")
            lines.append(f"   Fix hint: {fix_hint}")
    return "\n".join(lines)


def suggest_improvements(ctx: TestContext) -> TestContext:
    logger.info("Suggester starting - passed=%d, failed=%d", ctx.passed, ctx.failed)
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
        ctx.suggestions_structured = {
            "verdict": "ERROR",
            "summary": str(e),
            "findings": [],
        }
        return ctx

    try:
        payload = _extract_json_object(response)
    except Exception:
        payload = _fallback_payload(response)

    ctx.suggestions_structured = payload
    ctx.suggestions = _format_suggestions(payload)
    return ctx
