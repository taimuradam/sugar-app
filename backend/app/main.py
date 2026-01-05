from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes.auth import router as auth_router
from app.api.routes.banks import router as banks_router
from app.api.routes.transactions import router as tx_router
from app.api.routes.ledger import router as ledger_router
from app.api.routes.reports import router as reports_router
from app.api.routes.users import router as users_router
from app.api.routes.audit import router as audit_router

app = FastAPI(title="Finance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(banks_router)
app.include_router(tx_router)
app.include_router(ledger_router)
app.include_router(reports_router)
app.include_router(users_router)
app.include_router(audit_router)