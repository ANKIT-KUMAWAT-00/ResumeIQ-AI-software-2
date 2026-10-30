from abc import ABC, abstractmethod
from typing import NamedTuple

class VerificationResult(NamedTuple):
    success: bool
    message: str
    code_for_development: str | None = None
    is_simulated: bool = False

class VerificationConfigurationError(RuntimeError):
    """Raised when production email/SMS providers are not configured."""
    pass

class VerificationProvider(ABC):
    @abstractmethod
    def send_verification_code(self, target: str, code: str, verification_type: str = "email") -> VerificationResult:
        pass
