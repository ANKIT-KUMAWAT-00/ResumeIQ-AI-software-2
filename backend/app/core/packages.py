PACKAGES = {
 "resume-review": {"name":"Resume Review","desc":"Role-fit feedback, ATS findings, and prioritized fixes.","price_inr":299,"entitlements":["role_fit","ats_check","line_fixes","three_rewritten_bullets"],"revisions":0},
 "resume-template": {"name":"Resume + Template","desc":"Resume review plus a formatted DOCX/PDF rebuild.","price_inr":499,"entitlements":["role_fit","ats_check","line_fixes","three_rewritten_bullets","docx_download","pdf_download"],"revisions":0},
 "resume-linkedin": {"name":"Resume + LinkedIn + Template","desc":"Resume and document formatting plus LinkedIn guidance.","price_inr":799,"entitlements":["role_fit","ats_check","line_fixes","three_rewritten_bullets","docx_download","pdf_download","linkedin_optimization"],"revisions":0},
 "full-makeover": {"name":"Full Makeover","desc":"Complete package with one revision round and voice-note link.","price_inr":1199,"entitlements":["role_fit","ats_check","line_fixes","three_rewritten_bullets","docx_download","pdf_download","linkedin_optimization","one_revision","voice_note_link"],"revisions":1},
}
def package_or_404(package_id: str):
 from fastapi import HTTPException
 if package_id not in PACKAGES: raise HTTPException(status_code=400, detail="Unknown package.")
 return PACKAGES[package_id]
