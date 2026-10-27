from app.core.packages import PACKAGES

def test_package_prices_and_entitlements_are_server_configured():
 assert [PACKAGES[k]['price_inr'] for k in ['resume-review','resume-template','resume-linkedin','full-makeover']]==[299,499,799,1199]
 assert 'docx_download' not in PACKAGES['resume-review']['entitlements']
 assert 'linkedin_optimization' in PACKAGES['resume-linkedin']['entitlements']
 assert PACKAGES['full-makeover']['revisions']==1
