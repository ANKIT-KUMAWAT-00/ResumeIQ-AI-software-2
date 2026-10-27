from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
class StrictModel(BaseModel): model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
class ContactInfo(StrictModel):
 full_name: Text
 email: str | None = Field(default=None, max_length=254)
 phone: str | None = Field(default=None, max_length=50)
 location: str | None = Field(default=None, max_length=200)
 github_url: HttpUrl | None = None
 linkedin_url: HttpUrl | None = None
 portfolio_url: HttpUrl | None = None
class EducationEntry(StrictModel):
 institution: Text; degree: str | None = None; field_of_study: str | None = None
 start_date: str | None = None; end_date: str | None = None; location: str | None = None
 details: list[str] = Field(default_factory=list, max_length=20)
class SkillGroup(StrictModel): category: Text; skills: list[Text] = Field(default_factory=list, max_length=100)
class ResumeBullet(StrictModel): text: Text; source_reference: str | None = None
class ProjectEntry(StrictModel):
 title: Text; technologies: list[str] = Field(default_factory=list, max_length=50); bullets: list[ResumeBullet] = Field(default_factory=list, max_length=30)
 url: HttpUrl | None = None; start_date: str | None = None; end_date: str | None = None
class ExperienceEntry(StrictModel):
 title: Text; organization: Text; location: str | None = None; start_date: str | None = None; end_date: str | None = None
 bullets: list[ResumeBullet] = Field(default_factory=list, max_length=40)
class SimpleEntry(StrictModel): title: Text; issuer: str | None = None; date: str | None = None; details: list[str] = Field(default_factory=list, max_length=20)
class ActivityEntry(StrictModel): title: Text; organization: str | None = None; date: str | None = None; details: list[str] = Field(default_factory=list, max_length=20)
class ResumeJSON(StrictModel):
 contact: ContactInfo
 summary: str | None = Field(default=None, max_length=2000)
 education: list[EducationEntry] = Field(default_factory=list, max_length=20)
 skills: list[SkillGroup] = Field(default_factory=list, max_length=40)
 projects: list[ProjectEntry] = Field(default_factory=list, max_length=50)
 experience: list[ExperienceEntry] = Field(default_factory=list, max_length=50)
 certifications: list[SimpleEntry] = Field(default_factory=list, max_length=50)
 achievements: list[SimpleEntry] = Field(default_factory=list, max_length=50)
 extracurricular_activities: list[ActivityEntry] = Field(default_factory=list, max_length=50)
 @field_validator("summary")
 @classmethod
 def blank_summary_to_none(cls, value): return value if value and value.strip() else None
