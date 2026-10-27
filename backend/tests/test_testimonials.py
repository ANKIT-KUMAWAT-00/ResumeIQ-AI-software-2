import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models import User
from app.core.security import issue_session
from app.core.config import settings

def test_testimonial_requires_explicit_public_consent():
 with TestClient(app) as client:
  db=SessionLocal();user=User(email=f'testimonial-{uuid.uuid4().hex}@example.com',role='user');db.add(user);db.commit();db.refresh(user);token=issue_session(user.id,db);db.commit();db.close()
  client.cookies.set(settings.session_cookie_name,token)
  no_consent=client.post('/api/testimonials',json={'display_name':'Example','body':'This is a useful review with enough length.'})
  assert no_consent.status_code==422
  consent=client.post('/api/testimonials',json={'display_name':'Example','body':'This is a useful review with enough length.','consent_public':True})
  assert consent.status_code==200 and consent.json()['approved'] is False
