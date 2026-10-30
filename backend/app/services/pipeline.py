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

def generate_resume_document(resume_id: int, db: Session):
    raise NotImplementedError()
