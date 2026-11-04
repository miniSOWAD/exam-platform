from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import router

app=FastAPI(title=settings.app_name,version="1.3.1",description="Online examination platform API",docs_url="/docs" if settings.environment!="production" else None,redoc_url=None)
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Content-Type","X-CSRF-Token"])
app.include_router(router,prefix="/api/v1")
