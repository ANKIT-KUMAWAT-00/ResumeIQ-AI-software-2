from datetime import datetime,timezone
from pathlib import Path
from app.db.session import SessionLocal
from app.models import Resume,Output,Extraction,Review,UserSession,OTPCode
from app.services.storage.service import delete_private

def cleanup_expired():
 db=SessionLocal();now=datetime.now(timezone.utc);removed=0
 try:
  for row in db.query(Resume).filter(Resume.expires_at<now,Resume.status!='expired').all():
   delete_private(row.file_path);db.query(Extraction).filter_by(resume_id=row.id).delete();db.query(Review).filter_by(resume_id=row.id).delete();row.status='expired';removed+=1
  for row in db.query(Output).filter(Output.expires_at<now).all(): delete_private(row.file_path);db.delete(row);removed+=1
  db.query(UserSession).filter(UserSession.expires_at<now).delete(synchronize_session=False)
  db.query(OTPCode).filter(OTPCode.expires_at<now).delete(synchronize_session=False)
  db.commit();return {'removed':removed}
 finally: db.close()
