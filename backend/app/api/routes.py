import hashlib,json,os,secrets,hmac
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request,Response,UploadFile,File,Form,Header
from fastapi.responses import FileResponse,RedirectResponse
from pydantic import BaseModel,EmailStr,Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.db.session import get_db
from app.models import User,OTPCode,Order,Payment,Resume,Extraction,Review,Template,Output,AuditLog,WebhookEvent,RevisionRequest,Testimonial,UserSession,RoleRubric
from app.core.config import settings
from app.core.security import (
    new_otp,
    hash_otp,
    verify_otp,
    issue_session,
    revoke_session,
    hash_password,
    verify_password,
)
from app.core.packages import PACKAGES,package_or_404
from app.core.limits import enforce_rate_limit
from app.api.deps import current_user
from app.services.mailer import send_otp
from app.services.auth import AuthService, DevelopmentVerificationProvider
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    VerifyEmailRequest,
    VerifyPhoneRequest,
    ResendVerificationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.schemas.questions import ResumeAnswerSubmission
from app.schemas.resume import ResumeJSON
from app.services.gemini.client import GeminiService
from app.services.extraction.normalizer import ResumeNormalizer
from app.services.pipeline import (
    extract_and_normalize,
    detect_missing_info,
    apply_resume_answers,
    generate_resume_document,
)
from app.services.payments.razorpay import RazorpayGateway,PaymentConfigurationError
from app.services.storage.service import store_upload,read_private,delete_private,signed_download_url
from app.services.pipeline import process_resume_job
from app.schemas.template import TemplateSpec
from app.schemas.review import ResumeReviewResult
router=APIRouter()
class OTPRequest(BaseModel): email: EmailStr
class OTPVerify(BaseModel): email: EmailStr; code: str=Field(min_length=6,max_length=6)
class OrderRequest(BaseModel): package_id: str
class CheckoutVerify(BaseModel): internal_order_id: int; razorpay_order_id: str; razorpay_payment_id: str; razorpay_signature: str
# Renamed: the old name clashed with the RevisionRequest DB model imported above.
class RevisionBody(BaseModel): notes: str=Field(min_length=5,max_length=2000)

def order_unlocked(order):
 # Dev bypass: when payments are not required, everything is unlocked.
 return (not settings.payments_required) or bool(order and order.status=='paid')

def audit(db,user,action,typ,rid,details=None):
 db.add(AuditLog(actor_user_id=user.id if user else None,action=action,resource_type=typ,resource_id=str(rid),details=details or {}))

def enqueue_resume(resume_id:int):
 if settings.run_jobs_inline: process_resume_job(resume_id); return
 try:
  from redis import Redis
  from rq import Queue
  Queue(settings.queue_name,connection=Redis.from_url(settings.redis_url)).enqueue(process_resume_job,resume_id,job_timeout=900,result_ttl=86400,failure_ttl=86400)
 except Exception as exc:
  # Do not pretend a queued job exists. Keep the record failed with a clear state.
  from app.db.session import SessionLocal
  db=SessionLocal()
  try:
   r=db.get(Resume,resume_id)
   if r: r.status='failed'; db.add(AuditLog(actor_user_id=r.user_id,action='resume.queue_failed',resource_type='resume',resource_id=str(resume_id),details={'error_type':type(exc).__name__})); db.commit()
  finally: db.close()

@router.get('/health')
def health(): return {'status':'ok','service':'resumeiq-api'}
@router.get('/packages')
def packages(): return [{'id':k,**v} for k,v in PACKAGES.items()]
@router.post('/auth/register')
def register(body: RegisterRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit('register-ip:' + str(request.client.host if request.client else 'unknown'), 10, 900)
    email = body.email.lower().strip()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, 'An account with this email already exists.')
    user = User(
        full_name=body.full_name.strip(),
        email=email,
        phone=body.phone.strip() if body.phone else None,
        password_hash=hash_password(body.password),
        role='admin' if email in settings.admins else 'user',
        email_verified=False,
        phone_verified=False,
        account_status='active',
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    auth_svc = AuthService(db)
    dispatch_info = auth_svc.create_verification(email, 'email', user.id)

    token = issue_session(user.id, db)
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.app_env.lower() == 'production',
        samesite='none' if settings.app_env.lower() == 'production' else 'lax',
        max_age=settings.session_ttl_hours * 3600,
        path='/',
    )
    res = {
        'id': user.id,
        'full_name': user.full_name,
        'email': user.email,
        'phone': user.phone,
        'role': user.role,
        'email_verified': user.email_verified,
        'phone_verified': user.phone_verified,
        'account_status': user.account_status,
        'token': token,
        'verification': dispatch_info,
    }
    return res

@router.post('/auth/login')
def login(body: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    enforce_rate_limit('login-ip:' + str(request.client.host if request.client else 'unknown'), 20, 900)
    user = None
    if body.email:
        user = db.query(User).filter_by(email=body.email.lower().strip()).first()
    elif body.phone:
        user = db.query(User).filter_by(phone=body.phone.strip()).first()
    if not user or user.deleted_at:
        raise HTTPException(401, 'Invalid credentials.')

    # 1. Password login
    if body.password:
        if not verify_password(body.password, user.password_hash):
            raise HTTPException(401, 'Invalid credentials.')
    # 2. OTP code login
    elif body.code:
        auth_svc = AuthService(db)
        auth_svc.verify_code(user.email, 'email', body.code)
    else:
        raise HTTPException(400, 'Password or verification code is required.')

    token = issue_session(user.id, db)
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.app_env.lower() == 'production',
        samesite='none' if settings.app_env.lower() == 'production' else 'lax',
        max_age=settings.session_ttl_hours * 3600,
        path='/',
    )
    return {
        'id': user.id,
        'full_name': user.full_name,
        'email': user.email,
        'phone': user.phone,
        'role': user.role,
        'email_verified': user.email_verified,
        'phone_verified': user.phone_verified,
        'account_status': user.account_status,
        'token': token,
    }

@router.post('/auth/verify-email')
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    auth_svc = AuthService(db)
    record = auth_svc.verify_code(email, 'email', body.code)
    user = db.query(User).filter_by(email=email).first()
    if user:
        user.email_verified = True
        db.commit()
    return {'ok': True, 'email_verified': True, 'message': 'Email successfully verified.'}

@router.post('/auth/verify-phone')
def verify_phone(body: VerifyPhoneRequest, db: Session = Depends(get_db)):
    phone = body.phone.strip()
    auth_svc = AuthService(db)
    record = auth_svc.verify_code(phone, 'phone', body.code)
    user = db.query(User).filter_by(phone=phone).first()
    if user:
        user.phone_verified = True
        db.commit()
    return {'ok': True, 'phone_verified': True, 'message': 'Phone successfully verified.'}

@router.post('/auth/resend-verification')
def resend_verification(body: ResendVerificationRequest, db: Session = Depends(get_db)):
    ident = body.identifier.strip().lower()
    user = None
    if body.verification_type == 'email':
        user = db.query(User).filter_by(email=ident).first()
    elif body.verification_type == 'phone':
        user = db.query(User).filter_by(phone=ident).first()
    auth_svc = AuthService(db)
    return auth_svc.create_verification(ident, body.verification_type, user.id if user else None)

@router.post('/auth/forgot-password')
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.query(User).filter_by(email=email).first()
    if not user:
        # Don't leak user existence in generic message
        return {'ok': True, 'message': 'If an account exists with this email, a reset code has been sent.'}
    auth_svc = AuthService(db)
    res = auth_svc.create_verification(email, 'password_reset', user.id)
    return {'ok': True, 'message': 'Password reset code has been dispatched.', **res}

@router.post('/auth/reset-password')
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.query(User).filter_by(email=email).first()
    if not user:
        raise HTTPException(404, 'User not found.')
    auth_svc = AuthService(db)
    auth_svc.verify_code(email, 'password_reset', body.code)
    user.password_hash = hash_password(body.new_password)
    # Revoke old sessions
    db.query(UserSession).filter_by(user_id=user.id).update({'revoked': True})
    db.commit()
    return {'ok': True, 'message': 'Password has been reset successfully. Please log in.'}

@router.post('/auth/request-otp')
def request_otp(body:OTPRequest,request:Request,db:Session=Depends(get_db)):
 enforce_rate_limit('otp-ip:'+str(request.client.host if request.client else 'unknown'),10,900)
 email=body.email.lower().strip(); now=datetime.now(timezone.utc)
 recent=db.query(OTPCode).filter(OTPCode.email==email,OTPCode.created_at>now-timedelta(minutes=15)).count()
 if recent>=5: raise HTTPException(429,'Too many sign-in codes requested. Please try again later.')
 code=new_otp(); row=OTPCode(email=email,code_hash=hash_otp(code),expires_at=now+timedelta(minutes=settings.otp_ttl_minutes)); db.add(row); db.commit()
 try: send_otp(email,code)
 except Exception as exc: row.consumed=True; db.commit(); raise HTTPException(503,str(exc))
 result={'message':'If email delivery is configured, a sign-in code has been sent.'}
 if settings.app_env.lower()=='development' and settings.allow_dev_otp and not settings.smtp_host: result['development_code']=code
 return result

@router.post('/auth/verify-otp')
def verify_otp_route(body:OTPVerify,response:Response,request:Request,db:Session=Depends(get_db)):
 enforce_rate_limit('verify-otp-ip:'+str(request.client.host if request.client else 'unknown'),20,900)
 email=body.email.lower().strip(); now=datetime.now(timezone.utc)
 row=db.query(OTPCode).filter_by(email=email,consumed=False).order_by(desc(OTPCode.created_at)).first()
 if not row or (row.expires_at.replace(tzinfo=timezone.utc) if row.expires_at.tzinfo is None else row.expires_at)<now or row.attempts>=settings.otp_max_attempts:
  raise HTTPException(400,'Code is invalid or expired. Request a new one.')
 row.attempts+=1
 if not verify_otp(body.code,row.code_hash): db.commit(); raise HTTPException(400,'Code is invalid or expired.')
 row.consumed=True; user=db.query(User).filter_by(email=email).first()
 if not user: user=User(email=email,role='admin' if email in settings.admins else 'user'); db.add(user); db.flush()
 else: user.role='admin' if email in settings.admins else 'user'
 token=issue_session(user.id,db);db.commit();response.set_cookie(settings.session_cookie_name,token,httponly=True,secure=settings.app_env.lower()=='production',samesite='none' if settings.app_env.lower()=='production' else 'lax',max_age=settings.session_ttl_hours*3600,path='/')
 return {'id':user.id,'email':user.email,'role':user.role}

@router.post('/auth/logout')
def logout(response:Response,request:Request,db:Session=Depends(get_db)):
 revoke_session(request.cookies.get(settings.session_cookie_name),db);response.delete_cookie(settings.session_cookie_name,path='/');return {'ok':True}

@router.get('/auth/me')
def me(user:User=Depends(current_user)):
 return {
     'id': user.id,
     'full_name': user.full_name,
     'email': user.email,
     'phone': user.phone,
     'role': user.role,
     'email_verified': user.email_verified,
     'phone_verified': user.phone_verified,
     'account_status': user.account_status,
     'created_at': user.created_at.isoformat() if user.created_at else '',
 }

@router.post('/payments/orders')
def create_order(body:OrderRequest,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
 enforce_rate_limit('orders-user:'+str(user.id),10,3600)
 pkg=package_or_404(body.package_id); internal=Order(user_id=user.id,package_id=body.package_id,amount_paise=pkg['price_inr']*100,status='creating'); db.add(internal); db.commit(); db.refresh(internal)
 try: remote=RazorpayGateway().create_order(internal.amount_paise,f'rq-{internal.id}',{'internal_order_id':str(internal.id),'user_id':str(user.id),'package_id':body.package_id})
 except PaymentConfigurationError as exc: internal.status='failed'; db.commit(); raise HTTPException(503,str(exc))
 except Exception as exc: internal.status='failed'; db.commit(); raise HTTPException(502,str(exc))
 internal.razorpay_order_id=remote['id']; internal.status='pending'; db.add(Payment(order_id=internal.id,status='pending')); audit(db,user,'payment.order_created','order',internal.id,{'package_id':body.package_id}); db.commit()
 return {'internal_order_id':internal.id,'razorpay_order_id':remote['id'],'amount':internal.amount_paise,'currency':'INR','key_id':settings.razorpay_key_id,'package':pkg}
@router.post('/payments/verify')
def verify_payment(body:CheckoutVerify,db:Session=Depends(get_db),user:User=Depends(current_user)):
 order=db.query(Order).filter_by(id=body.internal_order_id,user_id=user.id).first()
 if not order: raise HTTPException(404,'Order not found.')
 if order.status=='paid': return {'status':'paid','order_id':order.id}
 if order.razorpay_order_id!=body.razorpay_order_id: raise HTTPException(400,'Order identifier mismatch.')
 gateway=RazorpayGateway()
 if not gateway.verify_checkout(body.razorpay_order_id,body.razorpay_payment_id,body.razorpay_signature): raise HTTPException(400,'Payment signature verification failed.')
 try: provider_payment=gateway.fetch_payment(body.razorpay_payment_id)
 except Exception as exc: raise HTTPException(503,'Payment signature was valid, but provider status could not be confirmed. Retry shortly.') from exc
 if provider_payment.get('order_id')!=order.razorpay_order_id or provider_payment.get('amount')!=order.amount_paise: raise HTTPException(400,'Payment details do not match the server order.')
 pay=db.query(Payment).filter_by(order_id=order.id).first()
 if not pay: pay=Payment(order_id=order.id); db.add(pay)
 pay.provider_payment_id=body.razorpay_payment_id; pay.signature_verified=True; pay.status=provider_payment.get('status','pending')
 # Checkout callback alone never unlocks a package; the provider must report captured or a verified captured webhook must arrive.
 if provider_payment.get('status')=='captured': order.status='paid'; audit(db,user,'payment.provider_captured','order',order.id)
 else: order.status='pending'; audit(db,user,'payment.signature_verified_pending_capture','order',order.id)
 db.commit()
 return {'status':order.status,'order_id':order.id,'message':'Payment provider status checked. Package access unlocks only after capture is confirmed.'}
@router.post('/payments/webhook')
async def razorpay_webhook(request:Request,x_razorpay_signature:str=Header(default=''),x_razorpay_event_id:str=Header(default=''),db:Session=Depends(get_db)):
 raw=await request.body()
 try: valid=RazorpayGateway().verify_webhook(raw,x_razorpay_signature)
 except PaymentConfigurationError as exc: raise HTTPException(503,str(exc))
 if not valid: raise HTTPException(400,'Invalid webhook signature.')
 try: payload=json.loads(raw); event=payload.get('event',''); payment_entity=payload.get('payload',{}).get('payment',{}).get('entity',{}); order_entity=payload.get('payload',{}).get('order',{}).get('entity',{})
 except Exception: raise HTTPException(400,'Malformed webhook payload.')
 event_id=x_razorpay_event_id or payload.get('id') or hashlib.sha256(raw).hexdigest();matched_order=False
 if db.query(WebhookEvent).filter_by(event_id=event_id).first(): return {'ok':True,'duplicate':True}
 ev=WebhookEvent(event_id=event_id,processed=False); db.add(ev); db.flush()
 remote_order=payment_entity.get('order_id') or order_entity.get('id')
 order=db.query(Order).filter_by(razorpay_order_id=remote_order).first() if remote_order else None
 matched_order=bool(order)
 if order and event in ('payment.captured','order.paid'):
  amount=payment_entity.get('amount') or order_entity.get('amount')
  if amount==order.amount_paise and order.status not in ('refunded','partially_refunded','refund_pending','cancelled'):
   order.status='paid'; pay=db.query(Payment).filter_by(order_id=order.id).first()
   if not pay: pay=Payment(order_id=order.id); db.add(pay)
   pay.provider_payment_id=payment_entity.get('id'); pay.status='captured'; pay.signature_verified=True
 elif order and event=='payment.failed' and order.status not in ('paid','refunded','partially_refunded','refund_pending','cancelled'):
  order.status='payment_failed'; pay=db.query(Payment).filter_by(order_id=order.id).first()
  if pay: pay.status='failed'
 if event in ('refund.processed','refund.failed'):
  refund_entity=payload.get('payload',{}).get('refund',{}).get('entity',{})
  refund_payment_id=refund_entity.get('payment_id')
  pay=db.query(Payment).filter_by(provider_payment_id=refund_payment_id).first() if refund_payment_id else None
  if pay:
   refund_order=db.get(Order,pay.order_id);matched_order=True
   if event=='refund.processed':
    fully_refunded=int(refund_entity.get('amount') or 0)>=refund_order.amount_paise
    pay.status='refunded' if fully_refunded else 'partially_refunded';refund_order.status='refunded' if fully_refunded else 'partially_refunded';pay.provider_refund_id=refund_entity.get('id') or pay.provider_refund_id
   else: pay.status='captured';refund_order.status='paid'
 ev.processed=True; db.commit(); return {'ok':True,'matched_order':matched_order}

@router.get('/orders/me')
def my_orders(db:Session=Depends(get_db),user:User=Depends(current_user)):
 rows=db.query(Order).filter_by(user_id=user.id).order_by(desc(Order.created_at)).limit(100).all()
 return [{'id':o.id,'package_id':o.package_id,'amount_paise':o.amount_paise,'status':o.status,'created_at':o.created_at.isoformat()} for o in rows]

@router.post('/resumes')
@router.post('/resumes/upload')
async def upload_resume(request:Request,file:UploadFile=File(...),order_id: int | None = Form(None),target_role:str=Form('sde-general'),template_id:str=Form('ats-clean'),template_overrides:str=Form('{}'),db:Session=Depends(get_db),user:User=Depends(current_user)):
 enforce_rate_limit('upload-user:'+str(user.id),50,3600)
 order=None
 if settings.payments_required:
  order=db.query(Order).filter_by(id=order_id,user_id=user.id,status='paid').first()
  if not order:
   raise HTTPException(403,'A verified paid order is required before uploading a resume.')
  if db.query(Resume).filter_by(order_id=order.id).first():
   raise HTTPException(409,'This package order has already been used for a resume upload.')
  package_or_404(order.package_id)
 if target_role not in {'backend','frontend','fullstack','ai-ml','data-analyst','cloud-devops','mobile','cybersecurity','sde-general'}: raise HTTPException(400,'Unsupported target role.')
 tpl=db.query(Template).filter_by(template_id=template_id,published=True).first()
 if not tpl: raise HTTPException(400,'Selected template is not available.')
 try:
  overrides=json.loads(template_overrides or '{}')
  if not isinstance(overrides,dict) or set(overrides)-{'fonts','margins','spacing'}: raise ValueError()
  for group,allowed in {'fonts':{'family','body_pt'},'margins':{'top_in','bottom_in','left_in','right_in'},'spacing':{'line_spacing','paragraph_after_pt'}}.items():
   if group in overrides and (not isinstance(overrides[group],dict) or set(overrides[group])-allowed): raise ValueError()
  merged=json.loads(json.dumps(tpl.spec))
  for group,values in overrides.items(): merged[group].update(values)
  TemplateSpec.model_validate(merged)
 except Exception as exc: raise HTTPException(422,'Unsupported template formatting options.') from exc
 name=(file.filename or 'resume').replace(chr(92),'/').split('/')[-1]
 suffix=Path(name).suffix.lower()
 if suffix not in ('.pdf','.docx'): raise HTTPException(415,'Only PDF and DOCX files are supported.')
 content=await file.read(settings.max_upload_mb*1024*1024+1)
 if len(content)>settings.max_upload_mb*1024*1024: raise HTTPException(413,f'Maximum upload size is {settings.max_upload_mb} MB.')
 if suffix=='.pdf' and not content.startswith(b'%PDF-'): raise HTTPException(415,'File content does not match a PDF signature.')
 if suffix=='.docx' and not (content.startswith(b'PK') and b'word/document.xml' in content[:200000]): raise HTTPException(415,'File content does not look like a DOCX document.')
 path,digest=store_upload(content,name,user.id)
 row=Resume(user_id=user.id,order_id=order.id if order else None,original_filename=name[:255],file_path=path,mime_type='application/pdf' if suffix=='.pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',sha256=digest,target_role=target_role,template_id=template_id,template_overrides=overrides,template_snapshot=tpl.spec,status='queued',collection_status='uploaded',generation_status='pending',expires_at=datetime.now(timezone.utc)+timedelta(days=settings.retention_days))
 db.add(row); db.commit(); db.refresh(row); audit(db,user,'resume.uploaded','resume',row.id,{'sha256':digest,'size_bytes':len(content)}); db.commit(); rid=row.id
 if settings.run_jobs_inline: process_resume_job(rid)
 else:
  try:
   from redis import Redis
   from rq import Queue
   Queue(settings.queue_name,connection=Redis.from_url(settings.redis_url)).enqueue(process_resume_job,rid,job_timeout=900,result_ttl=86400,failure_ttl=86400)
  except Exception as exc:
   row.status='failed'; db.add(AuditLog(actor_user_id=user.id,action='resume.queue_failed',resource_type='resume',resource_id=str(row.id),details={'error_type':type(exc).__name__})); db.commit()
 return {'id':rid,'status':row.status,'collection_status':row.collection_status,'generation_status':row.generation_status,'message':'Resume accepted. Processing status reflects the backend job state.'}
@router.get('/resumes')
def list_resumes(db:Session=Depends(get_db),user:User=Depends(current_user)):
 rows=db.query(Resume).filter_by(user_id=user.id).order_by(desc(Resume.created_at)).all()
 return [{'id':r.id,'filename':r.original_filename,'status':r.status,'target_role':r.target_role,'template_id':r.template_id,'created_at':r.created_at.isoformat()} for r in rows]
@router.get('/resumes/{resume_id}')
def get_resume(resume_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=db.query(Resume).filter_by(id=resume_id,user_id=user.id).first()
 if not r: raise HTTPException(404,'Resume not found.')
 ex=db.query(Extraction).filter_by(resume_id=r.id).first(); rev=db.query(Review).filter_by(resume_id=r.id).order_by(desc(Review.created_at)).first(); outputs=db.query(Output).filter_by(resume_id=r.id).all(); order=db.get(Order,r.order_id) if r.order_id else None
 if not order_unlocked(order): outputs=[]
 voice=db.query(AuditLog).filter_by(resource_type='resume',resource_id=str(r.id),action='full_makeover.voice_note_added').order_by(desc(AuditLog.created_at)).first()
 return {
     'id':r.id,
     'filename':r.original_filename,
     'status':r.status,
     'collection_status':r.collection_status,
     'generation_status':r.generation_status,
     'validation_report':r.validation_report,
     'target_role':r.target_role,
     'template_id':r.template_id,
     'package_id':(order.package_id if order else None),
     'extraction':ex.data if ex else None,
     'review':rev.data if rev else None,
     'voice_note_url':voice.details.get('url') if voice else None,
     'outputs':[{'id':o.id,'kind':o.kind,'download_url':f'/api/outputs/{o.id}/download'} for o in outputs if (o.expires_at.replace(tzinfo=timezone.utc) if o.expires_at.tzinfo is None else o.expires_at)>datetime.now(timezone.utc)],
     'error':'Processing failed. Check configuration and try again or contact support.' if r.status=='failed' else None
 }

@router.get('/resumes/{resume_id}/status')
def get_resume_status(resume_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    return {
        'id': r.id,
        'status': r.status,
        'collection_status': r.collection_status,
        'generation_status': r.generation_status,
        'has_validation_report': r.validation_report is not None,
    }

@router.post('/resumes/{resume_id}/extract')
def extract_resume_endpoint(resume_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    try:
        canonical = extract_and_normalize(r.id, db)
        return {'ok': True, 'resume_id': r.id, 'collection_status': r.collection_status, 'data': canonical.model_dump(mode='json')}
    except Exception as exc:
        raise HTTPException(502, f'Extraction failed: {exc}') from exc

@router.post('/resumes/{resume_id}/normalize')
def normalize_resume_endpoint(resume_id: int, body: dict = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    raw_data = body if body and isinstance(body, dict) else None
    if not raw_data:
        ex = db.query(Extraction).filter_by(resume_id=r.id).first()
        if not ex:
            raise HTTPException(400, 'Resume has not been extracted yet.')
        raw_data = ex.data
    try:
        normalized = ResumeNormalizer.normalize(raw_data)
        # Update extraction
        ex = db.query(Extraction).filter_by(resume_id=r.id).first()
        if ex:
            ex.data = normalized.model_dump(mode='json')
            db.commit()
        return {'ok': True, 'normalized': normalized.model_dump(mode='json')}
    except Exception as exc:
        raise HTTPException(422, f'Normalization failed: {exc}') from exc

@router.get('/resumes/{resume_id}/missing-information')
def get_missing_information(resume_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    try:
        report = detect_missing_info(r.id, db)
        return report.model_dump(mode='json')
    except Exception as exc:
        raise HTTPException(500, f'Failed to assess missing information: {exc}') from exc

@router.post('/resumes/{resume_id}/answers')
def submit_answers_endpoint(
    resume_id: int,
    body: ResumeAnswerSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    try:
        updated = apply_resume_answers(r.id, body.answers, db, body.confirm)
        report = detect_missing_info(r.id, db)
        return {
            'ok': True,
            'collection_status': r.collection_status,
            'missing_information': report.model_dump(mode='json'),
            'updated_resume': updated.model_dump(mode='json'),
        }
    except Exception as exc:
        raise HTTPException(422, f'Failed to process answers: {exc}') from exc

@router.post('/resumes/{resume_id}/enhance')
def enhance_resume_endpoint(resume_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    ex = db.query(Extraction).filter_by(resume_id=r.id).first()
    if not ex:
        raise HTTPException(400, 'Resume must be extracted before content enhancement.')
    try:
        canonical = ResumeJSON.model_validate(ex.data)
        gemini = GeminiService()
        enhanced = gemini.enhance(canonical, r.target_role)
        ex.data = enhanced.model_dump(mode='json')
        db.commit()
        return {'ok': True, 'enhanced': enhanced.model_dump(mode='json')}
    except Exception as exc:
        raise HTTPException(502, f'Content enhancement failed: {exc}') from exc

@router.post('/resumes/{resume_id}/generate')
def generate_resume_endpoint(resume_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    order = db.get(Order, r.order_id) if r.order_id else None
    if not order_unlocked(order):
        raise HTTPException(403, 'A verified paid order is required for generation.')
    try:
        gen_doc = generate_resume_document(r.id, db)
        return {
            'ok': True,
            'resume_id': r.id,
            'generation_status': r.generation_status,
            'quality_score': gen_doc.quality_score,
            'is_valid': gen_doc.is_valid,
            'validation_report': gen_doc.validation_result,
            'docx_available': gen_doc.docx_path is not None,
            'pdf_available': gen_doc.pdf_path is not None,
        }
    except Exception as exc:
        raise HTTPException(500, f'Generation failed: {exc}') from exc

@router.get('/resumes/{resume_id}/download')
def download_generated_resume(
    resume_id: int,
    format: str = "docx",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    r = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not r:
        raise HTTPException(404, 'Resume not found.')
    order = db.get(Order, r.order_id) if r.order_id else None
    if not order_unlocked(order):
        raise HTTPException(403, 'Access not permitted.')
    out = (
        db.query(Output)
        .filter_by(resume_id=r.id, kind=format.lower())
        .order_by(desc(Output.created_at))
        .first()
    )
    if not out:
        raise HTTPException(404, f'Generated {format.upper()} document not found.')
    if (out.expires_at.replace(tzinfo=timezone.utc) if out.expires_at.tzinfo is None else out.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(410, 'This output has expired.')
    if out.file_path.startswith('s3://'):
        try:
            return RedirectResponse(signed_download_url(out.file_path), status_code=302)
        except Exception as exc:
            raise HTTPException(503, 'Private storage download temporarily unavailable.') from exc
    if not Path(out.file_path).is_file():
        raise HTTPException(404, 'Output file is unavailable.')
    return FileResponse(
        out.file_path,
        filename=f"ResumeIQ-AI-{r.id}.{out.kind}",
        media_type='application/pdf' if out.kind == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
@router.get('/outputs/{output_id}/download')
def download_output(output_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
 out=db.get(Output,output_id); resume=db.get(Resume,out.resume_id) if out else None
 if not out or not resume or resume.user_id!=user.id: raise HTTPException(404,'Output not found.')
 order=db.get(Order,resume.order_id) if resume.order_id else None
 if not order_unlocked(order): raise HTTPException(403,'Package access is unavailable for this order.')
 if (out.expires_at.replace(tzinfo=timezone.utc) if out.expires_at.tzinfo is None else out.expires_at)<datetime.now(timezone.utc): raise HTTPException(410,'This output has expired.')
 if out.file_path.startswith('s3://'):
  try: return RedirectResponse(signed_download_url(out.file_path),status_code=302)
  except Exception as exc: raise HTTPException(503,'Private object storage download is temporarily unavailable.') from exc
 if not Path(out.file_path).is_file(): raise HTTPException(404,'Output file is unavailable.')
 return FileResponse(out.file_path,filename=f'ResumeIQ-AI-{resume.id}.{out.kind}',media_type='application/pdf' if out.kind=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
@router.get('/resumes/{resume_id}/original/download')
def download_original_resume(resume_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=db.query(Resume).filter_by(id=resume_id,user_id=user.id).first()
 if not r: raise HTTPException(404,'Resume not found.')
 if (r.expires_at.replace(tzinfo=timezone.utc) if r.expires_at.tzinfo is None else r.expires_at)<datetime.now(timezone.utc): raise HTTPException(410,'The uploaded resume has expired from private storage.')
 if r.file_path.startswith('s3://'):
  try:return RedirectResponse(signed_download_url(r.file_path),status_code=302)
  except Exception as exc:raise HTTPException(503,'Private object storage download is temporarily unavailable.') from exc
 if not Path(r.file_path).is_file():raise HTTPException(404,'Original upload is unavailable.')
 return FileResponse(r.file_path,filename=r.original_filename,media_type=r.mime_type)

@router.post('/resumes/{resume_id}/retry')
def retry_resume(resume_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=db.query(Resume).filter_by(id=resume_id,user_id=user.id).first()
 if not r: raise HTTPException(404,'Resume not found.')
 if r.status!='failed': raise HTTPException(409,'Only failed jobs can be retried.')
 r.status='queued'; db.commit()
 if settings.run_jobs_inline: process_resume_job(r.id)
 else:
  from redis import Redis
  from rq import Queue
  try: Queue(settings.queue_name,connection=Redis.from_url(settings.redis_url)).enqueue(process_resume_job,r.id,job_timeout=900)
  except Exception: r.status='failed'; db.commit(); raise HTTPException(503,'Job queue is unavailable.')
 return {'id':r.id,'status':r.status}
@router.post('/resumes/{resume_id}/revision')
def request_revision(resume_id:int,body:RevisionBody,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=db.query(Resume).filter_by(id=resume_id,user_id=user.id).first()
 if not r: raise HTTPException(404,'Resume not found.')
 order=db.get(Order,r.order_id) if r.order_id else None
 # In dev bypass mode there is no order, so skip the package check.
 if settings.payments_required and (not order or order.package_id!='full-makeover' or order.status!='paid'): raise HTTPException(403,'A revision is included only in the paid Full Makeover package.')
 existing=db.query(RevisionRequest).filter_by(resume_id=r.id).count()
 if existing>=1: raise HTTPException(409,'The included revision has already been used.')
 revision=RevisionRequest(resume_id=r.id,user_id=user.id,notes=body.notes,status='requested');db.add(revision);audit(db,user,'revision.requested','resume',r.id);db.commit();db.refresh(revision)
 return {'id':revision.id,'status':revision.status,'message':'Revision request recorded for admin review.'}

@router.post('/templates/upload')
async def upload_template(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    enforce_rate_limit('upload-template-user:' + str(user.id), 20, 3600)
    name = (file.filename or 'template').replace(chr(92), '/').split('/')[-1]
    suffix = Path(name).suffix.lower()
    if suffix not in ('.docx', '.pdf'):
        raise HTTPException(415, 'Only DOCX and PDF template files are supported.')

    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f'Maximum upload size is {settings.max_upload_mb} MB.')

    if suffix == '.pdf' and not content.startswith(b'%PDF-'):
        raise HTTPException(415, 'File content does not match a PDF signature.')
    if suffix == '.docx' and not (content.startswith(b'PK') and b'word/document.xml' in content[:200000]):
        raise HTTPException(415, 'File content does not look like a DOCX document.')

    path, digest = store_upload(content, name, user.id)

    from app.services.templates.analyzer import TemplateAnalyzer
    try:
        analyzer = TemplateAnalyzer(path)
        spec = analyzer.analyze()
    except Exception as exc:
        raise HTTPException(422, f'Template analysis failed: {exc}') from exc

    tpl_id = f"custom-{user.id}-{secrets.token_hex(4)}"
    spec_dict = spec.model_dump(mode='json')
    spec_dict['template_id'] = tpl_id
    spec_dict['template_name'] = name
    spec_dict['file_type'] = 'docx' if suffix == '.docx' else 'pdf'

    row = Template(
        template_id=tpl_id,
        template_name=name,
        template_type='custom_docx' if suffix == '.docx' else 'custom_pdf',
        original_file_path=path,
        version='1.0.0',
        spec=spec_dict,
        analysis_status='analyzed',
        is_confirmed=False,
        published=False,
        created_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(db, user, 'template.uploaded', 'template', tpl_id, {'filename': name, 'sha256': digest})

    return {
        'id': row.id,
        'template_id': row.template_id,
        'template_name': row.template_name,
        'template_type': row.template_type,
        'is_confirmed': row.is_confirmed,
        'analysis_status': row.analysis_status,
        'specification': row.spec,
        'message': 'Template analyzed successfully. Please review and confirm the specification.',
    }

@router.get('/templates')
def list_templates(request: Request, db: Session = Depends(get_db)):
    user_id = None
    try:
        from app.core.security import get_current_user
        u = get_current_user(request, db)
        user_id = u.id
    except Exception:
        pass

    if user_id:
        rows = db.query(Template).filter(
            or_(Template.published.is_(True), Template.created_by_user_id == user_id)
        ).all()
    else:
        rows = db.query(Template).filter(Template.published.is_(True)).all()
    return [
        {
            'template_id': t.template_id,
            'template_name': t.template_name or t.spec.get('display_name', t.template_id),
            'version': t.version,
            'template_type': t.template_type,
            'display_name': t.spec.get('display_name', t.template_id),
            'description': t.spec.get('description', ''),
            'layout': t.spec.get('layout', 'single-column'),
            'page_size': t.spec.get('page_size', 'LETTER'),
            'is_confirmed': t.is_confirmed,
            'sections': [
                {
                    'id': s.get('id'),
                    'heading': s.get('heading') or s.get('label'),
                    'required': s.get('required', False),
                    'order': s.get('order', idx + 1),
                }
                for idx, s in enumerate(t.spec.get('sections', []))
            ],
        }
        for t in rows
    ]

@router.get('/templates/{template_id}')
def get_template(template_id: str, db: Session = Depends(get_db)):
    tpl = db.query(Template).filter_by(template_id=template_id).first()
    if not tpl:
        raise HTTPException(404, 'Template not found.')
    return {
        'template_id': tpl.template_id,
        'template_name': tpl.template_name,
        'template_type': tpl.template_type,
        'version': tpl.version,
        'analysis_status': tpl.analysis_status,
        'is_confirmed': tpl.is_confirmed,
        'published': tpl.published,
        'specification': tpl.spec,
    }

@router.post('/templates/{template_id}/analyze')
def analyze_template_endpoint(template_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tpl = db.query(Template).filter_by(template_id=template_id).first()
    if not tpl:
        raise HTTPException(404, 'Template not found.')
    if tpl.created_by_user_id and tpl.created_by_user_id != user.id and user.role != 'admin':
        raise HTTPException(403, 'Permission denied.')
    if not tpl.original_file_path or not Path(tpl.original_file_path).exists():
        raise HTTPException(400, 'Original template file is not available on disk.')

    from app.services.templates.analyzer import TemplateAnalyzer
    analyzer = TemplateAnalyzer(tpl.original_file_path)
    spec = analyzer.analyze()
    spec_dict = spec.model_dump(mode='json')
    spec_dict['template_id'] = tpl.template_id
    tpl.spec = spec_dict
    tpl.analysis_status = 'analyzed'
    db.commit()
    return {'ok': True, 'specification': tpl.spec}

@router.get('/templates/{template_id}/specification')
def get_template_specification(template_id: str, db: Session = Depends(get_db)):
    tpl = db.query(Template).filter_by(template_id=template_id).first()
    if not tpl:
        raise HTTPException(404, 'Template not found.')
    return tpl.spec

@router.post('/templates/{template_id}/confirm')
def confirm_template(
    template_id: str,
    body: dict = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    tpl = db.query(Template).filter_by(template_id=template_id).first()
    if not tpl:
        raise HTTPException(404, 'Template not found.')
    if tpl.created_by_user_id and tpl.created_by_user_id != user.id and user.role != 'admin':
        raise HTTPException(403, 'Permission denied.')

    # User may optionally pass custom adjustments to the specification
    if body and isinstance(body, dict) and 'specification' in body:
        try:
            valid = TemplateSpec.model_validate(body['specification'])
            tpl.spec = valid.model_dump(mode='json')
        except Exception as exc:
            raise HTTPException(422, f'Invalid template adjustments: {exc}') from exc

    tpl.is_confirmed = True
    tpl.published = True
    audit(db, user, 'template.confirmed', 'template', template_id)
    db.commit()
    return {
        'ok': True,
        'template_id': tpl.template_id,
        'is_confirmed': True,
        'published': True,
        'message': 'Template confirmed and activated.',
    }
@router.get('/account/export')
def export_account(db:Session=Depends(get_db),user:User=Depends(current_user)):
 orders=db.query(Order).filter_by(user_id=user.id).all(); resumes=db.query(Resume).filter_by(user_id=user.id).all()
 data={'user':{'email':user.email,'created_at':user.created_at.isoformat()},'orders':[{'id':o.id,'package_id':o.package_id,'amount_paise':o.amount_paise,'status':o.status} for o in orders],'resumes':[{'id':r.id,'filename':r.original_filename,'sha256':r.sha256,'status':r.status,'target_role':r.target_role,'template_id':r.template_id,'created_at':r.created_at.isoformat(),'original_download_url':f'/api/resumes/{r.id}/original/download','extraction':(db.query(Extraction).filter_by(resume_id=r.id).first().data if db.query(Extraction).filter_by(resume_id=r.id).first() else None),'review':(db.query(Review).filter_by(resume_id=r.id).order_by(desc(Review.created_at)).first().data if db.query(Review).filter_by(resume_id=r.id).order_by(desc(Review.created_at)).first() else None),'outputs':[{'kind':o.kind,'download_url':f'/api/outputs/{o.id}/download'} for o in db.query(Output).filter_by(resume_id=r.id).all()]} for r in resumes],'testimonials':[{'display_name':t.display_name,'body':t.body,'approved':t.approved,'consent_public':t.consent_public} for t in db.query(Testimonial).filter_by(user_id=user.id).all()]}
 return data
@router.delete('/account')
def delete_account(db:Session=Depends(get_db),user:User=Depends(current_user)):
 rows=db.query(Resume).filter_by(user_id=user.id).all()
 for r in rows:
  delete_private(r.file_path)
  for o in db.query(Output).filter_by(resume_id=r.id).all(): delete_private(o.file_path)
  db.query(Output).filter_by(resume_id=r.id).delete(); db.query(Extraction).filter_by(resume_id=r.id).delete(); db.query(Review).filter_by(resume_id=r.id).delete()
 db.query(OTPCode).filter_by(email=user.email).delete();db.query(RevisionRequest).filter(RevisionRequest.user_id==user.id).delete();db.query(Testimonial).filter(Testimonial.user_id==user.id).delete();db.query(UserSession).filter(UserSession.user_id==user.id).update({'revoked':True});db.query(Resume).filter_by(user_id=user.id).delete(); db.query(Order).filter_by(user_id=user.id).update({'status':'deleted'})
 user.deleted_at=datetime.now(timezone.utc); user.email=f'deleted-{user.id}-{secrets.token_hex(4)}@invalid.local'; audit(db,user,'account.deleted','user',user.id); db.commit()
 return {'ok':True,'message':'Account content deletion requested and local files removed where accessible.'}

# Admin routes use the same server-side role check for every action.
@router.get('/admin/orders')
def admin_orders(db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 return [{'id':o.id,'email':db.get(User,o.user_id).email,'package_id':o.package_id,'amount_inr':o.amount_paise/100,'status':o.status,'created_at':o.created_at.isoformat()} for o in db.query(Order).order_by(desc(Order.created_at)).limit(500).all()]
@router.get('/admin/templates')
def admin_templates(db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 return [{'template_id':t.template_id,'version':t.version,'published':t.published,'spec':t.spec} for t in db.query(Template).all()]
@router.put('/admin/templates/{template_id}')
def update_template(template_id:str,spec:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 try: valid=TemplateSpec.model_validate(spec)
 except Exception as exc: raise HTTPException(422,'Invalid template specification.') from exc
 if valid.template_id!=template_id: raise HTTPException(400,'Template ID mismatch.')
 row=db.query(Template).filter_by(template_id=template_id).first()
 if not row: row=Template(template_id=template_id,version=valid.version,spec=valid.model_dump(mode='json'),published=False); db.add(row)
 else: row.version=valid.version; row.spec=valid.model_dump(mode='json'); row.published=False
 audit(db,user,'template.updated','template',template_id); db.commit(); return {'ok':True,'published':False,'message':'Template saved as unpublished. Review it before publishing.'}
@router.post('/admin/templates/{template_id}/publish')
def publish_template(template_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 row=db.query(Template).filter_by(template_id=template_id).first()
 if not row: raise HTTPException(404,'Template not found.')
 TemplateSpec.model_validate(row.spec); row.published=True; audit(db,user,'template.published','template',template_id); db.commit(); return {'ok':True}
@router.get('/admin/reviews/queue')
def admin_review_queue(db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 # In dev bypass mode resumes have no order, so list them all.
 q=db.query(Resume) if not settings.payments_required else db.query(Resume).filter(Resume.order_id.is_not(None))
 rows=q.order_by(desc(Resume.created_at)).all(); result=[]
 for r in rows:
  o=db.get(Order,r.order_id) if r.order_id else None
  if (not settings.payments_required) or (o and o.package_id=='full-makeover' and o.status=='paid'):
   u=db.get(User,r.user_id); rev=db.query(Review).filter_by(resume_id=r.id).order_by(desc(Review.created_at)).first()
   result.append({'resume_id':r.id,'email':u.email if u else None,'filename':r.original_filename,'status':r.status,'review':rev.data if rev else None})
 return result
@router.get('/admin/rubrics')
def admin_rubrics(db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 return [r.data for r in db.query(RoleRubric).order_by(RoleRubric.rubric_id).all()]
@router.put('/admin/rubrics/{rubric_id}')
def update_rubric(rubric_id:str,data:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 if rubric_id not in {'backend','frontend','fullstack','ai-ml','data-analyst','cloud-devops','mobile','cybersecurity','sde-general'}: raise HTTPException(404,'Rubric not found.')
 criteria=data.get('criteria')
 if not isinstance(criteria,list) or not criteria: raise HTTPException(422,'Rubric must contain criteria.')
 try: weights=[float(c['weight']) for c in criteria]
 except Exception: raise HTTPException(422,'Each criterion needs a numeric weight.')
 if any(w<0 or w>1 for w in weights) or abs(sum(weights)-1)>.02: raise HTTPException(422,'Rubric weights must be between 0 and 1 and sum to 1.')
 data['role_id']=rubric_id;row=db.query(RoleRubric).filter_by(rubric_id=rubric_id).first()
 if not row: raise HTTPException(404,'Rubric not found.')
 row.version=str(data.get('version',row.version));row.data=data;row.updated_by=user.id;audit(db,user,'rubric.updated','rubric',rubric_id);db.commit();return {'ok':True,'rubric_id':rubric_id,'version':row.version}
@router.post('/admin/resumes/{resume_id}/voice-note')
def add_voice_note(resume_id:int,body:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 url=body.get('url','')
 if not isinstance(url,str) or not url.startswith('https://') or len(url)>2048: raise HTTPException(422,'A valid HTTPS voice-note URL is required.')
 r=db.get(Resume,resume_id)
 if not r: raise HTTPException(404,'Resume not found.')
 order=db.get(Order,r.order_id) if r.order_id else None
 if settings.payments_required and (not order or order.package_id!='full-makeover'): raise HTTPException(403,'Voice-note link is only available for Full Makeover orders.')
 audit(db,user,'full_makeover.voice_note_added','resume',r.id,{'url':url});db.commit();return {'ok':True}

@router.post('/admin/templates/analyze')
async def analyze_template_upload(file:UploadFile=File(...),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 suffix=Path(file.filename or '').suffix.lower()
 if suffix not in ('.docx','.pdf'): raise HTTPException(415,'Upload a DOCX or PDF template sample.')
 data=await file.read(settings.max_upload_mb*1024*1024+1)
 if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(413,'Template sample exceeds upload limit.')
 import tempfile
 from app.services.templates.analyzer import analyze_docx,analyze_pdf
 with tempfile.TemporaryDirectory(prefix='resumeiq-template-') as td:
  path=Path(td)/('sample'+suffix);path.write_bytes(data)
  try: draft=analyze_docx(path) if suffix=='.docx' else analyze_pdf(path); valid=TemplateSpec.model_validate(draft)
  except Exception as exc: raise HTTPException(422,'Could not analyze this template sample.') from exc
 return {'draft':valid.model_dump(mode='json'),'message':'Draft inferred; inspect uncertainty notes and preview before publishing.'}

@router.get('/admin/revisions')
def admin_revisions(db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 rows=db.query(RevisionRequest).order_by(desc(RevisionRequest.created_at)).limit(200).all()
 return [{'id':x.id,'resume_id':x.resume_id,'email':db.get(User,x.user_id).email,'notes':x.notes,'status':x.status,'admin_notes':x.admin_notes} for x in rows]
@router.patch('/admin/revisions/{revision_id}')
def update_revision(revision_id:int,body:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 row=db.get(RevisionRequest,revision_id)
 if not row: raise HTTPException(404,'Revision request not found.')
 status_value=body.get('status')
 if status_value not in {'in_review','completed','rejected'}: raise HTTPException(422,'Unsupported revision status.')
 row.status=status_value;row.admin_notes=str(body.get('admin_notes',''))[:2000];audit(db,user,'revision.status_updated','revision',row.id,{'status':status_value});db.commit();return {'ok':True,'status':row.status}
@router.put('/admin/resumes/{resume_id}/review')
def admin_edit_review(resume_id:int,body:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 r=db.get(Resume,resume_id)
 if not r: raise HTTPException(404,'Resume not found.')
 try: valid=ResumeReviewResult.model_validate(body)
 except Exception as exc: raise HTTPException(422,'Review does not match the expected schema.') from exc
 row=db.query(Review).filter_by(resume_id=r.id).order_by(desc(Review.created_at)).first()
 if row: row.data=valid.model_dump(mode='json')
 else: db.add(Review(resume_id=r.id,data=valid.model_dump(mode='json'),model='admin-edited',prompt_version='admin-v1'))
 audit(db,user,'review.admin_edited','resume',r.id);db.commit();return {'ok':True}
@router.post('/admin/orders/{order_id}/refund')
def admin_refund(order_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 order=db.get(Order,order_id)
 if not order: raise HTTPException(404,'Order not found.')
 if order.status!='paid': raise HTTPException(409,'Only paid orders can be refunded.')
 payment=db.query(Payment).filter_by(order_id=order.id).first()
 if not payment or not payment.provider_payment_id or payment.status not in {'captured','signature_verified','refund_pending'}: raise HTTPException(409,'No confirmed captured payment is available to refund.')
 try: result=RazorpayGateway().refund_payment(payment.provider_payment_id,order.amount_paise,{'internal_order_id':str(order.id)})
 except Exception as exc: raise HTTPException(502,'Razorpay did not confirm the refund request.') from exc
 payment.provider_refund_id=result['id'];payment.status='refunded' if result.get('status')=='processed' else ('captured' if result.get('status')=='failed' else 'refund_pending');order.status='refunded' if result.get('status')=='processed' else ('paid' if result.get('status')=='failed' else 'refund_pending');audit(db,user,'payment.refund_requested','order',order.id,{'provider_refund_id':result['id'],'provider_status':result.get('status')});db.commit()
 return {'status':order.status,'provider_status':result.get('status'),'refund_id':result['id']}
@router.get('/testimonials')
def public_testimonials(db:Session=Depends(get_db)):
 return [{'id':t.id,'display_name':t.display_name,'body':t.body} for t in db.query(Testimonial).filter_by(approved=True,consent_public=True).order_by(desc(Testimonial.created_at)).limit(20).all()]
@router.post('/testimonials')
def submit_testimonial(body:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
 display=str(body.get('display_name') or user.email.split('@')[0])[:100];content=str(body.get('body') or '').strip()
 if body.get('consent_public') is not True: raise HTTPException(422,'Explicit consent to display the testimonial publicly is required.')
 if len(content)<20 or len(content)>1000: raise HTTPException(422,'Testimonial must be 20–1000 characters.')
 row=Testimonial(user_id=user.id,display_name=display,body=content,approved=False,consent_public=True);db.add(row);db.commit();db.refresh(row);audit(db,user,'testimonial.submitted','testimonial',row.id);db.commit();return {'id':row.id,'approved':False,'message':'Submitted for admin approval.'}
@router.get('/admin/testimonials')
def admin_testimonials(db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 return [{'id':t.id,'display_name':t.display_name,'body':t.body,'approved':t.approved,'consent_public':t.consent_public} for t in db.query(Testimonial).order_by(desc(Testimonial.created_at)).limit(200).all()]
@router.post('/admin/testimonials/{testimonial_id}/approve')
def approve_testimonial(testimonial_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 t=db.get(Testimonial,testimonial_id)
 if not t: raise HTTPException(404,'Testimonial not found.')
 if not t.consent_public: raise HTTPException(409,'Public display consent is missing.')
 t.approved=True;audit(db,user,'testimonial.approved','testimonial',t.id);db.commit();return {'ok':True}

@router.get('/admin/audit-log')
def admin_audit_log(limit:int=100,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 limit=max(1,min(limit,500));rows=db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).all()
 return [{'id':x.id,'actor_user_id':x.actor_user_id,'action':x.action,'resource_type':x.resource_type,'resource_id':x.resource_id,'details':x.details,'created_at':x.created_at.isoformat()} for x in rows]

@router.get('/admin/analytics')
def admin_analytics(db:Session=Depends(get_db),user:User=Depends(current_user)):
 if user.role!='admin': raise HTTPException(403,'Administrator access required.')
 orders=db.query(Order).all(); return {'orders_total':len(orders),'paid_orders':sum(o.status=='paid' for o in orders),'revenue_inr':sum(o.amount_paise for o in orders if o.status=='paid')/100,'users_total':db.query(User).count(),'resumes_total':db.query(Resume).count()}