import os
import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_API_KEY")
EXCHANGE_RATE_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

TW_STOCK_PATTERN = lambda t: (t.isdigit() and len(t) == 4) or (t.isdigit() and len(t) == 5)
CRYPTO_TICKERS = {"BTC", "ETH", "BNB", "SOL", "USDT"}

INDEX_SYMBOLS = {
    "SPX":   {"label": "S&P 500"},
    "NDX":   {"label": "NASDAQ 100"},
    "SOX":   {"label": "費城半導體"},
    "VIX":   {"label": "VIX"},
    "DXY":   {"label": "美元指數"},
    "TWII":  {"label": "台灣加權指數"},
    "XAU":   {"label": "黃金"},
    "BTC":   {"label": "比特幣"},
    "TXFR1": {"label": "台指期"},
}

# Twelve Data symbol mapping
TD_SYMBOLS = {
    "SPX":  "SPX",
    "NDX":  "NDX",
    "SOX":  "SOX",
    "VIX":  "VIX",
    "DXY":  "DXY",
    "TWII": "TWII:INDX",
    "XAU":  "XAU/USD",
    "BTC":  "BTC/USD",
}

class QuoteService:
    def __init__(self, shioaji_service=None):
        self.shioaji = shioaji_service
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

    # ─── Market Overview ─────────────────────────────────────────────────────
    async def get_market_overview(self) -> List[Dict]:
        """
        Fetch all 9 indices in as few API calls as possible.
        Uses Twelve Data batch for SPX/NDX/SOX/VIX/DXY/TWII/XAU/BTC (1 call).
        Taiwan Futures from Shioaji if available.
        """
        # Single batch call for 8 of 9 symbols
        symbols_to_fetch = ["SPX", "NDX", "SOX", "VIX", "DXY", "TWII", "XAU", "BTC"]
        td_symbols = [TD_SYMBOLS[s] for s in symbols_to_fetch]
        
        batch = await self._td_batch(td_symbols)
        
        # Map back from TD symbol to our key
        td_reverse = {v: k for k, v in TD_SYMBOLS.items()}
        data_by_key = {}
        for td_sym, result in batch.items():
            key = td_reverse.get(td_sym, td_sym)
            data_by_key[key] = result

        # Taiwan Futures — Shioaji only, no fallback that works on Render
        if self.shioaji and self.shioaji.is_connected:
            cached = self.shioaji.get_cached_quote("TXFR1")
            if cached:
                data_by_key["TXFR1"] = cached
            else:
                txf_note = {"note": "永豐API未連線，無台指期備援"}
                data_by_key["TXFR1"] = txf_note
        else:
            data_by_key["TXFR1"] = {
                "price": None,
                "note": "請連線永豐API取得台指期報價"
            }

        # Build output list
        output = []
        for key in ["SPX","NDX","SOX","TWII","TXFR1","VIX","XAU","BTC","DXY"]:
            label = INDEX_SYMBOLS.get(key, {}).get("label", key)
            result = data_by_key.get(key, {})
            
            if result.get("price") is None and key != "TXFR1":
                output.append({"symbol": key, "label": label,
                                "price": None, "change": None,
                                "change_pct": None, "error": True})
            else:
                # Rename fields for frontend consistency
                item = {
                    "symbol": key,
                    "label": label,
                    "price": result.get("price"),
                    "price_change": result.get("price_change"),
                    "price_change_pct": result.get("price_change_pct"),
                    "high": result.get("high"),
                    "low": result.get("low"),
                    "volume": result.get("volume"),
                    "source": result.get("source", "twelve_data"),
                    "fetched_at": result.get("fetched_at"),
                }
                if result.get("note"):
                    item["note"] = result["note"]
                output.append(item)
        return output

    # ─── Portfolio Quotes ─────────────────────────────────────────────────────
    async def get_quote(self, ticker: str, asset_type: str = None) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        if asset_type == "crypto" or ticker in CRYPTO_TICKERS:
            return await self._td_single(f"{ticker}/USD", original_ticker=ticker)
        if TW_STOCK_PATTERN(ticker) or asset_type in ("tw_stock", "etf_tw"):
            return await self._get_tw_stock_quote(ticker)
        if ticker == "XAU" or asset_type == "gold":
            return await self._td_single("XAU/USD", original_ticker="XAU")
        # US stock / ETF
        return await self._td_single(ticker)

    async def get_multiple_quotes(self, tickers_with_types: List[Dict]) -> Dict[str, Any]:
        tasks = [self.get_quote(i["ticker"], i.get("asset_type")) for i in tickers_with_types]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = {}
        for item, result in zip(tickers_with_types, results):
            output[item["ticker"]] = {"error": str(result)} if isinstance(result, Exception) else result
        return output

    async def get_exchange_rates(self, pairs: List[Dict]) -> List[Dict]:
        results = []
        for pair in pairs:
            try:
                rate = await self._get_exchange_rate(pair["from_currency"], pair["to_currency"])
                results.append({**pair, "rate": rate.get("rate"),
                                 "change_pct": rate.get("change_pct"),
                                 "fetched_at": datetime.now(timezone.utc).isoformat()})
            except Exception as e:
                results.append({**pair, "rate": None, "error": str(e)})
        return results

    # ─── Taiwan Stock ─────────────────────────────────────────────────────────
    async def _get_tw_stock_quote(self, ticker: str) -> Dict:
        # Shioaji first
        if self.shioaji and self.shioaji.is_connected:
            cached = self.shioaji.get_cached_quote(ticker)
            if cached:
                return cached
            snapshot = await self.shioaji.get_snapshot([ticker])
            if snapshot.get(ticker):
                return snapshot[ticker]
        # Twelve Data with .TW suffix
        result = await self._td_single(f"{ticker}:XTAI", original_ticker=ticker)
        if result.get("price"):
            return result
        # Try alternate format
        return await self._td_single(f"{ticker}.TW", original_ticker=ticker)

    # ─── Twelve Data Core ─────────────────────────────────────────────────────
    async def _td_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """One API call for multiple symbols. Returns dict keyed by TD symbol."""
        if not TWELVE_DATA_KEY:
            return {s: {"error": "No Twelve Data API key"} for s in symbols}

        symbol_str = ",".join(symbols)
        try:
            resp = await self.http.get(
                "https://api.twelvedata.com/quote",
                params={"symbol": symbol_str, "apikey": TWELVE_DATA_KEY}
            )
            raw = resp.json()
            # Single symbol returns object directly; multiple returns dict of objects
            if len(symbols) == 1:
                raw = {symbols[0]: raw}

            result = {}
            for sym, data in raw.items():
                if not isinstance(data, dict):
                    result[sym] = {"error": "Invalid response"}
                    continue
                if data.get("code") or data.get("status") == "error":
                    logger.warning(f"Twelve Data error for {sym}: {data.get('message')}")
                    result[sym] = {"error": data.get("message", "TD error")}
                    continue
                try:
                    # TD /quote returns 'close' as latest price
                    price = float(data.get("close") or 0)
                    prev  = float(data.get("previous_close") or price)
                    change = price - prev
                    change_pct = (change / prev * 100) if prev else 0
                    result[sym] = {
                        "ticker": sym,
                        "price": price if price else None,
                        "price_change": round(change, 4),
                        "price_change_pct": round(change_pct, 4),
                        "open":   float(data.get("open") or 0),
                        "high":   float(data.get("high") or 0),
                        "low":    float(data.get("low") or 0),
                        "volume": int(data.get("volume") or 0),
                        "prev_close": prev,
                        "source": "twelve_data",
                        "currency": data.get("currency", "USD"),
                        "fetched_at": datetime.now(timezone.utc).isoformat()
                    }
                except Exception as e:
                    result[sym] = {"error": str(e)}
            return result
        except Exception as e:
            logger.error(f"Twelve Data batch failed {symbols}: {e}")
            return {s: {"error": str(e)} for s in symbols}

    async def _td_single(self, symbol: str, original_ticker: str = None) -> Dict:
        batch = await self._td_batch([symbol])
        result = batch.get(symbol, {"error": "No data"})
        if original_ticker and "ticker" in result:
            result["ticker"] = original_ticker
        return result

    # ─── Historical K-Bars ────────────────────────────────────────────────────
    async def get_historical_kbars(self, ticker: str, start: str, end: str,
                                    interval: str = "1day") -> List[Dict]:
        if TW_STOCK_PATTERN(ticker) and self.shioaji and self.shioaji.is_connected:
            result = await self.shioaji.get_kbars(ticker, start, end)
            if result:
                return result
        if not TWELVE_DATA_KEY:
            return []
        # Taiwan stock: try XTAI exchange
        if TW_STOCK_PATTERN(ticker):
            symbol = f"{ticker}:XTAI"
        else:
            symbol = ticker
        try:
            resp = await self.http.get(
                "https://api.twelvedata.com/time_series",
                params={"symbol": symbol, "interval": interval,
                        "start_date": start, "end_date": end,
                        "apikey": TWELVE_DATA_KEY, "outputsize": 5000}
            )
            data = resp.json()
            if "values" in data:
                return [{"ts": item["datetime"],
                         "open":   float(item["open"]),
                         "high":   float(item["high"]),
                         "low":    float(item["low"]),
                         "close":  float(item["close"]),
                         "volume": int(item.get("volume") or 0)}
                        for item in reversed(data["values"])]
            logger.warning(f"Twelve Data time_series for {symbol}: {data.get('message','no values')}")
        except Exception as e:
            logger.error(f"Historical data failed {ticker}: {e}")
        return []

    # ─── Exchange Rate ────────────────────────────────────────────────────────
    async def _get_exchange_rate(self, from_cur: str, to_cur: str) -> Dict:
        # ExchangeRate-API first (most reliable)
        if EXCHANGE_RATE_KEY:
            try:
                resp = await self.http.get(
                    f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_KEY}/pair/{from_cur}/{to_cur}"
                )
                data = resp.json()
                if data.get("result") == "success":
                    return {"rate": data["conversion_rate"], "change_pct": None}
            except Exception as e:
                logger.error(f"ExchangeRate-API failed {from_cur}/{to_cur}: {e}")
        # Fallback: Twelve Data forex
        td = await self._td_single(f"{from_cur}/{to_cur}")
        if td.get("price"):
            return {"rate": td["price"], "change_pct": td.get("price_change_pct")}
        return {"rate": None, "error": "Exchange rate unavailable"}
