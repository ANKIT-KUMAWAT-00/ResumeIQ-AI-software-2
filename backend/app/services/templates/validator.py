from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from docx import Document
import pdfplumber

from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
from app.schemas.validation import (
    DocumentQualityReport,
    ValidationCheck,
    ValidationSeverity,
)

class DocumentValidator:
    """
    Document Quality Validation service:
    Validates generated DOCX/PDF artifacts against the selected TemplateSpecification
    and canonical ResumeJSON before marking generation successful.
    """
    @classmethod
    def validate(
        cls,
        resume: ResumeJSON,
        template: TemplateSpec,
        docx_path: str | Path | None = None,
        pdf_path: str | Path | None = None,
    ) -> DocumentQualityReport:
        checks: list[ValidationCheck] = []
        failed_checks: list[str] = []
        warnings: list[str] = []
        fidelity_notes: list[str] = []
        score = 100

        # 1. Required Contact Information Check
        c = resume.contact
        if not c.full_name or c.full_name == "Candidate":
            checks.append(ValidationCheck(
                check_id="contact_name",
                name="Candidate Name Check",
                severity="fail",
                message="Valid candidate name is missing.",
            ))
            failed_checks.append("contact_name")
            score -= 20
        else:
            checks.append(ValidationCheck(
                check_id="contact_name",
                name="Candidate Name Check",
                severity="pass",
                message=f"Name verified: {c.full_name}",
            ))

        if not c.email or "@" not in c.email:
            checks.append(ValidationCheck(
                check_id="contact_email",
                name="Contact Email Check",
                severity="fail",
                message="Valid contact email is missing.",
            ))
            failed_checks.append("contact_email")
            score -= 15
        else:
            checks.append(ValidationCheck(
                check_id="contact_email",
                name="Contact Email Check",
                severity="pass",
                message=f"Email verified: {c.email}",
            ))

        # 2. Template Required Sections Check
        section_data_map = {
            "education": resume.education,
            "skills": resume.skills,
            "projects": resume.projects,
            "experience": resume.experience,
            "certifications": resume.certifications,
            "achievements": resume.achievements,
            "extracurricular": resume.extracurricular_activities,
        }

        for sec in template.sections:
            if not sec.enabled:
                continue
            items = section_data_map.get(sec.id, [])
            if sec.required and len(items) == 0:
                checks.append(ValidationCheck(
                    check_id=f"required_section_{sec.id}",
                    name=f"Required Section: {sec.label}",
                    severity="fail",
                    message=f"Required section '{sec.label}' ({sec.id}) contains no entries.",
                ))
                failed_checks.append(f"required_section_{sec.id}")
                score -= 15
            elif len(items) > 0:
                checks.append(ValidationCheck(
                    check_id=f"section_{sec.id}",
                    name=f"Section: {sec.label}",
                    severity="pass",
                    message=f"Section '{sec.label}' populated with {len(items)} items.",
                ))

        # 3. URL Format Check
        for proj in resume.projects:
            if proj.url and not (str(proj.url).startswith("http://") or str(proj.url).startswith("https://")):
                checks.append(ValidationCheck(
                    check_id=f"proj_url_{proj.title}",
                    name=f"Project URL Check: {proj.title}",
                    severity="warning",
                    message=f"URL for project '{proj.title}' is not a valid HTTP/HTTPS link.",
                ))
                warnings.append(f"Invalid URL in project '{proj.title}'")
                score -= 5

        # 4. DOCX Integrity Check
        if docx_path:
            p_docx = Path(docx_path)
            if not p_docx.exists() or p_docx.stat().st_size == 0:
                checks.append(ValidationCheck(
                    check_id="docx_file_exists",
                    name="DOCX Output Existence",
                    severity="fail",
                    message="Generated DOCX file is missing or 0 bytes.",
                ))
                failed_checks.append("docx_file_exists")
                score -= 40
            else:
                try:
                    doc = Document(p_docx)
                    p_count = len(doc.paragraphs)
                    checks.append(ValidationCheck(
                        check_id="docx_open_check",
                        name="DOCX Structure Integrity",
                        severity="pass",
                        message=f"DOCX opened successfully ({p_count} paragraphs rendered).",
                    ))
                    fidelity_notes.append(f"DOCX generated with {p_count} paragraphs and {len(doc.tables)} tables.")
                except Exception as exc:
                    checks.append(ValidationCheck(
                        check_id="docx_open_check",
                        name="DOCX Structure Integrity",
                        severity="fail",
                        message=f"Failed to open generated DOCX: {exc}",
                    ))
                    failed_checks.append("docx_open_check")
                    score -= 40

        # 5. PDF Integrity & Page Count Check
        page_count = None
        if pdf_path:
            p_pdf = Path(pdf_path)
            if not p_pdf.exists() or p_pdf.stat().st_size == 0:
                checks.append(ValidationCheck(
                    check_id="pdf_file_exists",
                    name="PDF Output Existence",
                    severity="fail",
                    message="Generated PDF file is missing or 0 bytes.",
                ))
                failed_checks.append("pdf_file_exists")
                score -= 30
            else:
                try:
                    with pdfplumber.open(p_pdf) as pdf:
                        page_count = len(pdf.pages)
                        if page_count > template.max_pages:
                            checks.append(ValidationCheck(
                                check_id="pdf_page_budget",
                                name="Page Count Budget Check",
                                severity="warning",
                                message=f"Generated PDF has {page_count} pages, exceeding target of {template.max_pages} pages.",
                            ))
                            warnings.append(f"PDF exceeds target page count ({page_count} > {template.max_pages})")
                            score -= 10
                        else:
                            checks.append(ValidationCheck(
                                check_id="pdf_page_budget",
                                name="Page Count Budget Check",
                                severity="pass",
                                message=f"PDF fits within budget: {page_count} page(s) (target <= {template.max_pages}).",
                            ))
                        fidelity_notes.append(f"PDF rendered with {page_count} page(s).")
                except Exception as exc:
                    checks.append(ValidationCheck(
                        check_id="pdf_open_check",
                        name="PDF Structure Integrity",
                        severity="fail",
                        message=f"Failed to parse generated PDF: {exc}",
                    ))
                    failed_checks.append("pdf_open_check")
                    score -= 30

        final_score = max(0, min(100, score))
        is_valid = len(failed_checks) == 0

        return DocumentQualityReport(
            is_valid=is_valid,
            quality_score=final_score,
            checks=checks,
            failed_checks=failed_checks,
            warnings=warnings,
            page_count=page_count,
            template_fidelity_notes=fidelity_notes,
            timestamp=datetime.now(timezone.utc),
        )

