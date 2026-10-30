import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
from app.services.extraction.normalizer import ResumeNormalizer
from app.services.extraction.adaptive_questions import AdaptiveQuestionEngine
from app.services.templates.validator import DocumentValidator
from app.services.templates.renderer import render_resume

ROOT = Path(__file__).resolve().parents[2]

def test_resume_normalizer_handles_loose_fields():
    loose_data = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "mobile": "+1234567890",
        "linkedin": "linkedin.com/in/janedoe",
        "github": "github.com/janedoe",
        "skills": {
            "Languages": "Python, TypeScript, SQL",
            "Frameworks": "FastAPI, React",
        },
        "education": [
            {
                "college": "State University",
                "major": "Computer Science",
                "date_range": "2020 - 2024",
                "cgpa": "3.9",
            }
        ],
        "work_experience": [
            {
                "role": "Software Engineering Intern",
                "company": "Tech Corp",
                "start": "Jun 2023",
                "end": "Aug 2023",
                "description": "• Built RESTful APIs with FastAPI.\n• Integrated PostgreSQL database.",
            }
        ],
        "projects": [
            {
                "name": "Cloud Dashboard",
                "tech_stack": "React, Tailwind, Node.js",
                "link": "https://dashboard.example.com",
                "details": ["Developed responsive real-time analytics UI."],
            }
        ],
        "achievements": ["Hackathon Winner 2023"],
    }

    normalized = ResumeNormalizer.normalize(loose_data)
    assert isinstance(normalized, ResumeJSON)
    assert normalized.contact.full_name == "Jane Doe"
    assert normalized.contact.email == "jane@example.com"
    assert str(normalized.contact.linkedin_url) == "https://linkedin.com/in/janedoe"
    assert len(normalized.skills) == 2
    assert normalized.skills[0].category == "Languages"
    assert "Python" in normalized.skills[0].skills
    assert normalized.education[0].institution == "State University"
    assert normalized.education[0].field_of_study == "Computer Science"
    assert normalized.experience[0].title == "Software Engineering Intern"
    assert normalized.experience[0].organization == "Tech Corp"
    assert len(normalized.experience[0].bullets) == 2
    assert normalized.projects[0].title == "Cloud Dashboard"
    assert "React" in normalized.projects[0].technologies
    assert len(normalized.achievements) == 1
    assert normalized.achievements[0].title == "Hackathon Winner 2023"

def test_normalizer_does_not_invent_missing_fields():
    minimal_data = {
        "name": "Alex Smith",
        "email": "alex@example.com",
    }
    normalized = ResumeNormalizer.normalize(minimal_data)
    assert normalized.contact.phone is None
    assert normalized.contact.github_url is None
    assert normalized.summary is None
    assert len(normalized.education) == 0
    assert len(normalized.experience) == 0
    assert len(normalized.projects) == 0

def test_adaptive_questions_detect_missing_required_fields():
    # Load LPU template
    lpu_spec = TemplateSpec.model_validate_json((ROOT / "template_specs/lpu-standard.json").read_text())

    # Minimal resume missing phone, linkedin, and projects
    resume_data = {
        "contact": {"full_name": "Bob Builder", "email": "bob@example.com"},
        "education": [{"institution": "Engineering College", "degree": "B.Tech"}],
        "skills": [{"category": "Languages", "skills": ["Python"]}],
    }
    canonical = ResumeNormalizer.normalize(resume_data)

    report = AdaptiveQuestionEngine.generate_questions(canonical, lpu_spec, resume_id=101)
    assert report.is_complete is False
    assert report.missing_required_count >= 2

    q_fields = [q.field_path for q in report.questions]
    assert "contact.phone" in q_fields
    assert "contact.linkedin_url" in q_fields # LPU uses 2-col contact with LinkedIn
    assert "projects" in q_fields # Projects required in LPU

def test_applying_answers_updates_canonical_resume():
    lpu_spec = TemplateSpec.model_validate_json((ROOT / "template_specs/lpu-standard.json").read_text())

    initial_resume = ResumeNormalizer.normalize({
        "name": "Test Candidate",
        "email": "test@example.com",
        "education": [{"institution": "University"}],
        "skills": [{"category": "Tech", "skills": ["Go"]}],
    })

    answers = {
        "contact.phone": "+91-9876543210",
        "contact.linkedin_url": "https://linkedin.com/in/testcandidate",
        "education.0.degree": "B.Sc Computer Science",
    }

    updated = AdaptiveQuestionEngine.apply_answers(initial_resume, answers)
    assert updated.contact.phone == "+91-9876543210"
    assert str(updated.contact.linkedin_url) == "https://linkedin.com/in/testcandidate"
    assert updated.education[0].degree == "B.Sc Computer Science"

def test_document_quality_validation(tmp_path):
    lpu_spec = TemplateSpec.model_validate_json((ROOT / "template_specs/lpu-standard.json").read_text())
    ref_resume = ResumeJSON.model_validate_json((ROOT / "sample_data/reference_resume.json").read_text())

    # Render docx
    docx_file = render_resume(ref_resume, lpu_spec, tmp_path / "valid_resume.docx")
    assert docx_file.exists()

    # Validate output
    val_report = DocumentValidator.validate(ref_resume, lpu_spec, docx_path=docx_file)
    assert val_report.is_valid is True
    assert val_report.quality_score >= 90
    assert len(val_report.failed_checks) == 0

def test_document_validation_fails_on_corrupt_or_missing_file():
    lpu_spec = TemplateSpec.model_validate_json((ROOT / "template_specs/lpu-standard.json").read_text())
    ref_resume = ResumeJSON.model_validate_json((ROOT / "sample_data/reference_resume.json").read_text())

    # Non-existent file
    val_report = DocumentValidator.validate(ref_resume, lpu_spec, docx_path="/tmp/non_existent_file.docx")
    assert val_report.is_valid is False
    assert "docx_file_exists" in val_report.failed_checks

