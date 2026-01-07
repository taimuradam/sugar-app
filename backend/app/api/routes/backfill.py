from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db, current_user
from app.schemas.backfill import BackfillStatusOut
from app.services.kibor_backfill import get_status, ensure_started


router = APIRouter(prefix="/banks/{bank_id}/kibor-backfill", tags=["kibor"])


@router.get("/status", response_model=BackfillStatusOut)
def status(bank_id: int, s: Session = Depends(db), u=Depends(current_user)):
    # s is unused but keeps signature consistent with auth/deps
    return get_status(bank_id)


@router.post("/start", response_model=BackfillStatusOut)
def start(bank_id: int, s: Session = Depends(db), u=Depends(current_user)):
    # Starts in background thread and returns immediately
    return ensure_started(bank_id)
