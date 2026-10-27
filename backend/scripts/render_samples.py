import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
from app.services.templates.renderer import render_resume
from app.services.templates.pdf import convert_docx_to_pdf,PDFConversionError
PROJECT_ROOT=ROOT.parent
r=ResumeJSON.model_validate_json((PROJECT_ROOT/'sample_data/reference_resume.json').read_text())
out=PROJECT_ROOT/'artifacts';out.mkdir(exist_ok=True)
for name in ('lpu-standard','ats-clean','modern-one-page'):
 spec=TemplateSpec.model_validate_json((PROJECT_ROOT/'template_specs'/f'{name}.json').read_text())
 docx=render_resume(r,spec,out/f'reference-{name}.docx');print('DOCX',docx)
 try: print('PDF',convert_docx_to_pdf(docx,out))
 except PDFConversionError as e: print('PDF skipped:',e)
