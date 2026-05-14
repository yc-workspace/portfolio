from fastapi import APIRouter
import httpx
import os
import asyncio

router = APIRouter()

@router.get("/debug/connectivity")
async def test_connectivity():
    """Test all external API connections"""
    results = {}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        # 1. Test Twelve Data
        td_key = os.getenv("TWELVE_DATA_API_KEY", "NOT_SET")
        results["twelve_data_key_set"] = td_key != "NOT_SET"
        results["twelve_data_key_prefix"] = td_key[:6] + "..." if td_key != "NOT_SET" else "NOT_SET"
        try:
            r = await client.get(
                "https://api.twelvedata.com/price",
                params={"symbol": "AAPL", "apikey": td_key}
            )
            results["twelve_data_response"] = r.json()
        except Exception as e:
            results["twelve_data_error"] = str(e)

        # 2. Test CoinGecko
        try:
            r = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                headers={"Accept": "application/json"}
            )
            results["coingecko_status"] = r.status_code
            results["coingecko_response"] = r.json()
        except Exception as e:
            results["coingecko_error"] = str(e)

        # 3. Test Yahoo Finance
        try:
            r = await client.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/AAPL",
                params={"interval": "1d", "range": "1d"},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            results["yahoo_status"] = r.status_code
            meta = r.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
            results["yahoo_aapl_price"] = meta.get("regularMarketPrice")
        except Exception as e:
            results["yahoo_error"] = str(e)

        # 4. Test ExchangeRate-API
        er_key = os.getenv("EXCHANGE_RATE_API_KEY", "NOT_SET")
        results["exchange_rate_key_set"] = er_key != "NOT_SET"
        try:
            r = await client.get(
                f"https://v6.exchangerate-api.com/v6/{er_key}/pair/USD/TWD"
            )
            results["exchange_rate_response"] = r.json()
        except Exception as e:
            results["exchange_rate_error"] = str(e)

    return results
