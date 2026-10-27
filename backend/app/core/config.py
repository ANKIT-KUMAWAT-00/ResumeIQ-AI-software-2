from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore", case_sensitive=False)
    app_env: str = "development"
    app_name: str = "ResumeIQ AI"
    secret_key: str = "unsafe-development-secret-change-me"
    frontend_origins: str = "http://localhost:3000"
    database_url: str = "sqlite:///./resumeiq-dev.db"
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "resumeiq"
    run_jobs_inline: bool = False
    upload_dir: str = "./private_uploads"
    output_dir: str = "./private_outputs"
    max_upload_mb: int = 10
    retention_days: int = 30
    session_cookie_name: str = "resumeiq_session"
    session_ttl_hours: int = 72
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    allow_dev_otp: bool = True
    admin_emails: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: int = 45
    gemini_max_retries: int = 2
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_base_url: str = "https://api.razorpay.com/v1"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "ResumeIQ AI <no-reply@example.com>"
    smtp_use_tls: bool = True
    storage_backend: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_presigned_url_seconds: int = 300

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.frontend_origins.split(",") if x.strip()]
    @property
    def admins(self) -> set[str]:
        return {x.strip().lower() for x in self.admin_emails.split(",") if x.strip()}

    @property
    def payments_required(self) -> bool:
        return self.app_env.strip().lower() == "production"

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
