from fastapi import APIRouter, Request
from typing import List, Optional
from services.quote_service import QuoteService

router = APIRouter()

@router.get("/market-overview")
async def market_overview(request: Request):
    """Get all 9 market indices for dashboard"""
    shioaji = request.app.state.shioaji
    svc = QuoteService(shioaji)
    return await svc.get_market_overview()

@router.get("/price/{ticker}")
async def get_price(ticker: str, asset_type: Optional[str] = None, request: Request = None):
    """Get single ticker price"""
    shioaji = request.app.state.shioaji
    svc = QuoteService(shioaji)
    return await svc.get_quote(ticker, asset_type)

@router.get("/exchange-rates")
async def get_exchange_rates(request: Request):
    """Get all configured currency pairs"""
    from database import get_supabase
    shioaji = request.app.state.shioaji
    svc = QuoteService(shioaji)
    
    db = get_supabase()
    pairs = db.table("currency_pairs").select("*").order("sort_order").execute()
    
    return await svc.get_exchange_rates(pairs.data)

@router.get("/history/{ticker}")
async def get_history(
    ticker: str,
    start: str,
    end: str,
    interval: str = "1day",
    request: Request = None
):
    """Get historical OHLCV data for charting"""
    shioaji = request.app.state.shioaji
    svc = QuoteService(shioaji)
    return await svc.get_historical_kbars(ticker, start, end, interval)
