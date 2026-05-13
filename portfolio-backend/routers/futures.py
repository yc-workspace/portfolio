from fastapi import APIRouter, Request
from services.quote_service import QuoteService

router = APIRouter()

@router.get("/txf")
async def get_txf_quote(request: Request):
    """Get Taiwan Futures (台指期) real-time quote"""
    shioaji = request.app.state.shioaji
    svc = QuoteService(shioaji)
    
    # Try Shioaji first for real TXF data
    if shioaji.is_connected:
        cached = shioaji.get_cached_quote("TXFR1")
        if cached:
            return {**cached, "contract": "TXFR1", "name": "臺股期貨近月"}
        
        snapshot = await shioaji.get_snapshot(["TXFR1"])
        if snapshot.get("TXFR1"):
            return {**snapshot["TXFR1"], "contract": "TXFR1", "name": "臺股期貨近月"}
    
    # Fallback: TWII as proxy
    result = await svc._get_yahoo_quote("^TWII")
    return {
        **result,
        "contract": "TWII_proxy",
        "name": "台灣加權指數（台指期備用）",
        "note": "永豐API未連線，顯示加權指數替代"
    }

@router.get("/international")
async def get_international_futures(request: Request):
    """Get major international futures quotes"""
    shioaji = request.app.state.shioaji
    svc = QuoteService(shioaji)
    
    # ES (S&P 500 futures), NQ (Nasdaq futures) via Twelve Data
    import asyncio
    results = await asyncio.gather(
        svc._get_twelve_data_quote("/ES", "futures"),
        svc._get_twelve_data_quote("/NQ", "futures"),
        svc._get_twelve_data_quote("GC=F", "futures"),  # Gold futures
        return_exceptions=True
    )
    
    labels = ["ES（S&P 500期貨）", "NQ（Nasdaq期貨）", "GC（黃金期貨）"]
    symbols = ["ES", "NQ", "GC"]
    
    output = []
    for sym, label, result in zip(symbols, labels, results):
        if isinstance(result, Exception) or (isinstance(result, dict) and "error" in result):
            output.append({"symbol": sym, "label": label, "price": None, "error": True})
        else:
            output.append({"symbol": sym, "label": label, **result})
    
    return output
