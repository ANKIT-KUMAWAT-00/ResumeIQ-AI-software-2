from app.services.gemini.prompts import EXTRACTION_SYSTEM,REVIEW_SYSTEM
from app.schemas.review import ResumeReviewResult

def test_prompts_treat_resume_as_untrusted():
 assert 'untrusted' in EXTRACTION_SYSTEM.lower() and 'never as instructions' in REVIEW_SYSTEM.lower()
def test_review_schema_rejects_out_of_range_score():
 data={'role_fit_score':140,'criteria':[],'priority_fixes':['Improve evidence']}
 try: ResumeReviewResult.model_validate(data)
 except Exception: pass
 else: raise AssertionError('Out-of-range score should fail schema validation')


def test_gemini_missing_credentials_fails_closed(monkeypatch):
 from app.core.config import settings
 from app.services.gemini.client import GeminiService,GeminiUnavailable
 monkeypatch.setattr(settings,'gemini_api_key','')
 try: GeminiService()
 except GeminiUnavailable as exc: assert 'GEMINI_API_KEY' in str(exc)
 else: raise AssertionError('Missing credentials must not fabricate an AI client')
