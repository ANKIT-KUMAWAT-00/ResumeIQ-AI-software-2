
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Resume, Extraction, Review, Order, Output, AuditLog, RoleRubric
from app.core.packages import PACKAGES
from app.services.storage.service import read_private, store_output_file, delete_private
from app.services.extraction.parser import extract_text
from app.services.gemini.client import GeminiService
from app.schemas.template import TemplateSpec
from app.schemas.resume import ResumeJSON
from app.services.templates.renderer import render_resume
from app.services.templates.pdf import convert_docx_to_pdf, PDFConversionError
import json
import os

ROOT = Path(__file__).resolve().parents[3]


def process_resume_job(resume_id: int):
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
                raise RuntimeError(
                    "A verified paid order is required for processing."
                )

            package = PACKAGES[order.package_id]
        else:
            package = {
                "entitlements": [
                    "linkedin_optimization",
                    "docx_download",
                    "pdf_download",
                ]
            }

        text = extract_text(
            read_private(resume.file_path),
            resume.original_filename,
        )

        gemini = GeminiService()
        parsed = gemini.extract(text)

        extraction = Extraction(
            resume_id=resume.id,
            data=parsed.model_dump(mode="json"),
            model=gemini.model,
        )

        existing = (
            db.query(Extraction)
            .filter_by(resume_id=resume.id)
            .first()
        )

        if existing:
            existing.data = extraction.data
            existing.model = gemini.model
        else:
            db.add(extraction)

        db.commit()

        rubric_row = (
            db.query(RoleRubric)
            .filter_by(rubric_id=resume.target_role)
            .first()
        )

        if rubric_row:
            rubric = rubric_row.data
        else:
            rubric_path = ROOT / "role_rubrics" / f"{resume.target_role}.json"

            if not rubric_path.exists():
                rubric_path = ROOT / "role_rubrics" / "sde-general.json"

            rubric = json.loads(rubric_path.read_text())

        review = gemini.review(
            parsed,
            rubric,
            resume.target_role,
            "linkedin_optimization" in package["entitlements"],
        )

        existing_review = (
            db.query(Review)
            .filter_by(resume_id=resume.id)
            .first()
        )

        if existing_review:
            existing_review.data = review.model_dump(mode="json")
            existing_review.model = gemini.model
        else:
            db.add(
                Review(
                    resume_id=resume.id,
                    data=review.model_dump(mode="json"),
                    model=gemini.model,
                )
            )

        db.commit()

        entitlements = package["entitlements"]

        if (
            "docx_download" in entitlements
            or "pdf_download" in entitlements
        ):
            Template = __import__(
                "app.models",
                fromlist=["Template"],
            ).Template

            template_record = (
                db.query(Template)
                .filter_by(
                    template_id=resume.template_id,
                    published=True,
                )
                .first()
            )

            if resume.template_snapshot:
                spec_data = json.loads(
                    json.dumps(resume.template_snapshot)
                )
            elif template_record:
                spec_data = json.loads(
                    json.dumps(template_record.spec)
                )
            else:
                spec_data = json.loads(
                    (ROOT / "template_specs" / "ats-clean.json").read_text()
                )

            for group, values in (resume.template_overrides or {}).items():
                spec_data[group].update(values)

            spec = TemplateSpec.model_validate(spec_data)

            outdir = (
                Path(settings.output_dir) / f"resume_{resume.id}"
            )
            outdir.mkdir(
                parents=True,
                exist_ok=True,
                mode=0o700,
            )
            os.chmod(outdir, 0o700)

            docx = render_resume(
                parsed,
                spec,
                outdir / "resume.docx",
            )

            expires = datetime.now(timezone.utc) + timedelta(
                days=settings.retention_days
            )

            pdf = None

            if "pdf_download" in entitlements:
                try:
                    pdf = convert_docx_to_pdf(docx, outdir)
                except PDFConversionError:
                    pdf = None

            if "docx_download" in entitlements:
                stored_docx = store_output_file(
                    str(docx),
                    resume.user_id,
                )

                db.add(
                    Output(
                        resume_id=resume.id,
                        kind="docx",
                        file_path=stored_docx,
                        expires_at=expires,
                    )
                )

                if stored_docx.startswith("s3://"):
                    delete_private(str(docx))

            if pdf is not None:
                stored_pdf = store_output_file(
                    str(pdf),
                    resume.user_id,
                )

                db.add(
                    Output(
                        resume_id=resume.id,
                        kind="pdf",
                        file_path=stored_pdf,
                        expires_at=expires,
                    )
                )

                if stored_pdf.startswith("s3://"):
                    delete_private(str(pdf))

        resume.status = "completed"

        db.add(
            AuditLog(
                actor_user_id=resume.user_id,
                action="resume.processed",
                resource_type="resume",
                resource_id=str(resume.id),
                details={"model": gemini.model},
            )
        )

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

            db.add(
                AuditLog(
                    actor_user_id=resume.user_id,
                    action="resume.processing_failed",
                    resource_type="resume",
                    resource_id=str(resume.id),
                    details={"error_type": type(exc).__name__},
                )
            )

            db.commit()

    finally:
        db.close()
