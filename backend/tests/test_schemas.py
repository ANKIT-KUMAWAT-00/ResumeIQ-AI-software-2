import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.schemas.resume import ResumeJSON
from app.schemas.template import TemplateSpec
ROOT=Path(__file__).resolve().parents[2]
def test_reference_resume_schema():
 r=ResumeJSON.model_validate_json((ROOT/'sample_data/reference_resume.json').read_text());assert r.contact.full_name=='Ankit Kumawat';assert len(r.projects)==3
def test_unknown_resume_field_rejected():
 with pytest.raises(ValidationError): ResumeJSON.model_validate({'contact':{'full_name':'Test','bad_field':'x'}})
@pytest.mark.parametrize('name',['lpu-standard.json','ats-clean.json','modern-one-page.json'])
def test_template_specs_validate(name):
 spec=TemplateSpec.model_validate_json((ROOT/'template_specs'/name).read_text());assert spec.sections and spec.max_pages>=1
def test_unknown_section_reference_rejected():
 d=json.loads((ROOT/'template_specs/ats-clean.json').read_text());d['section_order'].append('missing')
 with pytest.raises(ValidationError):TemplateSpec.model_validate(d)
def test_lpu_template_has_uncertainty_note():
 spec=TemplateSpec.model_validate_json((ROOT/'template_specs/lpu-standard.json').read_text());assert any('official' in x.lower() for x in spec.notes_and_uncertainty)

def test_unsupported_photo_setting_is_rejected():
 d=json.loads((ROOT/'template_specs/ats-clean.json').read_text());d['allow_photo']=True
 with pytest.raises(ValidationError):TemplateSpec.model_validate(d)


def test_role_rubric_weights_are_normalized():
 for path in (ROOT/'role_rubrics').glob('*.json'):
  data=json.loads(path.read_text());weights=[float(c['weight']) for c in data['criteria']]
  assert weights and abs(sum(weights)-1)<0.001, path.name
