from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_supabase
from services.quote_service import QuoteService

# ─── Watchlist ────────────────────────────────────────────────────────────────
router = APIRouter()

class WatchlistItem(BaseModel):
    ticker: str
    name: Optional[str] = None
    asset_type: str
    currency: str
    exchange: Optional[str] = None
    notes: Optional[str] = None

@router.get("")
async def list_watchlist():
    db = get_supabase()
    result = db.table("watchlist").select("*").order("sort_order").execute()
    return result.data

@router.post("")
async def add_to_watchlist(item: WatchlistItem):
    db = get_supabase()
    data = item.model_dump(exclude_none=True)
    data["ticker"] = data["ticker"].upper().strip()
    try:
        result = db.table("watchlist").insert(data).execute()
        return result.data[0]
    except Exception:
        raise HTTPException(status_code=400, detail="Ticker already in watchlist or invalid data")

@router.delete("/{ticker}")
async def remove_from_watchlist(ticker: str):
    db = get_supabase()
    db.table("watchlist").delete().eq("ticker", ticker.upper()).execute()
    return {"status": "ok"}
