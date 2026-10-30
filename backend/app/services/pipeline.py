from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import (
    Resume,
    Extraction,
    Review,
    Order,
    Output,
    AuditLog,
    RoleRubric,
    Template,
    ResumeAnswer,
    GeneratedDocument,
)
from app.core.packages import PACKAGES
from app.services.storage.service import (
    read_private,
    store_output_file,
    delete_private,
)
from app.services.extraction.parser import extract_text
from app.services.extraction.normalizer import ResumeNormalizer
from app.services.extraction.adaptive_questions import AdaptiveQuestionEngine
from app.services.gemini.client import GeminiService
from app.schemas.template import TemplateSpec
from app.schemas.resume import ResumeJSON
from app.schemas.questions import MissingInformationReport
from app.services.templates.renderer import render_resume
from app.services.templates.pdf import convert_docx_to_pdf, PDFConversionError
from app.services.templates.validator import DocumentValidator

ROOT = Path(__file__).resolve().parents[3]

def resolve_template_spec(resume: Resume, db: Session) -> TemplateSpec:
    template_record = (
        db.query(Template)
        .filter_by(template_id=resume.template_id)
        .first()
    )
    if resume.template_snapshot:
        spec_data = json.loads(json.dumps(resume.template_snapshot))
    elif template_record:
        spec_data = json.loads(json.dumps(template_record.spec))
    else:
        spec_path = ROOT / "template_specs" / f"{resume.template_id}.json"
        if not spec_path.exists():
            spec_path = ROOT / "template_specs" / "ats-clean.json"
        spec_data = json.loads(spec_path.read_text())

    for group, values in (resume.template_overrides or {}).items():
        if group in spec_data and isinstance(spec_data[group], dict) and isinstance(values, dict):
            spec_data[group].update(values)

    return TemplateSpec.model_validate(spec_data)

def extract_and_normalize(resume_id: int, db: Session) -> ResumeJSON:
    resume = db.get(Resume, resume_id)
    if not resume:
        raise ValueError(f"Resume #{resume_id} not found.")

    resume.collection_status = "extracting"
    db.commit()

    raw_bytes = read_private(resume.file_path)
    text = extract_text(raw_bytes, resume.original_filename)

    gemini = GeminiService()
    parsed_resume = gemini.extract(text)

    # Deterministic normalization pass
    canonical_resume = ResumeNormalizer.normalize(parsed_resume.model_dump(mode="json"))

    extraction = db.query(Extraction).filter_by(resume_id=resume.id).first()
    if extraction:
        extraction.data = canonical_resume.model_dump(mode="json")
        extraction.model = gemini.model
    else:
        db.add(Extraction(
            resume_id=resume.id,
            data=canonical_resume.model_dump(mode="json"),
            model=gemini.model,
        ))

    resume.collection_status = "extracted"
    db.commit()
    return canonical_resume

def detect_missing_info(resume_id: int, db: Session) -> MissingInformationReport:
    resume = db.get(Resume, resume_id)
    if not resume:
        raise ValueError(f"Resume #{resume_id} not found.")

    extraction = db.query(Extraction).filter_by(resume_id=resume.id).first()
    if not extraction:
        canonical = extract_and_normalize(resume_id, db)
    else:
        canonical = ResumeJSON.model_validate(extraction.data)

    spec = resolve_template_spec(resume, db)
    report = AdaptiveQuestionEngine.generate_questions(canonical, spec, resume.id)

    resume.collection_status = "ready_for_generation" if report.is_complete else "needs_input"
    db.commit()
    return report

def apply_resume_answers(resume_id: int, answers: dict, db: Session, confirm: bool = False) -> ResumeJSON:
    resume = db.get(Resume, resume_id)
    if not resume:
        raise ValueError(f"Resume #{resume_id} not found.")

    extraction = db.query(Extraction).filter_by(resume_id=resume.id).first()
    if not extraction:
        raise ValueError("Resume has not been extracted yet.")

    current = ResumeJSON.model_validate(extraction.data)
    updated = AdaptiveQuestionEngine.apply_answers(current, answers)

    # Persist answers
    for field_path, val in answers.items():
        existing_answer = (
            db.query(ResumeAnswer)
            .filter_by(resume_id=resume.id, field_path=field_path)
            .first()
        )
        if existing_answer:
            existing_answer.answer_value = {"value": val}
            existing_answer.confirmed = confirm
        else:
            db.add(ResumeAnswer(
                resume_id=resume.id,
                user_id=resume.user_id,
                field_path=field_path,
                question=f"User answer for {field_path}",
                answer_value={"value": val},
                confirmed=confirm,
            ))

    extraction.data = updated.model_dump(mode="json")
    if confirm:
        resume.collection_status = "ready_for_generation"
    db.commit()
    return updated

def generate_resume_document(resume_id: int, db: Session) -> GeneratedDocument:
    resume = db.get(Resume, resume_id)
    if not resume:
        raise ValueError(f"Resume #{resume_id} not found.")

    extraction = db.query(Extraction).filter_by(resume_id=resume.id).first()
    if not extraction:
        raise ValueError("Resume must be extracted before generation.")

    resume.generation_status = "generating"
    db.commit()

    canonical = ResumeJSON.model_validate(extraction.data)
    spec = resolve_template_spec(resume, db)

    outdir = Path(settings.output_dir) / f"resume_{resume.id}"
    outdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(outdir, 0o700)

    # 1. Render DOCX
    docx_file = render_resume(canonical, spec, outdir / "resume.docx")

    # 2. Render PDF if possible
    pdf_file = None
    try:
        pdf_file = convert_docx_to_pdf(docx_file, outdir)
    except (PDFConversionError, Exception) as exc:
        pdf_file = None

    # 3. Document Quality Validation
    val_report = DocumentValidator.validate(canonical, spec, docx_file, pdf_file)
    resume.validation_report = val_report.model_dump(mode="json")

    expires = datetime.now(timezone.utc) + timedelta(days=settings.retention_days)

    stored_docx = store_output_file(str(docx_file), resume.user_id)
    stored_pdf = store_output_file(str(pdf_file), resume.user_id) if pdf_file else None

    # Output records for downloading
    db.add(Output(
        resume_id=resume.id,
        kind="docx",
        file_path=stored_docx,
        expires_at=expires,
    ))
    if stored_pdf:
        db.add(Output(
            resume_id=resume.id,
            kind="pdf",
            file_path=stored_pdf,
            expires_at=expires,
        ))

    gen_doc = GeneratedDocument(
        resume_id=resume.id,
        docx_path=stored_docx,
        pdf_path=stored_pdf,
        template_id=resume.template_id,
        template_version=spec.version,
        validation_result=val_report.model_dump(mode="json"),
        quality_score=val_report.quality_score,
        is_valid=val_report.is_valid,
        expires_at=expires,
    )
    db.add(gen_doc)

    if val_report.is_valid:
        resume.generation_status = "completed"
        resume.status = "completed"
    else:
        resume.generation_status = "failed"
        resume.status = "failed"

    db.commit()
    db.refresh(gen_doc)
    return gen_doc

def process_resume_job(resume_id: int):
    """
    Main background job orchestrating the end-to-end pipeline:
    Extraction -> Normalization -> Question check -> Review -> Generation -> Quality Validation.
    """
    db: Session = SessionLocal()
    try:
        resume = db.get(Resume, resume_id)
        if not resume:
            return

        resume.status = "processing"
        db.commit()

        order = db.get(Order, resume.order_id) if resume.order_id else None
        if settings.payments_required:
            if not order or order.status != "paid":
                raise RuntimeError("A verified paid order is required for processing.")
            package = PACKAGES[order.package_id]
        else:
            package = {
                "entitlements": [
                    "linkedin_optimization",
                    "docx_download",
                    "pdf_download",
                ]
            }

        # 1. Extraction & Normalization
        canonical = extract_and_normalize(resume.id, db)

        # 2. Check missing information
        missing_report = detect_missing_info(resume.id, db)

        # 3. Rubric review
        gemini = GeminiService()
        rubric_row = db.query(RoleRubric).filter_by(rubric_id=resume.target_role).first()
        if rubric_row:
            rubric = rubric_row.data
        else:
            rubric_path = ROOT / "role_rubrics" / f"{resume.target_role}.json"
            if not rubric_path.exists():
                rubric_path = ROOT / "role_rubrics" / "sde-general.json"
            rubric = json.loads(rubric_path.read_text())

        review = gemini.review(
            canonical,
            rubric,
            resume.target_role,
            "linkedin_optimization" in package["entitlements"],
        )

        existing_review = db.query(Review).filter_by(resume_id=resume.id).first()
        if existing_review:
            existing_review.data = review.model_dump(mode="json")
            existing_review.model = gemini.model
        else:
            db.add(Review(
                resume_id=resume.id,
                data=review.model_dump(mode="json"),
                model=gemini.model,
            ))
        db.commit()

        # 4. Document Generation and Quality Validation
        entitlements = package["entitlements"]
        if "docx_download" in entitlements or "pdf_download" in entitlements:
            generate_resume_document(resume.id, db)

        audit_entry = AuditLog(
            actor_user_id=resume.user_id,
            action="resume.processed",
            resource_type="resume",
            resource_id=str(resume.id),
            details={"model": gemini.model},
        )
        db.add(audit_entry)
        db.commit()

    except Exception as exc:
        print(
            f"Resume processing failed: resume_id={resume_id}, "
            f"error_type={type(exc).__name__}, error={exc}",
            flush=True,
        )
        db.rollback()
        resume = db.get(Resume, resume_id)
        if resume:
            resume.status = "failed"
            resume.generation_status = "failed"
            db.add(AuditLog(
                actor_user_id=resume.user_id,
                action="resume.processing_failed",
                resource_type="resume",
                resource_id=str(resume.id),
                details={"error_type": type(exc).__name__},
            ))
            db.commit()
    finally:
        db.close()
