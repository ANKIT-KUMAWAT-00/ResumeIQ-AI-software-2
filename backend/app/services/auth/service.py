import hashlib
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_otp, verify_otp, new_otp, hash_password, verify_password
from app.models import User, Verification
from app.services.auth.providers import (
    get_verification_provider,
    DevelopmentVerificationProvider,
    VerificationConfigurationError,
)

logger = logging.getLogger("resumeiq.auth")

RESEND_COOLDOWN_SECONDS = 60

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def create_verification(
        self,
        identifier: str,
        verification_type: str,
        user_id: int | None = None,
    ) -> dict:
        identifier = identifier.strip().lower()
        now = datetime.now(timezone.utc)

        # Check resend cooldown
        last_verification = (
            self.db.query(Verification)
            .filter_by(identifier=identifier, verification_type=verification_type)
            .order_by(desc(Verification.created_at))
            .first()
        )
        if last_verification:
            created = last_verification.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created).total_seconds() < RESEND_COOLDOWN_SECONDS:
                remaining = int(RESEND_COOLDOWN_SECONDS - (now - created).total_seconds())
                raise HTTPException(
                    429,
                    f"Please wait {remaining} seconds before requesting a new verification code.",
                )

        try:
            provider = get_verification_provider()
            is_dev = settings.app_env.strip().lower() == "development"

            # Determine OTP code
            if is_dev and settings.allow_dev_otp and isinstance(provider, DevelopmentVerificationProvider):
                code = DevelopmentVerificationProvider.DEV_OTP
            else:
                code = new_otp()

            expires = now + timedelta(minutes=settings.otp_ttl_minutes)
            row = Verification(
                user_id=user_id,
                identifier=identifier,
                verification_type=verification_type,
                token_hash=hash_otp(code),
                expires_at=expires,
                attempts=0,
                verified_at=None,
            )
            self.db.add(row)
            self.db.commit()

            # Dispatch via provider
            if verification_type == "email":
                dispatch_result = provider.send_email_verification(identifier, code)
            elif verification_type == "phone":
                dispatch_result = provider.send_phone_verification(identifier, code)
            elif verification_type == "password_reset":
                dispatch_result = provider.send_password_reset(identifier, code)
            else:
                raise HTTPException(400, "Unknown verification type.")
        except VerificationConfigurationError as exc:
            self.db.rollback()
            raise HTTPException(503, str(exc)) from exc
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as exc:
            self.db.rollback()
            raise HTTPException(502, f"Failed to deliver verification code: {exc}") from exc

        result = {
            "message": "Verification code dispatched.",
            "verification_type": verification_type,
            "expires_in_minutes": settings.otp_ttl_minutes,
        }

        # Expose simulation data ONLY in development mode
        if is_dev and dispatch_result.get("simulated"):
            result["simulated"] = True
            result["development_code"] = dispatch_result.get("development_code")

        return result

    def verify_code(
        self,
        identifier: str,
        verification_type: str,
        code: str,
    ) -> Verification:
        identifier = identifier.strip().lower()
        now = datetime.now(timezone.utc)

        record = (
            self.db.query(Verification)
            .filter_by(identifier=identifier, verification_type=verification_type)
            .filter(Verification.verified_at.is_(None))
            .order_by(desc(Verification.created_at))
            .first()
        )

        if not record:
            raise HTTPException(400, "Invalid or expired verification request.")

        # Check attempt limits
        if record.attempts >= settings.otp_max_attempts:
            raise HTTPException(
                400,
                "Maximum verification attempts exceeded. Please request a new code.",
            )

        # Check expiration
        expires = record.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise HTTPException(400, "Verification code has expired. Request a new one.")

        # Increment attempts
        record.attempts += 1

        # Check code validity
        is_dev = settings.app_env.strip().lower() == "development"
        valid = False

        if verify_otp(code, record.token_hash):
            valid = True
        elif is_dev and settings.allow_dev_otp and code == DevelopmentVerificationProvider.DEV_OTP:
            # Explicit development simulator check
            valid = True

        if not valid:
            self.db.commit()
            raise HTTPException(400, "Invalid verification code.")

        record.verified_at = now
        self.db.commit()
        return record
