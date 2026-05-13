import os
import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_API_KEY")
EXCHANGE_RATE_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

# Ticker type detection
TW_STOCK_PATTERN = lambda t: (t.isdigit() and len(t) == 4) or (t.isdigit() and len(t) == 5)
CRYPTO_TICKERS = {"BTC", "ETH", "BNB", "SOL", "USDT"}
GOLD_TICKERS = {"XAU", "GOLD", "GLD"}

# Market index symbols mapping
INDEX_SYMBOLS = {
    "SPX":  {"twelve": "SPX", "label": "S&P 500"},
    "NDX":  {"twelve": "NDX", "label": "NASDAQ 100"},
    "SOX":  {"twelve": "SOX", "label": "費城半導體"},
    "VIX":  {"twelve": "VIX", "label": "VIX"},
    "DXY":  {"twelve": "DXY", "label": "美元指數"},
    "TWII": {"twelve": "TWII:INDX", "label": "台灣加權指數"},
    "XAU":  {"twelve": "XAU/USD", "label": "黃金"},
    "BTC":  {"coingecko": "bitcoin", "label": "比特幣"},
    "TXFR1": {"shioaji": True, "label": "台指期"},
}

class QuoteService:
    def __init__(self, shioaji_service=None):
        self.shioaji = shioaji_service
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    # ─── Main Entry Point ───────────────────────────────────────────────────

    async def get_quote(self, ticker: str, asset_type: str = None) -> Dict[str, Any]:
        """
        Get quote for any ticker with automatic source selection and fallback.
        Waterfall: Shioaji → Twelve Data → Yahoo Finance → Error
        """
        ticker = ticker.upper().strip()
        
        if asset_type == "crypto" or ticker in CRYPTO_TICKERS:
            return await self._get_crypto_quote(ticker)
        
        if TW_STOCK_PATTERN(ticker) or asset_type == "tw_stock":
            return await self._get_tw_stock_quote(ticker)
        
        if ticker == "XAU" or asset_type == "gold":
            return await self._get_gold_quote()
        
        # Default: US stock or ETF
        return await self._get_us_stock_quote(ticker)

    async def get_multiple_quotes(self, tickers_with_types: List[Dict]) -> Dict[str, Any]:
        """Get quotes for multiple tickers concurrently"""
        tasks = []
        for item in tickers_with_types:
            tasks.append(self.get_quote(item["ticker"], item.get("asset_type")))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = {}
        for item, result in zip(tickers_with_types, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get quote for {item['ticker']}: {result}")
                output[item["ticker"]] = {"error": str(result)}
            else:
                output[item["ticker"]] = result
        
        return output

    async def get_market_overview(self) -> List[Dict]:
        """Get the 9 market indices for dashboard"""
        tasks = {
            "SPX":   self._get_twelve_data_quote("SPX", "index"),
            "NDX":   self._get_twelve_data_quote("NDX", "index"),
            "SOX":   self._get_twelve_data_quote("SOX", "index"),
            "TWII":  self._get_twii_quote(),
            "TXFR1": self._get_txf_quote(),
            "VIX":   self._get_twelve_data_quote("VIX", "index"),
            "XAU":   self._get_gold_quote(),
            "BTC":   self._get_crypto_quote("BTC"),
            "DXY":   self._get_twelve_data_quote("DXY", "index"),
        }
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        output = []
        for key, result in zip(tasks.keys(), results):
            info = INDEX_SYMBOLS.get(key, {})
            if isinstance(result, Exception) or (isinstance(result, dict) and "error" in result):
                output.append({
                    "symbol": key,
                    "label": info.get("label", key),
                    "price": None,
                    "change": None,
                    "change_pct": None,
                    "error": True
                })
            else:
                output.append({
                    "symbol": key,
                    "label": info.get("label", key),
                    **result
                })
        
        return output

    async def get_exchange_rates(self, pairs: List[Dict]) -> List[Dict]:
        """Get exchange rates for currency pairs"""
        results = []
        for pair in pairs:
            try:
                rate = await self._get_exchange_rate(pair["from_currency"], pair["to_currency"])
                results.append({
                    **pair,
                    "rate": rate.get("rate"),
                    "change_pct": rate.get("change_pct"),
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                results.append({**pair, "rate": None, "error": str(e)})
        return results

    # ─── Taiwan Stock ────────────────────────────────────────────────────────

    async def _get_tw_stock_quote(self, ticker: str) -> Dict:
        """TW Stock: Shioaji → Yahoo Finance fallback"""
        
        # Try Shioaji first (if connected)
        if self.shioaji and self.shioaji.is_connected:
            cached = self.shioaji.get_cached_quote(ticker)
            if cached:
                return cached
            
            snapshot = await self.shioaji.get_snapshot([ticker])
            if snapshot.get(ticker):
                return snapshot[ticker]
        
        # Fallback: Yahoo Finance (no key needed, uses .TW suffix)
        return await self._get_yahoo_quote(f"{ticker}.TW")

    async def _get_twii_quote(self) -> Dict:
        """Taiwan Weighted Index"""
        if self.shioaji and self.shioaji.is_connected:
            try:
                import shioaji as sj
                import asyncio
                loop = asyncio.get_event_loop()
                def _get():
                    snapshots = self.shioaji.api.snapshots([self.shioaji.api.Contracts.Indexs.TSE["001"]])
                    if snapshots:
                        s = snapshots[0]
                        return {
                            "price": float(s.close),
                            "price_change": float(s.change_price),
                            "price_change_pct": float(s.change_rate),
                            "source": "shioaji",
                            "currency": "TWD"
                        }
                result = await loop.run_in_executor(None, _get)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Shioaji TWII failed: {e}")
        
        return await self._get_yahoo_quote("^TWII")

    async def _get_txf_quote(self) -> Dict:
        """Taiwan Futures (台指期)"""
        if self.shioaji and self.shioaji.is_connected:
            cached = self.shioaji.get_cached_quote("TXFR1")
            if cached:
                return cached
        
        # Fallback: Yahoo Finance for TWII as proxy
        result = await self._get_yahoo_quote("^TWII")
        result["note"] = "台指期使用加權指數替代（無永豐API）"
        return result

    # ─── US Stock / ETF ──────────────────────────────────────────────────────

    async def _get_us_stock_quote(self, ticker: str) -> Dict:
        """US Stock: Twelve Data → Yahoo Finance fallback"""
        result = await self._get_twelve_data_quote(ticker, "stock")
        if "error" not in result:
            return result
        return await self._get_yahoo_quote(ticker)

    # ─── Crypto ──────────────────────────────────────────────────────────────

    async def _get_crypto_quote(self, ticker: str) -> Dict:
        """Crypto via CoinGecko (no API key needed)"""
        coin_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "BNB": "binancecoin",
            "SOL": "solana",
        }
        coin_id = coin_map.get(ticker.upper(), ticker.lower())
        
        try:
            resp = await self.http.get(
                f"https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_24hr_vol": "true"
                }
            )
            data = resp.json()
            if coin_id in data:
                d = data[coin_id]
                return {
                    "ticker": ticker,
                    "price": d.get("usd"),
                    "price_change_pct": d.get("usd_24h_change"),
                    "volume": d.get("usd_24h_vol"),
                    "source": "coingecko",
                    "currency": "USD",
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.error(f"CoinGecko failed for {ticker}: {e}")
        
        return {"ticker": ticker, "error": "Failed to fetch crypto price"}

    # ─── Gold ────────────────────────────────────────────────────────────────

    async def _get_gold_quote(self) -> Dict:
        """Gold (XAU/USD) via Twelve Data"""
        return await self._get_twelve_data_quote("XAU/USD", "forex")

    # ─── Twelve Data ─────────────────────────────────────────────────────────

    async def _get_twelve_data_quote(self, symbol: str, instrument_type: str = "stock") -> Dict:
        """Generic Twelve Data quote fetcher"""
        if not TWELVE_DATA_KEY:
            return {"error": "Twelve Data API key not configured"}
        
        try:
            resp = await self.http.get(
                "https://api.twelvedata.com/price",
                params={"symbol": symbol, "apikey": TWELVE_DATA_KEY}
            )
            price_data = resp.json()
            
            # Also get quote for change info
            resp2 = await self.http.get(
                "https://api.twelvedata.com/quote",
                params={"symbol": symbol, "apikey": TWELVE_DATA_KEY}
            )
            quote_data = resp2.json()
            
            if "price" in price_data and "code" not in price_data:
                price = float(price_data["price"])
                prev_close = float(quote_data.get("previous_close", price))
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0
                
                return {
                    "ticker": symbol,
                    "price": price,
                    "price_change": change,
                    "price_change_pct": change_pct,
                    "open": float(quote_data.get("open", 0) or 0),
                    "high": float(quote_data.get("high", 0) or 0),
                    "low": float(quote_data.get("low", 0) or 0),
                    "volume": int(quote_data.get("volume", 0) or 0),
                    "prev_close": prev_close,
                    "source": "twelve_data",
                    "currency": "USD" if "/" not in symbol else "USD",
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.error(f"Twelve Data failed for {symbol}: {e}")
        
        return {"error": f"Twelve Data failed for {symbol}"}

    async def get_historical_kbars(self, ticker: str, start: str, end: str, interval: str = "1day") -> List[Dict]:
        """Get historical OHLCV data"""
        # Try Shioaji for TW stocks
        if TW_STOCK_PATTERN(ticker) and self.shioaji and self.shioaji.is_connected:
            result = await self.shioaji.get_kbars(ticker, start, end)
            if result:
                return result
        
        # Twelve Data for everything else
        if not TWELVE_DATA_KEY:
            return []
        
        symbol = f"{ticker}.TW" if TW_STOCK_PATTERN(ticker) else ticker
        
        try:
            resp = await self.http.get(
                "https://api.twelvedata.com/time_series",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "start_date": start,
                    "end_date": end,
                    "apikey": TWELVE_DATA_KEY,
                    "outputsize": 5000
                }
            )
            data = resp.json()
            
            if "values" in data:
                return [
                    {
                        "ts": item["datetime"],
                        "open": float(item["open"]),
                        "high": float(item["high"]),
                        "low": float(item["low"]),
                        "close": float(item["close"]),
                        "volume": int(item.get("volume", 0) or 0)
                    }
                    for item in reversed(data["values"])
                ]
        except Exception as e:
            logger.error(f"Historical data failed for {ticker}: {e}")
        
        return []

    # ─── Yahoo Finance (fallback, no key needed) ──────────────────────────────

    async def _get_yahoo_quote(self, symbol: str) -> Dict:
        """Yahoo Finance fallback - no API key needed"""
        try:
            resp = await self.http.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("previousClose", price)
                change = price - prev
                change_pct = (change / prev * 100) if prev else 0
                
                return {
                    "ticker": symbol,
                    "price": price,
                    "price_change": change,
                    "price_change_pct": change_pct,
                    "open": meta.get("regularMarketOpen", 0),
                    "high": meta.get("regularMarketDayHigh", 0),
                    "low": meta.get("regularMarketDayLow", 0),
                    "volume": meta.get("regularMarketVolume", 0),
                    "source": "yahoo_finance",
                    "currency": meta.get("currency", "USD"),
                    "fetched_at": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.error(f"Yahoo Finance failed for {symbol}: {e}")
        
        return {"ticker": symbol, "error": "All quote sources failed"}

    # ─── Exchange Rate ────────────────────────────────────────────────────────

    async def _get_exchange_rate(self, from_cur: str, to_cur: str) -> Dict:
        """Get exchange rate"""
        if not EXCHANGE_RATE_KEY:
            # Fallback: use Twelve Data forex
            result = await self._get_twelve_data_quote(f"{from_cur}/{to_cur}", "forex")
            if "price" in result:
                return {"rate": result["price"], "change_pct": result.get("price_change_pct")}
        
        try:
            resp = await self.http.get(
                f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_KEY}/pair/{from_cur}/{to_cur}"
            )
            data = resp.json()
            if data.get("result") == "success":
                return {
                    "rate": data["conversion_rate"],
                    "change_pct": None  # ExchangeRate-API free doesn't provide change
                }
        except Exception as e:
            logger.error(f"Exchange rate failed {from_cur}/{to_cur}: {e}")
        
        return {"rate": None, "error": "Failed to fetch exchange rate"}
