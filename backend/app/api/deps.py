from fastapi import Depends, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models import User

def current_user(request: Request, db: Session=Depends(get_db)) -> User: return get_current_user(request,db)
