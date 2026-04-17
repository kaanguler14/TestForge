from dataclasses import dataclass, field
from typing import Optional

@dataclass
class TestContext:
    
    # Kaynak kod bilgisi — ne test ediyoruz
    source_code: str
    source_type: str  # "function" veya "api"

    # Ajan 1 çıktısı
    generated_tests: Optional[str] = None

    # Ajan 2 çıktısı
    test_output: Optional[str] = None
    passed: int = 0
    failed: int = 0

    coverage: int = 0
    coverage_threshold: int = 80

    # Ajan 3 çıktısı
    analysis: Optional[str] = None
    failure_type: Optional[str] = None  # "test_error" veya "source_bug"

    # Ajan 4 çıktısı
    suggestions: Optional[str] = None

    # Model ayarları — her ajan farklı model kullanabilir
    writer_model: str = "qwen2.5-coder:7b"
    analyzer_model: str = "qwen3:8b"
    suggester_model: str = "qwen3:8b"

    # Döngü yönetimi
    iteration: int = 0
    max_iterations: int = 3
    history: list = field(default_factory=list)

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
        """Her iterasyonun özetini sakla"""
        self.history.append({
            "iteration": self.iteration,
            "passed": self.passed,
            "failed": self.failed,
            "coverage": self.coverage,
            "analysis": self.analysis
        })

    def build_writer_context(self) -> str:
        base = f"### Source Code\n{self.source_code}\n"

        if self.iteration > 0:
            base += f"\n### Previous Test Output\n{self.test_output}"
            base += f"\n### Analysis\n{self.analysis}"
            base += f"\n\nThis is attempt #{self.iteration}. Fix the tests accordingly."

        return base