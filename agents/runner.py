import logging
import os
import re
import subprocess
import tempfile

from .context import TestContext

logger = logging.getLogger(__name__)

USE_DOCKER = os.getenv("AUTOTEST_USE_DOCKER", "").lower() in ("1", "true", "yes")
DOCKER_IMAGE = os.getenv("AUTOTEST_DOCKER_IMAGE", "autotest-sandbox")
_image_checked = False


def _ensure_docker_image() -> None:
    global _image_checked
    if _image_checked:
        return
    try:
        check = subprocess.run(
            ["docker", "image", "inspect", DOCKER_IMAGE],
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "AUTOTEST_USE_DOCKER is set but the docker CLI was not found"
        ) from exc
    if check.returncode != 0:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        dockerfile = os.path.join(repo_root, "Dockerfile.sandbox")
        logger.info("Building sandbox image %s from %s", DOCKER_IMAGE, dockerfile)
        subprocess.run(
            ["docker", "build", "-t", DOCKER_IMAGE, "-f", dockerfile, repo_root],
            check=True,
        )
    _image_checked = True


def _build_pytest_cmd(sandbox_dir: str, test_filename: str) -> list[str]:
    pytest_args = [test_filename, "-v", "--tb=short", "--cov=source_code", "--cov-report=term"]
    if not USE_DOCKER:
        return ["pytest", *pytest_args]
    _ensure_docker_image()
    return [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "512m", "--cpus", "2",
        "-v", f"{sandbox_dir}:/work",
        "-w", "/work",
        DOCKER_IMAGE,
        "pytest", *pytest_args,
    ]


def run_tests(ctx: TestContext) -> TestContext:
    logger.info("Runner starting - iteration %d", ctx.iteration)
    sandbox_dir = os.path.abspath("sandbox")
    os.makedirs(sandbox_dir, exist_ok=True)

    if not ctx.generated_tests:
        ctx.test_output = "ERROR: No tests were generated"
        ctx.failed = 1
        return ctx

    has_assertions = (
        "assert" in ctx.generated_tests
        or "pytest.raises" in ctx.generated_tests
        or "pytest.approx" in ctx.generated_tests
    )
    if not has_assertions:
        ctx.test_output = "ERROR: No assertions found in tests"
        ctx.failed = 1
        return ctx

    source_path = os.path.join(sandbox_dir, "source_code.py")
    with open(source_path, "w", encoding="utf-8") as file:
        file.write(ctx.source_code)

    test_code = "from source_code import *\n\n" + ctx.generated_tests

    try:
        compile(test_code, "<test>", "exec")
    except SyntaxError as e:
        ctx.test_output = f"SYNTAX ERROR: {e}"
        ctx.failed = 1
        return ctx

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=sandbox_dir, delete=False, encoding="utf-8") as file:
        file.write(test_code)
        tmp_path = file.name

    test_filename = os.path.basename(tmp_path)
    try:
        cmd = _build_pytest_cmd(sandbox_dir, test_filename)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=sandbox_dir if not USE_DOCKER else None,
        )
        ctx.test_output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        ctx.test_output = "ERROR: Test timed out after 30 seconds"
        ctx.failed = 1
    except RuntimeError as exc:
        ctx.test_output = f"ERROR: {exc}"
        ctx.failed = 1
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    passed = re.search(r"(\d+) passed", ctx.test_output)
    failed = re.search(r"(\d+) failed", ctx.test_output)
    errors = re.search(r"(\d+) error", ctx.test_output)
    ctx.passed = int(passed.group(1)) if passed else 0
    ctx.failed = int(failed.group(1)) if failed else 0

    if errors and ctx.passed == 0:
        ctx.failed = max(ctx.failed, int(errors.group(1)))

    coverage_match = re.search(r"source_code\.py\s+\d+\s+\d+\s+(\d+)%", ctx.test_output)
    ctx.coverage = int(coverage_match.group(1)) if coverage_match else 0

    logger.info("Runner done - passed=%d, failed=%d, coverage=%d%%", ctx.passed, ctx.failed, ctx.coverage)
    return ctx
