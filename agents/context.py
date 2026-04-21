from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TestContext:
    source_code: str
    source_type: str  # "function" or "api"
    run_id: Optional[str] = None
    artifact_dir: Optional[str] = None

    generated_tests: Optional[str] = None

    test_output: Optional[str] = None
    passed: int = 0
    failed: int = 0

    coverage: int = 0
    coverage_threshold: int = 80

    analysis: Optional[str] = None
    analysis_structured: dict = field(default_factory=dict)
    failure_type: Optional[str] = None  # "test_error" or "source_bug"

    suggestions: Optional[str] = None
    suggestions_structured: dict = field(default_factory=dict)

    writer_model: str = "qwen2.5-coder:7b"
    analyzer_model: str = "qwen3:8b"
    suggester_model: str = "qwen3:8b"

    iteration: int = 0
    max_iterations: int = 3
    history: list = field(default_factory=list)
    timings_summary: dict = field(default_factory=dict)

    def should_retry(self) -> bool:
        if self.iteration >= self.max_iterations:
            return False
        if self.failure_type == "source_bug":
            return False
        if self.failed > 0:
            return True
        if self.coverage < self.coverage_threshold:
            return True
        return False

    def add_to_history(self):
        self.history.append(
            {
                "iteration": self.iteration,
                "passed": self.passed,
                "failed": self.failed,
                "coverage": self.coverage,
                "analysis": self.analysis,
                "failure_type": self.failure_type,
            }
        )

    def build_writer_context(self) -> str:
        base = f"### Source Code\n{self.source_code}\n"

        if self.iteration > 0:
            if self.test_output:
                base += f"\n### Previous Test Output\n{self.test_output}"
            if self.analysis:
                base += f"\n### Analysis\n{self.analysis}"
            base += f"\n\nThis is attempt #{self.iteration}. Fix the tests accordingly."

        return base
