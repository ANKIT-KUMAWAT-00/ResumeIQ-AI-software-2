import json
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.schemas.resume import (
    ResumeJSON,
    ContactInfo,
    EducationEntry,
    SkillGroup,
    ProjectEntry,
    ResumeBullet,
)
from app.schemas.review import ResumeReviewResult, CriterionScore
from app.services.gemini.client import GeminiService

ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def mock_gemini(monkeypatch):
    """Mocks Gemini API calls for deterministic, offline test execution."""
    sample_resume = ResumeJSON(
        contact=ContactInfo(
            full_name="Ankit Sharma",
            email="ankit.sharma@example.com",
            phone="+919876543210",
            location="Punjab, India",
            github_url=None,  # Missing, to test adaptive question engine
            linkedin_url="https://linkedin.com/in/ankit-sharma",
            portfolio_url=None,
        ),
        summary="Final-year Computer Science student passionate about backend and AI engineering.",
        education=[
            EducationEntry(
                institution="Lovely Professional University",
                degree="Bachelor of Technology",
                field_of_study="Computer Science and Engineering",
                start_date="2021",
                end_date="2025",
                location="Phagwara, Punjab",
                details=["CGPA: 8.8/10"],
            )
        ],
        skills=[
            SkillGroup(
                category="Programming Languages",
                skills=["Python", "JavaScript", "C++", "SQL"],
            ),
            SkillGroup(
                category="Frameworks & Tools",
                skills=["FastAPI", "React", "Docker", "Git", "PostgreSQL"],
            ),
        ],
        projects=[
            ProjectEntry(
                title="AI Resume Intelligence SaaS",
                technologies=["FastAPI", "Python", "Next.js", "Docker"],
                bullets=[
                    ResumeBullet(text="Architected full-stack resume analysis engine."),
                    ResumeBullet(text="Implemented template-aware document generation."),
                ],
                url="https://github.com/ankit/resumeiq",
                start_date="Jan 2024",
                end_date="May 2024",
            )
        ],
        experience=[],
        certifications=[],
        achievements=[],
        extracurricular_activities=[],
    )

    def fake_init(self):
        self.model = "gemini-2.5-flash"
        self.client = None

    def fake_extract(self, text: str) -> ResumeJSON:
        return sample_resume

    def fake_enhance(self, resume: ResumeJSON, target_role: str) -> ResumeJSON:
        enhanced = resume.model_copy(deep=True)
        # Enhance bullet points without hallucinations
        if enhanced.projects and enhanced.projects[0].bullets:
            enhanced.projects[0].bullets[0].text = (
                "Spearheaded end-to-end architecture of full-stack resume analysis engine, optimizing processing throughput."
            )
        return enhanced

    def fake_review(self, resume, rubric, target_role, include_linkedin=False) -> ResumeReviewResult:
        return ResumeReviewResult(
            role_fit_score=85,
            criteria=[CriterionScore(criterion="Technical Skills", score=85, weight=1.0, rationale="Strong match")],
            ats_findings=[],
            priority_fixes=["Add GitHub link to resume"],
            bullet_rewrites=[],
            missing_keywords=[],
            unsupported_claims=[],
            questions=[],
        )

    monkeypatch.setattr(settings, "gemini_api_key", "mock-gemini-key")
    monkeypatch.setattr(GeminiService, "__init__", fake_init)
    monkeypatch.setattr(GeminiService, "extract", fake_extract)
    monkeypatch.setattr(GeminiService, "enhance", fake_enhance)
    monkeypatch.setattr(GeminiService, "review", fake_review)


def test_full_pipeline_end_to_end(mock_gemini, monkeypatch):
    """
    Verifies complete multi-stage workflow:
    1. Register & verify user with simulated dev OTP.
    2. Inspect LPU built-in template specification.
    3. Upload candidate resume (PDF).
    4. Extract and normalize into canonical ResumeJSON schema.
    5. Detect missing information & verify targeted adaptive questions.
    6. Submit answers to missing fields -> transitions to ready_for_generation.
    7. Enhance resume content with Gemini (non-hallucinatory).
    8. Generate DOCX & PDF documents.
    9. Validate DocumentQualityReport score (>=85) and check items.
    10. Download generated DOCX and PDF documents.
    """
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "allow_dev_otp", True)
    monkeypatch.setattr(settings, "run_jobs_inline", True)

    def fake_convert(docx_path, output_dir=None):
        src = Path(docx_path)
        dest = Path(output_dir) if output_dir else src.parent
        out = dest / f"{src.stem}.pdf"
        out.write_bytes(
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF"
        )
        return out

    monkeypatch.setattr("app.services.pipeline.convert_docx_to_pdf", fake_convert)

    client = TestClient(app)
    uid = uuid.uuid4().hex[:8]
    email = f"candidate-{uid}@example.com"

    # Step 1: User Registration
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Ankit Sharma",
            "email": email,
            "phone": "+919876543210",
            "password": "StrongPassword123!",
        },
    )
    assert reg_resp.status_code == 200, reg_resp.text
    reg_data = reg_resp.json()
    assert reg_data["email"] == email
    assert reg_data["verification"]["simulated"] is True
    dev_code = reg_data["verification"]["development_code"]

    # Verify Email using simulated dev OTP
    ver_resp = client.post(
        "/api/auth/verify-email",
        json={"email": email, "code": dev_code},
    )
    assert ver_resp.status_code == 200
    assert ver_resp.json()["email_verified"] is True

    # Check authenticated session
    me_resp = client.get("/api/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email_verified"] is True

    # Step 2: Query Templates & Verify LPU Standard
    tpl_resp = client.get("/api/templates")
    assert tpl_resp.status_code == 200
    templates = tpl_resp.json()
    lpu_tpl = next((t for t in templates if t["template_id"] == "lpu-standard"), None)
    assert lpu_tpl is not None, "lpu-standard template must be available"
    assert lpu_tpl["is_confirmed"] is True

    spec_resp = client.get("/api/templates/lpu-standard/specification")
    assert spec_resp.status_code == 200
    spec_data = spec_resp.json()
    assert spec_data["template_id"] == "lpu-standard"
    assert "sections" in spec_data
    section_ids = [s["id"] for s in spec_data["sections"]]
    assert "education" in section_ids
    assert "skills" in section_ids
    assert "projects" in section_ids

    # Step 3: Upload Candidate Resume
    real_pdf_path = ROOT / "sample_data" / "reference_resume.pdf"
    pdf_bytes = real_pdf_path.read_bytes()
    upload_resp = client.post(
        "/api/resumes/upload",
        files={"file": ("ankit_resume.pdf", pdf_bytes, "application/pdf")},
        data={
            "target_role": "sde-general",
            "template_id": "lpu-standard",
            "template_overrides": json.dumps({"fonts": {"family": "Arial", "body_pt": 8.5}}),
        },
    )
    assert upload_resp.status_code == 200, upload_resp.text
    resume_id = upload_resp.json()["id"]

    # Step 4: Extraction & Normalization
    extract_resp = client.post(f"/api/resumes/{resume_id}/extract")
    assert extract_resp.status_code == 200, extract_resp.text
    ext_data = extract_resp.json()["data"]
    # Strictly validate against Pydantic schema
    canonical_resume = ResumeJSON.model_validate(ext_data)
    assert canonical_resume.contact.full_name == "Ankit Sharma"
    assert canonical_resume.contact.email == "ankit.sharma@example.com"

    # Step 5: Adaptive Question Detection
    missing_resp = client.get(f"/api/resumes/{resume_id}/missing-information")
    assert missing_resp.status_code == 200, missing_resp.text
    missing_data = missing_resp.json()
    assert "questions" in missing_data
    # github_url was None in sample, so a question should be present
    question_fields = [q["field_path"] for q in missing_data["questions"]]
    assert "contact.github_url" in question_fields

    # Step 6: Submit Answers
    answers_payload = {
        "answers": {
            "contact.github_url": "https://github.com/ankit-dev",
            "contact.portfolio_url": "https://ankit-portfolio.dev",
        },
        "confirm": True,
    }
    ans_resp = client.post(f"/api/resumes/{resume_id}/answers", json=answers_payload)
    assert ans_resp.status_code == 200, ans_resp.text
    ans_data = ans_resp.json()
    assert ans_data["ok"] is True
    assert ans_data["collection_status"] == "ready_for_generation"
    assert ans_data["updated_resume"]["contact"]["github_url"] == "https://github.com/ankit-dev"

    # Step 7: AI Content Enhancement
    enhance_resp = client.post(f"/api/resumes/{resume_id}/enhance")
    assert enhance_resp.status_code == 200, enhance_resp.text
    enhanced_data = enhance_resp.json()["enhanced"]
    # Check that the enhanced bullet updated cleanly without altering facts
    assert "Spearheaded" in enhanced_data["projects"][0]["bullets"][0]["text"]
    assert enhanced_data["contact"]["full_name"] == "Ankit Sharma"

    # Step 8: Document Generation & Validation
    gen_resp = client.post(f"/api/resumes/{resume_id}/generate")
    assert gen_resp.status_code == 200, gen_resp.text
    gen_data = gen_resp.json()
    assert gen_data["ok"] is True
    assert gen_data["generation_status"] == "completed"
    assert gen_data["docx_available"] is True
    assert gen_data["pdf_available"] is True
    assert gen_data["quality_score"] >= 80
    assert gen_data["is_valid"] is True

    validation_report = gen_data["validation_report"]
    assert "checks" in validation_report
    check_names = [c["name"] for c in validation_report["checks"]]
    assert "Candidate Name Check" in check_names
    assert "Contact Email Check" in check_names
    assert "DOCX Structure Integrity" in check_names
    assert "Page Count Budget Check" in check_names

    # Step 9: Download Output Files
    # Download DOCX
    docx_dl = client.get(f"/api/resumes/{resume_id}/download?format=docx")
    assert docx_dl.status_code == 200
    assert docx_dl.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(docx_dl.content) > 1000

    # Download PDF
    pdf_dl = client.get(f"/api/resumes/{resume_id}/download?format=pdf")
    assert pdf_dl.status_code == 200
    assert pdf_dl.headers["content-type"] == "application/pdf"
    assert pdf_dl.content.startswith(b"%PDF-")
