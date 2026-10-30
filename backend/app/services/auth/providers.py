from abc import ABC, abstractmethod
import logging
from app.core.config import settings
from app.services.mailer import send_otp

logger = logging.getLogger("resumeiq.auth")

class VerificationError(Exception):
    pass

class VerificationConfigurationError(VerificationError):
    pass

class BaseVerificationProvider(ABC):
    @abstractmethod
    def send_email_verification(self, email: str, code: str) -> dict:
        """Send verification code to an email address."""
        pass

    @abstractmethod
    def send_phone_verification(self, phone: str, code: str) -> dict:
        """Send verification code to a phone number."""
        pass

    @abstractmethod
    def send_password_reset(self, email: str, code: str) -> dict:
        """Send password reset code to an email address."""
        pass


class DevelopmentVerificationProvider(BaseVerificationProvider):
    """
    Simulation provider for development mode.
    Strictly forbidden and blocked in production.
    """
    DEV_OTP = "123456"

    def __init__(self):
        if settings.app_env.strip().lower() == "production":
            raise VerificationConfigurationError(
                "DevelopmentVerificationProvider is forbidden in production environments."
            )

    def send_email_verification(self, email: str, code: str) -> dict:
        effective_code = self.DEV_OTP if settings.allow_dev_otp else code
        logger.info(
            f"[DEV SIMULATED EMAIL] Verification for {email} -> Simulated OTP: {effective_code}"
        )
        return {
            "delivered": True,
            "simulated": True,
            "development_code": effective_code,
            "message": "Simulated development verification code generated.",
        }

    def send_phone_verification(self, phone: str, code: str) -> dict:
        effective_code = self.DEV_OTP if settings.allow_dev_otp else code
        logger.info(
            f"[DEV SIMULATED SMS] Verification for {phone} -> Simulated OTP: {effective_code}"
        )
        return {
            "delivered": True,
            "simulated": True,
            "development_code": effective_code,
            "message": "Simulated development SMS verification code generated.",
        }

    def send_password_reset(self, email: str, code: str) -> dict:
        effective_code = self.DEV_OTP if settings.allow_dev_otp else code
        logger.info(
            f"[DEV SIMULATED RESET] Password reset for {email} -> Simulated OTP: {effective_code}"
        )
        return {
            "delivered": True,
            "simulated": True,
            "development_code": effective_code,
            "message": "Simulated development password reset code generated.",
        }


class ProductionEmailVerificationProvider(BaseVerificationProvider):
    """
    Production email provider using configured SMTP.
    Fails closed if SMTP is unconfigured in production.
    """
    def __init__(self):
        if not settings.smtp_host and settings.app_env.strip().lower() == "production":
            raise VerificationConfigurationError(
                "Production email provider requires SMTP_HOST to be configured. Failing closed."
            )

    def send_email_verification(self, email: str, code: str) -> dict:
        if not settings.smtp_host:
            raise VerificationConfigurationError(
                "SMTP is not configured on this server."
            )
        send_otp(email, code)
        return {
            "delivered": True,
            "simulated": False,
            "message": "Verification email dispatched via SMTP.",
        }

    def send_phone_verification(self, phone: str, code: str) -> dict:
        raise VerificationConfigurationError(
            "SMS verification provider is required for phone numbers."
        )

    def send_password_reset(self, email: str, code: str) -> dict:
        if not settings.smtp_host:
            raise VerificationConfigurationError(
                "SMTP is not configured on this server."
            )
        send_otp(email, code)
        return {
            "delivered": True,
            "simulated": False,
            "message": "Password reset email dispatched via SMTP.",
        }


class ProductionSMSVerificationProvider(BaseVerificationProvider):
    """
    Production SMS provider interface.
    Fails closed when SMS credentials are not configured in production.
    """
    def __init__(self):
        if settings.app_env.strip().lower() == "production":
            raise VerificationConfigurationError(
                "Production SMS verification provider is not configured. Failing closed."
            )

    def send_email_verification(self, email: str, code: str) -> dict:
        raise VerificationConfigurationError(
            "SMS provider cannot send email verifications."
        )

    def send_phone_verification(self, phone: str, code: str) -> dict:
        raise VerificationConfigurationError(
            "Production SMS provider is not active. Real provider required in production."
        )

    def send_password_reset(self, email: str, code: str) -> dict:
        raise VerificationConfigurationError(
            "SMS provider cannot send email password resets."
        )


def get_verification_provider() -> BaseVerificationProvider:
    """
    Factory resolving verification provider based on APP_ENV and configuration.
    Strictly forbids development providers when APP_ENV=production.
    """
    is_prod = settings.app_env.strip().lower() == "production"

    if is_prod:
        # Must fail-closed if required configuration is missing
        return ProductionEmailVerificationProvider()

    # Development mode: prefer DevelopmentVerificationProvider unless user configured SMTP
    if settings.smtp_host:
        return ProductionEmailVerificationProvider()
    return DevelopmentVerificationProvider()

