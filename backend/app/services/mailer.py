import smtplib
from email.message import EmailMessage
from app.core.config import settings

def send_otp(email: str, code: str) -> None:
 if not settings.smtp_host:
  if settings.app_env.lower()=='development' and settings.allow_dev_otp:
   print(f"[DEV ONLY] ResumeIQ AI OTP for {email}: {code}")
   return
  raise RuntimeError('Email delivery is not configured. Set SMTP_HOST and related SMTP variables.')
 msg=EmailMessage(); msg['Subject']='Your ResumeIQ AI sign-in code'; msg['From']=settings.smtp_from; msg['To']=email
 msg.set_content(f"Your ResumeIQ AI sign-in code is {code}. It expires in {settings.otp_ttl_minutes} minutes. If you did not request it, ignore this email.")
 with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
  if settings.smtp_use_tls: smtp.starttls()
  if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password)
  smtp.send_message(msg)
