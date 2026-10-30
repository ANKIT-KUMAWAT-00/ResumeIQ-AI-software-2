import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import User, UserSession

PBKDF2_ITERATIONS = 200_000

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"

def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed or not hashed.startswith("pbkdf2_sha256$"):
        return False
    try:
        parts = hashed.split("$")
        if len(parts) != 4:
            return False
        _, iterations_str, salt_hex, digest_hex = parts
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False

def hash_otp(code: str) -> str:
    return hashlib.sha256((settings.secret_key + code).encode()).hexdigest()

def verify_otp(code: str, digest: str) -> bool:
    return hmac.compare_digest(hash_otp(code), digest)

def issue_session(user_id: int, db: Session) -> str:
    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)
    db.add(
        UserSession(
            user_id=user_id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=expires,
            revoked=False,
        )
    )
    db.flush()
    return token

def revoke_session(token: str | None, db: Session) -> None:
    if not token:
        return
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = db.query(UserSession).filter_by(token_hash=digest, revoked=False).first()
    if row:
        row.revoked = True
        db.commit()

def get_current_user(request: Request, db: Session) -> User:
    # 1. Cookie check
    token = request.cookies.get(settings.session_cookie_name)
    # 2. Authorization Bearer header fallback
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to continue.",
        )
    digest = hashlib.sha256(token.encode()).hexdigest()
    session = db.query(UserSession).filter_by(token_hash=digest, revoked=False).first()
    now = datetime.now(timezone.utc)
    if not session or (
        session.expires_at.replace(tzinfo=timezone.utc)
        if session.expires_at.tzinfo is None
        else session.expires_at
    ) < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )
    user = db.get(User, session.user_id)
    if not user or user.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to continue.",
        )
    return user

def require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")

def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
