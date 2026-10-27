import hashlib,hmac,requests
from app.core.config import settings
class PaymentConfigurationError(RuntimeError): pass
class RazorpayGateway:
 def _config(self):
  if not settings.razorpay_key_id or not settings.razorpay_key_secret: raise PaymentConfigurationError('Razorpay test/live credentials are not configured.')
 def create_order(self,amount_paise:int,receipt:str,notes:dict):
  self._config()
  try:
   r=requests.post(settings.razorpay_base_url.rstrip('/')+'/orders',auth=(settings.razorpay_key_id,settings.razorpay_key_secret),json={"amount":amount_paise,"currency":"INR","receipt":receipt[:40],"notes":notes},timeout=15)
   r.raise_for_status(); data=r.json()
   if data.get('amount')!=amount_paise or data.get('currency')!='INR' or not data.get('id'): raise RuntimeError('Razorpay order response did not match requested amount.')
   return data
  except requests.RequestException as e: raise RuntimeError('Razorpay order creation failed; no payment was marked successful.') from e
 def fetch_payment(self,payment_id:str)->dict:
  self._config()
  try:
   r=requests.get(settings.razorpay_base_url.rstrip('/')+'/payments/'+payment_id,auth=(settings.razorpay_key_id,settings.razorpay_key_secret),timeout=15)
   r.raise_for_status(); return r.json()
  except requests.RequestException as e: raise RuntimeError('Could not confirm payment status with Razorpay.') from e
 def verify_checkout(self,order_id:str,payment_id:str,signature:str)->bool:
  if not settings.razorpay_key_secret: raise PaymentConfigurationError('Razorpay secret is not configured.')
  expected=hmac.new(settings.razorpay_key_secret.encode(),f'{order_id}|{payment_id}'.encode(),hashlib.sha256).hexdigest()
  return hmac.compare_digest(expected,signature)
 def verify_webhook(self,raw:bytes,signature:str)->bool:
  if not settings.razorpay_webhook_secret: raise PaymentConfigurationError('Razorpay webhook secret is not configured.')
  expected=hmac.new(settings.razorpay_webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
  return hmac.compare_digest(expected,signature)

 def refund_payment(self,payment_id:str,amount_paise:int,notes:dict|None=None)->dict:
     self._config()
     try:
         r=requests.post(settings.razorpay_base_url.rstrip('/')+'/payments/'+payment_id+'/refund',auth=(settings.razorpay_key_id,settings.razorpay_key_secret),json={'amount':amount_paise,'notes':notes or {}},timeout=20)
         r.raise_for_status(); data=r.json()
         if not data.get('id') or data.get('amount')!=amount_paise: raise RuntimeError('Razorpay refund response did not match the requested amount.')
         return data
     except requests.RequestException as e: raise RuntimeError('Razorpay refund request failed; the refund was not marked successful.') from e
