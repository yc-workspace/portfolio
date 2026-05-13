from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict
from database import get_supabase
from services.quote_service import QuoteService

# ─── Settings Router ──────────────────────────────────────────────────────────
router = APIRouter()

class SettingUpdate(BaseModel):
    value: str

class CurrencyPair(BaseModel):
    from_currency: str
    to_currency: str
    display_name: Optional[str] = None
    sort_order: Optional[int] = 99

@router.get("")
async def get_all_settings():
    db = get_supabase()
    result = db.table("user_settings").select("*").execute()
    # Return as key-value dict for easy frontend use
    return {row["key"]: row["value"] for row in result.data}

@router.put("/{key}")
async def update_setting(key: str, update: SettingUpdate):
    db = get_supabase()
    result = db.table("user_settings") \
        .update({"value": update.value}) \
        .eq("key", key) \
        .execute()
    if result.data:
        return result.data[0]
    raise HTTPException(status_code=404, detail="Setting not found")

@router.get("/currency-pairs")
async def get_currency_pairs():
    db = get_supabase()
    result = db.table("currency_pairs").select("*").order("sort_order").execute()
    return result.data

@router.post("/currency-pairs")
async def add_currency_pair(pair: CurrencyPair):
    db = get_supabase()
    data = pair.model_dump(exclude_none=True)
    data["from_currency"] = data["from_currency"].upper()
    data["to_currency"] = data["to_currency"].upper()
    if not data.get("display_name"):
        data["display_name"] = f"{data['from_currency']}/{data['to_currency']}"
    try:
        result = db.table("currency_pairs").insert(data).execute()
        return result.data[0]
    except Exception:
        raise HTTPException(status_code=400, detail="Currency pair already exists")

@router.delete("/currency-pairs/{pair_id}")
async def delete_currency_pair(pair_id: str):
    db = get_supabase()
    db.table("currency_pairs").delete().eq("id", pair_id).execute()
    return {"status": "ok"}

@router.post("/shioaji/connect")
async def connect_shioaji(request: Request):
    """Manually trigger Shioaji connection"""
    shioaji = request.app.state.shioaji
    success = await shioaji.login()
    return {
        "connected": success,
        "available": shioaji.available,
        "message": "Connected" if success else ("No credentials configured" if not shioaji.available else "Connection failed")
    }

@router.post("/shioaji/disconnect")
async def disconnect_shioaji(request: Request):
    """Manually disconnect Shioaji"""
    shioaji = request.app.state.shioaji
    await shioaji.logout()
    return {"connected": False, "message": "Disconnected"}
