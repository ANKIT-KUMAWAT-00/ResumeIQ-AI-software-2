import hashlib,hmac,secrets
from datetime import datetime,timedelta,timezone
from fastapi import Request,HTTPException,status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import User,UserSession

def hash_otp(code:str)->str: return hashlib.sha256((settings.secret_key+code).encode()).hexdigest()
def verify_otp(code:str,digest:str)->bool: return hmac.compare_digest(hash_otp(code),digest)
def issue_session(user_id:int,db:Session)->str:
 token=secrets.token_urlsafe(48); expires=datetime.now(timezone.utc)+timedelta(hours=settings.session_ttl_hours)
 db.add(UserSession(user_id=user_id,token_hash=hashlib.sha256(token.encode()).hexdigest(),expires_at=expires,revoked=False));db.flush();return token
def revoke_session(token:str|None,db:Session)->None:
 if not token:return
 digest=hashlib.sha256(token.encode()).hexdigest();row=db.query(UserSession).filter_by(token_hash=digest,revoked=False).first()
 if row:row.revoked=True;db.commit()
def get_current_user(request:Request,db:Session)->User:
 token=request.cookies.get(settings.session_cookie_name)
 if not token: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Please sign in to continue.')
 digest=hashlib.sha256(token.encode()).hexdigest();session=db.query(UserSession).filter_by(token_hash=digest,revoked=False).first();now=datetime.now(timezone.utc)
 if not session or (session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at)<now: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Session expired. Please sign in again.')
 user=db.get(User,session.user_id)
 if not user or user.deleted_at: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Please sign in to continue.')
 return user
def require_admin(user:User)->None:
 if user.role!='admin':raise HTTPException(status_code=403,detail='Administrator access required.')
def new_otp()->str:return f'{secrets.randbelow(1_000_000):06d}'
