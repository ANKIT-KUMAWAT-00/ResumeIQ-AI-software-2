from typing import Any, Literal
from pydantic import Field
from app.schemas.resume import StrictModel

QuestionInputType = Literal[
    "text",
    "textarea",
    "date",
    "url",
    "select",
    "multiselect",
    "repeatable",
]

class AdaptiveQuestion(StrictModel):
    field_path: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=5, max_length=500)
    input_type: QuestionInputType = "text"
    required: bool = False
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    help_text: str | None = Field(default=None, max_length=300)
    options: list[str] | None = Field(default=None, max_length=50)
    current_value: Any = None
    section_id: str | None = Field(default=None, max_length=60)

class MissingInformationReport(StrictModel):
    resume_id: int
    template_id: str
    is_complete: bool = False
    missing_required_count: int = 0
    missing_optional_count: int = 0
    questions: list[AdaptiveQuestion] = Field(default_factory=list)

class AnswerItem(StrictModel):
    field_path: str
    value: Any

class ResumeAnswerSubmission(StrictModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False

