import json
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.db.session import Base,engine,SessionLocal
from app.models import *
from app.api.routes import router
from app.schemas.template import TemplateSpec

def seed_templates():
 root=Path(__file__).resolve().parents[2]/'template_specs';db=SessionLocal()
 try:
  from app.models import Template
  for path in root.glob('*.json'):
   try: spec=TemplateSpec.model_validate_json(path.read_text())
   except Exception: continue
   row=db.query(Template).filter_by(template_id=spec.template_id).first()
   if not row: db.add(Template(template_id=spec.template_id,version=spec.version,spec=spec.model_dump(mode='json'),published=True))
  from app.models import RoleRubric
  rubric_root=root.parent/'role_rubrics'
  for path in rubric_root.glob('*.json'):
   try: data=json.loads(path.read_text())
   except Exception: continue
   row=db.query(RoleRubric).filter_by(rubric_id=path.stem).first()
   if not row: db.add(RoleRubric(rubric_id=path.stem,version=data.get('version','1.0.0'),data=data))
  db.commit()
 finally: db.close()

@asynccontextmanager
async def lifespan(app:FastAPI):
 if settings.app_env.lower()=='production' and (len(settings.secret_key)<32 or settings.secret_key in {'unsafe-development-secret-change-me','replace-with-at-least-32-random-bytes'} or settings.secret_key.lower().startswith(('replace-with','change-me'))):
  raise RuntimeError('Production requires a strong SECRET_KEY.')
 # Convenient for local development; production still runs the versioned Alembic migration first.
 Base.metadata.create_all(bind=engine);seed_templates()
 yield

app=FastAPI(title=settings.app_name,version='1.0.0',description='ResumeIQ AI resume intelligence API',lifespan=lifespan)
app.include_router(router,prefix='/api')
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'],allow_headers=['Content-Type','X-Requested-With','X-Razorpay-Signature','X-Razorpay-Event-Id'])
@app.middleware('http')
async def origin_guard(request:Request,call_next):
 if request.method in {'POST','PUT','PATCH','DELETE'} and request.url.path!='/api/payments/webhook':
  origin=request.headers.get('origin')
  if origin and origin not in settings.origins:
   return JSONResponse(status_code=403,content={'detail':'Request origin is not allowed.'})
 return await call_next(request)
@app.exception_handler(Exception)
async def safe_error_handler(request,exc):
 if settings.app_env.lower()=='development': return JSONResponse(status_code=500,content={'detail':f'Unexpected server error ({type(exc).__name__}). Check server logs.'})
 return JSONResponse(status_code=500,content={'detail':'An unexpected error occurred. Please retry later.'})
