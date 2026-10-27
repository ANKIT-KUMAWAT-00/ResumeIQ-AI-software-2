import hashlib,hmac
from app.core.config import settings
from app.services.payments.razorpay import RazorpayGateway

def test_checkout_signature_valid_and_invalid(monkeypatch):
 monkeypatch.setattr(settings,'razorpay_key_secret','test-secret');g=RazorpayGateway();order='order_123';payment='pay_123';sig=hmac.new(b'test-secret',f'{order}|{payment}'.encode(),hashlib.sha256).hexdigest()
 assert g.verify_checkout(order,payment,sig);assert not g.verify_checkout(order,payment,'0'*64)
def test_webhook_signature_valid_and_invalid(monkeypatch):
 monkeypatch.setattr(settings,'razorpay_webhook_secret','webhook-secret');g=RazorpayGateway();body=b'{"event":"payment.captured"}';sig=hmac.new(b'webhook-secret',body,hashlib.sha256).hexdigest()
 assert g.verify_webhook(body,sig);assert not g.verify_webhook(body,'bad')


def test_checkout_callback_does_not_unlock_until_provider_capture(monkeypatch):
 import uuid
 from fastapi.testclient import TestClient
 from app.main import app
 from app.db.session import SessionLocal
 from app.models import User,Order,Payment
 from app.core.security import issue_session
 from app.core.config import settings
 monkeypatch.setattr(settings,'razorpay_key_secret','test-secret')
 monkeypatch.setattr(RazorpayGateway,'verify_checkout',lambda self,o,p,s: True)
 remote_order='order_test_pending_'+uuid.uuid4().hex;payment_id='pay_test_'+uuid.uuid4().hex
 monkeypatch.setattr(RazorpayGateway,'fetch_payment',lambda self,p:{'id':p,'order_id':remote_order,'amount':49900,'status':'authorized'})
 db=SessionLocal(); email=f'payment-check-{uuid.uuid4().hex}@example.com'; user=User(email=email,role='user');db.add(user);db.commit();db.refresh(user)
 order=Order(user_id=user.id,package_id='resume-template',amount_paise=49900,status='pending',razorpay_order_id=remote_order);db.add(order);db.commit();db.refresh(order);db.add(Payment(order_id=order.id,status='pending'));db.commit();uid=user.id;oid=order.id;token=issue_session(uid,db);db.commit();db.close()
 with TestClient(app) as client:
  client.cookies.set(settings.session_cookie_name,token)
  response=client.post('/api/payments/verify',json={'internal_order_id':oid,'razorpay_order_id':remote_order,'razorpay_payment_id':payment_id,'razorpay_signature':'valid-signature'})
  assert response.status_code==200 and response.json()['status']=='pending'
 db=SessionLocal();assert db.get(Order,oid).status=='pending';db.close()

def test_verified_webhook_is_idempotent(monkeypatch):
 import json,uuid
 from fastapi.testclient import TestClient
 from app.main import app
 from app.db.session import SessionLocal
 from app.models import User,Order,Payment
 monkeypatch.setattr(RazorpayGateway,'verify_webhook',lambda self,raw,sig: True)
 remote_order='order_capture_'+uuid.uuid4().hex;event_id='evt_'+uuid.uuid4().hex;payment_id='pay_capture_'+uuid.uuid4().hex
 db=SessionLocal();user=User(email=f'webhook-{uuid.uuid4().hex}@example.com',role='user');db.add(user);db.commit();db.refresh(user)
 order=Order(user_id=user.id,package_id='resume-template',amount_paise=49900,status='pending',razorpay_order_id=remote_order);db.add(order);db.commit();db.refresh(order);db.add(Payment(order_id=order.id,status='pending'));db.commit();oid=order.id;db.close()
 payload={'id':event_id,'event':'payment.captured','payload':{'payment':{'entity':{'id':payment_id,'order_id':remote_order,'amount':49900,'status':'captured'}}}}
 with TestClient(app) as client:
  headers={'X-Razorpay-Signature':'test-signature','X-Razorpay-Event-Id':event_id}
  first=client.post('/api/payments/webhook',content=json.dumps(payload),headers=headers);assert first.status_code==200 and first.json()['ok']
  second=client.post('/api/payments/webhook',content=json.dumps(payload),headers=headers);assert second.status_code==200 and second.json()['duplicate']
 db=SessionLocal();assert db.get(Order,oid).status=='paid';db.close()
