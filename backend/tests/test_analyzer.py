from pathlib import Path
from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
from app.services.templates.renderer import render_resume
from app.services.templates.analyzer import analyze_docx,analyze_pdf
ROOT=Path(__file__).resolve().parents[2]
def test_docx_analyzer_creates_valid_draft(tmp_path):
 r=ResumeJSON.model_validate_json((ROOT/'sample_data/reference_resume.json').read_text());t=TemplateSpec.model_validate_json((ROOT/'template_specs/ats-clean.json').read_text());p=render_resume(r,t,tmp_path/'source.docx');draft=analyze_docx(p);assert TemplateSpec.model_validate(draft).template_id.startswith('draft-');assert draft['notes_and_uncertainty']
def test_pdf_analyzer_reads_supplied_reference():
 p=ROOT/'sample_data/reference_resume.pdf'
 if p.exists():
  draft=analyze_pdf(p);assert TemplateSpec.model_validate(draft).page_size=='LETTER';assert any('uncertainty' in n.lower() or 'review' in n.lower() for n in draft['notes_and_uncertainty'])
