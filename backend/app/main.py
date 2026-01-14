from fastapi import FastAPI
import asyncio
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.auth import router as auth_router
from app.api.routes.banks import router as banks_router
from app.api.routes.transactions import router as tx_router
from app.api.routes.rates import router as rates_router
from app.api.routes.ledger import router as ledger_router
from app.api.routes.reports import router as reports_router
from app.api.routes.users import router as users_router
from app.api.routes.audit import router as audit_router
from app.api.routes.backfill import router as backfill_router
from app.api.routes.loans import router as loans_router
from app.services.kibor_sync import kibor_sync_loop

app = FastAPI()

origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

app.include_router(auth_router)
app.include_router(banks_router)
app.include_router(tx_router)
app.include_router(rates_router)
app.include_router(ledger_router)
app.include_router(reports_router)
app.include_router(users_router)
app.include_router(audit_router)
app.include_router(backfill_router)
app.include_router(loans_router)

@app.on_event("startup")
async def _start_kibor_sync():
    if getattr(settings, "kibor_sync_enabled", True):
        asyncio.create_task(kibor_sync_loop())