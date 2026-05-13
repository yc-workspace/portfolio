from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime, timezone
from decimal import Decimal
import logging

from database import get_supabase
from services.quote_service import QuoteService

router = APIRouter()
logger = logging.getLogger(__name__)

# ─── Pydantic Models ─────────────────────────────────────────────────────────

class HoldingCreate(BaseModel):
    ticker: str
    name: Optional[str] = None
    asset_type: str  # tw_stock, us_stock, crypto, gold, etf
    currency: str    # TWD, USD
    exchange: Optional[str] = None
    shares: float
    cost_price: float
    cost_price_twd: Optional[float] = None
    buy_date: Optional[date] = None
    notes: Optional[str] = None

class HoldingUpdate(BaseModel):
    name: Optional[str] = None
    shares: Optional[float] = None
    cost_price: Optional[float] = None
    cost_price_twd: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class DividendCreate(BaseModel):
    holding_id: str
    ticker: str
    ex_date: date
    pay_date: Optional[date] = None
    dividend_per_share: float
    currency: str
    shares_held: Optional[float] = None
    exchange_rate: Optional[float] = None  # USD to TWD at time of receipt

# ─── Holdings CRUD ────────────────────────────────────────────────────────────

@router.get("/holdings")
async def list_holdings(request: Request):
    """Get all active holdings"""
    db = get_supabase()
    result = db.table("portfolio_holdings") \
        .select("*") \
        .eq("is_active", True) \
        .order("asset_type") \
        .execute()
    return result.data

@router.post("/holdings")
async def add_holding(holding: HoldingCreate):
    """Add a new holding"""
    db = get_supabase()
    
    data = holding.model_dump(exclude_none=True)
    data["ticker"] = data["ticker"].upper().strip()
    if data.get("buy_date"):
        data["buy_date"] = str(data["buy_date"])
    
    result = db.table("portfolio_holdings").insert(data).execute()
    
    if result.data:
        return result.data[0]
    raise HTTPException(status_code=400, detail="Failed to add holding")

@router.put("/holdings/{holding_id}")
async def update_holding(holding_id: str, update: HoldingUpdate):
    """Update a holding"""
    db = get_supabase()
    
    data = update.model_dump(exclude_none=True)
    result = db.table("portfolio_holdings") \
        .update(data) \
        .eq("id", holding_id) \
        .execute()
    
    if result.data:
        return result.data[0]
    raise HTTPException(status_code=404, detail="Holding not found")

@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: str, hard_delete: bool = False):
    """Soft delete (mark inactive) or hard delete a holding"""
    db = get_supabase()
    
    if hard_delete:
        db.table("portfolio_holdings").delete().eq("id", holding_id).execute()
    else:
        db.table("portfolio_holdings") \
            .update({"is_active": False}) \
            .eq("id", holding_id) \
            .execute()
    
    return {"status": "ok", "message": "Holding removed"}

# ─── Portfolio with Live Prices ───────────────────────────────────────────────

@router.get("/summary")
async def get_portfolio_summary(request: Request):
    """
    Get full portfolio with live prices, P&L, and currency conversion.
    This is the main endpoint for the portfolio page.
    """
    db = get_supabase()
    shioaji = request.app.state.shioaji
    quote_svc = QuoteService(shioaji)
    
    # 1. Get all active holdings
    holdings_result = db.table("portfolio_holdings") \
        .select("*") \
        .eq("is_active", True) \
        .execute()
    holdings = holdings_result.data
    
    if not holdings:
        return {"holdings": [], "summary": {}, "allocation": {}}
    
    # 2. Get current exchange rates
    usd_twd = await _get_usd_twd_rate(quote_svc)
    
    # 3. Fetch live prices for all holdings
    tickers_with_types = [
        {"ticker": h["ticker"], "asset_type": h["asset_type"]}
        for h in holdings
    ]
    prices = await quote_svc.get_multiple_quotes(tickers_with_types)
    
    # 4. Get dividend totals per holding
    dividends = db.table("dividend_records") \
        .select("holding_id, total_dividend, total_dividend_twd, currency") \
        .execute()
    
    div_by_holding = {}
    for d in dividends.data:
        hid = d["holding_id"]
        if hid not in div_by_holding:
            div_by_holding[hid] = {"total_usd": 0, "total_twd": 0}
        if d["currency"] == "TWD":
            div_by_holding[hid]["total_twd"] += float(d["total_dividend"] or 0)
        else:
            div_by_holding[hid]["total_usd"] += float(d["total_dividend"] or 0)
    
    # 5. Calculate P&L for each holding
    enriched = []
    total_cost_twd = 0
    total_value_twd = 0
    currency_allocation = {}
    ticker_allocation = {}
    
    for h in holdings:
        ticker = h["ticker"]
        price_data = prices.get(ticker, {})
        current_price = price_data.get("price")
        
        # Determine exchange rate for this holding
        if h["currency"] == "TWD":
            fx_rate = 1.0
        else:
            fx_rate = usd_twd  # Currently USD is the only non-TWD
        
        # Cost basis
        cost_price = float(h["cost_price"])
        shares = float(h["shares"])
        cost_price_twd = float(h.get("cost_price_twd") or cost_price * fx_rate)
        total_cost = cost_price * shares
        total_cost_twd_val = cost_price_twd * shares
        
        # Current value
        if current_price:
            current_value = current_price * shares
            current_value_twd = current_value * fx_rate
            
            # P&L
            pnl = current_value - total_cost
            pnl_twd = current_value_twd - total_cost_twd_val
            pnl_pct = (pnl / total_cost * 100) if total_cost else 0
            
            # Dividends
            h_id = h["id"]
            div_info = div_by_holding.get(h_id, {})
            if h["currency"] == "TWD":
                div_total = div_info.get("total_twd", 0)
                div_total_twd = div_total
            else:
                div_total = div_info.get("total_usd", 0)
                div_total_twd = div_total * fx_rate + div_info.get("total_twd", 0)
            
            # Total return including dividends
            total_return_twd = pnl_twd + div_total_twd
            total_return_pct = (total_return_twd / total_cost_twd_val * 100) if total_cost_twd_val else 0
        else:
            current_value = current_value_twd = None
            pnl = pnl_twd = pnl_pct = None
            total_return_twd = total_return_pct = None
        
        enriched_holding = {
            **h,
            "current_price": current_price,
            "price_change": price_data.get("price_change"),
            "price_change_pct": price_data.get("price_change_pct"),
            "current_value": current_value,
            "current_value_twd": current_value_twd,
            "total_cost": total_cost,
            "total_cost_twd": total_cost_twd_val,
            "pnl": pnl,
            "pnl_twd": pnl_twd,
            "pnl_pct": pnl_pct,
            "dividend_total_twd": div_total_twd if current_price else 0,
            "total_return_twd": total_return_twd,
            "total_return_pct": total_return_pct,
            "quote_source": price_data.get("source"),
            "fx_rate": fx_rate,
        }
        enriched.append(enriched_holding)
        
        # Accumulate for summary
        if current_value_twd:
            total_value_twd += current_value_twd
            total_cost_twd += total_cost_twd_val
            
            # Currency allocation
            cur = h["currency"]
            currency_allocation[cur] = currency_allocation.get(cur, 0) + current_value_twd
            
            # Ticker allocation
            ticker_allocation[ticker] = ticker_allocation.get(ticker, 0) + current_value_twd
    
    # 6. Build summary
    total_pnl_twd = total_value_twd - total_cost_twd
    total_pnl_pct = (total_pnl_twd / total_cost_twd * 100) if total_cost_twd else 0
    
    summary = {
        "total_value_twd": total_value_twd,
        "total_cost_twd": total_cost_twd,
        "total_pnl_twd": total_pnl_twd,
        "total_pnl_pct": total_pnl_pct,
        "usd_twd_rate": usd_twd,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # 7. Allocation percentages
    currency_alloc = {
        k: {"value_twd": v, "pct": v / total_value_twd * 100 if total_value_twd else 0}
        for k, v in currency_allocation.items()
    }
    ticker_alloc = {
        k: {"value_twd": v, "pct": v / total_value_twd * 100 if total_value_twd else 0}
        for k, v in sorted(ticker_allocation.items(), key=lambda x: x[1], reverse=True)
    }
    
    return {
        "holdings": enriched,
        "summary": summary,
        "currency_allocation": currency_alloc,
        "ticker_allocation": ticker_alloc
    }

# ─── Dividends ────────────────────────────────────────────────────────────────

@router.get("/dividends")
async def list_dividends(ticker: Optional[str] = None):
    db = get_supabase()
    query = db.table("dividend_records").select("*").order("ex_date", desc=True)
    if ticker:
        query = query.eq("ticker", ticker.upper())
    result = query.execute()
    return result.data

@router.post("/dividends")
async def add_dividend(dividend: DividendCreate):
    db = get_supabase()
    data = dividend.model_dump(exclude_none=True)
    data["ex_date"] = str(data["ex_date"])
    if data.get("pay_date"):
        data["pay_date"] = str(data["pay_date"])
    
    # Auto-calculate total dividend
    if data.get("shares_held") and data.get("dividend_per_share"):
        data["total_dividend"] = data["shares_held"] * data["dividend_per_share"]
        if data.get("exchange_rate") and data.get("currency") != "TWD":
            data["total_dividend_twd"] = data["total_dividend"] * data["exchange_rate"]
        elif data.get("currency") == "TWD":
            data["total_dividend_twd"] = data["total_dividend"]
    
    result = db.table("dividend_records").insert(data).execute()
    if result.data:
        return result.data[0]
    raise HTTPException(status_code=400, detail="Failed to add dividend")

@router.delete("/dividends/{dividend_id}")
async def delete_dividend(dividend_id: str):
    db = get_supabase()
    db.table("dividend_records").delete().eq("id", dividend_id).execute()
    return {"status": "ok"}

# ─── Helper ───────────────────────────────────────────────────────────────────

async def _get_usd_twd_rate(quote_svc: QuoteService) -> float:
    """Get USD/TWD rate with fallback"""
    try:
        rate_data = await quote_svc._get_exchange_rate("USD", "TWD")
        if rate_data.get("rate"):
            return float(rate_data["rate"])
    except Exception:
        pass
    return 32.0  # Emergency fallback
