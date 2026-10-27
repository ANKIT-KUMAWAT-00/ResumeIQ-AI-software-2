from pydantic import Field
from app.schemas.resume import StrictModel
class CriterionScore(StrictModel): criterion: str; score: int = Field(ge=0,le=100); weight: float = Field(ge=0,le=1); evidence: list[str] = Field(default_factory=list); rationale: str
class Finding(StrictModel): severity: str; category: str; issue: str; recommendation: str; source_reference: str | None = None
class BulletRewrite(StrictModel): original: str; rewritten: str; rationale: str; needs_input: bool = False; question: str | None = None
class LinkedInSuggestions(StrictModel): headlines: list[str] = Field(default_factory=list); about_rewrite: str = ""; skills: list[str] = Field(default_factory=list)
class ResumeReviewResult(StrictModel):
 role_fit_score: int = Field(ge=0,le=100)
 criteria: list[CriterionScore]
 ats_findings: list[Finding] = Field(default_factory=list)
 priority_fixes: list[str] = Field(min_length=1,max_length=5)
 bullet_rewrites: list[BulletRewrite] = Field(default_factory=list)
 missing_keywords: list[str] = Field(default_factory=list)
 unsupported_claims: list[str] = Field(default_factory=list)
 questions: list[str] = Field(default_factory=list)
 linkedin: LinkedInSuggestions | None = None
 advisory_note: str = "Advisory heuristic only; not a guaranteed ATS score, hiring probability, or employer decision."
