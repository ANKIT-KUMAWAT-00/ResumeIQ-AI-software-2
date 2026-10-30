from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import Field
from app.schemas.resume import StrictModel

ValidationSeverity = Literal["pass", "warning", "fail"]

class ValidationCheck(StrictModel):
    check_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    severity: ValidationSeverity = "pass"
    message: str = Field(min_length=1, max_length=500)
    details: dict[str, Any] | None = None

class DocumentQualityReport(StrictModel):
    is_valid: bool = True
    quality_score: int = Field(default=100, ge=0, le=100)
    checks: list[ValidationCheck] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    page_count: int | None = None
    template_fidelity_notes: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

