import shutil
from pathlib import Path
import pytest
from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT
from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
from app.services.templates.renderer import render_resume
from app.services.templates.pdf import convert_docx_to_pdf,PDFConversionError
ROOT=Path(__file__).resolve().parents[2]
def models(name='ats-clean'):
 return ResumeJSON.model_validate_json((ROOT/'sample_data/reference_resume.json').read_text()),TemplateSpec.model_validate_json((ROOT/'template_specs'/f'{name}.json').read_text())
def test_docx_render_preserves_facts_and_tab_stops(tmp_path):
 r,t=models();path=render_resume(r,t,tmp_path/'resume.docx');doc=Document(path);texts=[p.text for p in doc.paragraphs]
 assert any('Ankit Kumawat' in x for x in texts);assert any('ResumeIQ AI' in x for x in texts);assert any('EDUCATION' in x for x in texts)
 p=next(p for p in doc.paragraphs if '\t' in p.text);assert p.paragraph_format.tab_stops[0].alignment==WD_TAB_ALIGNMENT.RIGHT
def test_renderer_does_not_drop_project_bullets(tmp_path):
 r,t=models('modern-one-page');path=render_resume(r,t,tmp_path/'resume.docx');text='\n'.join(p.text for p in Document(path).paragraphs)
 assert 'single compromised factor alone cannot grant access' in text and 'database-enforced approval workflow' in text
@pytest.mark.skipif(not (shutil.which('libreoffice') or shutil.which('soffice')),reason='LibreOffice unavailable')
def test_pdf_conversion(tmp_path):
 r,t=models();docx=render_resume(r,t,tmp_path/'resume.docx');pdf=convert_docx_to_pdf(docx,tmp_path);assert pdf.is_file() and pdf.stat().st_size>0


def test_two_column_template_uses_real_table_layout(tmp_path):
 r,t=models();data=t.model_dump(mode='json');data['layout']='two-column';two=TemplateSpec.model_validate(data);path=render_resume(r,two,tmp_path/'two-column.docx');doc=Document(path)
 assert len(doc.tables)>=1 and len(doc.tables[0].columns)==2

def test_allowed_fields_are_respected(tmp_path):
 r,t=models();data=t.model_dump(mode='json')
 for section in data['sections']:
  if section['id']=='projects': section['allowed_fields']=['title','bullets','start_date','end_date']
 spec=TemplateSpec.model_validate(data);path=render_resume(r,spec,tmp_path/'filtered.docx');text='\n'.join(p.text for p in Document(path).paragraphs)
 assert 'Technologies:' not in text and 'ResumeIQ AI' in text
