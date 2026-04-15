import subprocess
import tempfile
import os
import re
import logging
from .context import TestContext

logger = logging.getLogger(__name__)

def run_tests(ctx: TestContext) -> TestContext:
    logger.info("Runner starting — iteration %d", ctx.iteration)
    # Test üretilmiş mi?
    if not ctx.generated_tests:
        ctx.test_output = "ERROR: No tests were generated"
        ctx.failed = 1
        return ctx

    # Assertion var mı?
    has_assertions = (
        "assert" in ctx.generated_tests
        or "pytest.raises" in ctx.generated_tests
        or "pytest.approx" in ctx.generated_tests
    )
    if not has_assertions:
        ctx.test_output = "ERROR: No assertions found in tests"
        ctx.failed = 1
        return ctx

    # Kaynak kodu ayrı dosyaya yaz
    source_path = os.path.abspath(os.path.join("sandbox", "source_code.py"))
    with open(source_path, "w", encoding="utf-8") as f:
        f.write(ctx.source_code)

    # Test koduna import ekle, kaynak kodu EKLEME
    test_code = "from source_code import *\n\n" + ctx.generated_tests

    # Syntax ön kontrolü — geçersiz kodu subprocess'e gönderme
    try:
        compile(test_code, "<test>", "exec")
    except SyntaxError as e:
        ctx.test_output = f"SYNTAX ERROR: {e}"
        ctx.failed = 1
        return ctx

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        dir="sandbox",
        delete=False
    ) as f:
        f.write(test_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["pytest", tmp_path, "-v", "--tb=short", "--cov=source_code", "--cov-report=term"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.abspath("sandbox")
        )
        ctx.test_output = result.stdout + result.stderr

    except subprocess.TimeoutExpired:
        ctx.test_output = "ERROR: Test timed out after 30 seconds"
        ctx.failed = 1

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Parse et
    passed = re.search(r"(\d+) passed", ctx.test_output)
    failed = re.search(r"(\d+) failed", ctx.test_output)
    errors = re.search(r"(\d+) error", ctx.test_output)
    ctx.passed = int(passed.group(1)) if passed else 0
    ctx.failed = int(failed.group(1)) if failed else 0

    # ERROR durumu — import hatası, collection hatası vb.
    if errors and ctx.passed == 0:
        ctx.failed = max(ctx.failed, int(errors.group(1)))

    # Coverage parse et
    cov = re.search(r"source_code\.py\s+\d+\s+\d+\s+(\d+)%", ctx.test_output)
    ctx.coverage = int(cov.group(1)) if cov else 0

    logger.info("Runner done — passed=%d, failed=%d, coverage=%d%%", ctx.passed, ctx.failed, ctx.coverage)
    return ctx