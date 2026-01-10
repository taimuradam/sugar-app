from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db, current_user
from app.schemas.backfill import BackfillStatusOut
from app.services.kibor_backfill import get_status, ensure_started

router = APIRouter(prefix="/banks/{bank_id}/loans/{loan_id}/kibor-backfill", tags=["kibor"])


@router.get("/status", response_model=BackfillStatusOut)
def status(bank_id: int, loan_id: int, s: Session = Depends(db), u=Depends(current_user)):
    return get_status(bank_id, loan_id)


@router.post("/start", response_model=BackfillStatusOut)
def start(bank_id: int, loan_id: int, s: Session = Depends(db), u=Depends(current_user)):
    return ensure_started(bank_id, loan_id)