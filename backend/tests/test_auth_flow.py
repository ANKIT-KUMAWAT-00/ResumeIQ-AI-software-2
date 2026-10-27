from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

def test_dev_otp_sign_in_and_logout(monkeypatch):
 monkeypatch.setattr(settings,'app_env','development');monkeypatch.setattr(settings,'allow_dev_otp',True);monkeypatch.setattr(settings,'smtp_host','')
 with TestClient(app) as client:
  import uuid
  email=f'test-auth-{uuid.uuid4().hex}@example.com';r=client.post('/api/auth/request-otp',json={'email':email});assert r.status_code==200
  code=r.json().get('development_code');assert code and len(code)==6
  v=client.post('/api/auth/verify-otp',json={'email':email,'code':code});assert v.status_code==200
  assert client.get('/api/auth/me').status_code==200
  assert client.post('/api/auth/logout').status_code==200
  assert client.get('/api/auth/me').status_code==401

def test_upload_rejects_file_signature_mismatch(monkeypatch):
 import uuid
 from app.db.session import SessionLocal
 from app.models import User,Order
 from app.core.security import issue_session
 with TestClient(app) as client:
  db=SessionLocal();user=User(email=f'upload-{uuid.uuid4().hex}@example.com',role='user');db.add(user);db.commit();db.refresh(user)
  order=Order(user_id=user.id,package_id='resume-review',amount_paise=29900,status='paid',razorpay_order_id='upload-'+uuid.uuid4().hex);db.add(order);db.commit();db.refresh(order)
  token=issue_session(user.id,db);db.commit();order_id=order.id;db.close();client.cookies.set(settings.session_cookie_name,token)
  response=client.post('/api/resumes',data={'order_id':str(order_id),'target_role':'sde-general','template_id':'ats-clean'},files={'file':('bad.pdf',b'not a pdf','application/pdf')})
  assert response.status_code==415
